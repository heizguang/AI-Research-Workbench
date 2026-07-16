"""
PPT 生成工具 — 复用 PPTSkillService 的完整管道
"""
import logging

from core.tool_registry import Tool

logger = logging.getLogger(__name__)


class GeneratePPTTool:
    """生成 PPT 工具"""

    def __init__(self):
        self.name = "generate_ppt"
        self.description = "根据报告内容生成 PPTX 演示文稿。支持模板选择和样式配置。"
        self.parameters = {
            "type": "object",
            "properties": {
                "report_content": {
                    "type": "string",
                    "description": "报告内容，用于生成 PPT（最大 50000 字符）"
                },
                "template": {
                    "type": "string",
                    "description": "模板名称，默认 default",
                    "default": "default"
                },
                "style": {
                    "type": "string",
                    "description": "样式风格: professional、academic、business",
                    "enum": ["professional", "academic", "business"],
                    "default": "professional"
                },
                "options": {
                    "type": "object",
                    "description": "额外选项（可选）",
                    "default": {}
                }
            },
            "required": ["report_content"]
        }
        self.timeout = 180

    async def execute(self, report_content: str, template: str = "default",
                      style: str = "professional", options: dict = None) -> str:
        """生成 PPT"""
        logger.info(f"[generate_ppt] 模板: {template} | 样式: {style} | 内容长度: {len(report_content)}")

        # 安全约束
        if len(report_content) > 50000:
            return "错误: 报告内容超过 50000 字符限制"

        # 模板白名单
        allowed_templates = {"default", "brand", "academic", "business", "gov"}
        if template not in allowed_templates:
            template = "default"

        try:
            from services.ppt.ppt_skill_service import PPTSkillService
            ppt_service = PPTSkillService()

            result_path = await ppt_service.create_ppt_from_report(
                report_content=report_content,
                template=template,
                style=style,
                options=options or {}
            )

            return f"PPT 已生成: {result_path}"

        except Exception as e:
            logger.error(f"[generate_ppt] 生成失败: {e}")
            return f"PPT 生成失败: {e}"


def create_generate_ppt_tool() -> Tool:
    t = GeneratePPTTool()
    return Tool(name=t.name, description=t.description, parameters=t.parameters, execute=t.execute, timeout=t.timeout)