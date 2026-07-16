"""
工具函数模块
提供各种辅助功能
"""

import os
import json
import uuid
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path


def generate_id() -> str:
    """生成唯一ID"""
    return str(uuid.uuid4())


def get_timestamp() -> str:
    """获取当前时间戳"""
    return datetime.now().isoformat()


def ensure_dir(dir_path: str) -> str:
    """确保目录存在"""
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


def read_json(file_path: str) -> Dict[str, Any]:
    """读取JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(data: Dict[str, Any], file_path: str) -> None:
    """写入JSON文件"""
    ensure_dir(os.path.dirname(file_path))
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_filename(filename: str) -> str:
    """清理文件名"""
    # 移除或替换非法字符
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    return filename


def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return os.path.splitext(filename)[1].lower()


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def parse_markdown_sections(content: str) -> list:
    """解析Markdown章节"""
    sections = []
    current_section = None
    current_content = []

    for line in content.split("\n"):
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


def extract_key_points(content: str, max_points: int = 5) -> list:
    """提取关键点"""
    # 简单的关键点提取
    points = []
    lines = content.split("\n")

    for line in lines:
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            points.append(line[2:])
        elif line.startswith("1. ") or line.startswith("2. "):
            points.append(line[3:])

    return points[:max_points]


def validate_topic(topic: str) -> bool:
    """验证主题"""
    if not topic or len(topic.strip()) == 0:
        return False
    if len(topic) > 500:
        return False
    return True


def sanitize_input(text: str) -> str:
    """清理用户输入"""
    # 移除潜在的恶意内容
    text = text.strip()
    # 不截断数据，由 LLM 参数控制输出长度
    return text


class Config:
    """配置管理类"""

    def __init__(self, config_path: str = "./config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        if os.path.exists(self.config_path):
            return read_json(self.config_path)
        return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "llm": {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 4000
            },
            "search": {
                "provider": "serpapi",
                "max_results": 10
            },
            "export": {
                "default_format": "markdown",
                "output_dir": "./data/exports"
            },
            "ppt": {
                "default_template": "default",
                "default_style": "professional"
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        keys = key.split(".")
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def save(self) -> None:
        """保存配置"""
        write_json(self.config, self.config_path)


# 全局配置实例
config = Config()
