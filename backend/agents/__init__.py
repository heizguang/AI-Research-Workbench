"""
智能体模块

Agent 类与任务模型已从 core/orchestrator.py 拆分到本包的各子模块：
  - base.py    : TaskType / TaskStatus / Task / Agent
  - topic.py   : TopicAnalysisAgent
  - search.py  : SearchAgent
  - document.py: DocumentAgent
  - report.py  : ReportAgent
  - ppt.py     : PPTAgent

新代码请使用：

    from agents import SearchAgent, DocumentAgent, ReportAgent, PPTAgent, TopicAnalysisAgent, Task, TaskType

core/orchestrator.py 现仅作为向后兼容的再导出壳。
"""
from .base import TaskType, TaskStatus, Task, Agent
from .topic import TopicAnalysisAgent
from .search import SearchAgent
from .document import DocumentAgent
from .report import ReportAgent
from .ppt import PPTAgent

__all__ = [
    "TaskType",
    "TaskStatus",
    "Task",
    "Agent",
    "TopicAnalysisAgent",
    "SearchAgent",
    "DocumentAgent",
    "ReportAgent",
    "PPTAgent",
]
