# CLAUDE.md

给 AI 编程助手使用的项目指南。

## 架构概览

项目以 **Agent Loop** 作为核心执行路径。

### 核心运行时

- `backend/core/agent_loop.py`: 统一循环引擎（ReAct 模式）
- `backend/core/tool_registry.py`: 工具注册与分组管理
- `backend/core/context_manager.py`: 对话上下文、滑动窗口、Token 预算
- `backend/core/llm.py`: LLM 客户端抽象

### API 层

- `backend/api/router.py`: FastAPI 路由（Agent Loop + 报告/PPT/历史等）

### Agent 层

位于 `backend/agents/`:
- `base.py`: `Task`、`TaskType`、`TaskStatus`、`Agent`
- `search.py`: `SearchAgent`
- `document.py`: `DocumentAgent`
- `report.py`: `ReportAgent`
- `ppt.py`: `PPTAgent`
- `topic.py`: `TopicAnalysisAgent`

推荐导入方式:
```python
from agents import SearchAgent, DocumentAgent, ReportAgent, PPTAgent, TopicAnalysisAgent, Task, TaskType
```

### 工具层

位于 `backend/tools/`:
- `web_search.py`、`file_ops.py`、`code_runner.py`、`report_gen.py`、`ppt_gen.py`、`ask_user.py`

### 前端页面

- `ReportPage.tsx`: Agent Loop 报告生成
- `QAPage.tsx`: Agent Loop 智能问答
- `PPTPage.tsx`: PPT 生成
- `HistoryPage.tsx`: 报告存储 + 历史 + 记忆 API
- `LogPage.tsx`: 日志查看

## 核心 API

### Agent Loop
- `POST /api/agent-loop/run` — 启动任务
- `GET /api/agent-loop/{task_id}/stream` — SSE 事件流
- `POST /api/agent-loop/{task_id}/interrupt` — 中断任务
- `GET /api/agent-loop/tools` — 查看工具列表

### 工具类 API
- `POST /api/reports/export`、`POST /api/reports/save`
- `GET /api/reports/list`、`GET /api/reports/{id}`
- `POST /api/ppt/generate`、`GET /api/ppt/templates`
- `POST /api/documents/upload`
- `GET /api/history`、`GET /api/memory/search`

## 开发环境

- 后端端口: `8081`
- 前端开发服务器代理到 `http://localhost:8081`
- 优先代码审查而非本地安装依赖
- 保留完整数据流，不要用切片截断 LLM 输出

## 推荐阅读顺序

1. `frontend/src/pages/ReportPage.tsx`
2. `frontend/src/services/api.ts`
3. `backend/api/router.py`
4. `backend/core/agent_loop.py`
5. `backend/agents/__init__.py`
6. `backend/tools/__init__.py`
