"""
Tavily API 测试脚本
测试 content 和 raw_content 字段的长度及具体内容
结果保存到 tests/test_data/Tavily测试报告_时间戳.md
"""
from tavily import TavilyClient
from datetime import datetime

# 配置
API_KEY = "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"
QUERY = "2026年人工智能发展趋势"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = f"tests/test_data/Tavily测试报告_{TIMESTAMP}.md"

def test_basic():
    """测试 basic 模式"""
    client = TavilyClient(api_key=API_KEY)
    response = client.search(
        query=QUERY,
        search_depth="basic",
        max_results=3
    )
    return response.get("results", [])

def test_advanced():
    """测试 advanced 模式"""
    client = TavilyClient(api_key=API_KEY)
    response = client.search(
        query=QUERY,
        search_depth="advanced",
        max_results=3
    )
    return response.get("results", [])

def test_advanced_with_raw():
    """测试 advanced 模式 + include_raw_content"""
    client = TavilyClient(api_key=API_KEY)
    response = client.search(
        query=QUERY,
        search_depth="advanced",
        include_raw_content=True,
        max_results=3
    )
    return response.get("results", [])

def format_results(mode_name, results, show_content=False):
    """格式化结果为 markdown"""
    lines = []
    lines.append(f"### {mode_name}")
    lines.append("")
    lines.append("| # | 标题 | URL | content 长度 | raw_content 长度 |")
    lines.append("|---|------|-----|-------------|-----------------|")

    for i, result in enumerate(results, 1):
        title = result.get("title", "")
        if len(title) > 30:
            title = title[:30] + "..."
        url = result.get("url", "")
        content_len = len(result.get("content", ""))
        raw_content_len = len(result.get("raw_content", "")) if result.get("raw_content") else 0
        lines.append(f"| {i} | {title} | {url} | {content_len} | {raw_content_len} |")

    lines.append("")

    # 显示具体内容
    if show_content:
        for i, result in enumerate(results, 1):
            title = result.get("title", "")
            url = result.get("url", "")
            content = result.get("content", "")
            raw_content = result.get("raw_content", "")

            lines.append(f"#### 结果 {i}：{title}")
            lines.append("")
            lines.append(f"**URL**：{url}")
            lines.append("")
            lines.append(f"**content**（{len(content)} 字符）：")
            lines.append("")
            lines.append("```")
            lines.append(content[:2000] + "..." if len(content) > 2000 else content)
            lines.append("```")
            lines.append("")

            if raw_content:
                lines.append(f"**raw_content**（{len(raw_content)} 字符）：")
                lines.append("")
                lines.append("```")
                lines.append(raw_content[:2000] + "..." if len(raw_content) > 2000 else raw_content)
                lines.append("```")
                lines.append("")

    return "\n".join(lines)

def main():
    print("开始测试 Tavily API...")
    print(f"查询: {QUERY}")

    # 运行测试
    print("测试 basic 模式...")
    basic_results = test_basic()

    print("测试 advanced 模式...")
    advanced_results = test_advanced()

    print("测试 advanced + raw_content 模式...")
    raw_results = test_advanced_with_raw()

    # 生成报告
    report = []
    report.append("# Tavily API 测试报告")
    report.append("")
    report.append(f"> 测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"> 测试查询：{QUERY}")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## 一、测试结果概览")
    report.append("")
    report.append(format_results("basic 模式", basic_results, show_content=False))
    report.append(format_results("advanced 模式", advanced_results, show_content=False))
    report.append(format_results("advanced + raw_content 模式", raw_results, show_content=False))

    # 统计
    report.append("## 二、统计汇总")
    report.append("")
    report.append("| 模式 | content 平均长度 | raw_content 平均长度 |")
    report.append("|------|-----------------|---------------------|")

    basic_avg = sum(len(r.get("content", "")) for r in basic_results) / len(basic_results) if basic_results else 0
    advanced_avg = sum(len(r.get("content", "")) for r in advanced_results) / len(advanced_results) if advanced_results else 0
    raw_avg = sum(len(r.get("raw_content", "")) for r in raw_results if r.get("raw_content")) / len([r for r in raw_results if r.get("raw_content")]) if raw_results else 0

    report.append(f"| basic | {basic_avg:.0f} 字符 | - |")
    report.append(f"| advanced | {advanced_avg:.0f} 字符 | - |")
    report.append(f"| advanced + raw_content | {advanced_avg:.0f} 字符 | {raw_avg:.0f} 字符 |")
    report.append("")

    # 结论
    report.append("## 三、结论")
    report.append("")
    report.append(f"- **content 字段**：{basic_avg:.0f}-{advanced_avg:.0f} 字符（basic vs advanced 模式）")
    report.append(f"- **raw_content 字段**：{raw_avg:.0f} 字符（需要设置 include_raw_content=True）")
    report.append(f"- **与传统搜索引擎对比**：百度/搜狗约 100-200 字符，Tavily 是其 {advanced_avg/150:.0f}-{advanced_avg/100:.0f} 倍")
    report.append("")
    report.append("---")
    report.append("")

    # 具体内容
    report.append("## 四、具体内容展示")
    report.append("")
    report.append("### basic 模式")
    report.append("")
    for i, result in enumerate(basic_results, 1):
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")
        report.append(f"#### 结果 {i}：{title}")
        report.append("")
        report.append(f"**URL**：{url}")
        report.append("")
        report.append(f"**content**（{len(content)} 字符）：")
        report.append("")
        report.append("```")
        report.append(content)
        report.append("```")
        report.append("")

    report.append("### advanced 模式")
    report.append("")
    for i, result in enumerate(advanced_results, 1):
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")
        report.append(f"#### 结果 {i}：{title}")
        report.append("")
        report.append(f"**URL**：{url}")
        report.append("")
        report.append(f"**content**（{len(content)} 字符）：")
        report.append("")
        report.append("```")
        report.append(content)
        report.append("```")
        report.append("")

    report.append("### advanced + raw_content 模式")
    report.append("")
    for i, result in enumerate(raw_results, 1):
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")
        raw_content = result.get("raw_content", "")
        report.append(f"#### 结果 {i}：{title}")
        report.append("")
        report.append(f"**URL**：{url}")
        report.append("")
        report.append(f"**content**（{len(content)} 字符）：")
        report.append("")
        report.append("```")
        report.append(content)
        report.append("```")
        report.append("")
        if raw_content:
            report.append(f"**raw_content**（{len(raw_content)} 字符）：")
            report.append("")
            report.append("```")
            report.append(raw_content[:3000] + "..." if len(raw_content) > 3000 else raw_content)
            report.append("```")
            report.append("")

    # 保存报告
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\n测试完成！报告已保存到: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
