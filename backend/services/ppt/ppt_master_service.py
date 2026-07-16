"""
PPT Master Service - 基于 ppt-polished-deck-collab skill 的 PPT 生成服务

流程：报告内容 → 创建项目 → LLM 生成设计规范 → LLM 逐页生成 SVG → 后处理脚本 → 导出 PPTX
"""

import os
import json
import time
import logging
import subprocess
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# 路径配置
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SKILL_DIR = PROJECT_ROOT / "skills" / "ppt-polished-deck-collab"
SCRIPTS_DIR = SKILL_DIR / "scripts"
REFERENCES_DIR = SKILL_DIR / "references"
TEMPLATES_DIR = SKILL_DIR / "templates"


def _get_llm():
    """延迟导入LLM模块并创建实例"""
    import openai
    from dotenv import load_dotenv

    backend_dir = Path(__file__).parent.parent.parent
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(str(env_path))

    smart_llm = os.getenv("SMART_LLM", "openai:mimo-v2.5-pro")
    if ":" in smart_llm:
        model_name = smart_llm.split(":")[1]
    else:
        model_name = smart_llm

    class LLMConfig:
        def __init__(self, model=None, temperature=0.7, max_tokens=8000):
            self.model = model or model_name
            self.temperature = temperature
            self.max_tokens = max_tokens

    class LLMInstance:
        def __init__(self):
            self.config = LLMConfig()
            self.client = openai.AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            )

        async def generate_text(self, prompt, system_prompt=None, config=None):
            cfg = config or self.config
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat.completions.create(
                model=cfg.model,
                messages=messages,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens
            )
            return response.choices[0].message.content

    return LLMInstance(), LLMConfig


# ───────────────────── 风格配置 ─────────────────────

STYLE_PRESETS = {
    "professional": {
        "mode": "briefing",
        "visual_style": "swiss-minimal",
        "colors": {
            "bg": "#FFFFFF",
            "secondary_bg": "#F5F7FA",
            "primary": "#00529B",
            "accent": "#FF9800",
            "secondary_accent": "#0078D4",
            "text": "#212121",
            "text_secondary": "#757575",
            "border": "#E0E0E0",
        }
    },
    "creative": {
        "mode": "showcase",
        "visual_style": "gradient-glow",
        "colors": {
            "bg": "#FFFFFF",
            "secondary_bg": "#FFF9F5",
            "primary": "#FF5722",
            "accent": "#4CAF50",
            "secondary_accent": "#FF9800",
            "text": "#212121",
            "text_secondary": "#757575",
            "border": "#E0E0E0",
        }
    },
    "minimal": {
        "mode": "briefing",
        "visual_style": "dense-editorial",
        "colors": {
            "bg": "#FFFFFF",
            "secondary_bg": "#F8F8F8",
            "primary": "#212121",
            "accent": "#C8C8C8",
            "secondary_accent": "#424242",
            "text": "#212121",
            "text_secondary": "#969696",
            "border": "#E0E0E0",
        }
    },
}


class PPTMasterService:
    """基于 ppt-master skill 的 PPT 生成服务"""

    def __init__(self, output_dir: str = "./data/ppt"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir = PROJECT_ROOT / "data" / "ppt_projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def _load_reference_files(self, mode: str = "briefing", visual_style: str = "swiss-minimal") -> dict:
        """完整加载 ppt-master skill 的参考文件（不截断）"""
        logger.info(f"[PPT Master] ── 完整加载 skill 参考文件 ──")
        refs = {}
        ref_dir = SKILL_DIR / "references"

        # 核心参考文件 — 完整加载
        for name, key in [
            ("shared-standards.md", "shared-standards"),
            ("executor-base.md", "executor-base"),
            ("strategist.md", "strategist"),
        ]:
            path = ref_dir / name
            if path.exists():
                refs[key] = path.read_text(encoding="utf-8")
                logger.info(f"[PPT Master]   ✓ {name} ({len(refs[key])} 字)")
            else:
                logger.warning(f"[PPT Master]   ✗ {name} 不存在: {path}")

        # 模式参考 — 完整加载
        mode_path = ref_dir / "modes" / f"{mode}.md"
        if mode_path.exists():
            refs["mode"] = mode_path.read_text(encoding="utf-8")
            logger.info(f"[PPT Master]   ✓ modes/{mode}.md ({len(refs['mode'])} 字)")
        else:
            logger.warning(f"[PPT Master]   ✗ modes/{mode}.md 不存在")

        # 视觉风格参考 — 完整加载
        style_path = ref_dir / "visual-styles" / f"{visual_style}.md"
        if style_path.exists():
            refs["visual_style"] = style_path.read_text(encoding="utf-8")
            logger.info(f"[PPT Master]   ✓ visual-styles/{visual_style}.md ({len(refs['visual_style'])} 字)")
        else:
            logger.warning(f"[PPT Master]   ✗ visual-styles/{visual_style}.md 不存在")

        total_chars = sum(len(v) for v in refs.values())
        logger.info(f"[PPT Master] 参考文件加载完成: {len(refs)} 个文件, 共 {total_chars} 字")
        return refs

    async def create_ppt_from_report(
        self,
        report_content: str,
        template: str = "default",
        style: str = "professional",
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """从报告内容创建 PPT（基于 ppt-master 流程）"""
        options = options or {}
        start_time = time.time()

        logger.info(f"[PPT Master] ========== 开始生成 PPT ==========")
        logger.info(f"[PPT Master] 配置 | 模板: {template} | 风格: {style}")

        # 0. 完整加载 skill 参考文件
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["professional"])
        reference_files = self._load_reference_files(
            mode=preset["mode"],
            visual_style=preset["visual_style"]
        )

        # 1. 初始化项目
        project_path = self._init_project(template, style)
        logger.info(f"[PPT Master] 项目初始化: {project_path}")

        # 2. 写入源内容
        self._import_source(project_path, report_content)
        logger.info(f"[PPT Master] 源内容写入完成")

        # 3. LLM 生成设计规范 (Strategist)
        logger.info(f"[PPT Master] 开始 Strategist 阶段...")
        await self._strategist_phase(project_path, report_content, style, options,
                                      reference_files=reference_files)
        logger.info(f"[PPT Master] Strategist 阶段完成")

        # 4. LLM 逐页生成 SVG (Executor)
        logger.info(f"[PPT Master] 开始 Executor 阶段...")
        await self._executor_phase(project_path, report_content,
                                    reference_files=reference_files)
        logger.info(f"[PPT Master] Executor 阶段完成")

        # 5. 后处理脚本
        logger.info(f"[PPT Master] 开始后处理...")
        pptx_path = self._post_process(project_path, style)

        # 6. 复制 SVG 文件到输出目录用于预览
        self._copy_svgs_for_preview(project_path, pptx_path)
        logger.info(f"[PPT Master] 后处理完成")

        total_time = time.time() - start_time
        logger.info(f"[PPT Master] PPT 生成完成 | 耗时: {total_time:.2f}s | 文件: {pptx_path}")
        logger.info(f"[PPT Master] ========== PPT 生成结束 ==========")

        return str(pptx_path)

    def _init_project(self, template: str, style: str) -> Path:
        """初始化 ppt-master 项目"""
        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        project_name = f"report_{template}_{style}_{date_str}"
        project_path = self.projects_dir / project_name

        # 使用 project_manager.py 初始化
        cmd = [
            "python", str(SCRIPTS_DIR / "project_manager.py"),
            "init", project_name,
            "--format", "ppt169",
            "--dir", str(self.projects_dir)
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=str(SKILL_DIR)
            )
            if result.returncode != 0:
                logger.warning(f"[PPT Master] project_manager init 返回非零: {result.stderr}")
                # 手动创建目录结构
                self._create_project_structure(project_path)
        except Exception as e:
            logger.warning(f"[PPT Master] project_manager 调用失败: {e}, 手动创建")
            self._create_project_structure(project_path)

        return project_path

    def _create_project_structure(self, project_path: Path):
        """手动创建项目目录结构"""
        dirs = ["sources", "images", "svg_output", "svg_final", "notes", "templates"]
        for d in dirs:
            (project_path / d).mkdir(parents=True, exist_ok=True)

    def _import_source(self, project_path: Path, report_content: str):
        """将报告内容写入 sources/ 目录"""
        sources_dir = project_path / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        source_file = sources_dir / "report.md"
        source_file.write_text(report_content, encoding="utf-8")

    async def _strategist_phase(
        self, project_path: Path, report_content: str,
        style: str, options: Dict[str, Any],
        reference_files: dict = None
    ):
        """Strategist 阶段：使用完整的 strategist.md 生成 design_spec.md 和 spec_lock.md"""
        logger.info(f"[PPT Master] ── Strategist 阶段开始 ──")
        llm, LLMConfig = _get_llm()

        # 获取风格预设
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["professional"])
        colors = preset["colors"]
        mode = preset["mode"]
        visual_style = preset["visual_style"]
        logger.info(f"[PPT Master]   风格预设: mode={mode}, visual_style={visual_style}")
        logger.info(f"[PPT Master]   颜色: primary={colors['primary']}, accent={colors['accent']}")

        # 应用自定义颜色
        if options.get("color_scheme") == "custom" and options.get("custom_colors"):
            custom = options["custom_colors"]
            for key in ["primary", "secondary", "accent"]:
                if key in custom:
                    colors[key] = custom[key]

        # 从报告中提取大纲结构
        outline = self._extract_outline(report_content)
        page_count = len(outline)

        # 构建 page_outline
        page_outline_lines = []
        for i, page in enumerate(outline):
            pnum = f"P{i+1:02d}"
            page_outline_lines.append(f"- {pnum}: {page['title']} | {page['type']} | {page.get('content', '')}")
        page_outline = "\n".join(page_outline_lines)

        # 构建完整的 Strategist system_prompt（包含完整 strategist.md）
        strategist_ref = reference_files.get("strategist", "") if reference_files else ""

        system_prompt = f"""你是 PPT 设计策略师（Strategist）。你的任务是根据报告内容，生成 PPT 的设计规范。

## 你的角色定义（来自 ppt-master skill）
{strategist_ref}

## 风格预设
- 模式: {mode}
- 视觉风格: {visual_style}
- 颜色方案: {json.dumps(colors, ensure_ascii=False)}

## 你的输出
你需要生成两个文件：

1. **spec_lock.md** — Executor 的执行锁定文件，必须包含：
   - canvas, mode, visual_style, colors, typography, icons
   - page_count, page_rhythm（每页 anchor/dense/breathing）
   - page_layouts, page_charts, images

2. **design_spec.md** — 人类可读的设计规范

请以 JSON 格式输出：
```json
{{
  "spec_lock": "spec_lock.md 的完整内容",
  "design_spec": "design_spec.md 的完整内容"
}}
```

## 关键规则
1. 颜色值必须是 HEX 格式（如 #00529B），不要用 rgba
2. page_rhythm 必须为每一页指定 anchor/dense/breathing
3. anchor 用于封面和结尾页，breathing 用于需要视觉呼吸的页面，dense 用于信息密集的页面
4. 字体大小从 body 基线按比例推导（body=22, title=1.5-2x body, annotation=0.7-0.85x body）
5. 颜色需要完整的中性色集（surface, grid, scrim, overlay, block-shade）
"""

        user_prompt = f"""请根据以下报告内容，生成 PPT 设计规范。

报告大纲（共 {page_count} 页）：
{page_outline}

报告内容：
{report_content}

请输出 JSON 格式的设计规范。"""

        try:
            logger.info(f"[PPT Master]   调用 LLM 生成 spec_lock.md + design_spec.md (model={llm.config.model})...")
            logger.info(f"[PPT Master]   system_prompt 大小: {len(system_prompt)} 字")
            llm_start = time.time()
            response = None
            for attempt in range(3):
                response = await llm.generate_text(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    config=LLMConfig(temperature=0.7, max_tokens=8000)
                )
                if response and response.strip():
                    break
                logger.warning(f"[PPT Master]   LLM 返回空内容，重试 {attempt+1}/3...")
            llm_elapsed = time.time() - llm_start
            logger.info(f"[PPT Master]   LLM 响应完成 | 耗时: {llm_elapsed:.1f}s | 响应长度: {len(response)} 字")

            # 解析 JSON 响应
            json_str = response
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            spec_lock_content = ""
            design_spec_content = ""

            try:
                result = json.loads(json_str.strip())
                spec_lock_content = result.get("spec_lock", "")
                design_spec_content = result.get("design_spec", "")
                logger.info(f"[PPT Master]   JSON 解析成功")
            except json.JSONDecodeError:
                # JSON 解析失败，尝试从响应中提取 spec_lock 内容
                logger.warning(f"[PPT Master]   JSON 解析失败，尝试提取 spec_lock 内容")
                # 尝试找到 spec_lock 的 markdown 内容
                import re
                # 方法1：从 JSON 字符串中提取 "spec_lock": "..." 的值
                m = re.search(r'"spec_lock"\s*:\s*"((?:[^"\\]|\\.)*)"', response, re.DOTALL)
                if m:
                    spec_lock_content = m.group(1).replace('\\n', '\n').replace('\\"', '"')
                    logger.info(f"[PPT Master]   从 JSON 中提取到 spec_lock ({len(spec_lock_content)} 字)")
                else:
                    # 方法2：如果响应包含 # Execution Lock，直接使用
                    if "# Execution Lock" in response:
                        spec_lock_content = response[response.index("# Execution Lock"):]
                        logger.info(f"[PPT Master]   从响应中提取到 spec_lock ({len(spec_lock_content)} 字)")
                    else:
                        # 方法3：使用默认 spec_lock
                        logger.error(f"[PPT Master]   无法提取 spec_lock，使用默认值")
                        spec_lock_content = self._build_default_spec_lock(colors, mode, visual_style, outline)

            # 清理 spec_lock 内容
            if "```" in spec_lock_content:
                lines = spec_lock_content.split("\n")
                clean_lines = []
                in_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_block = not in_block
                        continue
                    if in_block or not line.strip().startswith("```"):
                        clean_lines.append(line)
                spec_lock_content = "\n".join(clean_lines)

            spec_lock_content = spec_lock_content.strip()
            if "# Execution Lock" not in spec_lock_content:
                spec_lock_content = f"# Execution Lock\n\n{spec_lock_content}"

            # 写入 spec_lock.md
            spec_lock_file = project_path / "spec_lock.md"
            spec_lock_file.write_text(spec_lock_content, encoding="utf-8")
            logger.info(f"[PPT Master]   spec_lock.md 已写入 ({len(spec_lock_content)} 字)")
            logger.info(f"[PPT Master]   spec_lock 前 5 行:")
            for line in spec_lock_content.split("\n")[:5]:
                logger.info(f"[PPT Master]     {line}")

            # 写入 design_spec.md
            if design_spec_content:
                design_spec_file = project_path / "design_spec.md"
                design_spec_file.write_text(design_spec_content, encoding="utf-8")
                logger.info(f"[PPT Master]   design_spec.md 已写入 ({len(design_spec_content)} 字)")
            else:
                # 生成简单的 design_spec.md
                design_spec_lines = [f"# PPT Design Specification\n"]
                design_spec_lines.append(f"## Canvas\n- Format: PPT 16:9 (1280×720)\n")
                design_spec_lines.append(f"## Style\n- Mode: {mode}\n- Visual Style: {visual_style}\n")
                design_spec_lines.append(f"## Color Scheme\n")
                for k, v in colors.items():
                    design_spec_lines.append(f"- {k}: {v}")
                design_spec_lines.append(f"\n## Content Outline\n")
                for i, page in enumerate(outline):
                    design_spec_lines.append(f"- P{i+1:02d}: {page['title']} ({page['type']})")
                design_spec_file = project_path / "design_spec.md"
                design_spec_file.write_text("\n".join(design_spec_lines), encoding="utf-8")

            logger.info(f"[PPT Master] Strategist 阶段完成")

        except Exception as e:
            logger.error(f"[PPT Master] Strategist 阶段失败: {e}")
            raise RuntimeError(f"Strategist 阶段失败: {e}") from e

    def _generate_default_spec_lock(
        self, project_path: Path, style: str,
        colors: Dict[str, str], outline: List[Dict]
    ):
        """生成默认的 spec_lock.md（兜底）"""
        raise RuntimeError("Strategist 阶段失败，无法生成 spec_lock.md")

    def _build_default_spec_lock(self, colors, mode, visual_style, outline):
        """构建默认的 spec_lock.md 内容（兜底）"""
        page_rhythm_lines = []
        for i, page in enumerate(outline):
            pnum = f"P{i+1:02d}"
            if page["type"] == "cover":
                page_rhythm_lines.append(f"- {pnum}: anchor")
            elif page["type"] == "ending":
                page_rhythm_lines.append(f"- {pnum}: anchor")
            elif page["type"] == "toc":
                page_rhythm_lines.append(f"- {pnum}: breathing")
            elif i % 3 == 0:
                page_rhythm_lines.append(f"- {pnum}: breathing")
            else:
                page_rhythm_lines.append(f"- {pnum}: dense")

        return f"""# Execution Lock

## canvas
- viewBox: 0 0 1280 720
- format: PPT 16:9

## mode
- mode: {mode}

## visual_style
- visual_style: {visual_style}

## colors
- bg: {colors['bg']}
- primary: {colors['primary']}
- accent: {colors['accent']}
- secondary_accent: {colors['secondary_accent']}
- text: {colors['text']}
- text_secondary: {colors['text_secondary']}
- border: {colors['border']}

## typography
- font_family: "Microsoft YaHei", Arial, sans-serif
- body: 22
- title: 32
- subtitle: 24
- annotation: 14

## icons
- library: chunk-filled

## page_count
- count: {len(outline)}

## page_rhythm
{chr(10).join(page_rhythm_lines)}

## page_layouts

## page_charts

## images
"""

    def _extract_outline(self, report_content: str) -> List[Dict[str, Any]]:
        """从报告中提取大纲结构

        支持多级标题，每个标题都生成独立页面：
        - # 标题 → 报告标题
        - ## 标题 → 章节页面
        - ### 标题 → 章节页面
        - #### 标题 → 章节页面
        """
        lines = report_content.split("\n")
        sections = []
        current_section = None
        current_content = []

        def _clean_title(t: str) -> str:
            """清理标题中的 markdown 格式"""
            import re
            t = t.replace("**", "").replace("*", "").strip()
            t = re.sub(r'^\d+[\.\、]\s*', '', t)  # 去掉开头数字编号
            return t.strip()

        def _clean_content(c: str) -> str:
            """清理内容中的 markdown 格式"""
            import re
            c = c.replace("**", "").replace("*", "").strip()
            c = re.sub(r'【来源:.*?】', '', c)  # 去掉来源标注
            c = re.sub(r'\n{3,}', '\n\n', c)  # 合并多余空行
            return c.strip()

        for line in lines:
            stripped = line.strip()

            # 跳过参考来源等章节
            if any(kw in stripped for kw in ["参考来源", "参考文献", "报告说明"]):
                if current_section:
                    current_section["content"] = _clean_content("\n".join(current_content))
                    sections.append(current_section)
                current_section = None
                current_content = []
                continue

            # 识别标题：优先匹配 markdown 标题（## ### ####），
            # 如果没有 markdown 标题，则匹配编号标题（1. / 2. / 2.1 / 3. 等）
            is_heading = False
            for prefix in ["#### ", "### ", "## "]:
                if stripped.startswith(prefix):
                    is_heading = True
                    if current_section:
                        current_section["content"] = _clean_content("\n".join(current_content))
                        sections.append(current_section)
                    title = _clean_title(stripped)
                    current_section = {"title": title, "content": ""}
                    current_content = []
                    break

            # 兜底：匹配编号标题（如 "1. 摘要" "2.1 已发布的模型"）
            if not is_heading and not stripped.startswith("#"):
                import re
                # 匹配 "数字. 标题" 或 "数字.数字 标题" 模式，且标题长度合理
                m = re.match(r'^(\d+(?:\.\d+)*)\s+(.{2,})$', stripped)
                if m and len(stripped) < 80:
                    # 排除列表项（通常较短且不像是标题）
                    num_part = m.group(1)
                    title_part = m.group(2).strip()
                    # 只有一级和二级编号作为章节标题（1. / 2. / 2.1 / 3.1 等）
                    # 三级编号（2.1.1）及更深层不作为独立章节
                    if num_part.count(".") <= 1 and len(title_part) > 3:
                        is_heading = True
                        if current_section:
                            current_section["content"] = _clean_content("\n".join(current_content))
                            sections.append(current_section)
                        current_section = {"title": title_part, "content": ""}
                        current_content = []

            # 普通内容行
            if not is_heading and current_section and stripped:
                # 提取要点（- 或 * 或数字列表）
                if stripped.startswith(("- ", "* ")):
                    point = stripped.lstrip("- *").strip()
                    point = point.replace("**", "").replace("*", "").strip()
                    current_content.append(f"• {point}")
                elif stripped[0:1].isdigit() and ". " in stripped[:6]:
                    point = stripped.split(". ", 1)[-1].strip() if ". " in stripped else stripped
                    point = point.replace("**", "").replace("*", "").strip()
                    current_content.append(f"• {point}")
                elif not stripped.startswith("#"):
                    current_content.append(stripped)

        # 保存最后一个章节
        if current_section:
            current_section["content"] = _clean_content("\n".join(current_content))
            sections.append(current_section)

        # 提取报告标题
        report_title = ""
        for line in lines:
            if line.startswith("# ") and not line.startswith("## "):
                report_title = _clean_title(line)
                break

        # 如果没有找到 markdown 标题，尝试从第一行非空内容提取
        if not report_title:
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and len(stripped) < 60:
                    # 如果第一行像标题（不含句号结尾，较短）
                    if not stripped.endswith("。") and not stripped.endswith("；"):
                        report_title = stripped
                        break

        # 最后兜底
        if not report_title and sections:
            report_title = sections[0]["title"]

        # 构建大纲
        outline = []
        outline.append({"title": report_title or "报告", "type": "cover"})
        outline.append({
            "title": "目录",
            "type": "toc",
            "items": [s["title"] for s in sections]
        })
        for section in sections:
            outline.append({
                "title": section["title"],
                "type": "content",
                "content": section["content"]
            })
        outline.append({"title": "感谢观看", "type": "ending"})

        return outline[:25]

    async def _executor_phase(self, project_path: Path, report_content: str,
                               reference_files: dict = None):
        """Executor 阶段：逐页生成 SVG"""
        logger.info(f"[PPT Master] ── Executor 阶段开始 ──")
        llm, LLMConfig = _get_llm()

        # 读取 spec_lock.md
        spec_lock_file = project_path / "spec_lock.md"
        spec_lock = spec_lock_file.read_text(encoding="utf-8") if spec_lock_file.exists() else ""
        logger.info(f"[PPT Master]   spec_lock.md 已读取 ({len(spec_lock)} 字)")
        if reference_files:
            logger.info(f"[PPT Master]   参考文件已就绪: {list(reference_files.keys())}")

        # 提取大纲
        outline = self._extract_outline(report_content)
        svg_output_dir = project_path / "svg_output"
        svg_output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[PPT Master]   大纲提取完成: 共 {len(outline)} 页")
        for i, page in enumerate(outline):
            logger.info(f"[PPT Master]     P{i+1:02d}: [{page['type']}] {page['title']}")

        # 逐页生成 SVG
        executor_start = time.time()
        for i, page in enumerate(outline):
            page_num = i + 1
            page_type = page["type"]
            title = page["title"]

            page_start = time.time()
            logger.info(f"[PPT Master] ── 生成第 {page_num}/{len(outline)} 页 ──")
            logger.info(f"[PPT Master]   类型: {page_type} | 标题: {title}")

            svg_content = await self._generate_page_svg(
                llm, LLMConfig, spec_lock, page, page_num, len(outline), report_content,
                reference_files=reference_files
            )

            # 写入 SVG 文件
            safe_title = "".join(c for c in title if c.isalnum() or c in "_ -")[:30]
            svg_filename = f"{page_num:02d}_{safe_title}.svg"
            svg_file = svg_output_dir / svg_filename
            svg_file.write_text(svg_content, encoding="utf-8")

            page_elapsed = time.time() - page_start
            logger.info(f"[PPT Master]   第 {page_num} 页完成: {svg_filename} | 耗时: {page_elapsed:.1f}s | SVG 大小: {len(svg_content)} 字")

        executor_elapsed = time.time() - executor_start
        logger.info(f"[PPT Master] Executor 阶段完成 | 共 {len(outline)} 页 | 总耗时: {executor_elapsed:.1f}s")

    async def _generate_page_svg(
        self, llm, LLMConfig, spec_lock: str,
        page: Dict[str, Any], page_num: int, total_pages: int,
        report_content: str,
        reference_files: dict = None
    ) -> str:
        """生成单页 SVG，使用完整的 ppt-master skill 参考文件"""
        page_type = page["type"]
        title = page["title"]

        # 从 spec_lock 提取颜色
        colors = self._parse_colors_from_spec_lock(spec_lock)

        # 从 spec_lock 提取当前页面的 rhythm
        page_rhythm = "dense"
        pnum = f"P{page_num:02d}"
        for line in spec_lock.split("\n"):
            if line.strip().startswith(f"- {pnum}:"):
                page_rhythm = line.split(":")[-1].strip()
                break

        # 构建完整的 system_prompt（包含完整的 skill 参考文件）
        shared_standards = reference_files.get("shared-standards", "") if reference_files else ""
        executor_base = reference_files.get("executor-base", "") if reference_files else ""
        mode_ref = reference_files.get("mode", "") if reference_files else ""
        visual_style_ref = reference_files.get("visual_style", "") if reference_files else ""

        system_prompt = f"""你是一个专业的 SVG 页面设计师（Executor）。你的任务是为 PPT 生成高质量的 SVG 页面。

## 技术规范（来自 shared-standards.md）
{shared_standards}

## 执行规范（来自 executor-base.md）
{executor_base}

## 视觉风格
{visual_style_ref}

## 叙事模式
{mode_ref}

## spec_lock 定义
{spec_lock}

## 当前页面
- 页面类型: {page_type}
- 页码: {page_num}/{total_pages}
- 页面节奏: {page_rhythm}

## 输出要求
- 输出纯 SVG 代码，不要包含 ```xml 或 ``` 标记
- SVG 必须是合法的 XML
- 每个 <text> 元素的 <tspan> 不能有 x/y/dy 属性
- 遵循 Single Logical Line 规则
- 遵循页面节奏（{page_rhythm}）的布局要求
"""

        if page_type == "cover":
            user_prompt = f"""生成封面页 SVG：
标题: {title}
副标题: {page.get('subtitle', 'AI Generated Report')}

要求：
- 大标题居中，使用 primary 颜色
- 副标题在下方
- 底部添加装饰色块
- 底部显示 "多智能体报告生成系统 · AI Generated"
"""

        elif page_type == "toc":
            items = page.get("items", [])
            items_text = "\n".join([f"{j+1}. {item}" for j, item in enumerate(items)])
            user_prompt = f"""生成目录页 SVG：
标题: 目录
章节列表:
{items_text}

要求：
- 左侧有装饰色条
- 编号使用圆形背景
- 清晰的层级结构
"""

        elif page_type == "ending":
            user_prompt = f"""生成结束页 SVG：
标题: 感谢观看
副标题: 欢迎提问与交流

要求：
- 全屏 primary 颜色背景
- 白色文字居中
- 底部显示 "多智能体报告生成系统 · AI Generated"
"""

        else:  # content
            content = page.get("content", "")
            # 清理内容
            import re
            content = content.replace("**", "").replace("*", "").strip()
            content = re.sub(r'【来源:.*?】', '', content)

            # 提取要点
            points = []
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith(("• ", "- ", "* ")):
                    points.append(line.lstrip("• - *").strip())
                elif line[0:1].isdigit() and ". " in line[:6]:
                    points.append(line.split(". ", 1)[-1].strip() if ". " in line else line)
                elif len(line) > 10:
                    points.append(line)
            points = points[:6]  # 最多6个要点

            user_prompt = f"""生成内容页 SVG：
标题: {title}
要点内容（必须全部展示在 SVG 中）:
{chr(10).join([f'{i+1}. {p}' for i, p in enumerate(points)])}

页码: {page_num - 1}/{total_pages - 2}

要求：
- 顶部有 primary 颜色色条
- 左侧有装饰色条
- 标题使用 primary 颜色，下方有 accent 装饰线
- 每个要点用编号圆形 + 文字展示
- 要点文字必须完整显示，不能省略
- 右下角显示页码
"""

        try:
            logger.info(f"[PPT Master]     调用 LLM 生成 SVG (第{page_num}页, model={llm.config.model})...")
            llm_start = time.time()
            response = None
            for attempt in range(3):
                response = await llm.generate_text(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    config=LLMConfig(temperature=0.7, max_tokens=8000)
                )
                if response and response.strip():
                    break
                logger.warning(f"[PPT Master]     LLM 返回空内容，重试 {attempt+1}/3...")
            llm_elapsed = time.time() - llm_start
            logger.info(f"[PPT Master]     LLM 响应完成 | 耗时: {llm_elapsed:.1f}s | 响应长度: {len(response) if response else 0} 字")

            # 提取 SVG 代码
            svg_content = response
            if "```svg" in svg_content:
                svg_content = svg_content.split("```svg")[1].split("```")[0]
            elif "```xml" in svg_content:
                svg_content = svg_content.split("```xml")[1].split("```")[0]
            elif "```" in svg_content:
                svg_content = svg_content.split("```")[1].split("```")[0]

            svg_content = svg_content.strip()

            logger.info(f"[PPT Master] LLM 原始 SVG (第{page_num}页):")
            logger.info(f"[PPT Master] --- SVG 开始 ---")
            for line in svg_content.split("\n")[:30]:  # 只打印前30行
                logger.info(f"[PPT Master] {line}")
            if svg_content.count("\n") > 30:
                logger.info(f"[PPT Master] ... (共 {svg_content.count(chr(10))+1} 行)")
            logger.info(f"[PPT Master] --- SVG 结束 ---")

            # 确保有正确的 SVG 声明和 viewBox
            if not svg_content.startswith("<svg"):
                svg_content = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">\n{svg_content}\n</svg>'
                logger.info(f"[PPT Master]     补充了 SVG 声明")

            # 强制修正 viewBox 和 width/height 为 1280x720
            import re
            svg_content = re.sub(r'viewBox="[^"]*"', 'viewBox="0 0 1280 720"', svg_content)
            svg_content = re.sub(r'width="1920"', 'width="1280"', svg_content)
            svg_content = re.sub(r'height="1080"', 'height="720"', svg_content)

            # 第一步：去掉所有 XML 注释（中文注释会导致解析失败）
            import re
            svg_before = svg_content
            svg_content = re.sub(r'<!--[\s\S]*?-->', '', svg_content)
            if svg_content != svg_before:
                logger.info(f"[PPT Master]     清理步骤 1: 去除 XML 注释")

            # 第二步：用 XML 解析器清理 text 元素内容中的 markdown 符号
            svg_before = svg_content
            svg_content = self._clean_svg_text_content(svg_content)
            if svg_content != svg_before:
                logger.info(f"[PPT Master]     清理步骤 2: 清理 markdown 符号")

            # 第三步：清理空行
            svg_before = svg_content
            svg_content = re.sub(r'\n\s*\n', '\n', svg_content)
            if svg_content != svg_before:
                logger.info(f"[PPT Master]     清理步骤 3: 清理空行")

            # 第四步：展平 tspan（将多行 tspan 拆成独立 text 元素）
            svg_before = svg_content
            svg_content = self._flatten_tspans_in_svg(svg_content)
            if svg_content != svg_before:
                logger.info(f"[PPT Master]     清理步骤 4: 展平 tspan → 独立 text 元素")

            # 验证 SVG 是否为合法 XML
            try:
                from xml.etree.ElementTree import fromstring
                fromstring(svg_content)
                logger.info(f"[PPT Master] SVG XML 验证通过 (第{page_num}页)")
            except Exception as e:
                logger.error(f"[PPT Master] SVG XML 验证失败 (第{page_num}页): {e}")
                raise RuntimeError(f"第{page_num}页 SVG XML 验证失败: {e}") from e

            return svg_content

        except Exception as e:
            logger.error(f"[PPT Master] SVG 生成失败 (第{page_num}页): {e}")
            raise

    def _parse_colors_from_spec_lock(self, spec_lock: str) -> Dict[str, str]:
        """从 spec_lock.md 解析颜色"""
        colors = {
            "bg": "#FFFFFF",
            "primary": "#00529B",
            "accent": "#FF9800",
            "secondary_accent": "#0078D4",
            "text": "#212121",
            "text_secondary": "#757575",
            "border": "#E0E0E0",
        }
        for line in spec_lock.split("\n"):
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                parts = line[2:].split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key in colors and value.startswith("#"):
                        colors[key] = value
        return colors

    @staticmethod
    def _clean_svg_text_content(svg_content: str) -> str:
        """清理 SVG text 元素中的 markdown 符号，保留 tspan 标签结构。

        使用 XML 解析器而非正则，避免把 <tspan> 标签转义成纯文本。
        """
        import re
        from xml.etree import ElementTree as ET

        try:
            root = ET.fromstring(svg_content)
        except ET.ParseError:
            # XML 不合法时原样返回，让后续验证报错
            return svg_content

        ns = "http://www.w3.org/2000/svg"
        changed = False

        for text_el in root.iter(f"{{{ns}}}text"):
            # 清理 text 元素自身的直接文本
            if text_el.text:
                cleaned = text_el.text
                cleaned = re.sub(r'^#{1,6}\s*', '', cleaned)  # 去掉标题符号
                cleaned = cleaned.replace("**", "").replace("*", "")
                if cleaned != text_el.text:
                    text_el.text = cleaned
                    changed = True

            # 清理每个 tspan 的文本
            for tspan in text_el.iter(f"{{{ns}}}tspan"):
                if tspan.text:
                    cleaned = tspan.text
                    cleaned = re.sub(r'^#{1,6}\s*', '', cleaned)
                    cleaned = cleaned.replace("**", "").replace("*", "")
                    if cleaned != tspan.text:
                        tspan.text = cleaned
                        changed = True

        if changed:
            logger.info(f"[PPT Master]       _clean_svg_text_content: 清理了 markdown 符号")
            return ET.tostring(root, encoding="unicode", xml_declaration=False)
        return svg_content

    @staticmethod
    def _flatten_tspans_in_svg(svg_content: str) -> str:
        """将 SVG 中的多行 tspan 展平为独立的 text 元素。

        DrawingML 无法在同一个段落内重新定位，所以带 x/y/dy 的 tspan
        必须拆成独立的 <text> 元素。
        """
        from xml.etree import ElementTree as ET

        ns = "http://www.w3.org/2000/svg"
        try:
            root = ET.fromstring(svg_content)
        except ET.ParseError:
            return svg_content

        def _get_num(el, attr):
            val = el.get(attr)
            if val is None:
                return None
            try:
                return float(val.strip().split()[0].rstrip(","))
            except (ValueError, IndexError):
                return None

        def _copy_style(src, dst):
            """复制 text 元素的样式属性到新的 text 元素"""
            style_attrs = [
                "font-family", "font-size", "font-weight", "font-style",
                "fill", "fill-opacity", "stroke", "stroke-width",
                "text-anchor", "dominant-baseline", "opacity",
                "text-decoration", "letter-spacing",
            ]
            for attr in style_attrs:
                val = src.get(attr)
                if val is not None:
                    dst.set(attr, val)

        changed = False
        # 收集需要处理的 text 元素（避免迭代时修改）
        text_elements = list(root.iter(f"{{{ns}}}text"))

        for text_el in text_elements:
            # 检查是否有 tspan 子元素需要展平
            tspans = list(text_el.iter(f"{{{ns}}}tspan"))
            if not tspans:
                continue

            # 检查是否有 positional tspan（需要展平的）
            needs_flatten = False
            for tspan in tspans:
                if _get_num(tspan, "y") is not None:
                    needs_flatten = True
                    break
                dy = _get_num(tspan, "dy")
                if dy is not None and dy != 0:
                    needs_flatten = True
                    break
                if _get_num(tspan, "x") is not None:
                    needs_flatten = True
                    break

            if not needs_flatten:
                continue

            # 找到父元素
            parent = None
            for p in root.iter():
                for c in p:
                    if c is text_el:
                        parent = p
                        break
                if parent is not None:
                    break
            if parent is None:
                parent = root

            # 获取 text 元素在父元素中的位置
            idx = list(parent).index(text_el)

            # 为每个 tspan 创建独立的 text 元素
            new_texts = []
            # text 元素自身的直接文本（tspan 之前）
            if text_el.text and text_el.text.strip():
                new_t = ET.SubElement(root, f"{{{ns}}}text")
                _copy_style(text_el, new_t)
                new_t.text = text_el.text.strip()
                new_texts.append(new_t)

            for tspan in tspans:
                new_t = ET.SubElement(root, f"{{{ns}}}text")
                _copy_style(text_el, new_t)
                # tspan 的属性覆盖 text 的属性
                for attr in ["x", "y", "dx", "dy"]:
                    val = tspan.get(attr)
                    if val is not None:
                        new_t.set(attr, val)
                # tspan 自身的样式
                for attr in ["font-size", "font-weight", "fill", "text-anchor"]:
                    val = tspan.get(attr)
                    if val is not None:
                        new_t.set(attr, val)
                new_t.text = tspan.text or ""
                new_texts.append(new_t)

            # 从 root 移除新的 text 元素（它们被自动添加到了末尾）
            for nt in new_texts:
                root.remove(nt)

            # 插入到原来的位置
            for j, nt in enumerate(new_texts):
                parent.insert(idx + j, nt)

            # 移除原始 text 元素
            parent.remove(text_el)
            changed = True

        if changed:
            logger.info(f"[PPT Master]       _flatten_tspans_in_svg: 展平了 positional tspan")
            return ET.tostring(root, encoding="unicode", xml_declaration=False)
        return svg_content

    def _post_process(self, project_path: Path, style: str) -> Path:
        """运行后处理脚本，导出 PPTX"""
        logger.info(f"[PPT Master] ── 后处理阶段开始 ──")
        post_start = time.time()

        # 7.1 分割演讲笔记（如果存在 total.md）
        notes_dir = project_path / "notes"
        total_md = notes_dir / "total.md"
        if total_md.exists():
            logger.info(f"[PPT Master]   7.1 分割演讲笔记...")
            step_start = time.time()
            try:
                cmd = ["python", str(SCRIPTS_DIR / "total_md_split.py"), str(project_path)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(SKILL_DIR))
                step_elapsed = time.time() - step_start
                if result.returncode != 0:
                    logger.warning(f"[PPT Master]   7.1 total_md_split 返回非零: {result.stderr[:200]} | 耗时: {step_elapsed:.1f}s")
                else:
                    logger.info(f"[PPT Master]   7.1 total_md_split 完成 | 耗时: {step_elapsed:.1f}s")
            except Exception as e:
                logger.warning(f"[PPT Master]   7.1 total_md_split 失败: {e}")
        else:
            logger.info(f"[PPT Master]   7.1 跳过演讲笔记（total.md 不存在）")

        # 7.2 SVG 后处理
        logger.info(f"[PPT Master]   7.2 SVG 后处理 (finalize_svg.py)...")
        step_start = time.time()
        try:
            cmd = ["python", str(SCRIPTS_DIR / "finalize_svg.py"), str(project_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(SKILL_DIR))
            step_elapsed = time.time() - step_start
            if result.returncode != 0:
                logger.warning(f"[PPT Master]   7.2 finalize_svg 返回非零 (code={result.returncode}) | 耗时: {step_elapsed:.1f}s")
                if result.stderr:
                    logger.warning(f"[PPT Master]   7.2 stderr: {result.stderr[:300]}")
                if result.stdout:
                    logger.info(f"[PPT Master]   7.2 stdout: {result.stdout[:300]}")
            else:
                logger.info(f"[PPT Master]   7.2 finalize_svg 完成 | 耗时: {step_elapsed:.1f}s")
        except Exception as e:
            logger.warning(f"[PPT Master]   7.2 finalize_svg 异常: {e}")

        # 7.3 导出 PPTX
        logger.info(f"[PPT Master]   7.3 导出 PPTX (svg_to_pptx.py)...")
        step_start = time.time()
        cmd = ["python", str(SCRIPTS_DIR / "svg_to_pptx.py"), str(project_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(SKILL_DIR))
        step_elapsed = time.time() - step_start
        if result.returncode != 0:
            stderr = result.stderr
            logger.error(f"[PPT Master]   7.3 svg_to_pptx 失败 (code={result.returncode}) | 耗时: {step_elapsed:.1f}s")
            logger.error(f"[PPT Master]   7.3 stderr: {stderr[:500]}")
            if result.stdout:
                logger.error(f"[PPT Master]   7.3 stdout: {result.stdout[:500]}")
            raise RuntimeError(f"svg_to_pptx 转换失败: {stderr[:300]}")
        else:
            logger.info(f"[PPT Master]   7.3 svg_to_pptx 完成 | 耗时: {step_elapsed:.1f}s")
            if result.stdout:
                # 输出 svg_to_pptx 的关键信息
                for line in result.stdout.split("\n"):
                    if line.strip() and ("Mode:" in line or "file:" in line or "Output" in line or "Slide" in line):
                        logger.info(f"[PPT Master]   7.3 {line.strip()}")

        # 查找生成的 PPTX 文件
        exports_dir = project_path / "exports"
        if exports_dir.exists():
            pptx_files = list(exports_dir.glob("*.pptx"))
            logger.info(f"[PPT Master]   exports/ 目录: {len(pptx_files)} 个 PPTX 文件")
            if pptx_files:
                src = pptx_files[0]
                date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                dst = self.output_dir / f"pptmaster_{style}_{date_str}.pptx"
                shutil.copy2(str(src), str(dst))
                post_elapsed = time.time() - post_start
                file_size = dst.stat().st_size
                logger.info(f"[PPT Master]   PPTX 复制完成: {dst.name} ({file_size/1024:.1f} KB)")
                logger.info(f"[PPT Master] 后处理阶段完成 | 总耗时: {post_elapsed:.1f}s")
                return dst
        else:
            logger.error(f"[PPT Master]   exports/ 目录不存在")

        raise RuntimeError("svg_to_pptx 完成但未找到导出的 PPTX 文件")

    def _copy_svgs_for_preview(self, project_path: Path, pptx_path: Path):
        """复制 SVG 文件到 PPT 输出目录，用于前端预览"""
        svg_output_dir = project_path / "svg_output"
        svg_final_dir = project_path / "svg_final"

        # 优先使用 svg_final（后处理后的），否则用 svg_output
        src_dir = svg_final_dir if svg_final_dir.exists() and list(svg_final_dir.glob("*.svg")) else svg_output_dir

        if not src_dir.exists():
            return

        # 在 PPTX 文件同目录创建 preview 文件夹
        preview_dir = pptx_path.parent / f"{pptx_path.stem}_preview"
        preview_dir.mkdir(parents=True, exist_ok=True)

        # 复制所有 SVG 文件
        for svg_file in sorted(src_dir.glob("*.svg")):
            dst = preview_dir / svg_file.name
            shutil.copy2(str(svg_file), str(dst))

        logger.info(f"[PPT Master] 预览文件已保存: {preview_dir} ({len(list(preview_dir.glob('*.svg')))} 页)")
