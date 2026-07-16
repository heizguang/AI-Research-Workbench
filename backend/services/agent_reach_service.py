"""
Agent Reach 搜索服务
封装 Agent Reach 工具链，提供统一的搜索接口
支持: Exa 全网搜索、Jina 网页阅读、GitHub 搜索、B站搜索、V2EX、
      百度搜索、360搜索、搜狗搜索（免费无需 API Key）

搜索方法索引:
  L71   search_web()          - Exa 全网搜索
  L92   search_code()         - Exa 代码搜索
  L111  search_github()       - GitHub 搜索
  L135  search_bilibili()     - B站搜索
  L164  search_v2ex()         - V2EX 热门
  L196  _search_baidu_sync()  - 百度搜索（同步）
  L232  _search_360_sync()    - 360搜索（同步）
  L268  _search_sogou_sync()  - 搜狗搜索（同步）
  L304  search_baidu()        - 百度搜索（异步包装）
  L308  search_360()          - 360搜索（异步包装）
  L312  search_sogou()        - 搜狗搜索（异步包装）
  L316  search_all()          - 多源聚合搜索（Exa+B站+百度+360+搜狗）
"""

import asyncio
import json
import logging
import os
import subprocess
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """统一搜索结果格式"""
    title: str
    url: str
    snippet: str
    score: float = 0.0
    source: str = ""


class AgentReachService:
    """Agent Reach 搜索服务封装"""

    def __init__(self):
        # 检测是否在 Windows 上
        self.is_windows = os.name == "nt"
        # Agent Reach 虚拟环境路径（自动适配 Windows / Linux）
        if self.is_windows:
            self.venv_activate = os.path.expanduser("~/.agent-reach-venv/Scripts/activate")
        else:
            self.venv_activate = os.path.expanduser("~/.agent-reach-venv/bin/activate")

    def _get_node_path(self) -> str:
        """获取 Node.js 安装路径（Windows 下 bash 子进程可能找不到 node）"""
        # 常见 Node.js 安装路径（使用 bash 兼容的 Unix 格式）
        candidates = []
        if self.is_windows:
            candidates.extend([
                "/c/Program Files/nodejs",
                "/c/Program Files (x86)/nodejs",
                os.path.expanduser("~/AppData/Roaming/npm"),
                "/d/devlop/nodejs",
            ])
        for p in candidates:
            node_exe = os.path.join(p, "node.exe") if self.is_windows else os.path.join(p, "node")
            if os.path.exists(node_exe):
                return p
        # 回退：尝试从 Windows PATH 中提取
        if self.is_windows:
            for p in os.environ.get("PATH", "").split(os.pathsep):
                if "nodejs" in p.lower() and os.path.exists(os.path.join(p, "node.exe")):
                    # 转换为 bash 兼容格式: D:\devlop\nodejs -> /d/devlop/nodejs
                    bash_path = "/" + p[0].lower() + p[2:].replace("\\", "/")
                    return bash_path
        return ""

    def _run_cmd(self, cmd: str, timeout: int = 30) -> Optional[str]:
        """执行命令并返回输出（服务器环境直接执行，本地通过 venv）"""
        try:
            # agent-reach 相关命令需要激活 venv；其他命令（curl/gh/bili）直接执行
            needs_venv = "agent-reach" in cmd and not cmd.startswith("curl")
            if needs_venv and os.path.exists(self.venv_activate):
                full_cmd = f'source "{self.venv_activate}" && {cmd}'
            else:
                full_cmd = cmd

            # Windows 下 bash 子进程需要 Unix 格式 PATH
            env = os.environ.copy()
            if self.is_windows:
                # 将 Windows PATH 转换为 bash 兼容格式
                win_path = env.get("PATH", "")
                bash_parts = []
                for p in win_path.split(";"):
                    p = p.strip()
                    if not p:
                        continue
                    # D:\devlop\nodejs -> /d/devlop/nodejs
                    if len(p) >= 2 and p[1] == ":":
                        p = "/" + p[0].lower() + p[2:].replace("\\", "/")
                    bash_parts.append(p)
                # 确保 Node.js 路径在 PATH 中
                node_path = self._get_node_path()
                if node_path and node_path not in bash_parts:
                    bash_parts.insert(0, node_path)
                env["PATH"] = ":".join(bash_parts)

            result = subprocess.run(
                ["bash", "-c", full_cmd],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.warning(f"[AgentReach] 命令失败: {cmd}\nstderr: {result.stderr[:300]}")
                return None
        except subprocess.TimeoutExpired:
            logger.warning(f"[AgentReach] 命令超时: {cmd}")
            return None
        except Exception as e:
            logger.warning(f"[AgentReach] 命令异常: {cmd} -> {e}")
            return None

    async def search_web(self, query: str, num_results: int = 5,
                         start_date: str = None, end_date: str = None) -> List[Dict]:
        """使用 Exa AI 进行全网搜索"""
        import time
        t0 = time.time()
        logger.info(f"[搜索] Exa 全网搜索开始 | 关键词: {query} | 数量: {num_results}")
        escaped_query = query.replace('"', '\\"')
        # 默认搜索最近1年
        if not start_date:
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        # 构建时间过滤参数
        date_params = f', startPublishedDate: "{start_date}T00:00:00.000Z"'
        if end_date:
            date_params += f', endPublishedDate: "{end_date}T23:59:59.999Z"'

        cmd = f'mcporter call \'exa.web_search_exa(query: "{escaped_query}", numResults: {num_results}{date_params})\''

        output = await asyncio.to_thread(self._run_cmd, cmd, 30)
        results = self._parse_exa_results(output) if output else []
        elapsed = round(time.time() - t0, 2)
        logger.info(f"[搜索] Exa 全网搜索完成 | 关键词: {query} | 结果: {len(results)} 条 | 耗时: {elapsed}s")
        return results

    async def search_code(self, query: str, tokens: int = 3000,
                          start_date: str = None, end_date: str = None) -> List[Dict]:
        """使用 Exa AI 进行代码搜索"""
        import time
        t0 = time.time()
        logger.info(f"[搜索] Exa 代码搜索开始 | 关键词: {query} | tokens: {tokens}")
        escaped_query = query.replace('"', '\\"')
        # 默认搜索最近1年
        if not start_date:
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        date_params = f', startPublishedDate: "{start_date}T00:00:00.000Z"'
        if end_date:
            date_params += f', endPublishedDate: "{end_date}T23:59:59.999Z"'
        cmd = f'mcporter call \'exa.get_code_context_exa(query: "{escaped_query}", tokensNum: {tokens}{date_params})\''

        output = await asyncio.to_thread(self._run_cmd, cmd, 30)
        results = self._parse_exa_results(output) if output else []
        elapsed = round(time.time() - t0, 2)
        logger.info(f"[搜索] Exa 代码搜索完成 | 关键词: {query} | 结果: {len(results)} 条 | 耗时: {elapsed}s")
        return results

    async def search_github(self, query: str, num_results: int = 5) -> List[Dict]:
        """使用 gh CLI 搜索 GitHub 仓库"""
        import time
        t0 = time.time()
        logger.info(f"[搜索] GitHub 搜索开始 | 关键词: {query} | 数量: {num_results}")
        escaped_query = query.replace('"', '\\"')
        cmd = f'gh search repos "{escaped_query}" --sort stars --limit {num_results} --json name,description,url,stargazersCount'

        output = await asyncio.to_thread(self._run_cmd, cmd, 15)
        if not output:
            logger.warning(f"[搜索] GitHub 搜索无结果 | 关键词: {query} | 耗时: {round(time.time() - t0, 2)}s")
            return []

        try:
            repos = json.loads(output)
            results = [
                {
                    "title": r.get("name", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("description", "") or "",
                    "score": min(r.get("stargazersCount", 0) / 10000, 1.0),
                    "source": "github",
                }
                for r in repos
            ]
            logger.info(f"[搜索] GitHub 搜索完成 | 关键词: {query} | 结果: {len(results)} 条 | 耗时: {round(time.time() - t0, 2)}s")
            return results
        except json.JSONDecodeError:
            logger.warning(f"[搜索] GitHub 搜索解析失败 | 关键词: {query} | 耗时: {round(time.time() - t0, 2)}s")
            return []

    async def search_bilibili(self, query: str, num_results: int = 5) -> List[Dict]:
        """使用 B站搜索 API 搜索视频"""
        import time
        import urllib.parse
        t0 = time.time()
        logger.info(f"[搜索] B站搜索开始 | 关键词: {query} | 数量: {num_results}")

        encoded_query = urllib.parse.quote(query)
        cmd = f'curl -s "https://api.bilibili.com/x/web-interface/search/all/v2?keyword={encoded_query}&page=1&page_size={num_results}" -H "User-Agent: agent-reach/1.0"'

        output = await asyncio.to_thread(self._run_cmd, cmd, 15)
        if not output:
            logger.warning(f"[搜索] B站搜索无结果 | 关键词: {query} | 耗时: {round(time.time() - t0, 2)}s")
            return []

        try:
            data = json.loads(output)
            results = []
            for item in data.get("data", {}).get("result", []):
                if item.get("result_type") == "video":
                    for v in item.get("data", [])[:num_results]:
                        title = v.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", "")
                        results.append({
                            "title": title,
                            "url": f"https://www.bilibili.com/video/{v.get('bvid', '')}",
                            "snippet": v.get("description", ""),
                            "score": v.get("play", 0) / 1000000,
                            "source": "bilibili",
                        })
            logger.info(f"[搜索] B站搜索完成 | 关键词: {query} | 结果: {len(results)} 条 | 耗时: {round(time.time() - t0, 2)}s")
            return results[:num_results]
        except (json.JSONDecodeError, KeyError):
            logger.warning(f"[搜索] B站搜索解析失败 | 关键词: {query} | 耗时: {round(time.time() - t0, 2)}s")
            return []

    async def search_v2ex(self, num_results: int = 10) -> List[Dict]:
        """获取 V2EX 热门话题"""
        import time
        t0 = time.time()
        logger.info(f"[搜索] V2EX 热门开始 | 数量: {num_results}")
        cmd = 'curl -s "https://www.v2ex.com/api/topics/hot.json" -H "User-Agent: agent-reach/1.0"'

        output = await asyncio.to_thread(self._run_cmd, cmd, 15)
        if not output:
            logger.warning(f"[搜索] V2EX 热门无结果 | 耗时: {round(time.time() - t0, 2)}s")
            return []

        try:
            topics = json.loads(output)
            results = [
                {
                    "title": t.get("title", ""),
                    "url": t.get("url", ""),
                    "snippet": t.get("content", ""),
                    "score": t.get("replies", 0) / 100,
                    "source": "v2ex",
                }
                for t in topics[:num_results]
            ]
            logger.info(f"[搜索] V2EX 热门完成 | 结果: {len(results)} 条 | 耗时: {round(time.time() - t0, 2)}s")
            return results
        except json.JSONDecodeError:
            logger.warning(f"[搜索] V2EX 热门解析失败 | 耗时: {round(time.time() - t0, 2)}s")
            return []

    async def read_webpage(self, url: str) -> str:
        """使用 Jina Reader 读取网页内容"""
        cmd = f'curl -s "https://r.jina.ai/{url}"'

        output = await asyncio.to_thread(self._run_cmd, cmd, 20)
        return output or ""

    # ── 免费中文搜索引擎（无需 API Key）──────────────────────────

    def _search_baidu_sync(self, query: str, num_results: int = 5) -> List[Dict]:
        """百度搜索（同步，需在线程中调用）"""
        import time
        import requests
        from lxml import html
        from urllib.parse import quote
        t0 = time.time()
        logger.info(f"[搜索] 百度搜索开始 | 关键词: {query} | 数量: {num_results}")

        url = f"https://www.baidu.com/s?wd={quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            tree = html.fromstring(resp.content)
            results = []
            for item in tree.cssselect("div.result, div.c-container, div.result-op"):
                title_el = item.cssselect("h3 a")
                # 尝试多种摘要选择器（更新：添加 cosc-card-content 和 result-op）
                snippet_el = item.cssselect("div.cosc-card-content, div.result-op, div.cr-content, div.c-abstract, span.content-right_8Zs40, span[class*='content']")
                if title_el:
                    title = title_el[0].text_content().strip()
                    href = title_el[0].get("href", "")
                    snippet = snippet_el[0].text_content().strip() if snippet_el else ""
                    if title and href:
                        # 补全相对 URL 为绝对 URL
                        if href.startswith("/"):
                            href = f"https://www.baidu.com{href}"
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet,
                            "score": 0.7,
                            "source": "百度",
                        })
            logger.info(f"[搜索] 百度搜索完成 | 关键词: {query} | 结果: {len(results)} 条 | 耗时: {round(time.time() - t0, 2)}s")
            return results[:num_results]
        except Exception as e:
            logger.warning(f"[搜索] 百度搜索失败 | 关键词: {query} | 错误: {e} | 耗时: {round(time.time() - t0, 2)}s")
            return []

    def _search_360_sync(self, query: str, num_results: int = 5) -> List[Dict]:
        """360搜索（同步，需在线程中调用）"""
        import time
        import requests
        from lxml import html
        from urllib.parse import quote
        t0 = time.time()
        logger.info(f"[搜索] 360搜索开始 | 关键词: {query} | 数量: {num_results}")

        url = f"https://www.so.com/s?q={quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            tree = html.fromstring(resp.content)
            results = []
            for item in tree.cssselect("li.res-list"):
                title_el = item.cssselect("h3 a")
                snippet_el = item.cssselect("span.res-list-summary, p.res-desc, div.res-rich")
                if title_el:
                    title = title_el[0].text_content().strip()
                    href = title_el[0].get("href", "")
                    snippet = snippet_el[0].text_content().strip() if snippet_el else ""
                    if title and href:
                        # 补全相对 URL 为绝对 URL
                        if href.startswith("/"):
                            href = f"https://www.so.com{href}"
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet,
                            "score": 0.7,
                            "source": "360",
                        })
            logger.info(f"[搜索] 360搜索完成 | 关键词: {query} | 结果: {len(results)} 条 | 耗时: {round(time.time() - t0, 2)}s")
            return results[:num_results]
        except Exception as e:
            logger.warning(f"[搜索] 360搜索失败 | 关键词: {query} | 错误: {e} | 耗时: {round(time.time() - t0, 2)}s")
            return []

    def _search_sogou_sync(self, query: str, num_results: int = 5) -> List[Dict]:
        """搜狗搜索（同步，需在线程中调用）"""
        import time
        import requests
        from lxml import html
        from urllib.parse import quote
        t0 = time.time()
        logger.info(f"[搜索] 搜狗搜索开始 | 关键词: {query} | 数量: {num_results}")

        url = f"https://www.sogou.com/web?query={quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            tree = html.fromstring(resp.content)
            results = []
            seen_urls = set()  # 用于去重
            # 搜狗搜索结果容器选择器
            for item in tree.cssselect("div.vrwrap, div.rb, div[class*='card'], div[class*='img-text']"):
                title_el = item.cssselect("h3 a, h3.vr-title, div[class*='title'] a")
                # 尝试多种摘要选择器
                snippet_el = item.cssselect("div.fz-mid.space-txt, div.img-text__content_c773, div.str-text-info, p.space-txt, div[class*='abstract'], div[class*='content']")
                if title_el:
                    title = title_el[0].text_content().strip()
                    href = title_el[0].get("href", "")
                    snippet = snippet_el[0].text_content().strip() if snippet_el else ""
                    if title and href:
                        # 补全相对 URL 为绝对 URL
                        if href.startswith("/"):
                            href = f"https://www.sogou.com{href}"
                        # 去重：跳过已见过的 URL
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet,
                            "score": 0.5,
                            "source": "搜狗",
                        })
            logger.info(f"[搜索] 搜狗搜索完成 | 关键词: {query} | 结果: {len(results)} 条 | 耗时: {round(time.time() - t0, 2)}s")
            return results[:num_results]
        except Exception as e:
            logger.warning(f"[搜索] 搜狗搜索失败 | 关键词: {query} | 错误: {e} | 耗时: {round(time.time() - t0, 2)}s")
            return []

    async def search_baidu(self, query: str, num_results: int = 5) -> List[Dict]:
        """百度搜索（异步包装）"""
        return await asyncio.to_thread(self._search_baidu_sync, query, num_results)

    async def search_360(self, query: str, num_results: int = 5) -> List[Dict]:
        """360搜索（异步包装）"""
        return await asyncio.to_thread(self._search_360_sync, query, num_results)

    async def search_sogou(self, query: str, num_results: int = 5) -> List[Dict]:
        """搜狗搜索（异步包装）"""
        return await asyncio.to_thread(self._search_sogou_sync, query, num_results)

    async def search_all(self, query: str, num_results: int = 10,
                         start_date: str = None, end_date: str = None) -> List[Dict]:
        """多源聚合搜索：Exa + B站 + 百度/360/搜狗"""
        all_results = []

        # 并行调用多个搜索源
        source_names = ["Exa", "B站", "百度", "360", "搜狗"]
        tasks = [
            self.search_web(query, min(num_results, 5), start_date=start_date, end_date=end_date),
            self.search_bilibili(query, min(num_results, 5)),
            self.search_baidu(query, min(num_results, 5)),
            self.search_360(query, min(num_results, 5)),
            self.search_sogou(query, min(num_results, 5)),
        ]

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        for i, results in enumerate(results_list):
            source = source_names[i] if i < len(source_names) else f"源{i}"
            if isinstance(results, list):
                all_results.extend(results)
                logger.info(f"[AgentReach] {source} 搜索 \"{query}\" 返回 {len(results)} 条")
            else:
                logger.warning(f"[AgentReach] {source} 搜索失败: {results}")

        # 按 score 排序，去重
        seen_urls = set()
        unique_results = []
        for r in sorted(all_results, key=lambda x: x.get("score", 0), reverse=True):
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

        # 过滤掉需认证的平台（外部用户无法访问）
        auth_platforms = ["feishu.cn", "notion.so", "atlassian.net", "yuque.com", "kdocs.cn"]
        filtered_results = []
        for r in unique_results:
            url = r.get("url", "")
            if any(platform in url for platform in auth_platforms):
                logger.info(f"[搜索] 过滤需认证平台: {url[:60]}...")
                continue
            filtered_results.append(r)
        if len(filtered_results) < len(unique_results):
            logger.info(f"[搜索] 过滤需认证平台: {len(unique_results)} → {len(filtered_results)} 条")

        # GPT-Researcher 风格：相关性评分 + 内容去重
        ranked_results = self._rank_and_filter_results(query, filtered_results)
        return ranked_results[:num_results]

    def _rank_and_filter_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """GPT-Researcher 风格：基于关键词匹配的相关性评分 + 内容去重"""
        import re
        if not results:
            return results

        # 提取查询关键词（中文词 + 英文词）
        chinese_words = set(re.findall(r'[一-鿿]{2,}', query))
        english_words = set(re.findall(r'[a-zA-Z]{2,}', query.lower()))
        keywords = chinese_words | english_words

        if not keywords:
            return results

        # 相关性评分
        scored_results = []
        for r in results:
            title = r.get("title", "").lower()
            snippet = r.get("snippet", "").lower()
            text = title + " " + snippet

            # 计算关键词命中数
            hits = sum(1 for kw in keywords if kw in text)
            # 标题命中权重更高
            title_hits = sum(1 for kw in keywords if kw in title)
            # 相关性分数 = 标题命中×2 + 内容命中
            relevance_score = title_hits * 2 + hits

            r["_relevance_score"] = relevance_score
            scored_results.append(r)

        # 按相关性分数排序
        scored_results.sort(key=lambda x: x.get("_relevance_score", 0), reverse=True)

        # 过滤掉完全不相关的（标题和内容都没有命中关键词）
        relevant_results = [r for r in scored_results if r.get("_relevance_score", 0) > 0]

        # 内容去重：标题相似度超过 70% 的只保留分数最高的
        deduped = []
        seen_titles = []
        for r in relevant_results:
            title = r.get("title", "")
            is_dup = False
            for seen_title in seen_titles:
                if self._title_similarity(title, seen_title) > 0.7:
                    is_dup = True
                    logger.info(f"[搜索] 内容去重: \"{title[:30]}...\" 与 \"{seen_title[:30]}...\" 相似")
                    break
            if not is_dup:
                deduped.append(r)
                seen_titles.append(title)

        if len(deduped) < len(relevant_results):
            logger.info(f"[搜索] 内容去重: {len(relevant_results)} → {len(deduped)} 条")

        return deduped

    def _title_similarity(self, title1: str, title2: str) -> float:
        """计算两个标题的相似度（基于 bigram Jaccard）"""
        if not title1 or not title2:
            return 0.0
        # 生成 bigrams
        bigrams1 = set(title1[i:i+2] for i in range(len(title1)-1))
        bigrams2 = set(title2[i:i+2] for i in range(len(title2)-1))
        if not bigrams1 or not bigrams2:
            return 0.0
        intersection = len(bigrams1 & bigrams2)
        union = len(bigrams1 | bigrams2)
        return intersection / union if union > 0 else 0.0

    async def fetch_full_text(self, url: str, max_chars: int = 15000) -> str:
        """使用 Jina Reader 抓取网页全文，返回纯文本"""
        import time
        t0 = time.time()
        try:
            jina_url = f"https://r.jina.ai/{url}"
            cmd = f'curl -sL --max-time 8 "{jina_url}" -H "Accept: text/plain"'
            output = await asyncio.to_thread(self._run_cmd, cmd, 12)
            if output:
                # 截取前 max_chars 个字符，保留完整段落
                if len(output) > max_chars:
                    cut_pos = output.rfind("\n", 0, max_chars)
                    output = output[:cut_pos] if cut_pos > max_chars // 2 else output[:max_chars]
                elapsed = round(time.time() - t0, 2)
                logger.info(f"[全文抓取] 成功 | URL: {url[:60]}... | 长度: {len(output)} 字符 | 耗时: {elapsed}s")
                return output
        except Exception as e:
            logger.warning(f"[全文抓取] 失败 | URL: {url[:60]}... | 错误: {e}")
        return ""

    async def enrich_results_with_full_text(self, results: List[Dict], top_n: int = 3) -> List[Dict]:
        """对搜索结果中数据相关性最高的 top_n 条抓取全文，替换 snippet"""
        if not results:
            return results

        # 标题含数据关键词的优先抓取
        data_keywords = ["对比", "性能", "参数", "mAP", "benchmark", "评测", "测试", "比较", "区别", "表格", "数据"]
        def data_relevance(r):
            title = r.get("title", "")
            return any(kw in title.lower() for kw in data_keywords)

        data_rich = [r for r in results if data_relevance(r)]
        others = [r for r in results if not data_relevance(r)]
        targets = (data_rich + others)[:top_n]

        logger.info(f"[全文增强] 对 {len(targets)} 条结果抓取全文 (数据类: {len(data_rich)}, 其他: {len(others)})")

        # 竞速探测：首条和剩余同时发起，首条失败则跳过全部
        first_task = asyncio.create_task(self.fetch_full_text(targets[0].get("url", "")))
        remaining_tasks = [asyncio.create_task(self.fetch_full_text(r.get("url", ""))) for r in targets[1:]]

        # 等首条结果
        first_text = await first_task
        if not first_text:
            # 首条失败，取消剩余任务，快速跳过
            for t in remaining_tasks:
                t.cancel()
            logger.warning(f"[全文增强] 首条抓取失败，Jina Reader 可能不可达，跳过全文增强")
            return results
        if len(first_text) > len(targets[0].get("snippet", "")):
            targets[0]["snippet"] = first_text
            logger.info(f"[全文增强] 第 1 条 snippet 已替换为全文 ({len(first_text)} 字符)")

        # 首条成功，等剩余（已在并行执行，不额外耗时）
        if remaining_tasks:
            try:
                full_texts = await asyncio.wait_for(asyncio.gather(*remaining_tasks), timeout=20)
                for i, text in enumerate(full_texts):
                    if text and len(text) > len(targets[i+1].get("snippet", "")):
                        targets[i+1]["snippet"] = text
                        logger.info(f"[全文增强] 第 {i+2} 条 snippet 已替换为全文 ({len(text)} 字符)")
            except asyncio.TimeoutError:
                logger.warning(f"[全文增强] 剩余抓取超时(20s)，跳过")
        return results

    def _parse_exa_results(self, output: str) -> List[Dict]:
        """解析 Exa 搜索结果（mcporter 文本格式）"""
        results = []

        # 先尝试 JSON 解析
        try:
            data = json.loads(output)
            if isinstance(data, list):
                for item in data:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("text", item.get("snippet", "")),
                        "score": item.get("score", 0.8),
                        "source": "exa",
                    })
                return results
            elif isinstance(data, dict):
                for item in data.get("results", data.get("contents", [])):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("text", item.get("snippet", "")),
                        "score": item.get("score", 0.8),
                        "source": "exa",
                    })
                return results
        except json.JSONDecodeError:
            pass

        # mcporter 文本格式：每条结果以 Title:/URL:/Published: 开头，Highlights 为内容
        lines = output.strip().split("\n")
        current = {}
        for line in lines:
            line = line.strip()
            if line.startswith("Title:"):
                if current.get("title") and current.get("url"):
                    results.append(current)
                current = {
                    "title": line[6:].strip(),
                    "url": "",
                    "snippet": "",
                    "score": 0.8,
                    "source": "exa",
                }
            elif line.startswith("URL:"):
                current["url"] = line[4:].strip()
            elif line.startswith("Published:"):
                pub_val = line[10:].strip()
                if pub_val and pub_val != "N/A":
                    current["snippet"] = f"[发布于 {pub_val}] " + current.get("snippet", "")
            elif line.startswith("Author:"):
                pass  # 忽略作者
            elif line.startswith("Highlights:"):
                pass  # 高亮标记行
            elif line.startswith("[...]"):
                current["snippet"] += "\n"
            elif line.startswith("|"):
                pass  # 表格行
            elif current.get("title"):
                # 累积完整内容到 snippet
                existing = current.get("snippet", "")
                current["snippet"] = (existing + " " + line).strip()

        # 收尾最后一条
        if current.get("title") and current.get("url"):
            results.append(current)

        return results


# 全局单例
_agent_reach_service: Optional[AgentReachService] = None


def get_agent_reach_service() -> AgentReachService:
    """获取 Agent Reach 服务实例"""
    global _agent_reach_service
    if _agent_reach_service is None:
        _agent_reach_service = AgentReachService()
    return _agent_reach_service
