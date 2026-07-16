"""
国际化模块
支持多语言
"""

from typing import Dict, Any, Optional
import json
import os
from dotenv import load_dotenv

load_dotenv()

# 支持的语言
SUPPORTED_LANGUAGES = ["zh", "en"]
DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "chinese")

# 语言映射
LANGUAGE_MAP = {
    "chinese": "zh",
    "english": "en"
}


class I18n:
    """国际化类"""

    def __init__(self, lang: Optional[str] = None):
        self.lang = lang or DEFAULT_LANGUAGE

        # 转换语言代码
        if self.lang in LANGUAGE_MAP:
            self.lang = LANGUAGE_MAP[self.lang]

        # 加载翻译
        self.translations = self._load_translations()

    def _load_translations(self) -> Dict[str, Dict[str, str]]:
        """加载翻译文件"""
        translations = {
            "zh": {
                # 通用
                "success": "成功",
                "error": "错误",
                "failed": "失败",
                "loading": "加载中...",
                "please_wait": "请稍候...",

                # 报告生成
                "report.generate": "生成报告",
                "report.generating": "正在生成报告...",
                "report.success": "报告生成成功",
                "report.failed": "报告生成失败",
                "report.modify": "修改报告",
                "report.modifying": "正在修改报告...",
                "report.modify.success": "报告修改成功",
                "report.export": "导出报告",
                "report.export.success": "报告导出成功",

                # 搜索
                "search.title": "网络搜索",
                "search.searching": "正在搜索...",
                "search.success": "搜索完成",
                "search.failed": "搜索失败",
                "search.no_results": "未找到相关结果",

                # 文档
                "document.upload": "上传文档",
                "document.uploading": "正在上传...",
                "document.upload.success": "文档上传成功",
                "document.analyze": "分析文档",
                "document.analyzing": "正在分析文档...",
                "document.analyze.success": "文档分析完成",

                # PPT
                "ppt.generate": "生成PPT",
                "ppt.generating": "正在生成PPT...",
                "ppt.success": "PPT生成成功",
                "ppt.download": "下载PPT",

                # 问答
                "qa.title": "智能问答",
                "qa.ask": "提问",
                "qa.asking": "正在思考...",
                "qa.answer.success": "回答生成成功",

                # 记忆
                "memory.save": "保存记忆",
                "memory.search": "搜索记忆",
                "memory.searching": "正在搜索记忆...",

                # 历史
                "history.title": "历史记录",
                "history.conversation": "对话历史",
                "history.qa": "问答历史",
                "history.memory": "记忆搜索",

                # 用户认证
                "auth.register": "注册",
                "auth.login": "登录",
                "auth.logout": "退出",
                "auth.register.success": "注册成功",
                "auth.login.success": "登录成功",
                "auth.username.exists": "用户名已存在",
                "auth.password.error": "用户名或密码错误",
                "auth.token.invalid": "无效的认证令牌",

                # 模式
                "mode.ai": "自动模式",
                "mode.document": "文档分析模式",
                "mode.search": "自动模式",

                # 格式
                "format.markdown": "Markdown",
                "format.word": "Word",
                "format.pdf": "PDF",

                # 样式
                "style.professional": "专业风格",
                "style.creative": "创意风格",
                "style.minimal": "简约风格",

                # 错误消息
                "error.server": "服务器错误",
                "error.not_found": "未找到",
                "error.unauthorized": "未授权",
                "error.forbidden": "禁止访问",
                "error.bad_request": "请求错误",
                "error.timeout": "请求超时",
                "error.network": "网络错误",
            },
            "en": {
                # General
                "success": "Success",
                "error": "Error",
                "failed": "Failed",
                "loading": "Loading...",
                "please_wait": "Please wait...",

                # Report
                "report.generate": "Generate Report",
                "report.generating": "Generating report...",
                "report.success": "Report generated successfully",
                "report.failed": "Failed to generate report",
                "report.modify": "Modify Report",
                "report.modifying": "Modifying report...",
                "report.modify.success": "Report modified successfully",
                "report.export": "Export Report",
                "report.export.success": "Report exported successfully",

                # Search
                "search.title": "Web Search",
                "search.searching": "Searching...",
                "search.success": "Search completed",
                "search.failed": "Search failed",
                "search.no_results": "No results found",

                # Document
                "document.upload": "Upload Document",
                "document.uploading": "Uploading...",
                "document.upload.success": "Document uploaded successfully",
                "document.analyze": "Analyze Document",
                "document.analyzing": "Analyzing document...",
                "document.analyze.success": "Document analysis completed",

                # PPT
                "ppt.generate": "Generate PPT",
                "ppt.generating": "Generating PPT...",
                "ppt.success": "PPT generated successfully",
                "ppt.download": "Download PPT",

                # QA
                "qa.title": "Smart Q&A",
                "qa.ask": "Ask",
                "qa.asking": "Thinking...",
                "qa.answer.success": "Answer generated successfully",

                # Memory
                "memory.save": "Save Memory",
                "memory.search": "Search Memory",
                "memory.searching": "Searching memory...",

                # History
                "history.title": "History",
                "history.conversation": "Conversation History",
                "history.qa": "Q&A History",
                "history.memory": "Memory Search",

                # Auth
                "auth.register": "Register",
                "auth.login": "Login",
                "auth.logout": "Logout",
                "auth.register.success": "Registration successful",
                "auth.login.success": "Login successful",
                "auth.username.exists": "Username already exists",
                "auth.password.error": "Invalid username or password",
                "auth.token.invalid": "Invalid authentication token",

                # Modes
                "mode.ai": "Auto Mode",
                "mode.document": "Document Analysis Mode",
                "mode.search": "Auto Mode",

                # Formats
                "format.markdown": "Markdown",
                "format.word": "Word",
                "format.pdf": "PDF",

                # Styles
                "style.professional": "Professional",
                "style.creative": "Creative",
                "style.minimal": "Minimal",

                # Error messages
                "error.server": "Server Error",
                "error.not_found": "Not Found",
                "error.unauthorized": "Unauthorized",
                "error.forbidden": "Forbidden",
                "error.bad_request": "Bad Request",
                "error.timeout": "Request Timeout",
                "error.network": "Network Error",
            }
        }

        return translations

    def get(self, key: str, **kwargs) -> str:
        """获取翻译"""
        lang_translations = self.translations.get(self.lang, {})
        text = lang_translations.get(key, key)

        # 替换变量
        if kwargs:
            for k, v in kwargs.items():
                text = text.replace(f"{{{k}}}", str(v))

        return text

    def t(self, key: str, **kwargs) -> str:
        """翻译的简写"""
        return self.get(key, **kwargs)


# 全局实例
_i18n_instance = None


def get_i18n(lang: Optional[str] = None) -> I18n:
    """获取I18n实例"""
    global _i18n_instance
    if lang or _i18n_instance is None:
        _i18n_instance = I18n(lang)
    return _i18n_instance


def t(key: str, **kwargs) -> str:
    """翻译函数的快捷方式"""
    return get_i18n().t(key, **kwargs)
