"""
网络搜索工具 — 复用 SearchAgent 的搜索逻辑
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.tool_registry import Tool

logger = logging.getLogger(__name__)


class WebSearchTool:
    """网络搜索工具"""

    def __init__(self):
        self.name = "web_search"
        self.description = "搜索互联网获取最新信息。适用于需要查找最新资料、数据、新闻等场景。"
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，最多500字符"
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认10，最大20",
                    "default": 10
                },
                "date_range": {
                    "type": "string",
                    "description": "日期范围过滤，格式: YYYY-MM-DD~YYYY-MM-DD，如 '2025-01-01~2026-01-01'",
                    "default": ""
                }
            },
            "required": ["query"]
        }
        self.timeout = 60
        self._tavily_api_key = os.getenv("TAVILY_API_KEY")

    async def execute(self, query: str, max_results: int = 10, date_range: str = "") -> str:
        """执行网络搜索"""
        # 安全约束
        if len(query) > 500:
            logger.warning(f"[web_search] 查询过长（{len(query)} 字符），搜索引擎可能截断")
        max_results = min(max_results, 20)

        # 解析日期范围
        start_date = None
        end_date = None
        if date_range and "~" in date_range:
            parts = date_range.split("~")
            start_date = parts[0].strip()
            if len(parts) > 1:
                end_date = parts[1].strip()
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"[web_search] 搜索: {query} | 时间范围: {start_date} ~ {end_date} | 最大结果: {max_results}")

        all_results = []

        # 1. Tavily 搜索
        if self._tavily_api_key:
            try:
                from tavily import TavilyClient
                client = TavilyClient(api_key=self._tavily_api_key)
                days = max((datetime.now() - datetime.strptime(start_date, "%Y-%m-%d")).days, 1)
                response = client.search(
                    query=query,
                    max_results=max_results,
                    search_depth="advanced",
                    days=days
                )
                for r in response.get("results", []):
                    all_results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                        "score": r.get("score", 0),
                        "source": "tavily"
                    })
                logger.info(f"[web_search] Tavily 返回 {len(all_results)} 条结果")
            except Exception as e:
                logger.warning(f"[web_search] Tavily 搜索失败: {e}")

        # 2. Agent Reach 兜底
        if not all_results:
            try:
                from services.agent_reach_service import get_agent_reach_service
                agent_reach = get_agent_reach_service()
                fallback_results = await agent_reach.search_all(query, max_results)
                for r in fallback_results:
                    all_results.append({
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "score": r.score,
                        "source": r.source
                    })
                logger.info(f"[web_search] Agent Reach 兜底返回 {len(fallback_results)} 条结果")
            except Exception as e:
                logger.warning(f"[web_search] Agent Reach 搜索失败: {e}")

        # 去重
        seen_urls = set()
        deduped = []
        for r in all_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(r)

        # 来源均衡排序
        source_priority = {"exa": 0, "tavily": 1, "bilibili": 2, "github": 2}
        deduped.sort(key=lambda r: (source_priority.get(r.get("source", ""), 9), -r.get("score", 0)))

        # 截取 max_results
        final_results = deduped[:max_results]

        # 格式化输出
        if not final_results:
            return "未找到相关搜索结果。"

        output = f"搜索 '{query}' 共找到 {len(final_results)} 条结果：\n\n"
        for i, r in enumerate(final_results, 1):
            output += f"{i}. **{r['title']}**\n"
            output += f"   来源: {r['source']} | URL: {r['url']}\n"
            output += f"   摘要: {r['snippet']}\n\n"

        return output


def create_web_search_tool() -> Tool:
    tool_instance = WebSearchTool()
    return Tool(
        name=tool_instance.name,
        description=tool_instance.description,
        parameters=tool_instance.parameters,
        execute=tool_instance.execute,
        timeout=tool_instance.timeout
    )