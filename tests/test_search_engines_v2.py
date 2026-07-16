"""
搜索引擎对比测试脚本 v2
使用项目中的 agent_reach_service.py 来测试
结果保存到 tests/test_data/搜索引擎对比测试_v2_时间戳.md
"""
import asyncio
import time
from datetime import datetime

# 添加项目路径
import sys
sys.path.insert(0, "backend")

from services.agent_reach_service import get_agent_reach_service

# 配置
QUERY = "2026年人工智能发展趋势"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = f"tests/test_data/搜索引擎对比测试_v2_{TIMESTAMP}.md"

async def test_baidu(query, num_results=3):
    """测试百度搜索"""
    print(f"测试百度搜索: {query}")
    service = get_agent_reach_service()
    t0 = time.time()
    results = await service.search_baidu(query, num_results)
    elapsed = time.time() - t0
    print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
    return results, elapsed

async def test_sogou(query, num_results=3):
    """测试搜狗搜索"""
    print(f"测试搜狗搜索: {query}")
    service = get_agent_reach_service()
    t0 = time.time()
    results = await service.search_sogou(query, num_results)
    elapsed = time.time() - t0
    print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
    return results, elapsed

async def test_360(query, num_results=3):
    """测试360搜索"""
    print(f"测试360搜索: {query}")
    service = get_agent_reach_service()
    t0 = time.time()
    results = await service.search_360(query, num_results)
    elapsed = time.time() - t0
    print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
    return results, elapsed

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

async def main():
    print("=" * 60)
    print("搜索引擎对比测试 v2（使用项目中的搜索服务）")
    print(f"查询: {QUERY}")
    print("=" * 60)
    print()

    # 运行测试
    baidu_results, baidu_time = await test_baidu(QUERY)
    sogou_results, sogou_time = await test_sogou(QUERY)
    so360_results, so360_time = await test_360(QUERY)
    tavily_results, tavily_time = await test_tavily(QUERY)

    # 生成报告
    report = []
    report.append("# 搜索引擎对比测试报告 v2")
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
    baidu_avg = sum(len(r.get("snippet", "")) for r in baidu_results) / len(baidu_results) if baidu_results else 0
    sogou_avg = sum(len(r.get("snippet", "")) for r in sogou_results) / len(sogou_results) if sogou_results else 0
    so360_avg = sum(len(r.get("snippet", "")) for r in so360_results) / len(so360_results) if so360_results else 0
    tavily_avg = sum(len(r.get("snippet", "")) for r in tavily_results) / len(tavily_results) if tavily_results else 0
    tavily_raw_avg = sum(len(r.get("raw_content", "")) for r in tavily_results if r.get("raw_content")) / len([r for r in tavily_results if r.get("raw_content")]) if tavily_results else 0

    report.append(f"| 百度 | {len(baidu_results)} | {baidu_time:.2f}s | {baidu_avg:.0f} 字符 | - |")
    report.append(f"| 搜狗 | {len(sogou_results)} | {sogou_time:.2f}s | {sogou_avg:.0f} 字符 | - |")
    report.append(f"| 360 | {len(so360_results)} | {so360_time:.2f}s | {so360_avg:.0f} 字符 | - |")
    report.append(f"| Tavily | {len(tavily_results)} | {tavily_time:.2f}s | {tavily_avg:.0f} 字符 | {tavily_raw_avg:.0f} 字符 |")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## 二、各搜索引擎详细结果")
    report.append("")

    # 百度结果
    report.append("### 百度搜索")
    report.append("")
    if baidu_results:
        for i, r in enumerate(baidu_results, 1):
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
    else:
        report.append("无结果")
        report.append("")

    # 搜狗结果
    report.append("### 搜狗搜索")
    report.append("")
    if sogou_results:
        for i, r in enumerate(sogou_results, 1):
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
    else:
        report.append("无结果")
        report.append("")

    # 360结果
    report.append("### 360搜索")
    report.append("")
    if so360_results:
        for i, r in enumerate(so360_results, 1):
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
    else:
        report.append("无结果")
        report.append("")

    # Tavily结果
    report.append("### Tavily 搜索")
    report.append("")
    if tavily_results:
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
                report.append(raw[:3000] + "..." if len(raw) > 3000 else raw)
                report.append("```")
                report.append("")
    else:
        report.append("无结果")
        report.append("")

    # 结论
    report.append("---")
    report.append("")
    report.append("## 三、结论")
    report.append("")
    report.append("| 搜索引擎 | 结果数量 | snippet 长度 | 特点 |")
    report.append("|----------|----------|-------------|------|")
    report.append(f"| 百度 | {len(baidu_results)} | {baidu_avg:.0f} 字符 | 搜索结果页摘要 |")
    report.append(f"| 搜狗 | {len(sogou_results)} | {sogou_avg:.0f} 字符 | 搜索结果页摘要 |")
    report.append(f"| 360 | {len(so360_results)} | {so360_avg:.0f} 字符 | 搜索结果页摘要 |")
    report.append(f"| Tavily | {len(tavily_results)} | {tavily_avg:.0f} 字符 | API 服务 |")
    report.append(f"| Tavily raw_content | {len(tavily_results)} | {tavily_raw_avg:.0f} 字符 | 完整网页内容 |")
    report.append("")
    report.append("**关键发现**：")
    report.append("")
    if baidu_results or sogou_results or so360_results:
        report.append(f"- 传统搜索引擎（百度/搜狗/360）的 snippet 约 {min(baidu_avg, sogou_avg, so360_avg):.0f}-{max(baidu_avg, sogou_avg, so360_avg):.0f} 字符")
        report.append(f"- Tavily 的 content 约 {tavily_avg:.0f} 字符，是传统搜索引擎的 {tavily_avg/max(baidu_avg, sogou_avg, so360_avg, 1):.1f} 倍")
    else:
        report.append("- 传统搜索引擎（百度/搜狗/360）返回 0 条结果（可能被反爬虫机制拦截）")
        report.append(f"- Tavily 的 content 约 {tavily_avg:.0f} 字符，稳定返回结果")
    report.append(f"- Tavily 的 raw_content 约 {tavily_raw_avg:.0f} 字符，提供完整网页内容")

    # 保存报告
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\n测试完成！报告已保存到: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
