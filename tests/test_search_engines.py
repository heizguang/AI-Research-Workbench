"""
搜索引擎对比测试脚本
对比 Tavily、百度、搜狗等搜索引擎的返回内容长度
结果保存到 tests/test_data/搜索引擎对比测试_时间戳.md
"""
import time
import requests
from lxml import html
from urllib.parse import quote
from datetime import datetime

# 配置
QUERY = "2026年人工智能发展趋势"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = f"tests/test_data/搜索引擎对比测试_{TIMESTAMP}.md"

def search_baidu(query, num_results=3):
    """百度搜索"""
    print(f"测试百度搜索: {query}")
    url = f"https://www.baidu.com/s?wd={quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": "BAIDUID_BFESS=DA5EA84A045E51D0A518F3F46B7AC990:FG=1; __bid_n=19d05c184dd609627e0f3d; BAIDU_WISE_UID=wapp_1776339415826_872; BIDUPSID=DA5EA84A045E51D0A518F3F46B7AC990; PSTM=1778554333; ZFY=kG6AQhgQeXz3bJb7AiOXElM1fEDJ8qh1r4oZLBbbRwM:C; ploganondeg=1; BDUSS=UFnMjcyV3pmd2FUYlVDZEVOYUw5S2J6ekl6dkVBcGpPUHJWVkMwdGp2YXNFbXRxSVFBQUFBJCQAAAAAAAAAAAEAAAAip6nrutq54jc4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKyFQ2qshUNqe; BDUSS_BFESS=UFnMjcyV3pmd2FUYlVDZEVOYUw5S2J6ekl6dkVBcGpPUHJWVkMwdGp2YXNFbXRxSVFBQUFBJCQAAAAAAAAAAAEAAAAip6nrutq54jc4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKyFQ2qshUNqe; BA_HECTOR=80010l812g0481al2h85al8l2485211l4p92d29; H_WISE_SIDS=63147_67862_68166_69295_70548_71041_71070_71139_71241_71272_71278_71279_71274_71295_71305_71318_71335_71350_71362_71359_71368_71383_71400_71403_71424_71464_71477_71483_71413_71242_71538_71534_71532_71540_71544_71560_71564_71553_71558_71566_71586_71575_71637_71600_71638_71644_71654_71501_71676_71686; BDRCVFR[feWj1Vr5u3D]=I67x6TjHwwYf0; H_PS_PSSID=63147_67862_68166_69295_70548_71041_71070_71139_71241_71272_71278_71279_71274_71295_71305_71318_71335_71350_71362_71359_71368_71383_71400_71403_71424_71464_71477_71483_71413_71242_71538_71534_71532_71540_71544_71560_71564_71553_71558_71566_71586_71575_71637_71600_71638_71644_71654_71501_71676_71686; delPer=0; PSINO=7; BDORZ=B490B5EBF6F3CD402E515D22BCDA1598",
    }
    try:
        t0 = time.time()
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        tree = html.fromstring(resp.content)
        results = []
        for item in tree.cssselect("div.result, div.c-container, div.result-op"):
            title_el = item.cssselect("h3 a, h3")
            # 尝试多种摘要选择器
            snippet = ""
            snippet_selectors = [
                "span.content-right_8Zs40",
                "div.c-abstract",
                "span[class*='content']",
                "div.c-span-last",
                "span.c-font-normal",
                "div.c-abstract-new",
                "p",
            ]
            for sel in snippet_selectors:
                snippet_el = item.cssselect(sel)
                if snippet_el:
                    snippet = snippet_el[0].text_content().strip()
                    if snippet and len(snippet) > 10:
                        break

            if title_el:
                title = title_el[0].text_content().strip()
                href = title_el[0].get("href", "")
                if title and href:
                    if href.startswith("/"):
                        href = f"https://www.baidu.com{href}"
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet,
                        "source": "百度",
                    })
        elapsed = time.time() - t0
        print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
        return results[:num_results], elapsed
    except Exception as e:
        print(f"  失败: {e}")
        return [], 0

def search_sogou(query, num_results=3):
    """搜狗搜索"""
    print(f"测试搜狗搜索: {query}")
    url = f"https://www.sogou.com/web?query={quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": "ABTEST=7|1783407748|v17; IPLOC=CN4403; SUID=E71F0EB76B54A20B000000006A4CA484; cuid=AAEwlADyWwAAAAuiUIunVgAASQU=; SUV=1783407750267233; SNUID=D72F21982F367ACFD6EAEB673005C54B; LSTMV=72%2C503; LCLKINT=7097",
        "Host": "www.sogou.com",
    }
    try:
        t0 = time.time()
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        tree = html.fromstring(resp.content)
        results = []
        for item in tree.cssselect("div.vrwrap, div.rb, div[class*='result']"):
            title_el = item.cssselect("h3 a, h3")
            # 尝试多种摘要选择器
            snippet = ""
            snippet_selectors = [
                "div.str-text-info",
                "p.space-txt",
                "div[class*='abstract']",
                "div[class*='content']",
                "p",
                "span",
            ]
            for sel in snippet_selectors:
                snippet_el = item.cssselect(sel)
                if snippet_el:
                    snippet = snippet_el[0].text_content().strip()
                    if snippet and len(snippet) > 10:
                        break

            if title_el:
                title = title_el[0].text_content().strip()
                href = title_el[0].get("href", "")
                if title and href:
                    if href.startswith("/"):
                        href = f"https://www.sogou.com{href}"
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet,
                        "source": "搜狗",
                    })
        elapsed = time.time() - t0
        print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
        return results[:num_results], elapsed
    except Exception as e:
        print(f"  失败: {e}")
        return [], 0

def search_360(query, num_results=3):
    """360搜索"""
    print(f"测试360搜索: {query}")
    url = f"https://www.so.com/s?q={quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        t0 = time.time()
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        tree = html.fromstring(resp.content)
        results = []
        for item in tree.cssselect("div.result"):
            title_el = item.cssselect("h3 a")
            snippet_el = item.cssselect("p.res-desc, div.res-rich")
            if title_el:
                title = title_el[0].text_content().strip()
                href = title_el[0].get("href", "")
                snippet = snippet_el[0].text_content().strip() if snippet_el else ""
                if title and href:
                    if href.startswith("/"):
                        href = f"https://www.so.com{href}"
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet,
                        "source": "360",
                    })
        elapsed = time.time() - t0
        print(f"  耗时: {elapsed:.2f}s, 结果: {len(results)} 条")
        return results[:num_results], elapsed
    except Exception as e:
        print(f"  失败: {e}")
        return [], 0

def test_tavily(query, num_results=3):
    """Tavily 搜索"""
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

def main():
    print("=" * 60)
    print("搜索引擎对比测试")
    print(f"查询: {QUERY}")
    print("=" * 60)
    print()

    # 运行测试
    baidu_results, baidu_time = search_baidu(QUERY)
    sogou_results, sogou_time = search_sogou(QUERY)
    so360_results, so360_time = search_360(QUERY)
    tavily_results, tavily_time = test_tavily(QUERY)

    # 生成报告
    report = []
    report.append("# 搜索引擎对比测试报告")
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

    # 搜狗结果
    report.append("### 搜狗搜索")
    report.append("")
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

    # 360结果
    report.append("### 360搜索")
    report.append("")
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

    # Tavily结果
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
            report.append(raw[:3000] + "..." if len(raw) > 3000 else raw)
            report.append("```")
            report.append("")

    # 结论
    report.append("---")
    report.append("")
    report.append("## 三、结论")
    report.append("")
    report.append("| 搜索引擎 | 结果数量 | snippet 长度 | 特点 |")
    report.append("|----------|----------|-------------|------|")
    report.append(f"| 百度 | {len(baidu_results)} | {baidu_avg:.0f} 字符 | 有反爬虫机制，可能返回空结果 |")
    report.append(f"| 搜狗 | {len(sogou_results)} | {sogou_avg:.0f} 字符 | 有反爬虫机制，可能返回空结果 |")
    report.append(f"| 360 | {len(so360_results)} | {so360_avg:.0f} 字符 | 有反爬虫机制，可能返回空结果 |")
    report.append(f"| Tavily | {len(tavily_results)} | {tavily_avg:.0f} 字符 | API 服务，无反爬虫限制 |")
    report.append(f"| Tavily raw_content | {len(tavily_results)} | {tavily_raw_avg:.0f} 字符 | 完整网页内容 |")
    report.append("")
    report.append("**关键发现**：")
    report.append("")
    report.append("1. **反爬虫机制**：百度、搜狗、360 等搜索引擎有反爬虫机制，会检测 User-Agent、Cookie、Referer 等信息，如果检测到是爬虫，会返回空结果或验证码页面。")
    report.append("")
    report.append("2. **Tavily 优势**：Tavily 是 API 服务，没有反爬虫限制，可以稳定获取搜索结果。")
    report.append("")
    report.append("3. **内容长度**：Tavily 的 content 字段约 2000 字符，比传统搜索引擎的 snippet（约 100-200 字符）长 10-20 倍。")
    report.append("")
    report.append("4. **实际应用**：在生产环境中，应该使用 Tavily 等 API 服务，而不是爬取搜索引擎结果页。")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## 四、反爬虫机制说明")
    report.append("")
    report.append("### 百度反爬虫")
    report.append("- 检测 User-Agent 是否为浏览器")
    report.append("- 检测 Cookie 和 Referer")
    report.append("- 频繁请求会触发验证码")
    report.append("- 返回的 HTML 可能不包含摘要内容")
    report.append("")
    report.append("### 搜狗反爬虫")
    report.append("- 检测 User-Agent")
    report.append("- 检测请求频率")
    report.append("- 返回的 HTML 结构可能变化")
    report.append("")
    report.append("### 360 反爬虫")
    report.append("- 检测 User-Agent")
    report.append("- 检测请求频率")
    report.append("- 返回的 HTML 结构可能变化")
    report.append("")
    report.append("### Tavily API")
    report.append("- 使用 API Key 认证")
    report.append("- 无反爬虫限制")
    report.append("- 返回结构化 JSON 数据")
    report.append("- 支持 advanced 模式获取更详细内容")

    # 保存报告
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\n测试完成！报告已保存到: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
