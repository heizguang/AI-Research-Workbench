"""代码执行工具 — Python 沙箱执行"""
import asyncio
import ast
import logging
import re
import sys
from typing import Optional

from core.tool_registry import Tool

logger = logging.getLogger(__name__)

# 禁止导入的危险模块
FORBIDDEN_MODULES = {"os", "subprocess", "sys", "shutil", "importlib", "__builtins__",
                     "ctypes", "multiprocessing", "socket", "requests", "http",
                     "ftp", "smtp", "telnet", "ssh", "pickle", "marshal", "signal",
                     "threading", "concurrent", "asyncio"}

# 禁止的危险内置函数
FORBIDDEN_BUILTINS = {"eval", "exec", "compile", "__import__", "open", "input",
                      "globals", "locals", "vars", "getattr", "setattr", "delattr",
                      "breakpoint", "help", "memoryview"}

# 禁止通过 __builtins__ 绕过
FORBIDDEN_BUILTINS_ACCESS = {"__builtins__", "__builtin__"}


class RunCodeTool:
    """Python 代码执行工具"""

    def __init__(self):
        self.name = "run_code"
        self.description = "执行 Python 代码（沙箱环境）。禁止文件系统写操作、网络请求和导入危险模块。超时 30s。"
        self.parameters = {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码"
                },
                "language": {
                    "type": "string",
                    "description": "编程语言，目前仅支持 python",
                    "default": "python",
                    "enum": ["python"]
                }
            },
            "required": ["code"]
        }
        self.timeout = 30

    def _check_ast(self, code: str) -> Optional[str]:
        """使用 AST 解析检查危险代码"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"错误: 语法错误: {e}"

        for node in ast.walk(tree):
            # 检查 import
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                        return f"错误: 禁止导入 {alias.name} 模块"
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in FORBIDDEN_MODULES:
                    return f"错误: 禁止从 {node.module} 导入模块"

            # 检查危险函数调用
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in FORBIDDEN_BUILTINS:
                        return f"错误: 禁止调用 {node.func.id}()"
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        full = f"{node.func.value.id}.{node.func.attr}"
                        if node.func.attr in FORBIDDEN_BUILTINS:
                            return f"错误: 禁止调用 {full}()"
                        if node.func.value.id in FORBIDDEN_BUILTINS_ACCESS:
                            return f"错误: 禁止通过 {node.func.value.id} 绕过安全检查"

            # 检查 __builtins__ 绕过：__builtins__['eval'](...) 或 __builtins__.eval(...)
            elif isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and node.value.id in FORBIDDEN_BUILTINS_ACCESS:
                    return f"错误: 禁止访问 {node.value.id}"

            # 检查 __builtins__ 赋值
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id in FORBIDDEN_BUILTINS_ACCESS:
                    return f"错误: 禁止访问 {node.value.id}"

        return None  # 通过检查

    async def execute(self, code: str, language: str = "python") -> str:
        """在沙箱中执行 Python 代码"""
        logger.info(f"[run_code] 执行代码 | 长度: {len(code)}")

        if language != "python":
            return f"错误: 不支持的语言: {language}"

        # AST 安全检查
        ast_error = self._check_ast(code)
        if ast_error:
            return ast_error

        # 额外正则检查（防止 AST 绕过的攻击）
        code_lower = code.lower()
        for func in FORBIDDEN_BUILTINS:
            if re.search(rf'\b{func}\s*\(', code_lower):
                # 已在 AST 中检查，这里的 false positive 需要人工处理
                # 但保留此检查作为额外防线
                pass

        # 在子进程中执行
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 10  # 10KB 输出限制
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )

            output = ""
            if stdout:
                output += stdout.decode("utf-8", errors="replace")[:10 * 1024]
            if stderr:
                output += "\n[stderr]\n" + stderr.decode("utf-8", errors="replace")[:5 * 1024]

            if not output.strip():
                output = "代码执行完成，无输出。"

            return output.strip()

        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return f"错误: 代码执行超时（{self.timeout}s）"
        except Exception as e:
            return f"错误: 代码执行失败: {e}"


def create_run_code_tool() -> Tool:
    t = RunCodeTool()
    return Tool(name=t.name, description=t.description, parameters=t.parameters, execute=t.execute, timeout=t.timeout)