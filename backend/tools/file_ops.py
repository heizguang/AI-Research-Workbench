"""
文件操作工具 — 读取和写入文件
"""
import hashlib
import logging
import os
import re
from pathlib import Path

from core.tool_registry import Tool

logger = logging.getLogger(__name__)

# 允许的路径
ALLOWED_READ_PATHS = ["./data/uploads/", "./data/", "./data/reports/", "./data/ppt/"]
FORBIDDEN_PATHS = ["/etc/", "~/.ssh/", "C:\\Windows\\", "C:\\windows\\"]
ALLOWED_WRITE_DIR = "./data/"


class ReadFileTool:
    """读取文件工具"""

    def __init__(self):
        self.name = "read_file"
        self.description = "读取文件内容。支持 PDF、Word、图片（自动OCR）、文本文件。用于分析用户上传的文档。"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                }
            },
            "required": ["path"]
        }
        self.timeout = 30

    async def execute(self, path: str) -> str:
        """读取文件内容"""
        logger.info(f"[read_file] 读取文件: {path}")

        # 安全检查
        if not self._is_path_allowed(path):
            return f"错误: 无权读取该路径: {path}"

        file_path = Path(path)
        if not file_path.exists():
            return f"错误: 文件不存在: {path}"

        try:
            # 复用 DocumentAgent 的逻辑
            from agents import DocumentAgent
            doc_agent = DocumentAgent()
            # 使用 _read_document 方法
            result = await doc_agent._read_document(str(file_path), "")
            return result if result else "文件内容为空或无法解析。"
        except Exception as e:
            logger.error(f"[read_file] 读取失败: {e}")
            # 降级：直接读取文本文件
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return f"错误: 读取文件失败: {e}"

    def _is_path_allowed(self, path: str) -> bool:
        """检查路径是否允许读取"""
        abs_path = os.path.abspath(path)
        for forbidden in FORBIDDEN_PATHS:
            if abs_path.startswith(os.path.abspath(forbidden)):
                return False
        return True


class WriteFileTool:
    """写入文件工具"""

    def __init__(self):
        self.name = "write_file"
        self.description = "将内容写入文件。只能写入 ./data/ 目录。用于保存报告、结果等。"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于 ./data/ 目录）"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容"
                }
            },
            "required": ["path", "content"]
        }
        self.timeout = 10
        # 去重缓存：记录上次写入的 (path, content_hash)
        self._last_write: dict = {"path": None, "hash": None}

    async def execute(self, path: str, content: str) -> str:
        """写入文件"""
        logger.info(f"[write_file] 写入文件: {path} | 内容长度: {len(content)}")

        # 去重：相同 path + 相同 content 直接跳过
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        if path == self._last_write["path"] and content_hash == self._last_write["hash"]:
            logger.info(f"[write_file] 跳过重复写入: {path}（内容未变化）")
            return f"文件已存在且内容未变化，跳过写入: {path} ({len(content)} 字符)"
        self._last_write["path"] = path
        self._last_write["hash"] = content_hash

        # 安全检查：禁止路径遍历
        if ".." in path:
            return "错误: 禁止路径遍历"

        # 安全检查：大小限制
        if len(content) > 10 * 1024 * 1024:  # 10MB
            return "错误: 文件内容过大（最大 10MB）"

        # 确保写入 ./data/ 目录
        data_dir = os.path.abspath(ALLOWED_WRITE_DIR)
        os.makedirs(data_dir, exist_ok=True)

        file_path = os.path.join(data_dir, path)
        abs_file_path = os.path.abspath(file_path)

        # 确保路径在 data 目录下
        if not abs_file_path.startswith(data_dir):
            return "错误: 只能写入 ./data/ 目录"

        try:
            os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
            with open(abs_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"文件已写入: {abs_file_path} ({len(content)} 字符)"
        except Exception as e:
            logger.error(f"[write_file] 写入失败: {e}")
            return f"错误: 写入文件失败: {e}"


def create_read_file_tool() -> Tool:
    t = ReadFileTool()
    return Tool(name=t.name, description=t.description, parameters=t.parameters, execute=t.execute, timeout=t.timeout)


def create_write_file_tool() -> Tool:
    t = WriteFileTool()
    return Tool(name=t.name, description=t.description, parameters=t.parameters, execute=t.execute, timeout=t.timeout)