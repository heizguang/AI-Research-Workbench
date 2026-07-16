"""
快速测试脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """测试模块导入"""
    print("=" * 50)
    print("测试模块导入...")
    print("=" * 50)

    try:
        from backend.core.llm import LLM, get_llm
        print("[OK] LLM模块导入成功")
    except Exception as e:
        print(f"[FAIL] LLM模块导入失败: {e}")
        return False

    try:
        from backend.core.memory import MemoryManager, get_memory_manager
        print("[OK] 记忆系统模块导入成功")
    except Exception as e:
        print(f"[FAIL] 记忆系统模块导入失败: {e}")
        return False

    try:
        from backend.agents import (
            SearchAgent,
            DocumentAgent,
            ReportAgent,
            PPTAgent,
            TopicAnalysisAgent,
            Task,
            TaskType,
            TaskStatus,
        )
        print("[OK] 智能体模块导入成功")
    except Exception as e:
        print(f"[FAIL] 智能体模块导入失败: {e}")
        return False

    try:
        from backend.models.schemas import GenerateReportRequest, ReportMode
        print("[OK] 数据模型导入成功")
    except Exception as e:
        print(f"[FAIL] 数据模型导入失败: {e}")
        return False

    try:
        from backend.services.report_service import ReportService
        print("[OK] 报告服务导入成功")
    except Exception as e:
        print(f"[FAIL] 报告服务导入失败: {e}")
        return False

    try:
        from backend.services.ppt_service import PPTService
        print("[OK] PPT服务导入成功")
    except Exception as e:
        print(f"[FAIL] PPT服务导入失败: {e}")
        return False

    return True


def test_env_config():
    """测试环境变量配置"""
    print("\n" + "=" * 50)
    print("测试环境变量配置...")
    print("=" * 50)

    from dotenv import load_dotenv
    load_dotenv("backend/.env")

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    smart_llm = os.getenv("SMART_LLM")
    tavily_key = os.getenv("TAVILY_API_KEY")

    if api_key:
        print(f"[OK] OPENAI_API_KEY: {api_key[:20]}...")
    else:
        print("[FAIL] OPENAI_API_KEY 未配置")
        return False

    if base_url:
        print(f"[OK] OPENAI_BASE_URL: {base_url}")
    else:
        print("[FAIL] OPENAI_BASE_URL 未配置")

    if smart_llm:
        print(f"[OK] SMART_LLM: {smart_llm}")
    else:
        print("[FAIL] SMART_LLM 未配置")

    if tavily_key:
        print(f"[OK] TAVILY_API_KEY: {tavily_key[:20]}...")
    else:
        print("[FAIL] TAVILY_API_KEY 未配置")

    return True


def test_llm_connection():
    """测试LLM连接"""
    print("\n" + "=" * 50)
    print("测试LLM连接...")
    print("=" * 50)

    import asyncio
    from dotenv import load_dotenv
    load_dotenv("backend/.env")

    async def _test():
        try:
            from backend.core.llm import get_llm
            llm = get_llm()
            print(f"[OK] LLM实例创建成功")
            print(f"   模型: {llm.config.model}")
            print(f"   最大token: {llm.config.max_tokens}")
            return True
        except Exception as e:
            print(f"[FAIL] LLM实例创建失败: {e}")
            return False

    return asyncio.run(_test())


def test_report_service():
    """测试报告服务"""
    print("\n" + "=" * 50)
    print("测试报告服务...")
    print("=" * 50)

    import asyncio
    from backend.services.report_service import ReportService

    async def _test():
        try:
            service = ReportService()

            # 测试Markdown导出
            test_content = "# 测试报告\n\n## 概述\n\n这是一个测试报告。\n\n## 主要内容\n\n- 要点1\n- 要点2"
            file_path = await service.export_report(test_content, "markdown", "test_report")

            if os.path.exists(file_path):
                print(f"[OK] Markdown导出成功: {file_path}")
                # 读取内容验证
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                print(f"   文件大小: {len(content)} 字节")
            else:
                print("[FAIL] Markdown导出失败")
                return False

            return True
        except Exception as e:
            print(f"[FAIL] 报告服务测试失败: {e}")
            return False

    return asyncio.run(_test())


def test_ppt_service():
    """测试PPT服务"""
    print("\n" + "=" * 50)
    print("测试PPT服务...")
    print("=" * 50)

    import asyncio
    from backend.services.ppt_service import PPTService

    async def _test():
        try:
            service = PPTService()

            # 测试PPT生成
            test_content = {
                "total_slides": 3,
                "slides": [
                    {"slide_number": 1, "title": "封面", "content": ["测试PPT"], "notes": "", "layout": "title"},
                    {"slide_number": 2, "title": "内容", "content": ["要点1", "要点2"], "notes": "备注", "layout": "default"},
                    {"slide_number": 3, "title": "结束", "content": ["谢谢"], "notes": "", "layout": "ending"}
                ],
                "style": "professional"
            }

            file_path = await service.create_ppt(test_content, "default", "professional")

            if os.path.exists(file_path):
                print(f"[OK] PPT生成成功: {file_path}")
                file_size = os.path.getsize(file_path)
                print(f"   文件大小: {file_size} 字节")
            else:
                print("[FAIL] PPT生成失败")
                return False

            return True
        except Exception as e:
            print(f"[FAIL] PPT服务测试失败: {e}")
            return False

    return asyncio.run(_test())


def test_agents():
    """测试底层智能体类"""
    print("\n" + "=" * 50)
    print("测试底层智能体...")
    print("=" * 50)

    from dotenv import load_dotenv
    load_dotenv("backend/.env")

    try:
        from backend.agents import (
            SearchAgent,
            DocumentAgent,
            ReportAgent,
            PPTAgent,
            TopicAnalysisAgent,
        )

        # 仅验证类可实例化（不触发实际 LLM / 网络调用）
        agents = {
            "SearchAgent": SearchAgent,
            "DocumentAgent": DocumentAgent,
            "ReportAgent": ReportAgent,
            "PPTAgent": PPTAgent,
            "TopicAnalysisAgent": TopicAnalysisAgent,
        }
        for name, cls in agents.items():
            instance = cls()
            print(f"[OK] {name} 实例化成功")

        return True
    except Exception as e:
        print(f"[FAIL] 智能体测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 50)
    print("多智能体报告生成系统 - 测试")
    print("=" * 50 + "\n")

    results = []

    # 运行测试
    results.append(("模块导入", test_imports()))
    results.append(("环境配置", test_env_config()))
    results.append(("LLM连接", test_llm_connection()))
    results.append(("报告服务", test_report_service()))
    results.append(("PPT服务", test_ppt_service()))
    results.append(("智能体", test_agents()))

    # 打印总结
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)

    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed

    for name, result in results:
        status = "[通过]" if result else "[失败]"
        print(f"{name}: {status}")

    print("\n" + "-" * 50)
    print(f"总计: {len(results)} 项测试")
    print(f"通过: {passed} 项")
    print(f"失败: {failed} 项")
    print("-" * 50)

    if failed == 0:
        print("\n所有测试通过！")
        return 0
    else:
        print(f"\n有 {failed} 项测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
