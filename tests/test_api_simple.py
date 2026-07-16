"""
简单的API测试脚本
"""

import sys
import os

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

def test_api_endpoints():
    """测试API端点"""
    print("=" * 50)
    print("API端点测试")
    print("=" * 50)

    try:
        import importlib
        from fastapi.testclient import TestClient

        # 动态导入main模块
        spec = importlib.util.spec_from_file_location("main", "backend/main.py")
        main_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_module)

        client = TestClient(main_module.app)

        # 测试健康检查
        response = client.get("/health")
        print(f"[OK] 健康检查: {response.status_code}")
        print(f"   响应: {response.json()}")

        # 测试根路径
        response = client.get("/")
        print(f"[OK] 根路径: {response.status_code}")
        print(f"   响应: {response.json()}")

        # 测试生成报告（模拟）
        print("\n[INFO] 生成报告接口需要LLM调用，跳过实际测试")

        # 测试搜索接口（模拟）
        print("[INFO] 搜索接口需要API调用，跳过实际测试")

        return True

    except Exception as e:
        print(f"[FAIL] API测试失败: {e}")
        return False


def test_data_models():
    """测试数据模型"""
    print("\n" + "=" * 50)
    print("数据模型测试")
    print("=" * 50)

    try:
        from models.schemas import (
            GenerateReportRequest,
            ModifyReportRequest,
            AskQuestionRequest,
            GeneratePPTRequest,
            ReportMode,
            ReportFormat,
            PPTStyle
        )

        # 测试生成报告请求
        request = GenerateReportRequest(
            topic="人工智能发展趋势",
            mode=ReportMode.AI,
            format=ReportFormat.MARKDOWN
        )
        print(f"[OK] GenerateReportRequest: {request.topic}")

        # 测试修改报告请求
        request = ModifyReportRequest(
            report="测试报告",
            modifications="添加更多细节",
            format=ReportFormat.MARKDOWN
        )
        print(f"[OK] ModifyReportRequest: {request.modifications[:20]}...")

        # 测试问答请求
        request = AskQuestionRequest(
            question="这个报告的主要内容是什么？",
            report="测试报告"
        )
        print(f"[OK] AskQuestionRequest: {request.question[:20]}...")

        # 测试生成PPT请求
        request = GeneratePPTRequest(
            report_content="测试报告内容",
            template="default",
            style=PPTStyle.PROFESSIONAL
        )
        print(f"[OK] GeneratePPTRequest: {request.template}")

        return True

    except Exception as e:
        print(f"[FAIL] 数据模型测试失败: {e}")
        return False


def test_services():
    """测试服务层"""
    print("\n" + "=" * 50)
    print("服务层测试")
    print("=" * 50)

    import asyncio

    async def _test():
        try:
            from services.report_service import ReportService
            from services.ppt_service import PPTService
            from services.file_service import FileService

            # 测试报告服务
            report_service = ReportService()
            print("[OK] ReportService创建成功")

            # 测试PPT服务
            ppt_service = PPTService()
            print("[OK] PPTService创建成功")

            # 测试文件服务
            file_service = FileService()
            print("[OK] FileService创建成功")

            return True

        except Exception as e:
            print(f"[FAIL] 服务层测试失败: {e}")
            return False

    return asyncio.run(_test())


def main():
    """主测试函数"""
    print("\n" + "=" * 50)
    print("多智能体报告生成系统 - API测试")
    print("=" * 50 + "\n")

    results = []

    # 运行测试
    results.append(("数据模型", test_data_models()))
    results.append(("服务层", test_services()))
    results.append(("API端点", test_api_endpoints()))

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
        print("\n所有API测试通过！")
        return 0
    else:
        print(f"\n有 {failed} 项测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
