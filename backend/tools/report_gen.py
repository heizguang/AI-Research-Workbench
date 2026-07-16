"""
报告生成工具 — 复用 ReportAgent 的完整逻辑
"""
import logging

from core.tool_registry import Tool

logger = logging.getLogger(__name__)


class GenerateReportTool:
    """生成报告工具"""

    def __init__(self):
        self.name = "generate_report"
        self.description = "生成研究报告。可传入 content（搜索结果、文档内容等）辅助生成。支持文档模式。"
        self.parameters = {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "报告主题"
                },
                "content": {
                    "type": "string",
                    "description": "报告内容或搜索上下文（可选）",
                    "default": ""
                },
                "mode": {
                    "type": "string",
                    "description": "生成模式: document（基于上传文档）、auto（默认，自动判断）",
                    "enum": ["document", "auto"],
                    "default": "auto"
                },
                "format": {
                    "type": "string",
                    "description": "输出格式",
                    "enum": ["markdown", "text"],
                    "default": "markdown"
                }
            },
            "required": ["topic"]
        }
        self.timeout = 300

    async def execute(self, topic: str, content: str = "", mode: str = "auto", format: str = "markdown") -> str:
        """生成报告"""
        logger.info(f"[generate_report] 主题: {topic} | 模式: {mode} | 格式: {format}")

        try:
            # 复用 ReportAgent
            from agents import ReportAgent, Task, TaskType
            report_agent = ReportAgent()

            last_err: Exception = Exception("未知错误")
            for attempt in range(2):
                try:
                    task = Task(
                        id="tool_report",
                        type=TaskType.REPORT,
                        input={
                            "topic": topic,
                            "content": content,
                            "mode": mode,
                            "format": format
                        }
                    )

                    result = await report_agent.execute(task)
                    report_content = result.get("content", "")

                    if not report_content:
                        last_err = Exception("未获取到内容")
                        logger.warning(f"[generate_report] 第 {attempt+1} 次未获取到内容，重试...")
                        continue

                    return report_content
                except Exception as e:
                    last_err = e
                    logger.warning(f"[generate_report] 第 {attempt+1} 次生成失败，重试: {e}")

            return f"报告生成失败: {last_err}"

        except Exception as e:
            logger.error(f"[generate_report] 生成失败: {e}")
            return f"报告生成失败: {e}"


class ModifyReportTool:
    """修改报告工具"""

    def __init__(self):
        self.name = "modify_report"

        self.description = "修改已有报告。可以添加、删除、修改报告内容。"
        self.parameters = {
            "type": "object",
            "properties": {
                "report": {
                    "type": "string",
                    "description": "要修改的原始报告内容"
                },
                "modifications": {
                    "type": "string",
                    "description": "修改要求（自然语言描述）"
                },
                "format": {
                    "type": "string",
                    "description": "输出格式",
                    "enum": ["markdown", "text"],
                    "default": "markdown"
                }
            },
            "required": ["report", "modifications"]
        }
        self.timeout = 300

    async def execute(self, report: str, modifications: str, format: str = "markdown") -> str:
        """修改报告"""
        logger.info(f"[modify_report] 修改要求: {modifications}")

        try:
            from agents import ReportAgent
            report_agent = ReportAgent()
            result = await report_agent.modify_report(report, modifications)
            return result
        except Exception as e:
            logger.error(f"[modify_report] 修改失败: {e}")
            return f"报告修改失败: {e}"


def create_generate_report_tool() -> Tool:
    t = GenerateReportTool()
    return Tool(name=t.name, description=t.description, parameters=t.parameters, execute=t.execute, timeout=t.timeout)


def create_modify_report_tool() -> Tool:
    t = ModifyReportTool()
    return Tool(name=t.name, description=t.description, parameters=t.parameters, execute=t.execute, timeout=t.timeout)