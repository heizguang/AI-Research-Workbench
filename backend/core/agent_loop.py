"""
Agent Loop 引擎 — 核心循环：思考 → 行动 → 观察
"""
import asyncio
import json
import logging
import os
import re
import time
import uuid
from typing import AsyncIterator, Dict, List, Optional

from core.llm import LLM, LLMMessage, LLMConfig, StreamChunk, get_llm
from core.tool_registry import ToolRegistry, registry
from core.context_manager import ContextManager

logger = logging.getLogger(__name__)

# 环境变量配置
MAX_LOOPS = int(os.getenv("AGENT_LOOP_MAX_LOOPS", "20"))
MAX_TOKENS = int(os.getenv("AGENT_LOOP_MAX_TOKENS", "100000"))
SUMMARY_THRESHOLD = int(os.getenv("AGENT_LOOP_SUMMARY_THRESHOLD", "80000"))
CONTEXT_WINDOW = int(os.getenv("AGENT_LOOP_CONTEXT_WINDOW", "10"))
MAX_CONCURRENT = int(os.getenv("AGENT_LOOP_MAX_CONCURRENT", "5"))
MAX_TOOL_RETRIES = int(os.getenv("AGENT_LOOP_MAX_TOOL_RETRIES", "2"))
MAX_ASK_USER = int(os.getenv("AGENT_LOOP_MAX_ASK_USER", "3"))
MAX_LLM_RETRIES = int(os.getenv("AGENT_LOOP_MAX_LLM_RETRIES", "1"))


class LoopEvent:
    """循环事件 — 通过 SSE 推送到前端"""

    def __init__(
        self,
        loop: int = 0,
        type: str = "think",
        content: Optional[str] = None,
        tool: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        tool_input: Optional[dict] = None,
        tool_output: Optional[str] = None,
        result: Optional[str] = None,
        status: Optional[str] = None,
        tokens: int = 0,
        timestamp: Optional[str] = None,
        duration: Optional[float] = None,
        stage: Optional[str] = None
    ):
        self.loop = loop
        self.type = type
        self.stage = stage
        self.content = content
        self.tool = tool
        self.tool_call_id = tool_call_id
        self.tool_input = tool_input
        self.tool_output = tool_output
        self.result = result
        self.status = status
        self.tokens = tokens
        self.timestamp = timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.duration = duration

    def to_dict(self) -> Dict:
        d = {"loop": self.loop, "type": self.type, "timestamp": self.timestamp}
        if self.stage is not None:
            d["stage"] = self.stage
        if self.content is not None:
            d["content"] = self.content
        if self.tool is not None:
            d["tool"] = self.tool
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_input is not None:
            d["tool_input"] = self.tool_input
        if self.tool_output is not None:
            d["tool_output"] = self.tool_output
        if self.result is not None:
            d["result"] = self.result
        if self.status is not None:
            d["status"] = self.status
        if self.tokens:
            d["tokens"] = self.tokens
        if self.duration is not None:
            d["duration"] = round(self.duration, 1)
        return d


class AgentLoopEngine:
    """Agent Loop 核心引擎"""

    def __init__(self, llm: LLM = None, tool_registry: ToolRegistry = None):
        self.llm = llm or get_llm()
        self.tool_registry = tool_registry or registry
        self._interrupt_flags: Dict[str, asyncio.Event] = {}
        self._task_semaphore = asyncio.Semaphore(MAX_CONCURRENT)  # 任务级并发控制
        self._task_queues: Dict[str, asyncio.Queue] = {}  # 后台执行的事件队列
        self._task_configs: Dict[str, dict] = {}  # 任务配置（model, tool_group）

    def interrupt(self, task_id: str):
        """中断任务"""
        if task_id in self._interrupt_flags:
            self._interrupt_flags[task_id].set()
            logger.info(f"[AgentLoop] 任务 {task_id} 收到中断信号")

    async def run_in_background(
        self,
        goal: str,
        task_id: str = None,
        max_loops: int = None,
        model: str = "smart",
        tool_group: str = "full",
        context_strategy: str = "sliding_window"
    ):
        """后台执行 Agent Loop，将事件放入队列供 SSE 消费"""
        task_id = task_id or str(uuid.uuid4())[:8]
        queue = asyncio.Queue(maxsize=100)
        self._task_queues[task_id] = queue
        self._task_configs[task_id] = {"model": model, "tool_group": tool_group}

        async def _runner():
            try:
                async with self._task_semaphore:
                    async for event in self.run(
                        goal=goal, task_id=task_id, max_loops=max_loops,
                        model=model, tool_group=tool_group,
                        context_strategy=context_strategy
                    ):
                        await queue.put(("step", event))
            except Exception as e:
                logger.error(f"[AgentLoop] 后台任务异常: {e}")
                await queue.put(("error", str(e)))
            finally:
                await queue.put(("done", None))
                self._task_queues.pop(task_id, None)
                self._task_configs.pop(task_id, None)

        asyncio.create_task(_runner())
        return task_id

    async def run_file_report_in_background(
        self,
        task_id: str,
        topic: str,
        file_path: str,
        include_search: bool = False,
        format: str = "markdown",
        additional_requirements: str = ""
    ):
        """后台执行文件报告流程，将事件放入队列供 SSE 消费"""
        queue = asyncio.Queue(maxsize=100)
        self._task_queues[task_id] = queue
        self._task_configs[task_id] = {"model": "file_report", "tool_group": "full"}

        async def _runner():
            try:
                async with self._task_semaphore:
                    async for event in self.run_file_report(
                        task_id=task_id, topic=topic, file_path=file_path,
                        include_search=include_search, format=format,
                        additional_requirements=additional_requirements
                    ):
                        await queue.put(("step", event))
            except Exception as e:
                logger.error(f"[FileReport] 后台任务异常: {e}")
                await queue.put(("error", str(e)))
            finally:
                await queue.put(("done", None))
                self._task_queues.pop(task_id, None)
                self._task_configs.pop(task_id, None)

        asyncio.create_task(_runner())
        return task_id

    async def run_file_report(
        self,
        task_id: str,
        topic: str,
        file_path: str,
        include_search: bool = False,
        format: str = "markdown",
        additional_requirements: str = ""
    ) -> AsyncIterator[LoopEvent]:
        """文件报告流程：DocumentAgent → SearchAgent(可选) → ReportAgent"""
        start_time = time.time()

        logger.info(f"[FileReport] ========== 文件报告任务开始 ==========")
        logger.info(f"[FileReport] task_id: {task_id}")
        logger.info(f"[FileReport] 主题: {topic}")
        logger.info(f"[FileReport] 文件: {file_path}")
        logger.info(f"[FileReport] 补充搜索: {include_search}")
        logger.info(f"[FileReport] ==============================")

        # 推送开始事件（流水线模式：用 stage 标记，不进入 loop 轮次）
        yield LoopEvent(loop=0, type="start", stage="文件报告", content="文件报告任务已启动")

        try:
            # ── Step 1: 读取文件 ──
            logger.info(f"[FileReport] Step 1: 读取文件 {file_path}")
            yield LoopEvent(loop=0, stage="解析文档", type="tool_call", tool="read_file",
                            tool_input={"path": file_path},
                            content="正在读取文件...")

            from agents import DocumentAgent
            doc_agent = DocumentAgent()
            file_content = await doc_agent._read_document(file_path, "")

            if not file_content or not file_content.strip():
                yield LoopEvent(loop=0, stage="解析文档", type="error", content="文件内容为空或无法解析")
                return

            logger.info(f"[FileReport] 文件读取完成 | 内容长度: {len(file_content)} 字符")
            yield LoopEvent(loop=0, stage="解析文档", type="tool_call", tool="read_file",
                            tool_output=f"读取完成，{len(file_content)} 字符",
                            content="文件读取完成")

            # ── Step 2: 搜索补充（可选）──
            search_context = ""
            if include_search:
                logger.info(f"[FileReport] Step 2: 搜索补充信息")
                yield LoopEvent(loop=0, stage="搜索补充", type="tool_call", tool="web_search",
                                content="正在提炼文档检索词...")

                # 关键：基于文档内容提炼检索词，而不是直接用用户输入的主题
                doc_excerpt = file_content[:3000]
                search_query = topic
                try:
                    extracted = await self.llm.generate_text_fast(
                        prompt=(
                            f"以下是一份文档的内容摘录：\n\n{doc_excerpt}\n\n"
                            f"请基于文档的核心主题，生成 1 条最适合的中文网络搜索关键词，"
                            f"用于补充与该文档主题相关的最新资料。"
                            f"只输出关键词本身，不要解释、不要标点或引号，长度不超过 30 字。"
                        ),
                        system_prompt="你是搜索关键词提取助手，擅长从文档中提炼核心检索词。"
                    )
                    extracted = (extracted or "").strip().strip('"\'' + '“”‘’').splitlines()[0].strip()
                    if extracted:
                        search_query = extracted
                except Exception as e:
                    logger.warning(f"[FileReport] 检索词提取失败，回退到用户主题: {e}")

                logger.info(f"[FileReport] 文档检索词: {search_query}（原始主题: {topic}）")
                yield LoopEvent(loop=0, stage="搜索补充", type="tool_call", tool="web_search",
                                tool_input={"query": search_query},
                                content=f"正在搜索补充信息：{search_query}")

                from agents import SearchAgent, Task as AgentTask, TaskType
                search_agent = SearchAgent()
                search_result = await search_agent.execute(AgentTask(
                    id=str(uuid.uuid4())[:8],
                    type=TaskType.SEARCH,
                    input={"query": search_query, "max_results": 10}
                ))
                search_context = search_result.get("summary", "")
                logger.info(f"[FileReport] 搜索完成 | 摘要长度: {len(search_context)} 字符")
                yield LoopEvent(loop=0, stage="搜索补充", type="tool_call", tool="web_search",
                                tool_output=search_context,
                                content="搜索完成")
            else:
                logger.info(f"[FileReport] Step 2: 跳过搜索（用户选择仅基于文件）")

            # ── Step 3: 生成报告 ──
            logger.info(f"[FileReport] Step 3: 生成报告")
            yield LoopEvent(loop=0, stage="生成报告", type="tool_call", tool="generate_report",
                            content="正在生成报告...")

            # 合并文件内容和搜索结果
            combined_content = file_content
            if search_context:
                combined_content += f"\n\n---\n\n以下是搜索补充信息：\n\n{search_context}"

            from agents import ReportAgent, Task as AgentTask, TaskType
            report_agent = ReportAgent()
            report_input = {
                "mode": "document",
                "content": combined_content,
                "topic": topic,
                "format": format,
            }
            if additional_requirements:
                report_input["additional_requirements"] = additional_requirements

            result = await report_agent.execute(AgentTask(
                id=str(uuid.uuid4())[:8],
                type=TaskType.REPORT,
                input=report_input
            ))

            report_content = result.get("content", "")
            logger.info(f"[FileReport] 报告生成完成 | 内容长度: {len(report_content)} 字符")
            yield LoopEvent(loop=0, stage="生成报告", type="tool_call", tool="generate_report",
                            tool_output=report_content,
                            content="报告生成完成")

            # ── 完成 ──
            duration = round(time.time() - start_time, 1)
            logger.info(f"[FileReport] ========== 任务完成 | 耗时: {duration}s ==========")
            yield LoopEvent(loop=0, stage="生成报告", type="done", result=report_content,
                            status="completed", duration=duration)

        except Exception as e:
            logger.error(f"[FileReport] 任务异常: {e}", exc_info=True)
            yield LoopEvent(type="error", content=f"文件报告生成失败: {str(e)}")

    async def stream_events(self, task_id: str) -> AsyncIterator[LoopEvent]:
        """从队列消费事件（供 SSE 端点使用）"""
        queue = self._task_queues.get(task_id)
        if not queue:
            yield LoopEvent(type="error", content=f"任务不存在: {task_id}")
            return

        while True:
            msg_type, payload = await queue.get()
            if msg_type == "step":
                yield payload
            elif msg_type == "error":
                yield LoopEvent(type="error", content=payload)
                return
            elif msg_type == "done":
                return
            queue.task_done()

    async def run(
        self,
        goal: str,
        task_id: str = None,
        max_loops: int = None,
        model: str = "smart",
        tool_group: str = "full",
        context_strategy: str = "sliding_window"
    ) -> AsyncIterator[LoopEvent]:
        """执行 Agent Loop（内部实现）"""
        task_id = task_id or str(uuid.uuid4())[:8]
        max_loops = max_loops or MAX_LOOPS

        # 选择模型
        if model == "fast":
            config = LLMConfig(
                model=self.llm.fast_model,
                temperature=0.7,
                max_tokens=2000
            )
        else:
            config = self.llm.config

        # 初始化上下文
        context = ContextManager(
            max_turns=CONTEXT_WINDOW,
            summary_threshold=SUMMARY_THRESHOLD,
            max_tokens=MAX_TOKENS
        )
        tools = self.tool_registry.get_group_tools(tool_group)
        system_prompt = context._build_system_prompt(tools)
        context.init(system_prompt, goal)

        # 预加载：如果 goal 中包含文件路径，自动读取文件内容并注入上下文
        file_path_match = re.search(r'(\./data/uploads/[^\s,，。！？\n]+)', goal)
        if file_path_match:
            file_path = file_path_match.group(1)
            logger.info(f"[AgentLoop] 检测到文件路径，预加载: {file_path}")
            try:
                from tools.file_ops import ReadFileTool
                read_tool = ReadFileTool()
                file_content = await read_tool.execute(file_path)
                if file_content and not file_content.startswith("错误"):
                    # 将文件内容作为上下文注入，让 LLM 直接可用
                    file_msg = f"以下是已读取的文件内容（路径：{file_path}）：\n\n{file_content}"
                    context.messages.append(LLMMessage(role="user", content=file_msg))
                    logger.info(f"[AgentLoop] 文件预加载成功 | 内容长度: {len(file_content)} 字符")
                else:
                    logger.warning(f"[AgentLoop] 文件预加载失败: {file_content}")
            except Exception as e:
                logger.error(f"[AgentLoop] 文件预加载异常: {e}")

        # 中断信号
        self._interrupt_flags[task_id] = asyncio.Event()
        consecutive_failures = 0
        final_status = "completed"
        loop_start_time = time.time()

        # 任务开始日志
        tool_names = [t.name for t in tools]
        logger.info(f"[AgentLoop] ========== 任务开始 ==========")
        logger.info(f"[AgentLoop] task_id: {task_id}")
        logger.info(f"[AgentLoop] 目标: {goal}")
        logger.info(f"[AgentLoop] 配置: max_loops={max_loops}, model={model}, 工具分组={tool_group}")
        logger.info(f"[AgentLoop] 已注册工具: {', '.join(tool_names)} ({len(tools)}个)")
        logger.info(f"[AgentLoop] ==============================")

        try:
            for loop_num in range(1, max_loops + 1):
                # 检查中断
                if self._interrupt_flags[task_id].is_set():
                    logger.info(f"[AgentLoop] 用户中断 | Loop {loop_num}")
                    final_status = "interrupted"
                    yield LoopEvent(
                        loop=loop_num, type="done",
                        result="任务已被用户中断", status="interrupted",
                        duration=round(time.time() - loop_start_time, 1)
                    )
                    return

                loop_start = time.time()
                logger.info(f"[AgentLoop] ===== Loop {loop_num}/{max_loops} 开始 =====")
                logger.info(f"[AgentLoop] 上下文 token 数: {context.get_token_count()} / {MAX_TOKENS}")

                # --- Token 预算检查 ---
                if context.get_token_count() > MAX_TOKENS * 0.8:
                    await context.compress_if_needed(self.llm)
                if context.get_token_count() > MAX_TOKENS:
                    logger.warning(f"[AgentLoop] Token 耗尽，强制终止")
                    final_status = "token_exhausted"
                    yield LoopEvent(
                        loop=loop_num, type="done",
                        result="已达 Token 上限，返回已有结果", status="token_exhausted",
                        duration=round(time.time() - loop_start_time, 1)
                    )
                    return

                # --- LLM 调用（流式）---
                model_name = config.model
                messages = context.get_messages()

                # 最后一轮禁止调用工具，强制模型输出最终文本
                is_last_loop = (loop_num >= max_loops)
                if is_last_loop:
                    openai_tools = []
                    logger.info(f"[LLM] 最后一轮，禁用工具调用，强制输出最终回复")
                else:
                    openai_tools = self.tool_registry.get_group_openai_tools(tool_group)

                logger.info(f"[LLM] 调用模型: {model_name} | 消息数: {len(messages)} | 工具数: {len(openai_tools)}")

                full_content = ""
                tool_calls = []
                total_chunks = 0
                llm_ok = False

                for attempt in range(MAX_LLM_RETRIES + 1):
                    full_content = ""
                    tool_calls = []
                    total_chunks = 0
                    try:
                        async for chunk in self.llm.chat_stream_with_tools(
                            messages, config, openai_tools, role=("fast" if model == "fast" else "smart")
                        ):
                            total_chunks += 1
                            if chunk.type == "content":
                                full_content += chunk.content
                                yield LoopEvent(
                                    loop=loop_num, type="think_chunk", content=chunk.content
                                )
                            elif chunk.type == "tool_calls":
                                tool_calls.append(chunk.tool_call)
                        llm_ok = True
                        break
                    except Exception as e:
                        logger.error(f"[AgentLoop] LLM 调用失败（尝试 {attempt+1}/{MAX_LLM_RETRIES+1}）: {e}")
                        if total_chunks > 0:
                            # 已向用户流出部分内容，重试会重复输出，直接失败
                            logger.error("[AgentLoop] 已流出部分内容，不再重试")
                            break
                        if attempt < MAX_LLM_RETRIES:
                            wait = 2 ** attempt
                            logger.info(f"[AgentLoop] {wait}s 后重试 LLM 调用...")
                            await asyncio.sleep(wait)

                if not llm_ok:
                    final_status = "llm_error"
                    yield LoopEvent(
                        loop=loop_num, type="done",
                        result="模型服务暂时不可用，请稍后重试。", status="llm_error",
                        duration=round(time.time() - loop_start_time, 1)
                    )
                    return

                logger.info(f"[LLM] 流式输出完成 | chunks: {total_chunks} | 总字符: {len(full_content)}")
                if tool_calls:
                    for i, tc in enumerate(tool_calls):
                        logger.info(f"[LLM]   [{i+1}] {tc['function']['name']}({tc['function']['arguments']})")

                # 记录思考
                context.add_assistant_message(full_content, tool_calls if tool_calls else None)
                context.add_think_tokens(len(full_content) // 4 + 500)

                # --- 无工具调用 → 任务完成 ---
                if not tool_calls:
                    logger.info(f"[AgentLoop] 任务完成 | 最终回复长度: {len(full_content)}")
                    final_status = "completed"
                    yield LoopEvent(
                        loop=loop_num, type="done",
                        result=full_content, status="completed",
                        duration=round(time.time() - loop_start_time, 1)
                    )
                    return

                # --- 并行工具调用 ---
                tool_call_names = [tc["function"]["name"] for tc in tool_calls]
                logger.info(f"[Tool] >>> 并行调用 {len(tool_calls)} 个工具: {', '.join(tool_call_names)}")

                # 通知前端：工具开始执行（立即发送，不等工具完成）
                for tc in tool_calls:
                    try:
                        tool_args = json.loads(tc["function"].get("arguments", "{}"))
                    except json.JSONDecodeError:
                        logger.warning(f"[AgentLoop] tool_call arguments JSON 解析失败，使用默认参数: {tc['function'].get('arguments', '')[:80]}")
                        tool_args = {}
                    yield LoopEvent(
                        loop=loop_num, type="tool_call",
                        tool=tc["function"]["name"], tool_call_id=tc["id"],
                        tool_input=tool_args, content=f"正在执行 {tc['function']['name']}..."
                    )

                # 设置 task_id 上下文（供 ask_user 等工具使用）
                self.tool_registry.set_task_context(task_id)

                async def _execute_with_retry(tc: Dict) -> Optional[Dict]:
                    """执行单个工具调用（含重试逻辑）"""
                    tool_name = tc["function"]["name"]
                    try:
                        tool_args = json.loads(tc["function"].get("arguments", "{}"))
                    except json.JSONDecodeError:
                        logger.warning(f"[AgentLoop] {tool_name} arguments JSON 解析失败，使用默认参数")
                        tool_args = {}
                    tool = self.tool_registry.get_tool(tool_name)
                    timeout = tool.timeout if tool else 60

                    logger.info(f"[Tool] >>> 开始调用 {tool_name}")
                    logger.info(f"[Tool] 模型: {model_name} | 轮次: Loop {loop_num} | 参数: {json.dumps(tool_args, ensure_ascii=False)}")

                    for attempt in range(MAX_TOOL_RETRIES + 1):
                        try:
                            result = await self.tool_registry.execute(tool_name, tool_args, timeout)
                            logger.info(f"[Tool] {tool_name} 完成 | 耗时: {round(time.time() - loop_start, 2)}s | 结果长度: {len(result)}")
                            return {"tool_call_id": tc["id"], "name": tool_name, "result": result, "input": tool_args, "success": True}
                        except Exception as e:
                            logger.error(f"[Tool] {tool_name} 执行失败 | 错误: {e}")
                            if attempt < MAX_TOOL_RETRIES:
                                wait = 1 * (2 ** attempt)
                                logger.info(f"[Tool] 重试 {attempt+1}/{MAX_TOOL_RETRIES} 等待 {wait}s...")
                                await asyncio.sleep(wait)
                            else:
                                return {"tool_call_id": tc["id"], "name": tool_name, "result": json.dumps({"error": str(e)}), "input": tool_args, "success": False}

                results = await asyncio.gather(*[_execute_with_retry(tc) for tc in tool_calls])

                # 检查连续失败：根据 result 中是否包含 {"error": 来判断
                for r in results:
                    if r is None:
                        consecutive_failures += 1
                    elif r.get("success") is False:
                        consecutive_failures += 1
                    elif r.get("result", "").startswith('{"error":'):
                        consecutive_failures += 1
                    else:
                        consecutive_failures = 0  # 至少有一个成功就重置

                if consecutive_failures >= 3:
                    logger.error(f"[AgentLoop] 连续 {consecutive_failures} 次工具调用失败，终止")
                    final_status = "consecutive_failures"
                    yield LoopEvent(
                        loop=loop_num, type="done",
                        result="连续工具调用失败，任务终止", status="consecutive_failures",
                        duration=round(time.time() - loop_start_time, 1)
                    )
                    return

                # 回填工具结果
                for r in results:
                    if r is None:
                        continue
                    context.add_tool_result(r["tool_call_id"], r["result"])
                    yield LoopEvent(
                        loop=loop_num, type="tool_call",
                        tool=r["name"], tool_call_id=r["tool_call_id"],
                        tool_input=r.get("input"), tool_output=r["result"]
                    )
                    yield LoopEvent(
                        loop=loop_num, type="observe",
                        tool=r["name"],
                        content=f"工具 {r['name']} 返回了结果（{len(r['result'])} 字符）"
                    )

                loop_elapsed = round(time.time() - loop_start, 2)
                logger.info(f"[AgentLoop] ===== Loop {loop_num}/{max_loops} 结束 | 耗时: {loop_elapsed}s | 累计 token: {context.get_token_count()} =====")

            # 达到最大轮次
            logger.warning(f"[AgentLoop] 达到最大轮次 {max_loops}")
            final_status = "max_loops_reached"
            yield LoopEvent(
                loop=max_loops, type="done",
                result="已达最大轮次限制，以下是当前结果", status="max_loops_reached",
                duration=round(time.time() - loop_start_time, 1)
            )

        finally:
            total_elapsed = round(time.time() - loop_start_time, 2)
            trace = context.to_trace()
            logger.info(f"[AgentLoop] ========== 任务结束 ==========")
            logger.info(f"[AgentLoop] task_id: {task_id}")
            logger.info(f"[AgentLoop] 总耗时: {total_elapsed}s | 总 token: {context.get_token_count()}")
            logger.info(f"[AgentLoop] ================================")

            self._interrupt_flags.pop(task_id, None)
            self.tool_registry.clear_task_context()
            self._save_trace(task_id, goal, trace, final_status)

    def _save_trace(self, task_id: str, goal: str, trace: Dict, status: str = "completed"):
        """持久化执行轨迹"""
        try:
            traces_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "traces")
            os.makedirs(traces_dir, exist_ok=True)

            trace_data = {
                "trace_id": task_id,
                "goal": goal,
                "status": status,
                "total_tokens": trace.get("token_budget", {}).get("used", 0),
                "started_at": trace.get("started_at"),
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "steps": trace.get("messages", [])
            }

            trace_path = os.path.join(traces_dir, f"{task_id}.json")
            with open(trace_path, "w", encoding="utf-8") as f:
                json.dump(trace_data, f, ensure_ascii=False, indent=2)

            logger.info(f"[AgentLoop] Trace 已保存: {trace_path}")

            self._cleanup_old_traces(traces_dir)

        except Exception as e:
            logger.error(f"[AgentLoop] Trace 保存失败: {e}")

    def _cleanup_old_traces(self, traces_dir: str):
        """清理旧 Trace，保留最近 100 条"""
        try:
            files = sorted(
                [f for f in os.listdir(traces_dir) if f.endswith(".json")],
                key=lambda f: os.path.getmtime(os.path.join(traces_dir, f)),
                reverse=True
            )
            for old_file in files[100:]:
                os.remove(os.path.join(traces_dir, old_file))
                logger.info(f"[AgentLoop] 清理旧 Trace: {old_file}")
        except Exception as e:
            logger.warning(f"[AgentLoop] Trace 清理失败: {e}")


# 全局引擎实例
engine = AgentLoopEngine()