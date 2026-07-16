"""
搜索智能体 - 使用 Agent Reach 工具链 + Tavily + last30days 兜底
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from .base import Agent, Task

logger = logging.getLogger(__name__)


class SearchAgent(Agent):
    """搜索智能体 - 使用 Agent Reach 工具链"""

    def __init__(self, llm: Optional[LLM] = None):
        super().__init__("search_agent", llm)
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.retriever_type = os.getenv("RETRIEVER", "agent_reach")
        # 延迟导入 Agent Reach 服务
        self._agent_reach = None

    def _get_agent_reach(self):
        if self._agent_reach is None:
            from services.agent_reach_service import get_agent_reach_service
            self._agent_reach = get_agent_reach_service()
        return self._agent_reach

    async def execute(self, task: Task) -> Dict[str, Any]:
        """执行搜索任务"""
        query = task.input.get("query", "")
        search_type = task.input.get("search_type", "web")
        max_results = task.input.get("max_results", 10)
        date_range = task.input.get("date_range")

        # 执行搜索
        results = await self._search(query, search_type, max_results, date_range)

        # 对前3条结果抓取全文，替换 snippet（Tavily 结果已是详细内容，跳过）
        all_tavily = all(r.get("source") == "tavily" for r in results)
        if not all_tavily:
            try:
                agent_reach = self._get_agent_reach()
                results = await agent_reach.enrich_results_with_full_text(results, top_n=3)
            except Exception as e:
                logger.warning(f"[搜索] 全文增强失败，继续使用 snippet: {e}")
        else:
            logger.info(f"[搜索] 全部为 Tavily 结果，跳过全文增强")

        # 使用LLM总结搜索结果
        summary = await self._summarize_results(query, results)

        return {
            "query": query,
            "results": results,
            "summary": summary,
            "total": len(results)
        }

    async def _search(self, query: str, search_type: str, max_results: int, date_range: Dict = None) -> List[Dict]:
        """执行搜索 - 使用 Agent Reach 多源聚合"""
        all_results = []
        start_date = date_range.get("start") if date_range else None
        end_date = date_range.get("end") if date_range else None

        # 计算实际生效的时间范围（含默认值）
        if not start_date:
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        actual_end = end_date or datetime.now().strftime("%Y-%m-%d")
        logger.info(f"[搜索] 关键词: {query} | 时间范围: {start_date} ~ {actual_end} | 最大结果: {max_results}")

        # 1. 使用 Agent Reach 多源搜索（Exa + B站）
        agent_reach = self._get_agent_reach()

        try:
            if search_type == "code":
                logger.info(f"[搜索] 引擎: Agent Reach (Exa 代码搜索)")
                all_results = await agent_reach.search_code(query, start_date=start_date, end_date=end_date)
                logger.info(f"[搜索] Agent Reach 代码搜索返回 {len(all_results)} 条结果")
            elif search_type == "bilibili":
                logger.info(f"[搜索] 引擎: Agent Reach (B站搜索)")
                all_results = await agent_reach.search_bilibili(query, max_results)
                logger.info(f"[搜索] B站搜索返回 {len(all_results)} 条结果")
            else:
                # 只用 Tavily 作为搜索引擎
                if self.tavily_api_key:
                    logger.info(f"[搜索] 引擎: Tavily | 查询: \"{query}\"")
                    tavily_results = await self._search_tavily(query, max_results, start_date, end_date)
                    all_results.extend(tavily_results)
                    logger.info(f"[搜索] Tavily 返回 {len(tavily_results)} 条结果")
                else:
                    logger.error(f"[搜索] 未配置 TAVILY_API_KEY，搜索功能不可用")
                    raise ValueError("搜索功能不可用：未配置 TAVILY_API_KEY")
        except Exception as e:
            logger.warning(f"[搜索] 搜索失败: {e}")

        # 2. 过滤掉明确超出时间范围的旧文章
        if start_date:
            before_count = len(all_results)
            all_results = self._filter_by_date(all_results, start_date, end_date)
            filtered_count = before_count - len(all_results)
            if filtered_count > 0:
                logger.info(f"[搜索] 日期过滤: 丢弃 {filtered_count} 条旧文章，剩余 {len(all_results)} 条")

        # 4. 如果都没有结果，使用备用搜索
        if not all_results:
            logger.info(f"[搜索] 所有引擎无结果，尝试 last30days 兜底")
            all_results = await self._search_fallback(query, max_results, start_date, end_date)
            logger.info(f"[搜索] last30days 兜底返回 {len(all_results)} 条结果")

        # 4.5 跨查询二次去重 + 来源均衡
        seen_urls = set()
        deduped = []
        for r in all_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(r)
        if len(deduped) < len(all_results):
            logger.info(f"[搜索] 跨查询去重: {len(all_results)} → {len(deduped)} 条")

        # 来源均衡：优先保留高质量来源（Exa/Tavily），搜狗/百度等短摘要往后排
        source_priority = {"exa": 0, "tavily": 1, "bilibili": 2, "github": 2}
        deduped.sort(key=lambda r: (source_priority.get(r.get("source", ""), 9), -r.get("score", 0)))
        all_results = deduped

        # 统计各来源数量
        from collections import Counter
        source_counts = Counter(r.get("source", "unknown") for r in all_results)
        sources_str = ", ".join(f"{k}:{v}" for k, v in source_counts.items())
        logger.info(f"[搜索] 最终结果: {len(all_results)} 条 | 来源分布: {sources_str}")

        return all_results[:max_results * 2]  # 返回最多2倍结果供筛选

    def _filter_by_date(self, results: List[Dict], start_date: str, end_date: str = None) -> List[Dict]:
        """过滤掉明确超出时间范围的旧文章（保留 Published: N/A 的结果）"""
        from datetime import datetime
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
        except ValueError:
            return results

        filtered = []
        for r in results:
            # 尝试从 snippet 中提取日期（Exa 输出中有 Published: 行）
            snippet = r.get("snippet", "")
            pub_date = None
            # 检查 snippet 中是否有 ISO 日期格式
            import re
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', snippet)
            if date_match:
                try:
                    pub_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                except ValueError:
                    pass
            # 没有日期信息的文章保留（可能是新文章但日期缺失）
            if pub_date is None:
                filtered.append(r)
            # 有日期且在范围内的保留
            elif start_dt <= pub_date <= end_dt:
                filtered.append(r)
            # 有日期但超出范围的丢弃（旧文章）
            # else: skip
        return filtered

    async def _search_tavily(self, query: str, max_results: int,
                             start_date: str = None, end_date: str = None) -> List[Dict]:
        """使用Tavily API搜索（备用）"""
        try:
            from tavily import TavilyClient
            from datetime import datetime

            client = TavilyClient(api_key=self.tavily_api_key)
            # 计算天数差作为 days 参数
            days = 365
            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    days = max((datetime.now() - start_dt).days, 1)
                except ValueError:
                    pass
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                days=days
            )

            results = []
            for result in response.get("results", []):
                url = result.get("url", "")
                title = result.get("title", "")
                content = result.get("content", "")
                logger.info(f"[Tavily] title={title[:50]}... | url={url[:60] if url else '无'} | content长度={len(content)}")
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": content,
                    "score": result.get("score", 0),
                    "source": "tavily"
                })

            return results

        except Exception as e:
            logger.warning(f"Tavily搜索失败: {e}")
            return []

    async def _search_fallback(self, query: str, max_results: int,
                               start_date: str = None, end_date: str = None) -> List[Dict]:
        """备用搜索方法 - 尝试 last30days skill"""
        try:
            import subprocess
            import json

            script_path = os.path.join(os.path.dirname(__file__), "../../skills/last30days/scripts/last30days.py")

            if not os.path.exists(script_path):
                logger.warning(f"[搜索] last30days 脚本不存在，所有搜索引擎均无结果")
                return []

            cmd = ["python3", script_path, query, "--json", "--max-results", str(max_results)]
            # 添加时间范围参数
            if start_date:
                cmd.extend(["--since", start_date])
            if end_date:
                cmd.extend(["--until", end_date])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(script_path)
            )

            if result.returncode != 0:
                logger.warning(f"[搜索] last30days 脚本执行失败 (code={result.returncode})")
                return []

            data = json.loads(result.stdout)
            results = []
            for item in data.get("results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", item.get("content", "")),
                    "score": item.get("score", item.get("engagement", 0)),
                    "source": item.get("source", "last30days")
                })
            return results

        except Exception as e:
            logger.warning(f"[搜索] last30days 兜底异常: {e}")
            return []

    async def _summarize_results(self, query: str, results: List[Dict]) -> str:
        """将完整搜索结果格式化为文本，不做截断"""
        if not results:
            return "未找到相关搜索结果"

        results_text = "\n\n".join([
            f"[来源 {i+1}] {r['title']}\n来源平台: {r.get('source', 'unknown')}\n链接: {r.get('url', '无')}\n内容:\n{r['snippet']}"
            for i, r in enumerate(results)
        ])

        return results_text
