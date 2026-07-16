"""
API测试
"""

import pytest
import asyncio
from httpx import AsyncClient
from backend.main import app


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client():
    """创建测试客户端"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client):
    """测试健康检查接口"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_root(client):
    """测试根路径"""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_generate_report(client):
    """测试生成报告接口"""
    request_data = {
        "topic": "人工智能发展趋势",
        "mode": "ai",
        "format": "markdown"
    }

    response = await client.post("/api/reports/generate", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data


@pytest.mark.asyncio
async def test_search(client):
    """测试搜索接口"""
    request_data = {
        "query": "人工智能",
        "max_results": 5
    }

    response = await client.post("/api/search", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_generate_ppt(client):
    """测试生成PPT接口"""
    request_data = {
        "report_content": "# 测试报告\n\n## 概述\n\n这是一个测试报告。\n\n## 主要内容\n\n- 要点1\n- 要点2\n- 要点3",
        "template": "default",
        "style": "professional"
    }

    response = await client.post("/api/ppt/generate", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_ask_question(client):
    """测试问答接口"""
    request_data = {
        "question": "这个报告的主要内容是什么？",
        "report": "# 测试报告\n\n这是一个关于人工智能的测试报告。主要内容包括AI的发展趋势和应用场景。"
    }

    response = await client.post("/api/reports/ask", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_get_history(client):
    """测试获取历史记录接口"""
    response = await client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_search_memory(client):
    """测试搜索记忆接口"""
    response = await client.get("/api/memory/search", params={"query": "test", "n_results": 5})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
