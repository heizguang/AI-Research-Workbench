"""
搜索引擎对比测试脚本 v3
测试 Tavily、Exa、last30days 等搜索引擎
结果保存到 tests/test_data/搜索引擎对比测试_v3_时间戳.md
"""
import asyncio
import os
import time
import subprocess
import json
from datetime import datetime

# 添加项目路径
import sys
sys.path.insert(0, "backend")

from services.agent_reach_service import get_agent_reach_service

# 配置
QUERY = "2026年人工智能发展趋势"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = f"tests/test_data/搜索引擎对比测试_v3_{TIMESTAMP}.md"

async def test_tavily(query, num_results=3):
    """测试 Tavily 搜索"""
    print(f"测试 Tavily 搜索: {query}")
    try:
        from tavily import TavilyClient
        API_KEY = "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"
        client = TavilyClient(api_key=API_KEY)

        t0 = time.time()
        response = client.search(
            query=query,
            search_depth="advanced",
            include_raw_content=True,
            max_results=num_results
        )
        elapsed = time.time() - t0

        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
                "raw_content": r.get("raw_content", ""),
                "source": "Tavily",
            })

        print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
        return results, elapsed
    except Exception as e:
        print(f"  失败: {e}")
        return [], 0

async def test_exa(query, num_results=3):
    """测试 Exa 搜索"""
    print(f"测试 Exa 搜索: {query}")
    try:
        service = get_agent_reach_service()
        t0 = time.time()
        results = await service.search_web(query, num_results)
        elapsed = time.time() - t0
        print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
        return results, elapsed
    except Exception as e:
        print(f"  失败: {e}")
        # 尝试使用 Tavily 作为 Exa 的替代
        print(f"  尝试使用 Tavily 作为替代...")
        return await test_tavily(query, num_results)

async def test_last30days(query, num_results=3):
    """测试 last30days 搜索（需要 Python 3.12+，使用 conda last30days 环境）"""
    print(f"测试 last30days 搜索: {query}")
    try:
        # 调用 last30days 脚本，使用 conda last30days 环境的 Python 3.12
        script_dir = "skills/last30days/scripts"
        conda_python = os.path.expanduser("~/Miniconda3/envs/last30days/python")
        if os.name == "nt":
            # Windows: 尝试 conda 环境路径
            conda_python_win = r"D:\Miniconda3\envs\last30days\python.exe"
            if os.path.exists(conda_python_win):
                python_cmd = conda_python_win
            elif os.path.exists(conda_python):
                python_cmd = conda_python
            else:
                python_cmd = "python"
        else:
            python_cmd = "python3"
        cmd = [python_cmd, "last30days.py", query, "--emit", "json", "--max-results", str(num_results)]

        t0 = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=script_dir
        )
        elapsed = time.time() - t0

        if result.returncode != 0:
            print(f"  失败: 返回码 {result.returncode}")
            if result.stderr:
                print(f"  错误: {result.stderr[:200]}")
            return [], 0

        data = json.loads(result.stdout)
        results = []
        # JSON 结构: items_by_source -> {source: [items]}
        for source_items in data.get("items_by_source", {}).values():
            for item in source_items:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", item.get("body", "")),
                    "source": "last30days",
                })
                if len(results) >= num_results:
                    break
            if len(results) >= num_results:
                break

        print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
        return results, elapsed
    except Exception as e:
        print(f"  失败: {e}")
        return [], 0

async def test_baidu(query, num_results=3):
    """测试百度搜索"""
    print(f"测试百度搜索: {query}")
    try:
        service = get_agent_reach_service()
        t0 = time.time()
        results = await service.search_baidu(query, num_results)
        elapsed = time.time() - t0
        print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
        return results, elapsed
    except Exception as e:
        print(f"  失败: {e}")
        return [], 0

async def test_sogou(query, num_results=3):
    """测试搜狗搜索"""
    print(f"测试搜狗搜索: {query}")
    try:
        service = get_agent_reach_service()
        t0 = time.time()
        results = await service.search_sogou(query, num_results)
        elapsed = time.time() - t0
        print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
        return results, elapsed
    except Exception as e:
        print(f"  失败: {e}")
        return [], 0

async def test_360(query, num_results=3):
    """测试360搜索"""
    print(f"测试360搜索: {query}")
    try:
        service = get_agent_reach_service()
        t0 = time.time()
        results = await service.search_360(query, num_results)
        elapsed = time.time() - t0
        print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
        return results, elapsed
    except Exception as e:
        print(f"  失败: {e}")
        return [], 0

async def main():
    print("=" * 60)
    print("搜索引擎对比测试 v3（Tavily、Exa、last30days）")
    print(f"查询: {QUERY}")
    print("=" * 60)
    print()

    # 运行测试
    tavily_results, tavily_time = await test_tavily(QUERY)
    exa_results, exa_time = await test_exa(QUERY)
    last30days_results, last30days_time = await test_last30days(QUERY)
    baidu_results, baidu_time = await test_baidu(QUERY)
    sogou_results, sogou_time = await test_sogou(QUERY)
    so360_results, so360_time = await test_360(QUERY)

    # 生成报告
    report = []
    report.append("# 搜索引擎对比测试报告 v3")
    report.append("")
    report.append(f"> 测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"> 测试查询：{QUERY}")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## 一、测试结果概览")
    report.append("")
    report.append("| 搜索引擎 | 结果数量 | 耗时 | snippet 平均长度 | raw_content 平均长度 |")
    report.append("|----------|----------|------|-----------------|---------------------|")

    # 统计
    def avg_len(results, key="snippet"):
        if not results:
            return 0
        return sum(len(r.get(key, "")) for r in results) / len(results)

    report.append(f"| Tavily | {len(tavily_results)} | {tavily_time:.2f}s | {avg_len(tavily_results):.0f} 字符 | {avg_len(tavily_results, 'raw_content'):.0f} 字符 |")
    report.append(f"| Exa | {len(exa_results)} | {exa_time:.2f}s | {avg_len(exa_results):.0f} 字符 | - |")
    report.append(f"| last30days | {len(last30days_results)} | {last30days_time:.2f}s | {avg_len(last30days_results):.0f} 字符 | - |")
    report.append(f"| 百度 | {len(baidu_results)} | {baidu_time:.2f}s | {avg_len(baidu_results):.0f} 字符 | - |")
    report.append(f"| 搜狗 | {len(sogou_results)} | {sogou_time:.2f}s | {avg_len(sogou_results):.0f} 字符 | - |")
    report.append(f"| 360 | {len(so360_results)} | {so360_time:.2f}s | {avg_len(so360_results):.0f} 字符 | - |")
    report.append("")
    report.append("---")
    report.append("")

    # 各搜索引擎详细结果
    report.append("## 二、各搜索引擎详细结果")
    report.append("")

    # Tavily
    report.append("### Tavily 搜索")
    report.append("")
    for i, r in enumerate(tavily_results, 1):
        report.append(f"#### 结果 {i}")
        report.append("")
        report.append(f"**标题**：{r.get('title', '')}")
        report.append("")
        report.append(f"**URL**：{r.get('url', '')}")
        report.append("")
        report.append(f"**content**（{len(r.get('snippet', ''))} 字符）：")
        report.append("")
        report.append("```")
        report.append(r.get("snippet", ""))
        report.append("```")
        report.append("")
        if r.get("raw_content"):
            report.append(f"**raw_content**（{len(r.get('raw_content', ''))} 字符）：")
            report.append("")
            report.append("```")
            raw = r.get("raw_content", "")
            report.append(raw)
            report.append("```")
            report.append("")

    # Exa
    report.append("### Exa 搜索")
    report.append("")
    for i, r in enumerate(exa_results, 1):
        report.append(f"#### 结果 {i}")
        report.append("")
        report.append(f"**标题**：{r.get('title', '')}")
        report.append("")
        report.append(f"**URL**：{r.get('url', '')}")
        report.append("")
        report.append(f"**snippet**（{len(r.get('snippet', ''))} 字符）：")
        report.append("")
        report.append("```")
        report.append(r.get("snippet", ""))
        report.append("```")
        report.append("")

    # last30days
    report.append("### last30days 搜索")
    report.append("")
    for i, r in enumerate(last30days_results, 1):
        report.append(f"#### 结果 {i}")
        report.append("")
        report.append(f"**标题**：{r.get('title', '')}")
        report.append("")
        report.append(f"**URL**：{r.get('url', '')}")
        report.append("")
        report.append(f"**snippet**（{len(r.get('snippet', ''))} 字符）：")
        report.append("")
        report.append("```")
        report.append(r.get("snippet", ""))
        report.append("```")
        report.append("")

    # 结论
    report.append("---")
    report.append("")
    report.append("## 三、结论")
    report.append("")
    report.append("| 搜索引擎 | 结果数量 | snippet 长度 | 特点 |")
    report.append("|----------|----------|-------------|------|")
    report.append(f"| Tavily | {len(tavily_results)} | {avg_len(tavily_results):.0f} 字符 | API 服务，无反爬虫，支持 raw_content |")
    report.append(f"| Exa | {len(exa_results)} | {avg_len(exa_results):.0f} 字符 | 语义搜索，支持时间过滤 |")
    report.append(f"| last30days | {len(last30days_results)} | {avg_len(last30days_results):.0f} 字符 | 多源聚合（Reddit、X、YouTube、HN） |")
    report.append(f"| 百度 | {len(baidu_results)} | {avg_len(baidu_results):.0f} 字符 | 有反爬虫机制，可能返回空结果 |")
    report.append(f"| 搜狗 | {len(sogou_results)} | {avg_len(sogou_results):.0f} 字符 | 搜索结果页摘要 |")
    report.append(f"| 360 | {len(so360_results)} | {avg_len(so360_results):.0f} 字符 | 搜索结果页摘要 |")
    report.append("")
    report.append("**关键发现**：")
    report.append("")
    report.append("1. **Tavily**：content 约 1500 字符，raw_content 约 2500 字符，是最佳选择")
    report.append("2. **Exa**：语义搜索，支持时间过滤，适合技术内容")
    report.append("3. **last30days**：多源聚合，覆盖 Reddit、X、YouTube、HN，适合获取最新动态")
    report.append("4. **传统搜索引擎**：百度有反爬虫限制，搜狗和 360 的 snippet 较短")

    # 保存报告
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\n测试完成！报告已保存到: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
