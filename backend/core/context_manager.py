"""
上下文管理器 — 管理 Agent Loop 的对话历史、滑动窗口和 Token 预算
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.llm import LLM, LLMMessage

logger = logging.getLogger(__name__)


class ContextManager:
    """Agent Loop 上下文管理器"""

    def __init__(
        self,
        max_turns: int = 10,
        summary_threshold: int = 80000,
        max_tokens: int = 100000
    ):
        self.max_turns = max_turns
        self.summary_threshold = summary_threshold
        self.max_tokens = max_tokens
        self.messages: List[LLMMessage] = []
        self.tool_results: List[Dict] = []
        self.token_budget: Dict = {
            "total_limit": max_tokens,
            "used": 0,
            "remaining": max_tokens,
            "by_step": []
        }
        self._summary: Optional[str] = None
        self._started_at: Optional[str] = None

    def init(self, system_prompt: str, goal: str):
        """初始化上下文"""
        self.messages = []
        self.tool_results = []
        self.token_budget = {
            "total_limit": self.max_tokens,
            "used": 0,
            "remaining": self.max_tokens,
            "by_step": []
        }
        self._summary = None
        self._started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        self.messages.append(LLMMessage(role="system", content=system_prompt))
        self.messages.append(LLMMessage(role="user", content=goal))

        logger.info(f"[Context] 初始化上下文 | 目标: {goal[:100]}...")
        logger.info(f"[Context] 当前上下文: 2 条消息 | token: 估算中 / {self.max_tokens}")

    def add_assistant_message(self, content: str, tool_calls: Optional[List[Dict]] = None):
        """添加 assistant 消息"""
        msg = LLMMessage(role="assistant", content=content)
        if tool_calls:
            msg.tool_calls = tool_calls
        self.messages.append(msg)
        logger.info(f"[Context] 添加 assistant message | tool_calls: {len(tool_calls) if tool_calls else 0} | content长度: {len(content)}")

    def add_tool_result(self, tool_call_id: str, result: str):
        """添加 tool 消息（工具调用结果）"""
        msg = LLMMessage(
            role="tool",
            content=result,
            tool_call_id=tool_call_id
        )
        self.messages.append(msg)
        self.tool_results.append({"tool_call_id": tool_call_id, "result": result})

        # 记录 token 预算
        step_tokens = self._estimate_tokens(result)
        self.token_budget["used"] += step_tokens
        self.token_budget["remaining"] = self.max_tokens - self.token_budget["used"]
        self.token_budget["by_step"].append({
            "step": f"tool_result:{tool_call_id}",
            "tokens": step_tokens
        })

        logger.info(f"[Context] 添加 tool result | tool_call_id: {tool_call_id} | 结果长度: {len(result)}")
        logger.info(f"[Context] 当前上下文: {len(self.messages)} 条消息 | token: {self.token_budget['used']} / {self.max_tokens}")

    def add_think_tokens(self, tokens: int):
        """记录思考步骤的 token 消耗"""
        self.token_budget["used"] += tokens
        self.token_budget["remaining"] = self.max_tokens - self.token_budget["used"]
        self.token_budget["by_step"].append({
            "step": "think",
            "tokens": tokens
        })

    def get_messages(self) -> List[LLMMessage]:
        """获取完整消息列表"""
        return self.messages

    def get_token_count(self) -> int:
        """获取当前 token 估算数"""
        return self.token_budget["used"]

    def get_token_budget(self) -> Dict:
        """获取 token 预算状态"""
        return self.token_budget

    def _estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数（中文约 1.5 字符/token，英文约 4 字符/token）"""
        if not text:
            return 0
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    async def compress_if_needed(self, llm: LLM):
        """当上下文接近 token 上限时，触发摘要压缩"""
        if self.get_token_count() < self.summary_threshold:
            return

        logger.info(f"[Context] 触发摘要压缩 | 压缩前: {self.get_token_count()} token")

        # 保留 system prompt + 最近 3 轮对话
        preserved = self.messages[:1]  # system prompt
        recent = self.messages[-6:]  # 最近 3 轮（每轮 assistant + tool）
        to_compress = self.messages[1:-6]

        if not to_compress:
            logger.info(f"[Context] 无可压缩内容")
            return

        # 生成摘要
        compress_prompt = "请将以下对话历史总结为一段简洁的摘要，保留关键发现和重要信息：\n\n"
        for msg in to_compress:
            if msg.content:
                compress_prompt += f"[{msg.role}]: {msg.content}\n"

        try:
            summary_msg = LLMMessage(role="user", content=compress_prompt)
            response = await llm.chat([summary_msg])
            self._summary = response.content
            self.messages = preserved + [LLMMessage(role="system", content=f"历史摘要: {self._summary}")] + recent

            # 重新计算 token_budget
            total = 0
            for msg in self.messages:
                if msg.content:
                    total += self._estimate_tokens(msg.content)
            self.token_budget["used"] = total
            self.token_budget["remaining"] = self.max_tokens - total

            logger.info(f"[Context] 压缩后: {self.get_token_count()} token")
        except Exception as e:
            logger.error(f"[Context] 摘要压缩失败: {e}")

    def _build_system_prompt(self, tools: List) -> str:
        """构建 System Prompt（5 段式结构）"""
        tool_descriptions = "\n".join([
            f"- **{t.name}**: {t.description}" for t in tools
        ])

        today = time.strftime("%Y-%m-%d")
        return f"""1. 角色定义：你是一个自主推理助手。**当前日期是 {today}**。

2. 行为约束：
   - 每轮必须有明确的思考过程
   - 优先使用工具获取信息，不要凭空编造
   - **时间意识：默认使用最近 1 年的信息。如果用户没有明确要求历史数据，不要引用超过 1 年的资料**
   - **搜索时间范围：调用 web_search 时，默认传入 date_range 参数，格式为 "{(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')}~{today}"（最近一年）**
   - 如果用户目标中已包含足够的参考内容（如报告、文档、搜索结果），直接阅读并回答，不要调用 generate_report 重新生成
   - 工具调用失败时尝试替代方案，而非直接放弃

3. 工具使用规则：
   可用工具：
{tool_descriptions}
   - 禁止连续重复调用相同工具（相同参数）
   - 调用工具时，先思考是否真的需要该工具

4. 输出规范：
   - 最终回复使用 Markdown 格式
   - 报告类任务必须包含 `## 参考来源` 章节，且每一条来源都必须带上可点击的 URL 链接，格式严格为：`1. [标题](URL)`
     示例：`1. [小米SU7 - 维基百科](https://zh.wikipedia.org/wiki/小米SU7)`
   - URL 必须来自 web_search 等工具返回结果中的原始链接；**严禁编造、推测或拼接任何 URL**
   - 若某条来源确实没有可用链接，如实写出来源名称并注明「（无公开链接）」，不要伪造链接，也不要用无链接的裸文字列表冒充参考来源
   - 相同 URL 在参考来源中只列出一次
   - 代码块使用正确的语言标记

5. 终止规则：
   - 任务完成时直接输出最终回复（不再调用工具）
   - 达到最大轮次时总结已有结果
   - 如果无法完成，诚实说明原因"""

    def to_trace(self) -> Dict:
        """导出完整执行轨迹"""
        steps = []
        for msg in self.messages:
            if msg.role == "assistant":
                steps.append({
                    "type": "think",
                    "content": msg.content or "",
                    "tool_calls": msg.tool_calls
                })
            elif msg.role == "tool":
                steps.append({
                    "type": "tool_result",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content or ""
                })

        return {
            "messages": [m.dict() for m in self.messages],
            "tool_results": self.tool_results,
            "token_budget": self.token_budget,
            "summary": self._summary,
            "started_at": self._started_at
        }