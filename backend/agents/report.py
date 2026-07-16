"""
报告智能体 - 基于提示词模板生成/修改报告
"""
from __future__ import annotations

import json
import logging
import re
from typing import List, Dict, Any

from .base import Agent, Task
from prompts import report as report_prompts

logger = logging.getLogger(__name__)


class ReportAgent(Agent):
    """报告智能体"""

    def __init__(self, llm: Optional[LLM] = None):
        super().__init__("report_agent", llm)

    async def execute(self, task: Task) -> Dict[str, Any]:
        """执行报告生成任务"""
        mode = task.input.get("mode", "auto")
        topic = task.input.get("topic", "")
        content = task.input.get("content", "")
        format = task.input.get("format", "markdown")

        if mode == "document":
            return await self._generate_from_document(content, topic, format)
        elif content:
            # 有内容（搜索结果）→ 基于内容生成
            return await self._generate_from_search(content, topic, format)
        else:
            # 无内容 → 纯 AI 生成
            return await self._generate_from_ai(topic, format)

    async def _generate_from_ai(self, topic: str, format: str) -> Dict[str, Any]:
        """无外部内容时生成报告"""
        prompt = report_prompts.generate_from_ai(topic, format)
        report = await self.think(prompt)
        report = self._extract_and_format_references(report)

        return {
            "topic": topic,
            "mode": "auto",
            "format": format,
            "content": report,
            "sections": self._extract_sections(report)
        }

    async def _generate_from_document(self, content: str, topic: str, format: str) -> Dict[str, Any]:
        """基于文档生成报告"""
        prompt = report_prompts.generate_from_document(content, topic, format)
        report = await self.think(prompt)

        return {
            "topic": topic,
            "mode": "document",
            "format": format,
            "content": report,
            "sections": self._extract_sections(report)
        }

    async def _generate_from_search(self, content: str, topic: str, format: str) -> Dict[str, Any]:
        """基于搜索结果生成报告"""
        prompt = report_prompts.generate_from_search(content, topic, format)
        report = await self.think(prompt)
        report = self._extract_and_format_references(report)

        return {
            "topic": topic,
            "mode": "auto",
            "format": format,
            "content": report,
            "sections": self._extract_sections(report)
        }

    async def modify_report(self, report: str, modifications: str, format: str = "markdown", search_context: str = "") -> Dict[str, Any]:
        """修改报告"""
        prompt = report_prompts.modify_report(report, modifications, format, search_context)
        modified_report = await self.think(prompt)
        modified_report = self._extract_and_format_references(modified_report)

        return {
            "content": modified_report,
            "sections": self._extract_sections(modified_report),
            "modifications_applied": modifications
        }

    def _extract_sections(self, report: str) -> List[Dict[str, str]]:
        """提取报告章节"""
        sections = []
        current_section = None
        current_content = []

        for line in report.split("\n"):
            if line.startswith("#"):
                if current_section:
                    sections.append({
                        "title": current_section,
                        "content": "\n".join(current_content).strip()
                    })
                current_section = line.lstrip("#").strip()
                current_content = []
            else:
                current_content.append(line)

        if current_section:
            sections.append({
                "title": current_section,
                "content": "\n".join(current_content).strip()
            })

        return sections

    def _extract_and_format_references(self, report: str) -> str:
        """从报告末尾提取结构化参考文献 JSON，格式化为 ## 参考文献章节"""
        match = re.search(
            r'__REFS_START__\s*(\[.*?\])\s*__REFS_END__',
            report, re.DOTALL
        )
        if not match:
            return report

        json_str = match.group(1).strip()
        try:
            refs = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(f"[ReportAgent] 参考文献 JSON 解析失败，保留原文")
            return report

        if not isinstance(refs, list) or len(refs) == 0:
            # 空数组或无效格式，直接移除 JSON 块
            return report[:match.start()].rstrip()

        # 格式化为 Markdown 参考文献章节
        lines = ["\n\n## 参考文献\n"]
        for i, ref in enumerate(refs, 1):
            title = ref.get("title", "").strip()
            author = ref.get("author", "").strip()
            year = ref.get("year", "").strip()
            url = ref.get("url", "").strip()

            if not title:
                continue

            # 组装文献描述
            parts = []
            if author:
                parts.append(author)
            if title:
                parts.append(f"*{title}*")
            if year:
                parts.append(f"({year})")
            desc = ". ".join(parts) if parts else title

            # 有 URL 就加链接，没有就只写文献信息
            if url:
                lines.append(f"{i}. {desc}. [查看原文]({url})")
            else:
                lines.append(f"{i}. {desc}.")

        formatted = "\n".join(lines)
        # 替换 JSON 块为格式化的参考文献章节
        cleaned_report = report[:match.start()].rstrip() + formatted
        return cleaned_report
