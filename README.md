# AI Research Workbench

基于 **Agent Loop** 自主推理引擎的 AI 研究工作台，支持智能报告生成、文档问答和 PPT 自动创建。LLM 在循环中自主思考、调用工具、观察结果、迭代优化，直至任务完成。

## 功能特性

- **智能报告生成** — 输入主题，Agent 自动搜索网络并生成带引用来源的结构化 Markdown 报告。
- **文档报告** — 上传 PDF/DOCX/TXT 文档，基于文档内容直接生成报告。
- **智能问答** — 粘贴报告内容后自由提问，Agent 自动判断是基于报告回答还是搜索网络补充信息。
- **PPT 生成** — 将报告一键转为精美 PPT。
- **实时流式反馈** — Agent 的思考过程、工具调用和结果通过 SSE 实时推送到前端。
- **多源聚合搜索** — 整合 Exa、Tavily、Bilibili、GitHub、百度、360、搜狗等多个搜索源。

## 系统架构

```
Frontend (React + TypeScript + Ant Design)
        │  SSE Stream + REST API
Backend (FastAPI)
        │
Agent Loop 引擎 (ReAct 模式)
   Think → Act → Observe → 循环...
        │
   ┌────┴────┐
   │  Tools  │  web_search, read_file, write_file,
   │         │  run_code, generate_report, generate_ppt, ask_user
   └────┬────┘
        │
   ┌────┴────────────────────────────┐
   │  Agents（可复用能力层）            │
   │  Search / Document / Report /   │
   │  PPT / TopicAnalysis            │
   └─────────────────────────────────┘
```

### 两条执行路径

1. **标准 Agent Loop（ReAct 模式）** — LLM 自主决定调用哪些工具、以何种顺序执行。适用于开放式研究和问答场景。
2. **文件报告流水线** — 确定性流水线：解析文档 → 生成报告。上传文件时自动走此路径。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18、TypeScript、Ant Design、React Router、React Markdown |
| 后端 | Python 3.10+、FastAPI、asyncio |
| LLM 集成 | OpenAI 兼容 API，支持流式工具调用 |
| 搜索 | Exa、Tavily、Agent Reach（多引擎聚合） |
| 文档解析 | RapidOCR + PP-OCRv6、python-docx、PyPDF2 |
| PPT 生成 | python-pptx、自定义 Skill 管线 |
| 存储 | 本地 JSON / Chroma（向量记忆） |

## 项目结构

```
├── backend/
│   ├── agents/          # Agent 类（Search、Document、Report、PPT、Topic）
│   ├── api/             # FastAPI 路由与端点
│   ├── core/            # Agent Loop 引擎、工具注册、上下文管理、LLM 客户端
│   ├── models/          # Pydantic 模型定义 + PP-OCRv6 ONNX 模型
│   ├── prompts/         # LLM 提示词模板
│   ├── services/        # 业务逻辑（搜索、报告、PPT、文件、存储）
│   ├── tools/           # 工具实现（web_search、file_ops、report_gen 等）
│   └── utils/           # 工具函数
├── frontend/
│   └── src/
│       ├── components/  # 公共 UI 组件
│       ├── hooks/       # 自定义 React Hook
│       ├── pages/       # 报告页、问答页、历史页、日志页、PPT 页
│       ├── services/    # API 客户端（REST + SSE 流）
│       ├── types/       # TypeScript 类型定义
│       └── utils/       # 工具函数
├── skills/              # PPT Skill 管线
├── tests/               # 测试脚本与数据
├── config/              # 配置文件
└── tools/               # 开发工具
```

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+
- LLM API 端点（OpenAI 兼容）

### 一键启动（推荐）

```bash
# 启动（自动创建 venv、安装依赖、启动前后端）
bash run.sh start

# 重启
bash run.sh restart

# 停止
bash run.sh stop

# 查看状态
bash run.sh status
```

> `run.sh` 会自动完成：检测 Python 环境 → 创建虚拟环境 → 安装后端依赖 → 安装前端依赖 → 创建数据目录 → 启动后端(8081) + 前端(3081)

### 手动启动

**后端**

```bash
cd backend
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM API Key 和搜索 API Key

# 启动
python main.py
```

后端默认监听 `http://localhost:8081`。

**前端**

```bash
cd frontend
npm install
npm start
```

前端开发服务器监听 `http://localhost:3081`，API 请求自动适配本地或 GitHub Codespaces 环境。

### GitHub Codespaces

在 Codespaces 上运行时，需将前后端端口设为 Public 可见性：

```bash
gh codespace ports visibility 3081:public -c $CODESPACE_NAME
gh codespace ports visibility 8081:public -c $CODESPACE_NAME
```

### Docker

```bash
docker-compose up -d
```

## 核心 API

| 端点 | 说明 |
|------|------|
| `POST /api/agent-loop/run` | 启动 Agent Loop 任务 |
| `GET /api/agent-loop/{id}/stream` | SSE 实时事件流 |
| `POST /api/agent-loop/{id}/interrupt` | 中断运行中的任务 |
| `POST /api/documents/upload` | 上传文档 |
| `POST /api/reports/export` | 导出报告（MD/PDF/DOCX） |
| `POST /api/ppt/generate` | 生成 PPT |
| `GET /api/history` | 获取对话历史 |
| `GET /api/agent-loop/tools` | 查看可用工具列表 |

## Agent Loop 工作原理

1. **初始化** — 引擎接收目标描述和可用工具集。
2. **思考** — LLM 分析当前上下文，决定下一步行动。
3. **行动** — 引擎并行执行选中的工具（含重试逻辑）。
4. **观察** — 工具结果回填到上下文，供下一轮决策。
5. **终止** — LLM 输出最终结果 / 达到最大轮次 / Token 预算耗尽时结束。

所有事件（思考片段、工具调用、执行结果、任务完成）通过 SSE 实时流式推送到前端。

## License

MIT
