"""
API路由定义
定义所有API端点
支持异步处理：先返回任务ID，后台处理
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks, Body, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import os
from pathlib import Path
import uuid
import json
from datetime import datetime
import asyncio
import logging

from models.schemas import (
    GenerateReportRequest, ModifyReportRequest, AskQuestionRequest,
    GeneratePPTRequest, SearchRequest, AnalyzeDocumentRequest,
    APIResponse, ReportResponse, SearchResponse, PPTResponse,
    HistoryResponse, FileUploadResponse, ReportMode, ReportFormat
)
from models.schemas import AgentLoopRunRequest, AgentLoopRunResponse, AskUserReply, AgentLoopTrace, ToolInfo
from core.auth import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    register_user, login_user, get_current_user,
    user_db
)
from services.report_service import ReportService
from services.ppt_service import PPTService
from services.file_service import FileService
from services.report_storage import report_storage

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["multi-agent"])

# PPT 输出目录：兼容老路径（./data/ppt）和新路径（PROJECT_ROOT/data/ppt）
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_PPT_DIRS = [
    _PROJECT_ROOT / "data" / "ppt",   # 新：ppt_skill_service 写入目录
    Path("./data/ppt"),                # 老：相对工作目录
]


def _get_ppt_dirs() -> list:
    """返回所有存在的 PPT 输出目录（去重）"""
    seen = set()
    dirs = []
    for d in _PPT_DIRS:
        resolved = d.resolve()
        if resolved not in seen and resolved.exists():
            seen.add(resolved)
            dirs.append(resolved)
    return dirs

# 任务存储（内存中）
tasks = {}


def load_tasks():
    """恢复任务状态（从持久化存储加载）"""
    global tasks
    tasks_file = "./data/tasks.json"
    try:
        if os.path.exists(tasks_file):
            with open(tasks_file, 'r', encoding='utf-8') as f:
                saved_tasks = json.load(f)
                tasks.update(saved_tasks)
                logger.info(f"[Router] 从 tasks.json 恢复了 {len(saved_tasks)} 个任务")
        else:
            logger.info("[Router] tasks.json 不存在，任务状态为空")
    except Exception as e:
        logger.error(f"[Router] 恢复任务状态失败: {e}")


def save_tasks():
    """保存任务状态到文件（安全写入：临时文件 + rename 防止损坏）"""
    global tasks
    tasks_file = "./data/tasks.json"
    try:
        os.makedirs("./data", exist_ok=True)
        tmp_file = tasks_file + ".tmp"
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        # 原子替换，防止写入中断导致文件损坏
        if os.path.exists(tasks_file):
            os.replace(tmp_file, tasks_file)
        else:
            os.rename(tmp_file, tasks_file)
    except Exception as e:
        logger.error(f"[Router] 保存任务状态失败: {e}")
        # 清理临时文件
        try:
            if os.path.exists(tasks_file + ".tmp"):
                os.remove(tasks_file + ".tmp")
        except Exception:
            pass


def log_task_input(task_id: str, task_type: str, input_data: dict):
    """记录任务输入（完整输出，不截断）"""
    logger.info(f"[{task_type}任务 {task_id[:8]}] ========== 任务开始 ==========")
    logger.info(f"[{task_type}任务 {task_id[:8]}] 用户输入:")
    for key, value in input_data.items():
        logger.info(f"[{task_type}任务 {task_id[:8]}]   {key}: {value}")


def log_task_output(task_id: str, task_type: str, output_data: dict):
    """记录任务输出（完整输出，不截断）"""
    logger.info(f"[{task_type}任务 {task_id[:8]}] 大模型返回:")
    for key, value in output_data.items():
        if isinstance(value, str):
            # 多行内容逐行输出，便于阅读
            logger.info(f"[{task_type}任务 {task_id[:8]}]   {key}:")
            for line in value.split("\n"):
                logger.info(f"[{task_type}任务 {task_id[:8]}]     {line}")
        else:
            logger.info(f"[{task_type}任务 {task_id[:8]}]   {key}: {value}")
    logger.info(f"[{task_type}任务 {task_id[:8]}] ========== 任务结束 ==========")

# 服务实例
report_service = ReportService()
ppt_service = PPTService()
file_service = FileService()


def init_task(task_id: str):
    """初始化任务状态"""
    tasks[task_id] = {
        "status": "processing",
        "result": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
        "logged": False  # 标记是否已打印过状态
    }


def log_task_if_needed(task_id: str, task_type: str):
    """只在任务完成或失败时打印一次日志"""
    task = tasks.get(task_id)
    if not task or task.get("logged"):
        return

    if task["status"] in ["completed", "failed"]:
        task["logged"] = True
        if task["status"] == "completed":
            logger.info(f"[{task_type}任务 {task_id[:8]}] ✅ 任务完成")
        else:
            logger.error(f"[{task_type}任务 {task_id[:8]}] ❌ 任务失败: {task.get('error', '未知错误')}")


# 认证相关接口
@router.post("/auth/register", response_model=APIResponse)
async def register(user_data: UserCreate):
    """用户注册"""
    try:
        result = register_user(user_data)
        return APIResponse(
            success=True,
            data=result.dict(),
            message="注册成功"
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/login", response_model=APIResponse)
async def login(login_data: UserLogin):
    """用户登录"""
    try:
        result = login_user(login_data)
        return APIResponse(
            success=True,
            data=result.dict(),
            message="登录成功"
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/me", response_model=APIResponse)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """获取当前用户信息"""
    return APIResponse(
        success=True,
        data=current_user.dict(),
        message="获取成功"
    )


@router.get("/auth/users", response_model=APIResponse)
async def list_users(current_user: UserResponse = Depends(get_current_user)):
    """列出所有用户"""
    try:
        users = []
        for username, user_data in user_db.users.items():
            users.append({
                "id": user_data.get("id", username),
                "username": user_data["username"],
                "email": user_data.get("email"),
                "nickname": user_data.get("nickname"),
                "created_at": user_data.get("created_at"),
                "is_active": user_data.get("is_active", True)
            })

        return APIResponse(
            success=True,
            data=users,
            message="获取成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 报告相关接口
@router.post("/reports/generate", response_model=APIResponse)
async def generate_report(request: GenerateReportRequest, background_tasks: BackgroundTasks):
    """生成报告（异步：先返回任务ID，后台处理）"""
    task_id = str(uuid.uuid4())

    # 初始化任务状态
    init_task(task_id)

    # 定义后台任务（async：直接 await，不创建新事件循环）
    async def process_task(task_id: str, request_data: dict):
        start_time = datetime.now()
        log_task_input(task_id, "报告生成", request_data)

        try:
            result = await _run_legacy_request(request_data)

            if result["success"]:
                report_data = result["report"]
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["result"] = {
                    "topic": request_data["topic"],
                    "mode": request_data["mode"],
                    "format": request_data["format"],
                    "content": report_data["content"],
                    "sections": report_data.get("sections", []),
                    "generated_at": datetime.now().isoformat()
                }

                # 记录完整报告内容到日志
                logger.info(f"[报告生成任务 {task_id[:8]}] 报告生成完成，完整内容:")
                logger.info(f"[报告生成任务 {task_id[:8]}] --- 报告开始 ---")
                for line in report_data["content"].split("\n"):
                    logger.info(f"[报告生成任务 {task_id[:8]}] {line}")
                logger.info(f"[报告生成任务 {task_id[:8]}] --- 报告结束 ---")
            else:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = "报告生成失败"
                logger.error(f"[报告生成任务 {task_id[:8]}] 报告生成失败")

        except Exception as e:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)
            logger.error(f"[报告生成任务 {task_id[:8]}] 报告生成异常: {str(e)}")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"[任务 {task_id[:8]}] 处理完成，耗时: {duration:.1f}秒")
        save_tasks()

    # 添加后台任务
    request_data = {
        "action": "generate_report",
        "mode": request.mode.value,
        "topic": request.topic,
        "format": request.format.value,
        "file_path": request.file_path,
        "include_search": request.include_search,
        "additional_requirements": request.additional_requirements,
    }
    if request.date_range:
        request_data["date_range"] = {
            "start": request.date_range.start,
            "end": request.date_range.end,
        }
    background_tasks.add_task(process_task, task_id, request_data)

    logger.info(f"[任务 {task_id[:8]}] 任务已提交")
    # 立即返回任务ID
    return APIResponse(
        success=True,
        data={"task_id": task_id},
        message="任务已提交，正在处理中"
    )


@router.post("/reports/generate/stream")
async def generate_report_stream(request: GenerateReportRequest):
    """流式生成报告（SSE）— 已迁移到 Agent Loop 引擎"""
    import json as _json

    async def event_generator():
        import time as _time
        t_start = _time.time()
        engine = _get_agent_loop_engine()
        mode = request.mode.value
        topic = request.topic
        logger.info(f"[报告流式] 开始生成 | 主题: {topic} | 模式: {mode}")

        # 构建 Agent Loop 目标
        goal = f"Generate a research report on '{topic}'. Mode: {mode}."
        if request.file_path:
            goal += f" Read file: {request.file_path}"
        if request.additional_requirements:
            goal += f" Requirements: {request.additional_requirements}"

        yield f"data: {_json.dumps({'type': 'status', 'content': 'Agent Loop '}, ensure_ascii=False)}\n\n"

        import uuid
        task_id = str(uuid.uuid4())[:8]
        full_content = ""

        try:
            async for event in engine.run(goal=goal, task_id=task_id, tool_group="report"):
                if event.type == "think_chunk" and event.content:
                    full_content += event.content
                    yield f"data: {_json.dumps({'type': 'chunk', 'content': event.content}, ensure_ascii=False)}\n\n"
                elif event.type == "tool_call":
                    yield f"data: {_json.dumps({'type': 'status', 'content': f'{event.tool}...'}, ensure_ascii=False)}\n\n"

            elapsed = round(_time.time() - t_start, 2)
            logger.info(f"[报告流式] 生成完成 | 总字符: {len(full_content)} | 耗时: {elapsed}s")
            yield f"data: {_json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            elapsed = round(_time.time() - t_start, 2)
            logger.error(f"[报告流式] 生成失败 | 耗时: {elapsed}s | 错误: {e}")
            yield f"data: {_json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/reports/task/{task_id}", response_model=APIResponse)
async def get_task_status(task_id: str):
    """查询任务状态（不打印日志，减少轮询噪音）"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task["status"] == "completed":
        return APIResponse(
            success=True,
            data={
                "status": "completed",
                "result": task["result"]
            },
            message="任务已完成"
        )
    elif task["status"] == "failed":
        return APIResponse(
            success=False,
            data={"status": "failed"},
            error=task["error"],
            message="任务失败"
        )
    else:
        return APIResponse(
            success=True,
            data={"status": "processing"},
            message="任务处理中"
        )


@router.post("/reports/modify", response_model=APIResponse)
async def modify_report(request: ModifyReportRequest, background_tasks: BackgroundTasks):
    """修改报告（异步：先返回任务ID，后台处理）"""
    task_id = str(uuid.uuid4())

    # 初始化任务状态
    init_task(task_id)

    # 定义后台任务（async：直接 await，不创建新事件循环）
    async def process_modify_task(task_id: str, request_data: dict):
        start_time = datetime.now()
        log_task_input(task_id, "修改", request_data)

        try:
            result = await _run_legacy_request(request_data)

            if result["success"]:
                report_data = result["report"]
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["result"] = {
                    "content": report_data["content"],
                    "sections": report_data.get("sections", [])
                }
                log_task_output(task_id, "修改", {"修改后内容": report_data["content"]})
            else:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = "报告修改失败"
                logger.error(f"[修改任务 {task_id[:8]}] 报告修改失败")

        except Exception as e:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)
            logger.error(f"[修改任务 {task_id[:8]}] 报告修改异常: {str(e)}")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"[修改任务 {task_id[:8]}] 处理完成，耗时: {duration:.1f}秒")
        save_tasks()

    # 添加后台任务
    background_tasks.add_task(
        process_modify_task,
        task_id,
        {
            "action": "modify_report",
            "report": request.report,
            "modifications": request.modifications,
            "format": request.format.value,
            "search_context": request.search_context,
        }
    )

    logger.info(f"[修改任务 {task_id[:8]}] 任务已提交")
    return APIResponse(
        success=True,
        data={"task_id": task_id},
        message="报告修改任务已提交，正在处理中"
    )


@router.get("/reports/modify/task/{task_id}", response_model=APIResponse)
async def get_modify_task_status(task_id: str):
    """查询报告修改任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task["status"] == "completed":
        return APIResponse(
            success=True,
            data={
                "status": "completed",
                "result": task["result"]
            },
            message="报告修改任务已完成"
        )
    elif task["status"] == "failed":
        return APIResponse(
            success=False,
            data={"status": "failed"},
            error=task["error"],
            message="报告修改任务失败"
        )
    else:
        return APIResponse(
            success=True,
            data={"status": "processing"},
            message="报告修改任务处理中"
        )


@router.post("/reports/ask", response_model=APIResponse)
async def ask_question(request: AskQuestionRequest, background_tasks: BackgroundTasks):
    """基于报告提问（异步：先返回任务ID，后台处理）"""
    task_id = str(uuid.uuid4())

    # 初始化任务状态
    init_task(task_id)

    # 定义后台任务（async：直接 await，不创建新事件循环）
    async def process_ask_task(task_id: str, request_data: dict):
        start_time = datetime.now()
        log_task_input(task_id, "问答", request_data)

        try:
            result = await _run_legacy_request(request_data)

            if result["success"]:
                # 保存问答历史到本地文件（按 session_id 分组）
                qa_history_file = "./data/qa_history.json"
                os.makedirs("./data", exist_ok=True)

                qa_history = []
                if os.path.exists(qa_history_file):
                    with open(qa_history_file, 'r', encoding='utf-8') as f:
                        qa_history = json.load(f)

                session_id = request_data.get("session_id", "")

                # 查找是否已有同 session 的记录
                existing = None
                for item in qa_history:
                    if item.get("session_id") == session_id and session_id:
                        existing = item
                        break

                if existing:
                    # 追加到已有对话
                    existing["messages"].append({
                        "role": "user",
                        "content": result["question"]
                    })
                    existing["messages"].append({
                        "role": "assistant",
                        "content": result["answer"]
                    })
                    existing["timestamp"] = datetime.now().isoformat()
                else:
                    # 新建对话记录
                    report_content = request_data.get("report", "")
                    qa_history.append({
                        "id": str(uuid.uuid4()),
                        "session_id": session_id or str(uuid.uuid4()),
                        "report_topic": report_content if report_content else None,
                        "report_content": report_content,
                        "messages": [
                            {"role": "user", "content": result["question"]},
                            {"role": "assistant", "content": result["answer"]}
                        ],
                        "timestamp": datetime.now().isoformat()
                    })

                # 只保留最近50个对话
                qa_history = qa_history[-50:]

                with open(qa_history_file, 'w', encoding='utf-8') as f:
                    json.dump(qa_history, f, ensure_ascii=False, indent=2)

                tasks[task_id]["status"] = "completed"
                tasks[task_id]["result"] = {
                    "question": result["question"],
                    "answer": result["answer"]
                }
                log_task_output(task_id, "问答", {"回答": result["answer"]})
            else:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = "回答生成失败"
                logger.error(f"[问答任务 {task_id[:8]}] 回答生成失败")

        except Exception as e:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)
            logger.error(f"[问答任务 {task_id[:8]}] 回答生成异常: {str(e)}")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"[问答任务 {task_id[:8]}] 处理完成，耗时: {duration:.1f}秒")
        save_tasks()

    # 添加后台任务
    background_tasks.add_task(
        process_ask_task,
        task_id,
        {
            "action": "ask_question",
            "question": request.question,
            "report": request.report,
            "session_id": request.session_id or "",
            "messages": request.messages or []
        }
    )

    logger.info(f"[问答任务 {task_id[:8]}] 任务已提交")
    return APIResponse(
        success=True,
        data={"task_id": task_id},
        message="问答任务已提交，正在处理中"
    )


@router.get("/reports/ask/task/{task_id}", response_model=APIResponse)
async def get_ask_task_status(task_id: str):
    """查询问答任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task["status"] == "completed":
        return APIResponse(
            success=True,
            data={
                "status": "completed",
                "result": task["result"]
            },
            message="问答任务已完成"
        )
    elif task["status"] == "failed":
        return APIResponse(
            success=False,
            data={"status": "failed"},
            error=task["error"],
            message="问答任务失败"
        )
    else:
        return APIResponse(
            success=True,
            data={"status": "processing"},
            message="问答任务处理中"
        )


@router.post("/reports/ask/stream")
async def ask_question_stream(request: AskQuestionRequest):
    """流式问答（SSE）"""
    import json as _json

    async def event_generator():
        import time as _time
        t_start = _time.time()
        llm = _get_default_llm()
        full_answer = ""  # ?????????????????????


        question = request.question
        report = request.report or ""
        messages_history = request.messages or []
        logger.info(f"[QA流式] 开始 | 问题: {question[:50]}")

        # 多轮上下文
        history_text = ""
        if messages_history:
            recent = messages_history[-6:]
            history_text = "\n".join([
                f"{'用户' if m.get('role') == 'user' else 'AI'}：{m.get('content', '')}"
                for m in recent
            ])
            history_text = f"\n\n对话历史：\n{history_text}\n"

        # ========== 优化：分类与搜索并行执行 ==========
        import asyncio

        # 分类 prompt（完整报告，不截断）
        classify_prompt = f"""你是智能问答助手。请判断以下报告内容是否足以完整回答用户的问题。

判断规则：
1. 如果报告内容包含了回答问题所需的所有信息 → 回答"能"
2. 如果问题涉及报告中没有提到的实体、话题或领域 → 回答"不能"
3. 如果问题部分与报告相关，但需要补充报告之外的信息才能完整回答 → 回答"不能"

报告内容：
{report}

用户问题：{question}

请只回答"能"或"不能"，不要解释。"""

        # 并行启动分类和搜索，搜索提前开始以隐藏延迟
        async def _do_search():
            search_queries = await _generate_search_queries(question)
            return await _multi_search(search_queries, num_results=3)

        search_task = asyncio.create_task(_do_search())
        classify_answer = await llm.generate_text_fast(classify_prompt)
        need_search = "不能" in classify_answer[:10]
        logger.info(f"[QA流式] 分类结果: {classify_answer[:20].strip()} | 需要搜索: {need_search}")

        # 准备报告回答的 prompt
        report_prompt = f"""你是智能问答助手。请基于以下报告内容回答用户的问题。

重要规则：
- 如果报告内容足以回答问题，直接回答即可，不需要标注任何来源
- 如果报告内容不足以完整回答问题，请在回答中明确说明"报告中未涉及以下内容"，然后基于你的知识补充回答
{history_text}
报告内容：
{report}

用户问题：{question}

请回答："""

        if not need_search:
            search_task.cancel()
            # 报告足够，直接流式输出（不搜索，最快）
            logger.info(f"[QA流式] 基于报告回答 | 问题: {question[:30]}")
            chunk_count = 0
            full_answer = ""
            async for chunk in llm.generate_text_fast_stream(report_prompt):
                chunk_count += 1
                full_answer += chunk
                yield f"data: {_json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
            elapsed = round(_time.time() - t_start, 2)
            logger.info(f"[QA流式] 回答完成 | chunks: {chunk_count} | 耗时: {elapsed}s | 来源: 报告")
            logger.info(f"[QA流式] 回答内容:\n{full_answer}")
            yield f"data: {_json.dumps({'type': 'done', 'sources': ['报告']}, ensure_ascii=False)}\n\n"
            return

        # 报告不足，等待搜索结果（已在后台运行）
        logger.info(f"[QA流式] 报告不足，等待搜索结果 | 问题: {question[:30]}")
        yield f"data: {_json.dumps({'type': 'status', 'content': '🔍 报告内容不足，正在搜索补充...'}, ensure_ascii=False)}\n\n"

        search_results = []
        try:
            search_results = await search_task
            # 过滤：空内容 + 与问题关键词相关性
            import re as _re
            # 提取中文词（2字以上）和英文词作为关键词
            chinese_words = _re.findall(r'[一-鿿]{2,}', question)
            english_words = _re.findall(r'[a-zA-Z]{2,}', question)
            question_words = set(chinese_words + english_words)
            filtered_results = []
            for r in search_results:
                if not r.get("snippet", "").strip() or not r.get("url", "").strip():
                    continue
                if not question_words:
                    # 无法提取关键词，不过滤
                    filtered_results.append(r)
                    continue
                text = (r.get("title", "") + r.get("snippet", "")).lower()
                if any(w.lower() in text for w in question_words):
                    filtered_results.append(r)
            search_results = filtered_results[:3]
            logger.info(f"[QA流式] 搜索完成 | 结果: {len(search_results)} 条 | 来源: {[r.get('source') for r in search_results]}")
        except Exception as e:
            logger.warning(f"[QA流式] 搜索失败: {e}")

        # 有搜索结果 → 综合回答；无结果 → 仅基于报告回答
        if search_results:
            sources = list(set(r.get("source", "") for r in search_results))
            search_context = "\n\n".join([
                f"【{r.get('source', '')}】{r.get('title', '')}\n链接: {r.get('url', '')}\n{r.get('snippet', '')}"
                for r in search_results
            ])

            combined_prompt = f"""你是智能问答助手。请综合以下信息回答用户的问题。

重要规则：
- 只回答用户的问题，不要回答用户没问的内容
- 正文中不要标注 [来源：xxx]，直接给出回答内容即可
- 在回答末尾添加"## 参考来源"章节，列出你参考过的搜索结果链接，格式为：
  1. **标题** — [查看原文](链接地址)
  2. **标题** — [查看原文](链接地址)
  注意：只使用搜索结果中提供的原始链接，严禁编造任何 URL。不要重复相同的链接，每个链接只出现一次
- 如果报告和搜索结果有冲突，以搜索结果为准
- 回答要简洁、直接，不要添加无关的延伸内容
- 如果搜索结果与问题无关，忽略它们，直接基于报告和你的知识回答
- 使用清晰的排版：要点用列表，对比用表格，避免大段文字

报告内容：
{report if report else '无'}

网络搜索结果（可能部分与问题无关，请自行筛选）：
{search_context}

用户问题：{question}

请综合以上信息，给出简洁、准确的回答："""

            # 流式输出搜索补充的回答
            logger.info(f"[QA流式] 流式输出搜索补充回答 | 来源: {sources}")
            chunk_count = 0
            full_answer = ""
            async for chunk in llm.generate_text_fast_stream(combined_prompt):
                chunk_count += 1
                full_answer += chunk
                yield f"data: {_json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
            elapsed = round(_time.time() - t_start, 2)
            logger.info(f"[QA流式] 回答完成 | chunks: {chunk_count} | 耗时: {elapsed}s | 来源: {sources}")
            logger.info(f"[QA流式] 回答内容:\n{full_answer}")
            yield f"data: {_json.dumps({'type': 'done', 'sources': sources}, ensure_ascii=False)}\n\n"
        else:
            # 搜索无结果，流式输出原始回答
            logger.info(f"[QA流式] 搜索无结果，基于报告回答")
            chunk_count = 0
            full_answer = ""
            async for chunk in llm.generate_text_fast_stream(report_prompt):
                chunk_count += 1
                full_answer += chunk
                yield f"data: {_json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
            elapsed = round(_time.time() - t_start, 2)
            logger.info(f"[QA流式] 回答完成 | chunks: {chunk_count} | 耗时: {elapsed}s | 来源: 报告")
            logger.info(f"[QA流式] 回答内容:\n{full_answer}")
            yield f"data: {_json.dumps({'type': 'done', 'sources': ['报告']}, ensure_ascii=False)}\n\n"

        # 保存历史
        try:
            qa_history_file = "./data/qa_history.json"
            os.makedirs("./data", exist_ok=True)
            qa_history = []
            if os.path.exists(qa_history_file):
                with open(qa_history_file, 'r', encoding='utf-8') as f:
                    qa_history = _json.load(f)

            session_id = request.session_id or ""
            existing = None
            for item in qa_history:
                if item.get("session_id") == session_id and session_id:
                    existing = item
                    break

            final_answer = full_answer  # 用流式回答保存
            if existing:
                existing["messages"].append({"role": "user", "content": question})
                existing["messages"].append({"role": "assistant", "content": final_answer})
                existing["timestamp"] = datetime.now().isoformat()
            else:
                qa_history.append({
                    "id": str(uuid.uuid4()),
                    "session_id": session_id or str(uuid.uuid4()),
                    "report_topic": report if report else None,
                    "report_content": report,
                    "messages": [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": final_answer}
                    ],
                    "timestamp": datetime.now().isoformat()
                })
            qa_history = qa_history[-50:]
            with open(qa_history_file, 'w', encoding='utf-8') as f:
                _json.dump(qa_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[QA流式] 保存历史失败: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/reports/export", response_model=APIResponse)
async def export_report(
    content: str = Body(...),
    format: ReportFormat = Body(default=ReportFormat.MARKDOWN),
    filename: Optional[str] = Body(default=None)
):
    """导出报告"""
    try:
        if not filename:
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        file_path = await report_service.export_report(content, format, filename)

        # format.value 是 "markdown"/"word"/"pdf"，但实际文件扩展名是 "md"/"docx"/"pdf"
        EXT_MAP = {"markdown": "md", "word": "docx", "pdf": "pdf"}
        real_ext = EXT_MAP.get(format.value, format.value)

        return APIResponse(
            success=True,
            data={
                "file_path": file_path,
                "filename": f"{filename}.{real_ext}",
                "format": format.value
            },
            message="报告导出成功"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/download/{filename}")
async def download_report(filename: str):
    """下载报告文件"""
    # 防止路径遍历攻击
    safe_name = os.path.basename(filename)
    file_path = os.path.join("./data/exports", safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type="application/octet-stream"
    )


@router.post("/ppt/generate", response_model=APIResponse)
async def generate_ppt(request: GeneratePPTRequest, background_tasks: BackgroundTasks):
    """生成PPT（异步：先返回任务ID，后台处理）"""
    task_id = str(uuid.uuid4())

    # 初始化任务状态
    init_task(task_id)

    # 定义后台任务（async：直接 await，不创建新事件循环）
    async def process_ppt_task(task_id: str, request_data: dict):
        start_time = datetime.now()
        log_task_input(task_id, "PPT", request_data)

        try:
            result = await _run_legacy_request(request_data)

            if result["success"]:
                ppt_data = result["ppt"]

                # PPTAgent V2 已直接生成 PPTX 文件
                pptx_path = ppt_data.get("pptx_path", "")

                # 下载链接只使用文件名（相对于 ./data/ppt/）
                download_filename = ""
                if pptx_path:
                    download_filename = os.path.basename(pptx_path)

                tasks[task_id]["status"] = "completed"
                tasks[task_id]["result"] = {
                    "pptx_path": pptx_path,
                    "template": ppt_data.get("template", request_data.get("template", "default")),
                    "style": ppt_data.get("style", request_data.get("style", "professional")),
                    "download_url": f"/api/ppt/download/{download_filename}" if download_filename else ""
                }
                log_task_output(task_id, "PPT", {"PPTX": pptx_path, "下载链接": f"/api/ppt/download/{download_filename}" if download_filename else ""})
            else:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = "PPT生成失败"
                logger.error(f"[PPT任务 {task_id[:8]}] PPT生成失败")

        except Exception as e:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)
            logger.error(f"[PPT任务 {task_id[:8]}] PPT生成异常: {str(e)}")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"[PPT任务 {task_id[:8]}] 处理完成，耗时: {duration:.1f}秒")
        save_tasks()

    # 添加后台任务
    background_tasks.add_task(
        process_ppt_task,
        task_id,
        {
            "action": "generate_ppt",
            "report_content": request.report_content,
            "template": request.template,
            "style": request.style.value,
            "options": request.options.model_dump() if request.options else {}
        }
    )

    logger.info(f"[PPT任务 {task_id[:8]}] 任务已提交")
    return APIResponse(
        success=True,
        data={"task_id": task_id},
        message="PPT生成任务已提交，正在处理中"
    )


@router.get("/ppt/task/{task_id}", response_model=APIResponse)
async def get_ppt_task_status(task_id: str):
    """查询PPT生成任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task["status"] == "completed":
        return APIResponse(
            success=True,
            data={
                "status": "completed",
                "result": task["result"]
            },
            message="PPT生成任务已完成"
        )
    elif task["status"] == "failed":
        return APIResponse(
            success=False,
            data={"status": "failed"},
            error=task["error"],
            message="PPT生成任务失败"
        )
    else:
        return APIResponse(
            success=True,
            data={"status": "processing"},
            message="PPT生成任务处理中"
        )


@router.get("/ppt/templates", response_model=APIResponse)
async def list_ppt_templates():
    """获取可用的PPT模板列表"""
    try:
        templates = await ppt_service.list_templates()
        return APIResponse(
            success=True,
            data=templates,
            message="获取模板列表成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ppt/list", response_model=APIResponse)
async def list_generated_ppt():
    """获取已生成的PPT列表"""
    ppt_dirs = _get_ppt_dirs()
    if not ppt_dirs:
        return APIResponse(success=True, data={"files": [], "total": 0})

    seen_filenames = set()
    files = []
    for ppt_dir in ppt_dirs:
        for f in os.listdir(ppt_dir):
            if f.endswith(".pptx") and not f.startswith("~$") and f not in seen_filenames:
                seen_filenames.add(f)
                file_path = os.path.join(ppt_dir, f)
                stat = os.stat(file_path)
                files.append({
                    "filename": f,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "download_url": f"/api/ppt/download/{f}"
                })

    # 按修改时间倒序排列
    files.sort(key=lambda x: x["created_at"], reverse=True)

    return APIResponse(
        success=True,
        data={"files": files, "total": len(files)}
    )


@router.get("/ppt/download/{filename:path}")
async def download_ppt(filename: str):
    """下载PPT文件"""
    # 安全检查：拒绝空文件名和目录路径
    if not filename or not filename.strip():
        raise HTTPException(status_code=404, detail="文件名不能为空")

    # 在所有 PPT 目录中查找文件
    file_path = None
    for ppt_dir in _get_ppt_dirs():
        candidate = ppt_dir / filename
        if candidate.exists() and candidate.is_file():
            file_path = str(candidate)
            break
    if not file_path:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 用于下载的文件名（只取最后一段）
    download_name = os.path.basename(filename)

    return FileResponse(
        path=file_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )


@router.post("/search", response_model=APIResponse)
async def search(request: SearchRequest, background_tasks: BackgroundTasks):
    """网络搜索（异步：先返回任务ID，后台处理）"""
    task_id = str(uuid.uuid4())

    # 初始化任务状态
    init_task(task_id)

    # 定义后台任务（async：直接 await，不创建新事件循环）
    async def process_search_task(task_id: str, request_data: dict):
        start_time = datetime.now()
        log_task_input(task_id, "搜索", request_data)

        try:
            result = await _run_legacy_request(request_data)

            if result["success"]:
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["result"] = result["search_results"]
                log_task_output(task_id, "搜索", {
                    "结果数量": len(result['search_results'].get('results', [])),
                    "搜索结果": result["search_results"]
                })
            else:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = "搜索失败"
                logger.error(f"[搜索任务 {task_id[:8]}] 搜索失败")

        except Exception as e:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)
            logger.error(f"[搜索任务 {task_id[:8]}] 搜索异常: {str(e)}")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"[搜索任务 {task_id[:8]}] 处理完成，耗时: {duration:.1f}秒")
        save_tasks()

    # 添加后台任务
    background_tasks.add_task(
        process_search_task,
        task_id,
        {
            "action": "search",
            "query": request.query,
            "max_results": request.max_results
        }
    )

    logger.info(f"[搜索任务 {task_id[:8]}] 任务已提交")
    # 立即返回任务ID
    return APIResponse(
        success=True,
        data={"task_id": task_id},
        message="搜索任务已提交，正在处理中"
    )


@router.get("/search/task/{task_id}", response_model=APIResponse)
async def get_search_task_status(task_id: str):
    """查询搜索任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task["status"] == "completed":
        return APIResponse(
            success=True,
            data={
                "status": "completed",
                "result": task["result"]
            },
            message="搜索任务已完成"
        )
    elif task["status"] == "failed":
        return APIResponse(
            success=False,
            data={"status": "failed"},
            error=task["error"],
            message="搜索任务失败"
        )
    else:
        return APIResponse(
            success=True,
            data={"status": "processing"},
            message="搜索任务处理中"
        )


@router.post("/documents/upload", response_model=APIResponse)
async def upload_document(file: UploadFile = File(...)):
    """上传文档"""
    try:
        # 验证文件类型
        allowed_types = [".pdf", ".docx", ".doc", ".txt", ".md"]
        file_ext = os.path.splitext(file.filename)[1].lower()

        if file_ext not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {file_ext}，支持的类型: {', '.join(allowed_types)}"
            )

        # 保存文件
        file_path = await file_service.save_upload_file(file)
        # 读取文件内容用于日志
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            content_preview = file_content[:500] + ("..." if len(file_content) > 500 else "")
        except Exception:
            content_preview = "(二进制文件，无法预览)"
        logger.info(f"[上传] 文件名: {file.filename} | 大小: {file.size} 字节 | 路径: {file_path}")
        logger.info(f"[上传] 文件内容预览:\n{content_preview}")

        return APIResponse(
            success=True,
            data=FileUploadResponse(
                file_path=file_path,
                file_name=file.filename,
                file_size=file.size,
                file_type=file_ext
            ),
            message="文件上传成功"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/analyze", response_model=APIResponse)
async def analyze_document(request: AnalyzeDocumentRequest, background_tasks: BackgroundTasks):
    """分析文档（异步：先返回任务ID，后台处理）"""
    task_id = str(uuid.uuid4())

    # 初始化任务状态
    init_task(task_id)

    # 定义后台任务（async：直接 await，不创建新事件循环）
    async def process_analyze_task(task_id: str, request_data: dict):
        start_time = datetime.now()
        log_task_input(task_id, "分析", request_data)

        try:
            result = await _run_legacy_request(request_data)

            if result["success"]:
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["result"] = result["analysis"]
                log_task_output(task_id, "分析", {"分析结果": result["analysis"]})
            else:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = "文档分析失败"
                logger.error(f"[分析任务 {task_id[:8]}] 文档分析失败")

        except Exception as e:
            import traceback
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)
            logger.error(f"[分析任务 {task_id[:8]}] 文档分析异常: {str(e)}")
            logger.error(f"[分析任务 {task_id[:8]}] 堆栈:\n{traceback.format_exc()}")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"[分析任务 {task_id[:8]}] 处理完成，耗时: {duration:.1f}秒")
        save_tasks()

    # 添加后台任务
    background_tasks.add_task(
        process_analyze_task,
        task_id,
        {
            "action": "analyze_document",
            "file_path": request.file_path,
            "file_type": request.file_type,
            "analyze_action": request.action
        }
    )

    logger.info(f"[分析任务 {task_id[:8]}] 任务已提交")
    return APIResponse(
        success=True,
        data={"task_id": task_id},
        message="文档分析任务已提交，正在处理中"
    )


@router.get("/documents/analyze/task/{task_id}", response_model=APIResponse)
async def get_analyze_task_status(task_id: str):
    """查询文档分析任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task["status"] == "completed":
        return APIResponse(
            success=True,
            data={
                "status": "completed",
                "result": task["result"]
            },
            message="文档分析任务已完成"
        )
    elif task["status"] == "failed":
        return APIResponse(
            success=False,
            data={"status": "failed"},
            error=task["error"],
            message="文档分析任务失败"
        )
    else:
        return APIResponse(
            success=True,
            data={"status": "processing"},
            message="文档分析任务处理中"
        )


@router.get("/history", response_model=APIResponse)
async def get_history(limit: Optional[int] = None):
    """获取历史记录"""
    try:
        history = _get_default_memory_manager().conversation_memory.get_history(limit)

        # 从本地存储读取问答历史
        qa_history_file = "./data/qa_history.json"
        qa_history = []
        if os.path.exists(qa_history_file):
            with open(qa_history_file, 'r', encoding='utf-8') as f:
                qa_history = json.load(f)

        # 按时间倒序排列，最新的在前
        qa_history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return APIResponse(
            success=True,
            data=HistoryResponse(
                conversations=history,
                qa_history=qa_history[:50],  # 最近50条
                total=len(history) + len(qa_history)
            ),
            message="获取历史记录成功"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history/save-qa", response_model=APIResponse)
async def save_qa_history(request: Request):
    """保存问答历史（Agent Loop 路径使用）"""
    try:
        body = await request.json()
        question = body.get("question", "")
        answer = body.get("answer", "")
        report_content = body.get("report_content", "")
        session_id = body.get("session_id", "")

        qa_history_file = "./data/qa_history.json"
        os.makedirs("./data", exist_ok=True)
        qa_history = []
        if os.path.exists(qa_history_file):
            with open(qa_history_file, 'r', encoding='utf-8') as f:
                qa_history = json.load(f)

        # 查找是否已有同 session 的记录
        existing = None
        if session_id:
            for item in qa_history:
                if item.get("session_id") == session_id:
                    existing = item
                    break

        if existing:
            msgs = existing["messages"]
            # 避免重复添加：只追加尚未存在的消息
            if question and not (msgs and msgs[-1].get("role") == "user" and msgs[-1].get("content") == question):
                msgs.append({"role": "user", "content": question})
            if answer and not (msgs and msgs[-1].get("role") == "assistant" and msgs[-1].get("content") == answer):
                msgs.append({"role": "assistant", "content": answer})
            existing["timestamp"] = datetime.now().isoformat()
        else:
            messages = []
            if question:
                messages.append({"role": "user", "content": question})
            if answer:
                messages.append({"role": "assistant", "content": answer})
            qa_history.append({
                "id": str(uuid.uuid4()),
                "session_id": session_id or str(uuid.uuid4()),
                "report_topic": report_content[:100] if report_content else None,
                "report_content": report_content,
                "messages": messages,
                "timestamp": datetime.now().isoformat()
            })

        qa_history = qa_history[-50:]
        with open(qa_history_file, 'w', encoding='utf-8') as f:
            json.dump(qa_history, f, ensure_ascii=False, indent=2)

        return APIResponse(success=True, message="保存问答历史成功")
    except Exception as e:
        logger.warning(f"[QA历史] 保存失败: {e}")
        return APIResponse(success=False, message=f"保存失败: {str(e)}")


@router.get("/memory/search", response_model=APIResponse)
async def search_memory(query: str, n_results: int = 5):
    """搜索记忆"""
    try:
        memory_manager = _get_default_memory_manager()
        memories = memory_manager.search_memory(query, n_results)
        results = [
            {
                "id": m.id,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "importance": m.importance,
            }
            for m in memories
        ]

        return APIResponse(
            success=True,
            data=results,
            message="记忆搜索完成"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/save", response_model=APIResponse)
async def save_memory():
    """保存记忆"""
    try:
        _get_default_memory_manager().save_state()

        return APIResponse(
            success=True,
            message="记忆保存成功"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# 报告存储相关接口
class SaveReportRequest(BaseModel):
    topic: str
    content: str
    format: str = "markdown"
    mode: str = "ai"


@router.post("/reports/save", response_model=APIResponse)
async def save_report(request: SaveReportRequest):
    """保存报告到本地存储"""
    try:
        report_id = await report_storage.save_report(
            topic=request.topic,
            content=request.content,
            format=request.format,
            mode=request.mode
        )
        return APIResponse(
            success=True,
            data={"report_id": report_id},
            message="报告保存成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/list", response_model=APIResponse)
async def list_reports(limit: int = 50, offset: int = 0):
    """列出所有报告"""
    try:
        reports = await report_storage.list_reports(limit=limit, offset=offset)
        return APIResponse(
            success=True,
            data=reports,
            message="获取报告列表成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}", response_model=APIResponse)
async def get_report(report_id: str):
    """获取报告详情"""
    try:
        report = await report_storage.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="报告不存在")

        return APIResponse(
            success=True,
            data=report,
            message="获取报告成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/reports/{report_id}", response_model=APIResponse)
async def delete_report(report_id: str):
    """删除报告"""
    try:
        success = await report_storage.delete_report(report_id)
        if not success:
            raise HTTPException(status_code=404, detail="报告不存在")

        return APIResponse(
            success=True,
            message="报告删除成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 日志相关接口 ====================

@router.get("/logs", response_model=APIResponse)
async def get_logs(lines: int = 200, log_type: str = "backend"):
    """获取日志内容"""
    try:
        # 确定日志文件路径
        project_root = Path(__file__).parent.parent.parent
        if log_type == "backend":
            log_file = project_root / "backend.log"
        elif log_type == "frontend":
            log_file = project_root / "frontend.log"
        else:
            raise HTTPException(status_code=400, detail="log_type 必须是 backend 或 frontend")

        # 如果文件不存在，尝试其他路径
        if not log_file.exists():
            # 尝试相对于工作目录的路径
            alt_log_file = Path("./backend.log") if log_type == "backend" else Path("./frontend.log")
            if alt_log_file.exists():
                log_file = alt_log_file
            else:
                return APIResponse(
                    success=True,
                    data={"lines": [], "file": str(log_file), "exists": False},
                    message="日志文件不存在"
                )

        # 读取最后 N 行
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            # 去掉换行符
            last_lines = [line.rstrip('\n') for line in last_lines]

        return APIResponse(
            success=True,
            data={
                "lines": last_lines,
                "file": str(log_file),
                "total_lines": len(all_lines),
                "showing": len(last_lines)
            },
            message="获取日志成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Agent Loop migration
# ============================================================

_agent_loop_engine = None
_tools_registered = False


def _get_agent_loop_engine():
    global _agent_loop_engine, _tools_registered
    if _agent_loop_engine is None:
        from core.agent_loop import engine
        _agent_loop_engine = engine
    if not _tools_registered:
        from tools import register_all_tools
        register_all_tools()
        _tools_registered = True
    return _agent_loop_engine


def _get_default_user_id() -> str:
    return "default_user"


def _get_default_llm():
    from core.llm import get_llm
    return get_llm()


def _get_default_memory_manager():
    from core.memory import get_memory_manager
    return get_memory_manager(_get_default_user_id())


async def _run_agent_loop_goal(goal: str, tool_group: str, max_loops: int = 20) -> str:
    engine = _get_agent_loop_engine()
    task_id = str(uuid.uuid4())[:8]
    final_result = ""
    tool_results = []  # 收集所有工具返回值（如 PPTX 路径）
    engine.tool_registry.set_task_context(task_id)
    engine.tool_registry._no_interactive = True
    try:
        async for event in engine.run(
            goal=goal,
            task_id=task_id,
            tool_group=tool_group,
            max_loops=max_loops,
        ):
            if event.type == "done" and event.result:
                final_result = event.result
            elif event.type == "think_chunk" and event.content:
                final_result += event.content
            elif event.type == "tool_call" and event.tool_output:
                tool_results.append(event.tool_output)
    finally:
        engine.tool_registry.clear_task_context()
        engine.tool_registry._no_interactive = False
    # 把工具返回值追加到结果末尾，确保 _extract_pptx_path 能找到文件路径
    if tool_results:
        final_result = final_result + "\n\n" + "\n".join(tool_results)
    return final_result or "Task completed"


def _extract_pptx_path(result_text: str) -> str:
    if not result_text:
        return ""

    try:
        parsed = json.loads(result_text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        pptx_path = parsed.get("pptx_path", "")
        if isinstance(pptx_path, str):
            return pptx_path

    import re as _re
    match = _re.search(r'(/\S+\.pptx)', result_text)
    return match.group(1) if match else ""


async def _run_legacy_request(request: dict) -> dict:
    action = request.get("action", "")

    if action == "generate_report":
        mode = request.get("mode", "ai")
        topic = request.get("topic", "")
        file_path = request.get("file_path", "")
        if file_path and mode == "document":
            # 文档模式：直接读文件内容生成报告，不要搜索
            goal = (
                f"使用 read_file 工具读取文件 {file_path}，"
                f"然后严格基于文件内容生成一份关于「{topic}」的详细报告。"
                f"重要：只使用文件内容，不要调用 web_search 搜索互联网。"
            )
        elif file_path:
            # 有文件但需要补充搜索：先读文件，再搜索补充
            goal = (
                f"首先使用 read_file 工具读取文件 {file_path}，"
                f"然后基于文件内容，搜索补充信息，生成关于「{topic}」的详细报告。\n\n"
                f"工作流程：先读取文件，再搜索补充信息，然后生成报告。"
            )
        else:
            goal = (
                f"请搜索并生成关于「{topic}」的详细报告。\n\n"
                f"工作流程：先搜索信息，然后生成报告。"
                f"对生成的报告质量不满意可以再次搜索并重新生成。"
            )
        if request.get("additional_requirements"):
            goal += f" Requirements: {request.get('additional_requirements')}"
        result = await _run_agent_loop_goal(goal, "report", max_loops=10)
        return {"success": True, "report": {"content": result, "sections": []}}

    if action == "ask_question":
        question = request.get("question", "")
        report = request.get("report", "")
        goal = f"Answer based on report:\n\n{report}\n\nQuestion: {question}"
        result = await _run_agent_loop_goal(goal, "qa", max_loops=10)
        return {"success": True, "question": question, "answer": result}

    if action == "generate_ppt":
        report_content = request.get("report_content", "")
        goal = f"Generate PPT from:\n\n{report_content}"
        result = await _run_agent_loop_goal(goal, "ppt", max_loops=6)
        return {
            "success": True,
            "ppt": {
                "pptx_path": _extract_pptx_path(result),
                "template": request.get("template", "default"),
                "style": request.get("style", "professional"),
                "content": result,
            },
        }

    if action == "search":
        from agents import SearchAgent, Task, TaskType

        search_agent = SearchAgent()
        result = await search_agent.execute(Task(
            id=str(uuid.uuid4())[:8],
            type=TaskType.SEARCH,
            input={
                "query": request.get("query", ""),
                "max_results": request.get("max_results", 10),
            },
        ))
        return {"success": True, "search_results": result}

    if action == "analyze_document":
        from agents import DocumentAgent, Task, TaskType

        document_agent = DocumentAgent()
        result = await document_agent.execute(Task(
            id=str(uuid.uuid4())[:8],
            type=TaskType.DOCUMENT,
            input={
                "file_path": request.get("file_path", ""),
                "file_type": request.get("file_type", ""),
                "action": request.get("action_type", request.get("action", "analyze")),
            },
        ))
        return {"success": True, "analysis": result}

    if action == "modify_report":
        report = request.get("report", "")
        modifications = request.get("modifications", "")
        goal = f"Modify the following report based on these instructions:\n\n{modifications}\n\nReport:\n{report}"
        result = await _run_agent_loop_goal(goal, "report", max_loops=10)
        return {"success": True, "report": {"content": result, "sections": []}}

    raise ValueError(f"Unsupported action: {action}")


async def _generate_search_queries(question: str) -> List[str]:
    from agents import TopicAnalysisAgent

    agent = TopicAnalysisAgent()
    result = await agent.analyze_topic(question)
    queries = result.get("search_queries") or [question]
    return [q for q in queries if q]


async def _multi_search(search_queries: List[str], num_results: int = 3) -> List[dict]:
    from agents import SearchAgent, Task, TaskType

    search_agent = SearchAgent()
    merged_results = []
    for query in search_queries:
        result = await search_agent.execute(Task(
            id=str(uuid.uuid4())[:8],
            type=TaskType.SEARCH,
            input={"query": query, "max_results": num_results},
        ))
        merged_results.extend(result.get("results", []))

    source_priority = {"exa": 0, "tavily": 1, "bilibili": 2, "github": 2}
    seen_urls = set()
    deduped = []
    for item in merged_results:
        url = item.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(item)

    deduped.sort(key=lambda item: (source_priority.get(item.get("source", ""), 9), -item.get("score", 0)))
    return deduped[:num_results]


@router.post("/agent-loop/run", response_model=AgentLoopRunResponse)
async def agent_loop_run(request: AgentLoopRunRequest, background_tasks: BackgroundTasks):
    engine = _get_agent_loop_engine()
    task_id = str(uuid.uuid4())[:8]

    if request.file_path:
        # 有文件：走文件报告流程（DocumentAgent → SearchAgent → ReportAgent）
        topic = request.topic or "文档报告"
        task_id = await engine.run_file_report_in_background(
            task_id=task_id,
            topic=topic,
            file_path=request.file_path,
            include_search=request.include_search or False,
            format="markdown",
            additional_requirements=""
        )
        tasks[task_id] = {
            "id": task_id, "type": "file_report", "status": "running",
            "goal": f"文件报告: {topic}", "created_at": datetime.now().isoformat(),
            "stream_url": f"/api/agent-loop/{task_id}/stream"
        }
    else:
        # 无文件：走原 Agent Loop
        task_id = await engine.run_in_background(
            goal=request.goal, task_id=task_id, max_loops=request.max_loops,
            model=request.model, tool_group=request.tool_group,
            context_strategy=request.context_strategy
        )
        tasks[task_id] = {
            "id": task_id, "type": "agent_loop", "status": "running",
            "goal": request.goal, "created_at": datetime.now().isoformat(),
            "stream_url": f"/api/agent-loop/{task_id}/stream"
        }

    save_tasks()
    return AgentLoopRunResponse(task_id=task_id, status="running", stream_url=f"/api/agent-loop/{task_id}/stream")


@router.get("/agent-loop/{task_id}/stream")
async def agent_loop_stream(task_id: str):
    engine = _get_agent_loop_engine()
    async def event_generator():
        try:
            async for event in engine.stream_events(task_id):
                event_dict = event.to_dict()
                yield f"event: step\ndata: {json.dumps(event_dict, ensure_ascii=False)}\n\n"
            if task_id in tasks:
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["finished_at"] = datetime.now().isoformat()
                try:
                    save_tasks()
                except Exception as save_err:
                    logger.error(f"[Router] 保存任务状态失败: {save_err}")
            yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"
        except Exception as e:
            if task_id in tasks:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = str(e)
                try:
                    save_tasks()
                except Exception as save_err:
                    logger.error(f"[Router] 保存任务状态失败: {save_err}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    return StreamingResponse(
        event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@router.post("/agent-loop/{task_id}/interrupt")
async def agent_loop_interrupt(task_id: str):
    engine = _get_agent_loop_engine()
    engine.interrupt(task_id)
    if task_id in tasks:
        tasks[task_id]["status"] = "interrupted"
        save_tasks()
    return APIResponse(success=True, message=f"Task {task_id} interrupted")


@router.post("/agent-loop/{task_id}/reply")
async def agent_loop_reply(task_id: str, reply: AskUserReply):
    from tools.ask_user import set_user_answer
    if set_user_answer(task_id, reply.tool_call_id, reply.answer):
        return APIResponse(success=True, message="Reply sent")
    return APIResponse(success=False, error="Question not found")


@router.get("/agent-loop/{task_id}/trace")
async def agent_loop_get_trace(task_id: str):
    traces_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "traces")
    trace_path = os.path.join(traces_dir, f"{task_id}.json")
    if not os.path.exists(trace_path):
        raise HTTPException(status_code=404, detail="Trace not found")
    with open(trace_path, "r", encoding="utf-8") as f:
        return APIResponse(success=True, data=json.load(f))


@router.get("/agent-loop/traces")
async def agent_loop_list_traces():
    traces_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "traces")
    os.makedirs(traces_dir, exist_ok=True)
    traces = []
    for fname in sorted(os.listdir(traces_dir), reverse=True):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(traces_dir, fname), "r", encoding="utf-8") as f:
                    t = json.load(f)
                    traces.append({
                        "trace_id": t.get("trace_id", fname[:-5]),
                        "goal": t.get("goal", ""),
                        "status": t.get("status", ""),
                        "total_tokens": t.get("total_tokens", 0),
                        "started_at": t.get("started_at"),
                        "finished_at": t.get("finished_at")
                    })
            except Exception:
                pass
    return APIResponse(success=True, data={"traces": traces, "total": len(traces)})


@router.get("/agent-loop/tools")
async def agent_loop_get_tools():
    from core.tool_registry import registry
    return APIResponse(success=True, data={
        "tools": [{"name": t.name, "description": t.description, "enabled": t.enabled, "timeout": t.timeout, "group": t.group} for t in registry.get_all_tools()]
    })


@router.post("/agent-loop/tools/{tool_name}/toggle")
async def agent_loop_toggle_tool(tool_name: str):
    from core.tool_registry import registry
    tool = registry.get_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
    new_state = not tool.enabled
    registry.toggle(tool_name, new_state)
    return APIResponse(success=True, data={"tool": tool_name, "enabled": new_state})
