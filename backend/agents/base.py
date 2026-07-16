"""
Agent 基类与任务模型

已从 core/orchestrator.py 拆分到本模块。
"""
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any

from pydantic import BaseModel
from core.llm import LLM, LLMMessage, get_llm

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型"""
    SEARCH = "search"
    DOCUMENT = "document"
    REPORT = "report"
    PPT = "ppt"
    QA = "qa"
    MODIFY = "modify"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    """任务模型"""
    id: str
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class Agent(ABC):
    """智能体基类"""

    def __init__(self, name: str, llm: Optional[LLM] = None):
        self.name = name
        self.llm = llm or get_llm()

    @abstractmethod
    async def execute(self, task: Task) -> Dict[str, Any]:
        """执行任务"""
        pass

    async def think(self, prompt: str, context: Optional[str] = None) -> str:
        """思考过程"""
        messages = []
        if context:
            messages.append(LLMMessage(role="system", content=context))
        messages.append(LLMMessage(role="user", content=prompt))

        response = await self.llm.chat(messages)
        return response.content
