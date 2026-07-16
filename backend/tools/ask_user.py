"""
ask_user 工具 — 向用户提问并等待回复
"""
import asyncio
import json
import logging

from core.tool_registry import Tool

logger = logging.getLogger(__name__)

# 全局存储：{task_id: {tool_call_id: {"event": asyncio.Event, "answer": str}}}
_pending_questions: dict = {}


class AskUserTool:
    """向用户提问工具"""

    def __init__(self):
        self.name = "ask_user"
        self.description = "向用户提问以获取补充信息。当 Agent 需要用户决策或补充信息时使用。"
        self.parameters = {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "向用户提出的问题"
                }
            },
            "required": ["question"]
        }
        self.timeout = 300

    async def execute(self, question: str) -> str:
        """
        向用户提问，通过 SSE 推送到前端，等待用户回复
        task_id 通过 ToolRegistry 的 task_context 传递
        """
        logger.info(f"[ask_user] 提问: {question}")

        # 从 ToolRegistry 的 task_context 获取 task_id
        from core.tool_registry import registry
        task_id = registry.get_task_context()

        if not task_id:
            logger.warning(f"[ask_user] 无法获取 task_id，返回默认回答")
            return json.dumps({"answer": "跳过，请自行判断"})

        # 兼容模式：不等待用户输入，直接返回默认回答
        if getattr(registry, '_no_interactive', False):
            logger.info(f"[ask_user] 兼容模式下自动跳过: {question[:50]}...")
            return json.dumps({"answer": "跳过，请自行判断"})

        tool_call_id = f"call_{hash(question + task_id) & 0x7FFFFFFF:x}"

        # 创建等待事件
        event = asyncio.Event()
        if task_id not in _pending_questions:
            _pending_questions[task_id] = {}
        _pending_questions[task_id][tool_call_id] = {"event": event, "answer": None}

        logger.info(f"[SSE] 发送事件: type=ask_user, tool_call_id={tool_call_id}, question={question[:50]}...")

        # 等待用户回复（超时 300s）
        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout)
            answer = _pending_questions[task_id].get(tool_call_id, {}).get("answer", "")
            if answer:
                logger.info(f"[SSE] 收到用户回复: \"{answer[:50]}...\"")
                return json.dumps({"answer": answer})
            else:
                return json.dumps({"error": "用户未回复"})
        except asyncio.TimeoutError:
            logger.warning(f"[ask_user] 等待用户回复超时 ({self.timeout}s)")
            return json.dumps({"error": "用户未回复"})
        finally:
            _pending_questions[task_id].pop(tool_call_id, None)
            if not _pending_questions[task_id]:
                _pending_questions.pop(task_id, None)


def set_user_answer(task_id: str, tool_call_id: str, answer: str):
    """设置用户回复（由 API 端点调用）"""
    if task_id in _pending_questions and tool_call_id in _pending_questions[task_id]:
        _pending_questions[task_id][tool_call_id]["answer"] = answer
        _pending_questions[task_id][tool_call_id]["event"].set()
        return True
    return False


def create_ask_user_tool() -> Tool:
    t = AskUserTool()
    return Tool(name=t.name, description=t.description, parameters=t.parameters, execute=t.execute, timeout=t.timeout)
