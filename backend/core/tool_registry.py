"""
工具注册系统 — 管理 Agent Loop 的所有可用工具
"""
import asyncio
import json
import logging
import time
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Tool:
    """工具定义"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,  # JSON Schema
        execute: Callable,  # async function
        timeout: int = 60,
        enabled: bool = True,
        group: str = "full"
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.execute = execute
        self.timeout = timeout
        self.enabled = enabled
        self.group = group

    def to_openai_format(self) -> Dict:
        """转为 OpenAI tools 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


# 工具分组映射 — 每个工具属于哪些分组
TOOL_GROUP_MAP = {
    "full": {"web_search", "read_file", "write_file", "run_code", "generate_report", "modify_report", "generate_ppt", "ask_user"},
    "search_only": {"web_search", "read_file"},
    "report": {"web_search", "read_file", "write_file", "generate_report", "modify_report"},
    "ppt": {"web_search", "read_file", "generate_report", "generate_ppt"},
    "code": {"web_search", "read_file", "write_file", "run_code"},
    "qa": {"web_search", "read_file"},
}


class ToolRegistry:
    """工具注册中心"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._semaphore = asyncio.Semaphore(5)  # 工具级最大并发 5
        self._task_context: Dict[str, str] = {}  # {tool_name: task_id} 用于 ask_user 获取 task_id

    def set_task_context(self, task_id: str):
        """设置当前任务上下文（在工具执行前调用）"""
        self._task_context["_current_task_id"] = task_id

    def get_task_context(self) -> Optional[str]:
        """获取当前任务 ID"""
        return self._task_context.get("_current_task_id")

    def clear_task_context(self):
        """清除当前任务上下文"""
        self._task_context.pop("_current_task_id", None)

    def register(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"[ToolRegistry] 注册工具: {tool.name} (超时={tool.timeout}s, 分组={tool.group})")

    def unregister(self, name: str):
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"[ToolRegistry] 注销工具: {name}")

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取单个工具"""
        return self._tools.get(name)

    def get_all_tools(self) -> List[Tool]:
        """获取所有已注册工具"""
        return list(self._tools.values())

    def get_enabled_tools(self) -> List[Tool]:
        """获取所有已启用的工具"""
        return [t for t in self._tools.values() if t.enabled]

    def get_openai_tools(self) -> List[Dict]:
        """获取 OpenAI 格式的工具列表（仅已启用）"""
        return [t.to_openai_format() for t in self.get_enabled_tools()]

    def get_group_tools(self, group: str) -> List[Tool]:
        """按分组获取工具（仅已启用）"""
        enabled = self.get_enabled_tools()
        if group == "full":
            return enabled
        allowed = TOOL_GROUP_MAP.get(group, set())
        return [t for t in enabled if t.name in allowed]

    def get_group_openai_tools(self, group: str) -> List[Dict]:
        """按分组获取 OpenAI 格式的工具列表"""
        return [t.to_openai_format() for t in self.get_group_tools(group)]

    def get_group_names(self) -> List[str]:
        """获取所有工具分组名称"""
        groups = set()
        for t in self._tools.values():
            groups.add(t.group)
        return sorted(groups)

    def toggle(self, name: str, enabled: bool):
        """启用/禁用工具"""
        if name in self._tools:
            self._tools[name].enabled = enabled
            logger.info(f"[ToolRegistry] 工具 {name} {'启用' if enabled else '禁用'}")

    async def execute(self, name: str, arguments: dict, timeout: int = None) -> str:
        """执行工具调用（含超时和并发控制）"""
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"工具不存在: {name}"})

        if not tool.enabled:
            return json.dumps({"error": f"工具已禁用: {name}"})

        effective_timeout = timeout or tool.timeout
        start_time = time.time()

        logger.info(f"[Tool] >>> 开始调用 {name}")
        logger.info(f"[Tool] 参数: {json.dumps(arguments, ensure_ascii=False)}")

        try:
            async with self._semaphore:
                result = await asyncio.wait_for(
                    tool.execute(**arguments),
                    timeout=effective_timeout
                )

            elapsed = round(time.time() - start_time, 2)
            result_str = str(result)
            logger.info(f"[Tool] {name} 完成 | 耗时: {elapsed}s | 结果长度: {len(result_str)} 字符")
            return result_str

        except asyncio.TimeoutError:
            elapsed = round(time.time() - start_time, 2)
            logger.warning(f"[Tool] {name} 超时 | 超时限制: {effective_timeout}s | 耗时: {elapsed}s")
            return json.dumps({"error": f"工具执行超时（{effective_timeout}s）"})

        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            logger.error(f"[Tool] {name} 执行失败 | 耗时: {elapsed}s | 错误: {e}")
            return json.dumps({"error": str(e)})


# 全局注册中心
registry = ToolRegistry()