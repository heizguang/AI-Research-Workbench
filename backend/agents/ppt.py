"""
PPT 智能体 - 基于 ppt-polished-deck-collab skill 脚本链路的原生 PPTX 生成
"""
from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from .base import Agent, Task

logger = logging.getLogger(__name__)


class PPTAgent(Agent):
    """PPT智能体 - 基于 ppt-polished-deck-collab skill 脚本链路的原生 PPTX 生成"""

    def __init__(self, llm: Optional[LLM] = None):
        super().__init__("ppt_agent", llm)
        self._ppt_service = None

    @property
    def ppt_service(self):
        if self._ppt_service is None:
            from services.ppt.ppt_skill_service import PPTSkillService
            self._ppt_service = PPTSkillService()
        return self._ppt_service

    async def execute(self, task: Task) -> Dict[str, Any]:
        """执行PPT生成任务"""
        import traceback
        report_content = task.input.get("report_content", "")
        template = task.input.get("template", "default")
        style = task.input.get("style", "professional")
        options = task.input.get("options", {})

        logger.info(f"[PPTAgent] 收到 PPT 生成任务 | 模板: {template} | 风格: {style}")
        logger.info(f"[PPTAgent] 输入报告长度: {len(report_content)} 字符")

        try:
            # 使用新的 PPT 服务生成 PPT
            pptx_path = await self.ppt_service.create_ppt_from_report(
                report_content=report_content,
                template=template,
                style=style,
                options=options
            )

            logger.info(f"[PPTAgent] PPT 生成完成: {pptx_path}")
            return {
                "pptx_path": pptx_path,
                "template": template,
                "style": style
            }
        except Exception as e:
            logger.error(f"[PPTAgent] PPT 生成失败: {e}")
            logger.error(f"[PPTAgent] 任务参数: template={template}, style={style}, options={options}")
            logger.error(f"[PPTAgent] 报告内容长度: {len(report_content)} 字符")
            logger.error(f"[PPTAgent] 错误详情: {traceback.format_exc()}")
            raise RuntimeError(f"PPT 生成失败 (模板={template}, 风格={style}): {e}") from e
