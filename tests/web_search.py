import requests
import json

# ========== 配置 ==========
API_KEY = "sk-ca305a3a6052408f82aef948c44af4a9"  # 替换为你的实际 Key
API_URL = "https://api.bocha.cn/v1/web-search"


def web_search(query, count=10, freshness="noLimit", search_type="web"):
    """
    博查搜索 API
    :param query: 搜索关键词
    :param count: 返回结果数量，1-50
    :param freshness: 时间范围 - noLimit/oneDay/oneWeek/oneMonth/oneYear
    :param search_type: 搜索类型 - web/image
    :return: 搜索结果列表
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "query": query,
        "count": count,
        "freshness": freshness,
        "summary": True
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        pages = result["data"]["webPages"]["value"]
        items = []
        for page in pages:
            items.append({
                "title": page.get("name", ""),
                "url": page.get("url", ""),
                "snippet": page.get("snippet", ""),
                "summary": page.get("summary", ""),
            })
        return items

    except requests.exceptions.Timeout:
        print("请求超时")
        return []
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return []
    except (KeyError, json.JSONDecodeError) as e:
        print(f"解析失败: {e}")
        return []


def print_results(results):
    """格式化打印搜索结果"""
    if not results:
        print("没有搜索结果")
        return
    for i, item in enumerate(results, 1):
        print(f"\n{'='*60}")
        print(f"[{i}] {item['title']}")
        print(f"    链接: {item['url']}")
        if item['snippet']:
            print(f"    摘要: {item['snippet'][:200]}")
        if item['summary']:
            print(f"    总结: {item['summary'][:200]}")


if __name__ == "__main__":
    keyword = input("请输入搜索关键词: ").strip()
    if keyword:
        results = web_search(keyword, count=5)
        print_results(results)
    else:
        print("关键词不能为空")
