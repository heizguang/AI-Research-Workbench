# -*- coding: utf-8 -*-
"""
PPT Skill 集成测试 - 使用 ppt-polished-deck-collab skill 生成 PPT

按照 skill 的正确工作流：
1. LLM 读取 SKILL.md 理解方法论
2. 读取 slide_specs.yaml 理解每页任务
3. 读取参考文件学习设计规范
4. LLM 直接调用 ppt_asset_helpers.py 逐页构建 PPTX
"""

import os
import sys
import json
import asyncio
import shutil
import subprocess
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent.parent
BACKEND_DIR = ROOT / "backend"
SKILL_DIR = ROOT / "skills" / "ppt-polished-deck-collab"
SCRIPTS_DIR = SKILL_DIR / "scripts"

# 添加路径
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from dotenv import load_dotenv
env_path = BACKEND_DIR / ".env"
if env_path.exists():
    load_dotenv(str(env_path))


def banner(msg):
    print()
    print("=" * 60)
    print(f"  {msg}")
    print("=" * 60)


TEST_OUTLINE = """# GPT系列发展报告：从GPT-5.5的发布到GPT-6的展望

## 1. 摘要
本报告梳理了OpenAI旗下GPT系列在2026年上半年的关键发展。GPT系列正从对话工具向智能体演进，终极目标直指AGI。

## 2. GPT-5.5：已发布最强模型
- 发布时间：2026年4月24日
- Terminal-Bench 2.2得分82.7%，SWE-Bench Pro得分58.6%
- 定价：每百万输入Token 5美元，输出30美元
- 支持100万Token上下文窗口

## 3. GPT-6：即将到来的旗舰
- 代号"Spud"，定档2026年4月14日
- 200万Token上下文（约150万字）
- Symphony原生多模态架构
- 5-6万亿参数MoE稀疏架构
- 综合性能较GPT-5.4提升40%

## 4. 技术演进路径
- GPT-5.5：高效能智能体
- GPT-6：全模态自主执行体
- 共同指向Agent和AGI

## 5. 市场竞争与应用变革
- 竞品：Claude、Gemini同期快速迭代
- 200万Token可简化甚至淘汰RAG架构
- AI从被动回答变为主自主执行

## 6. 结论
GPT-5.5是当前最强模型，GPT-6将颠覆AI应用架构，AI从能生成向能做事跃迁。
"""


async def test_workspace_init():
    """测试1: 工作区初始化"""
    banner("测试1: 工作区初始化")

    workspace = ROOT / "data" / "ppt_projects" / "_skill_test"
    if workspace.exists():
        shutil.rmtree(workspace)

    script = SCRIPTS_DIR / "init_deck_workspace.py"
    cmd = [sys.executable, str(script),
           "--workspace-dir", str(workspace),
           "--title", "GPT系列发展报告",
           "--audience", "AI从业者、技术管理者",
           "--scenario", "技术分享、战略规划"]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"  [FAIL] {result.stderr[:200]}")
        return False, None

    expected = ["brief.md", "deck_narrative.md"]
    for f in expected:
        if (workspace / f).exists():
            print(f"  [OK] {f}")
        else:
            print(f"  [FAIL] {f} 不存在")
            return False, None

    return True, workspace


async def test_narrative_generation(workspace):
    """测试2: LLM 生成叙事文档"""
    banner("测试2: LLM 生成叙事文档")

    import openai

    client = openai.AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

    smart_llm = os.getenv("SMART_LLM", "openai:mimo-v2.5-pro")
    model_name = smart_llm.split(":")[1] if ":" in smart_llm else smart_llm

    # 读取模板
    template = (workspace / "deck_narrative.md").read_text(encoding="utf-8")

    system_prompt = """你是一个专业的 PPT 叙事文档编写专家。

根据用户提供的大纲，编写 deck_narrative.md 文档。

格式要求：
1. YAML frontmatter 必须包含 deck 结构（title, audience, scenario, objective, theme_tokens 等）
2. 使用 ### Sxx | <title> 格式定义每页
3. 每页包含 YAML code block 定义 slide spec（title, reader_question, page_task, reading_mode, archetype, asset_mode, validation_mode, key_message）
4. 每页的 narrative_markdown 中包含具体的、可展示的内容，使用 On-slide Copy 格式
5. 每页至少包含 3-5 个具体的要点或数据

请生成 12-14 页。"""

    user_prompt = f"请根据以下大纲生成 deck_narrative.md：\n\n{TEST_OUTLINE}\n\n模板参考：\n{template[:1000]}"

    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=16000
        )

        content = response.choices[0].message.content
        if content.startswith("```"):
            content = content[content.index("\n")+1:]
        if content.endswith("```"):
            content = content[:-3]

        (workspace / "deck_narrative.md").write_text(content.strip(), encoding="utf-8")
        print(f"  [OK] deck_narrative.md ({len(content)} 字符)")
        return True

    except Exception as e:
        print(f"  [FAIL] {str(e)}")
        return False


async def test_derive_specs(workspace):
    """测试3: 派生 slide_specs.yaml"""
    banner("测试3: 派生 slide_specs.yaml")

    # 修复可能的 frontmatter 问题
    narrative = (workspace / "deck_narrative.md").read_text(encoding="utf-8")
    if narrative.startswith("yaml\n"):
        narrative = narrative[5:]
        (workspace / "deck_narrative.md").write_text(narrative, encoding="utf-8")

    # 检查 frontmatter 是否有 deck 结构
    import re
    match = re.match(r'^---\n(.*?)\n---\n', narrative, re.DOTALL)
    if match:
        import yaml
        fm = yaml.safe_load(match.group(1))
        if 'deck' not in fm:
            # 补充 deck 结构
            new_fm = {
                'deck': {
                    'title': fm.get('title', 'GPT系列发展报告'),
                    'audience': fm.get('audience', 'AI从业者'),
                    'scenario': fm.get('scenario', '技术分享'),
                    'objective': fm.get('objective', '了解GPT系列最新发展'),
                    'source_context': 'no_template',
                    'delivery_context': 'hybrid_review_deck',
                    'communication_profile': 'business_report',
                    'visual_profile': 'corporate_clear',
                    'density_profile': 'balanced_brief',
                    'editability_profile': 'fully_editable',
                    'template_file': None,
                }
            }
            rest = narrative[match.end():]
            narrative = '---\n' + yaml.dump(new_fm, allow_unicode=True, default_flow_style=False) + '---\n' + rest
            (workspace / "deck_narrative.md").write_text(narrative, encoding="utf-8")

    out_yaml = workspace / "build" / "generated" / "slide_specs.yaml"
    script = SCRIPTS_DIR / "derive_slide_specs_from_narrative.py"

    result = subprocess.run(
        [sys.executable, str(script), "--narrative", str(workspace / "deck_narrative.md"), "--out-yaml", str(out_yaml)],
        capture_output=True, text=True, cwd=str(ROOT)
    )

    if result.returncode != 0:
        print(f"  [FAIL] {result.stderr[:300]}")
        return False

    if out_yaml.exists():
        import yaml
        specs = yaml.safe_load(out_yaml.read_text(encoding="utf-8"))
        n = len(specs.get('slides', []))
        print(f"  [OK] slide_specs.yaml ({n} 页)")
        return True
    return False


async def test_generate_ppt_with_llm(workspace):
    """测试4: LLM 读取 skill 方法论，调用 ppt_asset_helpers 生成 PPT"""
    banner("测试4: LLM 使用 skill 生成 PPT")

    import openai

    client = openai.AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

    smart_llm = os.getenv("SMART_LLM", "openai:mimo-v2.5-pro")
    model_name = smart_llm.split(":")[1] if ":" in smart_llm else smart_llm

    # 读取关键文件
    skill_md = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    slide_specs = (workspace / "build" / "generated" / "slide_specs.yaml").read_text(encoding="utf-8")
    helpers_source = (SCRIPTS_DIR / "ppt_asset_helpers.py").read_text(encoding="utf-8")

    # 只取 helpers 的函数签名和说明，避免太长
    import re
    helper_docs = []
    for match in re.finditer(r'def (\w+)\((.*?)\):\s*"""(.*?)"""', helpers_source, re.DOTALL):
        name = match.group(1)
        args = match.group(2)
        doc = match.group(3).strip().split('\n')[0]
        helper_docs.append(f"def {name}({args})  # {doc}")
    helpers_summary = '\n'.join(helper_docs)

    system_prompt = f"""你是一个 PPT 设计专家，正在使用 ppt-polished-deck-collab skill 生成 PPT。

## Skill 方法论要点
{skill_md[:3000]}

## 可用的 ppt_asset_helpers 函数
```python
{helpers_summary}
```

## 你的任务
根据 slide_specs.yaml 中每页的定义，编写一个 Python 脚本来生成完整的 PPTX。

脚本要求：
1. 使用 from ppt_asset_helpers import new_presentation, add_slide_header, add_text_block, add_panel, save_presentation, default_palette, default_typography_tokens
2. 读取 slide_specs.yaml 获取每页信息
3. 为每页添加合适的标题、内容和布局
4. 使用深色主题（所有页面深蓝背景）
5. 保存到 {workspace / 'build' / 'pptx' / 'gpt_report.pptx'}

请直接输出完整的 Python 脚本代码（不要包含 ```python 标记）。"""

    user_prompt = f"""## slide_specs.yaml
```yaml
{slide_specs}
```

请根据上面的 slide_specs，生成一个完整的 Python 脚本来构建 PPTX。
每页都要有标题、关键内容和合适的布局。使用深色主题。"""

    try:
        print(f"  模型: {model_name}")
        print(f"  请求 LLM 生成构建脚本...")

        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=16000
        )

        script_content = response.choices[0].message.content

        # 清理
        if script_content.startswith("```python"):
            script_content = script_content[9:]
        if script_content.startswith("```"):
            script_content = script_content[3:]
        if script_content.endswith("```"):
            script_content = script_content[:-3]
        script_content = script_content.strip()

        # 保存并执行脚本
        script_path = workspace / "build" / "generated" / "build_pptx.py"
        script_path.write_text(script_content, encoding="utf-8")
        print(f"  [OK] 生成构建脚本 ({len(script_content)} 字符)")

        # 执行脚本
        print(f"  执行构建脚本...")
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True,
            cwd=str(SCRIPTS_DIR),  # 在 scripts 目录执行，方便 import ppt_asset_helpers
            timeout=120
        )

        if result.returncode != 0:
            print(f"  [FAIL] 脚本执行失败:")
            print(f"         {result.stderr[:500]}")
            return False

        # 检查输出
        pptx_path = workspace / "build" / "pptx" / "gpt_report.pptx"
        if pptx_path.exists():
            size = pptx_path.stat().st_size
            print(f"  [OK] PPTX 已生成: {pptx_path}")
            print(f"       大小: {size:,} bytes")

            # 复制到 final
            final_path = workspace / "final" / "gpt_report.pptx"
            shutil.copy2(pptx_path, final_path)
            return True
        else:
            print(f"  [FAIL] PPTX 文件未生成")
            if result.stdout:
                print(f"         stdout: {result.stdout[:300]}")
            return False

    except Exception as e:
        print(f"  [FAIL] {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "=" * 60)
    print("  PPT Skill 集成测试")
    print("  使用 ppt-polished-deck-collab skill 生成 PPT")
    print("=" * 60)

    results = {}

    workspace_ok, workspace = await test_workspace_init()
    results["工作区初始化"] = workspace_ok

    results["叙事文档生成"] = await test_narrative_generation(workspace) if workspace_ok else False
    results["Slide Specs 派生"] = await test_derive_specs(workspace) if workspace_ok else False
    results["LLM 使用 Skill 生成 PPT"] = await test_generate_ppt_with_llm(workspace) if workspace_ok else False

    banner("测试结果汇总")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    print(f"\n  总计: {passed}/{total} 通过")

    if workspace:
        pptx = workspace / "final" / "gpt_report.pptx"
        if pptx.exists():
            print(f"\n  PPTX 文件: {pptx}")
    print()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
