"""
SVG 后处理包装器

提供简化的接口用于 SVG 后处理
基于 PPT Master 的 finalize_svg.py 实现
"""

import sys
import shutil
from pathlib import Path

# 添加当前目录到 sys.path
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from svg_finalize.align_embed_images import (
    align_and_embed_images_in_svg,
    count_office_vector_refs_in_svg,
)
from svg_finalize.embed_icons import process_svg_file as embed_icons_in_file


def process_svg_directory(project_path: str, verbose: bool = False) -> None:
    """处理项目目录中的所有 SVG 文件

    处理流程（参考 PPT Master finalize_svg.py）：
    1. 复制 svg_output/ 到 svg_final/
    2. 嵌入图标
    3. 对齐和嵌入图片
    4. 文本扁平化
    5. 圆角矩形转路径

    Args:
        project_path: 项目路径
        verbose: 是否显示详细信息
    """
    project_path = Path(project_path)
    svg_output_dir = project_path / "svg_output"
    svg_final_dir = project_path / "svg_final"

    # 图标目录（相对于 backend/services/ppt/）
    icons_dir = current_dir / "templates" / "icons"

    if not svg_output_dir.exists():
        raise FileNotFoundError(f"未找到 svg_output 目录: {svg_output_dir}")

    svg_files = sorted(svg_output_dir.glob("*.svg"))
    if not svg_files:
        raise FileNotFoundError(f"svg_output 中没有 SVG 文件: {svg_output_dir}")

    if verbose:
        print(f"[SVG 后处理] 找到 {len(svg_files)} 个 SVG 文件")

    # Step 1: 复制 svg_output 到 svg_final
    if svg_final_dir.exists():
        shutil.rmtree(svg_final_dir)
    shutil.copytree(svg_output_dir, svg_final_dir)
    if verbose:
        print(f"[SVG 后处理] 已复制到 svg_final")

    # Step 2: 嵌入图标
    icons_count = 0
    for svg_file in svg_final_dir.glob("*.svg"):
        try:
            count = embed_icons_in_file(
                svg_file, icons_dir, dry_run=False, verbose=False
            )
            icons_count += count
        except Exception as e:
            if verbose:
                print(f"[SVG 后处理] 图标嵌入跳过: {svg_file.name} ({e})")
    if verbose:
        if icons_count > 0:
            print(f"[SVG 后处理] 嵌入 {icons_count} 个图标")
        else:
            print(f"[SVG 后处理] 无图标占位符")

    # Step 3: 对齐和嵌入图片
    img_count = 0
    img_errors = 0
    for svg_file in svg_final_dir.glob("*.svg"):
        try:
            count, errs = align_and_embed_images_in_svg(
                svg_file, dry_run=False, verbose=False
            )
            img_count += count
            img_errors += errs
        except Exception as e:
            if verbose:
                print(f"[SVG 后处理] 图片处理跳过: {svg_file.name} ({e})")
    if verbose:
        if img_count > 0:
            print(f"[SVG 后处理] 处理 {img_count} 张图片 ({img_errors} 错误)")
        else:
            print(f"[SVG 后处理] 无图片")

    if verbose:
        print(f"[SVG 后处理] 完成，输出到: {svg_final_dir}")
