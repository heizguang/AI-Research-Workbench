import requests
import json

# ========== 配置 ==========
API_KEY = "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"  # 替换为你的实际 Key，免费申请：https://tavily.com
API_URL = "https://api.tavily.com/search"


def tavily_search(query, max_results=5, search_depth="basic", include_answer=True):
    """
    Tavily 搜索 API（专为 AI/LLM 设计）
    :param query: 搜索关键词
    :param max_results: 返回结果数量，1-20
    :param search_depth: 搜索深度 - basic(快)/advanced(深)
    :param include_answer: 是否返回 AI 生成的直接回答
    :return: 搜索结果字典
    """
    payload = {
        "api_key": API_KEY,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": include_answer,
    }

    try:
        resp = requests.post(API_URL, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        items = []
        for page in result.get("results", []):
            items.append({
                "title": page.get("title", ""),
                "url": page.get("url", ""),
                "content": page.get("content", ""),
                "score": page.get("score", 0),
            })
        return {
            "answer": result.get("answer", ""),
            "results": items,
        }

    except requests.exceptions.Timeout:
        print("请求超时")
        return {"answer": "", "results": []}
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return {"answer": "", "results": []}
    except (KeyError, json.JSONDecodeError) as e:
        print(f"解析失败: {e}")
        return {"answer": "", "results": []}


def print_results(data):
    """格式化打印搜索结果"""
    if data["answer"]:
        print(f"\n{'='*60}")
        print(f"AI 直接回答:\n{data['answer']}")

    results = data["results"]
    if not results:
        print("没有搜索结果")
        return

    for i, item in enumerate(results, 1):
        print(f"\n{'='*60}")
        print(f"[{i}] {item['title']}")
        print(f"    链接: {item['url']}")
        print(f"    相关度: {item['score']:.2f}")
        if item['content']:
            print(f"    内容: {item['content'][:200]}")


if __name__ == "__main__":
    keyword = input("请输入搜索关键词: ").strip()
    if keyword:
        data = tavily_search(keyword, max_results=5)
        print_results(data)
    else:
        print("关键词不能为空")
