"""
大模型接口封装模块
提供统一的LLM调用接口，支持OpenAI等模型
"""

from typing import Optional, List, Dict, Any, AsyncGenerator
from pydantic import BaseModel
import json
import openai
from openai import AsyncOpenAI
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()


class LLMConfig(BaseModel):
    """LLM配置"""
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4000
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0


class LLMMessage(BaseModel):
    """消息模型"""
    role: str  # system, user, assistant, tool
    content: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class LLMResponse(BaseModel):
    """响应模型"""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    tool_calls: Optional[List[Dict]] = None  # OpenAI tool_calls 格式


class StreamChunk(BaseModel):
    """流式响应块"""
    type: str  # "content" | "tool_calls"
    content: Optional[str] = None
    tool_call: Optional[Dict] = None


class _Provider:
    """一个厂商端点：独立的 base_url / api_key / 模型映射。

    多个 _Provider 组成 fallback 链，调用时按顺序尝试，命中可用即返回。
    """

    def __init__(self, name: str, client, smart, fast, strategic):
        self.name = name
        self.client = client
        self.models = {"smart": smart, "fast": fast, "strategic": strategic}


class LLM:
    """大模型接口类

    支持多厂商故障转移：通过环境变量 LLM_PROVIDERS 配置多个厂商
    （如 sensenova,deepseek,openai），每个厂商用 `<NAME>_BASE_URL` /
    `<NAME>_API_KEY` / `<NAME>_SMART_LLM` 等定义。调用时按列表顺序尝试，
    某个厂商不可用（异常/超时）自动切换到下一个。未配置 LLM_PROVIDERS 时
    退回原单 client 行为，保持完全向后兼容。
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()

        # 构建厂商列表（支持多厂商 fallback）
        self.providers = self._build_providers()
        primary = self.providers[0]

        self.config.model = primary.models["smart"] or "gpt-4"
        self.config.max_tokens = int(os.getenv("SMART_TOKEN_LIMIT", "32000"))

        # 快速模型配置（用于问答等简单任务）
        self.fast_model = primary.models["fast"] or self.config.model
        self.strategic_model = primary.models["strategic"] or self.config.model

    @staticmethod
    def _parse_model(value: Optional[str]) -> Optional[str]:
        """兼容 `provider:model` 写法，只取模型名。"""
        if not value:
            return None
        return value.split(":")[-1] if ":" in value else value

    def _build_providers(self) -> List[_Provider]:
        """从环境变量构建厂商列表。

        优先读取 LLM_PROVIDERS（逗号分隔的厂商名），每个厂商用
        `<NAME>_BASE_URL` / `<NAME>_API_KEY` / `<NAME>_{SMART,FAST,STRATEGIC}_LLM`
        定义。若未配置或解析为空，退回原单 client 兼容模式。
        """
        provider_names = os.getenv("LLM_PROVIDERS")
        providers: List[_Provider] = []

        if provider_names:
            for name in [p.strip() for p in provider_names.split(",") if p.strip()]:
                prefix = name.upper()  # 环境变量统一大写，如 openai → OPENAI
                base_url = os.getenv(f"{prefix}_BASE_URL")
                api_key = os.getenv(f"{prefix}_API_KEY")
                if not base_url or not api_key:
                    logger.warning(f"[LLM] provider '{name}' 缺少 {prefix}_BASE_URL / {prefix}_API_KEY，已跳过")
                    continue
                smart = self._parse_model(
                    os.getenv(f"{prefix}_SMART_LLM") or os.getenv(f"{prefix}_SMART")
                )
                fast = self._parse_model(
                    os.getenv(f"{prefix}_FAST_LLM") or os.getenv(f"{prefix}_FAST")
                )
                strategic = self._parse_model(
                    os.getenv(f"{prefix}_STRATEGIC_LLM") or os.getenv(f"{prefix}_STRATEGIC")
                )
                client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                providers.append(_Provider(name, client, smart, fast, strategic))

        if providers:
            names = ", ".join(p.name for p in providers)
            logger.info(f"[LLM] 已加载多厂商 providers（fallback 顺序）: {names}")
            return providers

        # 向后兼容：单 client 模式
        client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )
        smart = self._parse_model(os.getenv("SMART_LLM", "openai:mimo-v2.5-pro"))
        fast = self._parse_model(os.getenv("FAST_LLM", "openai:mimo-v2.5"))
        strategic = self._parse_model(os.getenv("STRATEGIC_LLM"))
        logger.info("[LLM] 使用单厂商兼容模式（未配置 LLM_PROVIDERS）")
        return [_Provider("default", client, smart, fast, strategic)]

    def _resolve_chain(self, role: str, config: Optional[LLMConfig]):
        """解析 (厂商名, client, model) 调用链。

        - 指定 role（smart/fast/strategic）：遍历所有厂商对应的 role 模型，实现故障转移
        - 否则若 config 显式指定了 model：仅用主厂商 + 该 model（保持旧行为）
        - 否则：主厂商的 smart 模型
        """
        if role in ("smart", "fast", "strategic"):
            chain = [
                (p.name, p.client, p.models[role])
                for p in self.providers
                if p.models.get(role)
            ]
            if chain:
                return chain
        if config and getattr(config, "model", None):
            return [("default", self.providers[0].client, config.model)]
        return [("default", self.providers[0].client, self.config.model)]

    def _build_messages(self, messages: List[LLMMessage]) -> List[Dict]:
        """将 LLMMessage 列表转换为 OpenAI API 格式"""
        result = []
        for m in messages:
            msg = {"role": m.role}
            if m.content is not None:
                msg["content"] = m.content
            if m.tool_calls is not None:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id is not None:
                msg["tool_call_id"] = m.tool_call_id
            if m.name is not None:
                msg["name"] = m.name
            result.append(msg)
        return result

    async def chat(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict]] = None,
        role: str = "smart"
    ) -> LLMResponse:
        """
        聊天接口（支持 function calling）

        Args:
            messages: 消息列表
            config: 可选的配置覆盖（temperature / max_tokens 等，model 由 role 决定）
            tools: OpenAI tools 参数（function calling 工具定义）
            role: 模型档位 smart/fast/strategic，决定调用哪个厂商的哪个模型；
                  多厂商时按 fallback 顺序尝试，命中即用

        Returns:
            LLM响应
        """
        cfg = config or self.config
        chain = self._resolve_chain(role, cfg)
        last_err: Optional[Exception] = None

        for idx, (provider_name, client, model) in enumerate(chain):
            logger.info(f"[LLM] 尝试 provider '{provider_name}' 模型 '{model}'（{idx+1}/{len(chain)}）")
            try:
                kwargs = {
                    "model": model,
                    "messages": self._build_messages(messages),
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                    "top_p": cfg.top_p,
                    "frequency_penalty": cfg.frequency_penalty,
                    "presence_penalty": cfg.presence_penalty
                }
                if tools:
                    kwargs["tools"] = tools

                response = await client.chat.completions.create(**kwargs)

                choice = response.choices[0]
                tool_calls = None
                if choice.message.tool_calls:
                    tool_calls = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in choice.message.tool_calls
                    ]

                if idx > 0:
                    logger.info(f"[LLM] 已故障转移至 provider '{provider_name}' 模型 '{model}'")
                return LLMResponse(
                    content=choice.message.content or "",
                    model=response.model,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    },
                    finish_reason=choice.finish_reason,
                    tool_calls=tool_calls
                )
            except Exception as e:
                last_err = e
                logger.warning(f"[LLM] provider '{provider_name}' 调用失败，尝试下一个: {e}")

        raise Exception(f"LLM调用失败（所有 provider 均不可用）: {last_err}")

    async def chat_stream(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        role: str = "smart"
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天接口（纯文本，不支持 tools）

        Args:
            messages: 消息列表
            config: 可选的配置覆盖
            role: 模型档位 smart/fast/strategic，多厂商时按 fallback 顺序尝试

        Yields:
            流式响应内容
        """
        cfg = config or self.config
        chain = self._resolve_chain(role, cfg)
        last_err: Optional[Exception] = None

        yielded = False

        for idx, (provider_name, client, model) in enumerate(chain):
            logger.info(f"[LLM] 尝试 provider '{provider_name}' 模型 '{model}'（{idx+1}/{len(chain)}）")
            try:
                stream = await client.chat.completions.create(
                    model=model,
                    messages=self._build_messages(messages),
                    temperature=cfg.temperature,
                    max_tokens=cfg.max_tokens,
                    top_p=cfg.top_p,
                    frequency_penalty=cfg.frequency_penalty,
                    presence_penalty=cfg.presence_penalty,
                    stream=True
                )

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yielded = True
                        yield chunk.choices[0].delta.content
                if idx > 0:
                    logger.info(f"[LLM] 已故障转移至 provider '{provider_name}' 模型 '{model}'")
                return
            except Exception as e:
                last_err = e
                if yielded:
                    logger.error(f"[LLM] provider '{provider_name}' 流式中断（已输出部分内容），不再切换: {e}")
                    raise
                logger.warning(f"[LLM] provider '{provider_name}' 流式调用失败，尝试下一个: {e}")

        raise Exception(f"LLM流式调用失败（所有 provider 均不可用）: {last_err}")

    async def chat_stream_with_tools(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict]] = None,
        role: str = "smart"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        流式聊天接口（支持 function calling）

        Args:
            messages: 消息列表
            config: 可选的配置覆盖
            tools: OpenAI tools 参数
            role: 模型档位 smart/fast/strategic，多厂商时按 fallback 顺序尝试

        Yields:
            StreamChunk 对象，type 为 "content" 或 "tool_calls"
        """
        cfg = config or self.config
        chain = self._resolve_chain(role, cfg)
        last_err: Optional[Exception] = None

        yielded = False  # 是否已向调用方流出任何内容（防止 fallback 切换厂商时重复输出）

        for idx, (provider_name, client, model) in enumerate(chain):
            logger.info(f"[LLM] 尝试 provider '{provider_name}' 模型 '{model}'（{idx+1}/{len(chain)}）")
            try:
                kwargs = {
                    "model": model,
                    "messages": self._build_messages(messages),
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                    "top_p": cfg.top_p,
                    "frequency_penalty": cfg.frequency_penalty,
                    "presence_penalty": cfg.presence_penalty,
                    "stream": True
                }
                if tools:
                    kwargs["tools"] = tools

                stream = await client.chat.completions.create(**kwargs)

                accumulated_tool_calls: Dict[int, Dict] = {}
                finish_reason = None

                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    # 记录 finish_reason（流结束后最后一个 chunk 会携带）
                    if chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason

                    # 处理文本内容
                    if delta.content:
                        yielded = True
                        yield StreamChunk(type="content", content=delta.content)

                    # 处理 tool_calls
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc.id or "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                }
                            if tc.id:
                                accumulated_tool_calls[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    accumulated_tool_calls[idx]["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

                # 检测模型输出是否被截断
                if finish_reason == "length":
                    logger.warning(f"[LLM] 模型输出被截断（finish_reason=length），tool_call arguments 可能不完整")

                # 流结束后，发送完整的 tool_calls
                for idx in sorted(accumulated_tool_calls.keys()):
                    tc = accumulated_tool_calls[idx]
                    args_str = tc["function"]["arguments"]
                    # 校验 arguments 是否为合法 JSON
                    if args_str:
                        try:
                            json.loads(args_str)
                        except json.JSONDecodeError:
                            logger.warning(f"[LLM] tool_call arguments 不完整，尝试修复: {args_str[:80]}...")
                            # 尝试补全截断的 JSON 字符串
                            fixed = self._try_fix_truncated_json(args_str)
                            if fixed is not None:
                                tc["function"]["arguments"] = fixed
                                logger.info(f"[LLM] arguments 已修复: {fixed[:80]}...")
                            else:
                                logger.error(f"[LLM] arguments 无法修复，回退为默认参数")
                                tc["function"]["arguments"] = "{}"
                    yielded = True
                    yield StreamChunk(
                        type="tool_calls",
                        tool_call=tc
                    )
                if idx > 0:
                    logger.info(f"[LLM] 已故障转移至 provider '{provider_name}' 模型 '{model}'")
                return
            except Exception as e:
                last_err = e
                if yielded:
                    # 已向调用方流出部分内容，切换厂商会重复/错乱，直接失败
                    logger.error(f"[LLM] provider '{provider_name}' 流式中断（已输出部分内容），不再切换: {e}")
                    raise
                logger.warning(f"[LLM] provider '{provider_name}' 流式调用失败，尝试下一个: {e}")

        raise Exception(f"LLM流式调用失败（所有 provider 均不可用）: {last_err}")

    @staticmethod
    def _try_fix_truncated_json(s: str) -> Optional[str]:
        """
        尝试修复因流式截断而不完整的 JSON 字符串。
        策略：从后向前逐步闭合未关闭的引号、括号。
        """
        if not s:
            return None
        # 统计未关闭的结构
        stack = []
        in_string = False
        escape_next = False
        last_key = None  # 用于判断是否在 value 位置

        for i, ch in enumerate(s):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in '{[':
                stack.append(ch)
            elif ch == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
            elif ch == ']':
                if stack and stack[-1] == '[':
                    stack.pop()

        # 如果没有未关闭结构且不在字符串内，说明本身就是非法的
        if not stack and not in_string:
            return None

        # 修复：先闭合字符串，再闭合括号
        result = s.rstrip()
        if in_string:
            result += '"'
        # 如果在字符串后面紧跟逗号或冒号，去掉它们
        result = result.rstrip(',').rstrip(':').rstrip(',')
        # 闭合括号
        for bracket in reversed(stack):
            if bracket == '{':
                result += '}'
            elif bracket == '[':
                result += ']'

        # 验证修复结果
        try:
            json.loads(result)
            return result
        except json.JSONDecodeError:
            return None

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[LLMConfig] = None
    ) -> str:
        """
        简单的文本生成接口

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            config: 可选的配置覆盖

        Returns:
            生成的文本
        """
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))

        response = await self.chat(messages, config)
        return response.content

    async def generate_text_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        智能模型流式文本生成（用于报告等高质量任务）

        Args:
            prompt: 用户提示
            system_prompt: 系统提示

        Yields:
            流式响应内容片段
        """
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))

        async for chunk in self.chat_stream(messages, self.config):
            yield chunk

    async def generate_text_fast(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        快速文本生成接口（用于问答等简单任务）

        Args:
            prompt: 用户提示
            system_prompt: 系统提示

        Returns:
            生成的文本
        """
        fast_config = LLMConfig(
            model=self.fast_model,
            temperature=0.7,
            max_tokens=2000
        )

        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))

        response = await self.chat(messages, fast_config, role="fast")
        return response.content

    async def generate_text_fast_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        快速流式文本生成（用于问答等简单任务）

        Args:
            prompt: 用户提示
            system_prompt: 系统提示

        Yields:
            流式响应内容片段
        """
        fast_config = LLMConfig(
            model=self.fast_model,
            temperature=0.7,
            max_tokens=2000
        )

        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))

        async for chunk in self.chat_stream(messages, fast_config, role="fast"):
            yield chunk

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        获取文本嵌入向量（通过 OpenAI 兼容 API）

        Args:
            text: 输入文本

        Returns:
            嵌入向量，失败时返回 None
        """
        try:
            response = await self.providers[0].client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"嵌入API调用失败，将使用本地嵌入: {e}")
            return None


# 全局LLM实例
_llm_instance: Optional[LLM] = None


def get_llm() -> LLM:
    """获取全局LLM实例"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLM()
    return _llm_instance


async def test_llm():
    """测试LLM连接"""
    llm = get_llm()
    try:
        response = await llm.generate_text("你好，请简单介绍一下自己。")
        print(f"LLM测试成功: {response[:100]}...")
        return True
    except Exception as e:
        print(f"LLM测试失败: {str(e)}")
        return False


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_llm())
