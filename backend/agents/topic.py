"""
主题分析智能体 - 识别用户意图，生成搜索策略和报告结构
"""
from __future__ import annotations

import logging

from .base import Agent, Task

logger = logging.getLogger(__name__)


class TopicAnalysisAgent(Agent):
    """主题分析智能体 - 识别用户意图，生成搜索策略和报告结构"""

    def __init__(self, llm: Optional[LLM] = None):
        super().__init__("topic_analysis_agent", llm)

    async def execute(self, task: Task) -> Dict[str, Any]:
        """分析主题，返回搜索关键词和报告结构建议"""
        topic = task.input.get("topic", "") or task.input.get("query", "")
        result = await self.analyze_topic(topic)
        return result

    async def analyze_topic(self, topic: str) -> Dict[str, Any]:
        """生成搜索关键词：直接用主题，不依赖 LLM（最可靠）"""
        queries = [topic, f"{topic} 最新进展", f"{topic} 发展历程 各版本对比"]
        logger.info(f"[主题分析] 搜索关键词: {queries}")
        return {"search_queries": queries}
