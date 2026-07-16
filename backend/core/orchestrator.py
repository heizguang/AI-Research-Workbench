"""
多智能体协调器（已废弃 — 仅保留向后兼容壳）
==========================================

所有 Agent 类与任务模型（SearchAgent / DocumentAgent / ReportAgent /
PPTAgent / TopicAnalysisAgent / Task / TaskType / TaskStatus / Agent）已迁移至
`backend/agents/` 包（见 backend/agents/__init__.py）。

本文件仅作为兼容再导出层，避免破坏既有 `from core.orchestrator import ...` 的引用。

新代码请直接：

    from agents import SearchAgent, DocumentAgent, ReportAgent, PPTAgent, TopicAnalysisAgent, Task, TaskType

注意：原 Orchestrator 类与 get_orchestrator() 早已移除，本壳不再提供它们。
"""
from agents import (
    TaskType,
    TaskStatus,
    Task,
    Agent,
    TopicAnalysisAgent,
    SearchAgent,
    DocumentAgent,
    ReportAgent,
    PPTAgent,
)

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
