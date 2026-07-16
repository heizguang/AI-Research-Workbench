"""
调试脚本 v2：查看百度和搜狗搜索结果的 HTML 结构
"""
import requests
from lxml import html
from urllib.parse import quote

QUERY = "2026年人工智能发展趋势"

def debug_baidu():
    """调试百度搜索结果的 HTML 结构"""
    print("=" * 60)
    print("调试百度搜索结果的 HTML 结构")
    print("=" * 60)

    url = f"https://www.baidu.com/s?wd={quote(QUERY)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    resp = requests.get(url, headers=headers, timeout=10)
    tree = html.fromstring(resp.content)

    # 查找所有可能的结果容器
    containers = tree.cssselect("div.result, div.c-container, div.result-op")
    print(f"找到 {len(containers)} 个结果容器")

    for i, container in enumerate(containers[:5], 1):
        print(f"\n--- 容器 {i} ---")
        print(f"标签: {container.tag}")
        print(f"类名: {container.get('class', '无')}")

        # 查找标题
        title_el = container.cssselect("h3 a, h3")
        if title_el:
            print(f"标题: {title_el[0].text_content().strip()[:50]}...")

        # 查找所有子元素的类名
        print("子元素类名:")
        for child in container.cssselect("*"):
            class_name = child.get("class", "")
            if class_name:
                text = child.text_content().strip()
                if text and len(text) > 20:
                    print(f"  {child.tag}.{class_name}: {len(text)} 字符")
                    print(f"    内容: {text[:100]}...")

def debug_sogou():
    """调试搜狗搜索结果的 HTML 结构"""
    print("\n" + "=" * 60)
    print("调试搜狗搜索结果的 HTML 结构")
    print("=" * 60)

    url = f"https://www.sogou.com/web?query={quote(QUERY)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    resp = requests.get(url, headers=headers, timeout=10)
    tree = html.fromstring(resp.content)

    # 查找所有可能的结果容器
    containers = tree.cssselect("div.vrwrap, div.rb, div[class*='result']")
    print(f"找到 {len(containers)} 个结果容器")

    for i, container in enumerate(containers[:5], 1):
        print(f"\n--- 容器 {i} ---")
        print(f"标签: {container.tag}")
        print(f"类名: {container.get('class', '无')}")

        # 查找标题
        title_el = container.cssselect("h3 a, h3")
        if title_el:
            print(f"标题: {title_el[0].text_content().strip()[:50]}...")

        # 查找所有子元素的类名
        print("子元素类名:")
        for child in container.cssselect("*"):
            class_name = child.get("class", "")
            if class_name:
                text = child.text_content().strip()
                if text and len(text) > 20:
                    print(f"  {child.tag}.{class_name}: {len(text)} 字符")
                    print(f"    内容: {text[:100]}...")

if __name__ == "__main__":
    debug_baidu()
    debug_sogou()
