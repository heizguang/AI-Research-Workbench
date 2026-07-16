"""
RAG 分类准确率测试脚本
测试两步 LLM 调用中分类步骤的准确率
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

# Windows 终端 UTF-8 支持
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.core.llm import LLM
from backend.prompts.qa import classify


@dataclass
class TestResult:
    """单条测试结果"""
    id: int
    category: str
    question: str
    expected: str
    actual: str
    correct: bool
    reason: str
    latency: float = 0.0


@dataclass
class CategoryStats:
    """分类统计"""
    total: int = 0
    correct: int = 0
    false_positive: int = 0  # 实际不能 -> 判能
    false_negative: int = 0  # 实际能 -> 判不能
    true_positive: int = 0   # 实际能 -> 判能
    true_negative: int = 0   # 实际不能 -> 判不能
    latencies: List[float] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0

    @property
    def precision(self) -> float:
        """精确率：判为'能'的样本中，真正'能'的比例"""
        predicted_positive = self.true_positive + self.false_positive
        return self.true_positive / predicted_positive if predicted_positive > 0 else 0.0

    @property
    def recall(self) -> float:
        """召回率：实际'能'的样本中，被正确判为'能'的比例"""
        actual_positive = self.true_positive + self.false_negative
        return self.true_positive / actual_positive if actual_positive > 0 else 0.0

    @property
    def f1(self) -> float:
        """F1 分数"""
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0


def load_test_data(filepath: str) -> Dict:
    """加载测试数据"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


async def run_single_test(llm: LLM, report: str, question: str, expected: str, mock_mode: bool = False) -> Tuple[str, float]:
    """运行单条测试"""
    if mock_mode:
        # 模拟模式：返回预期结果（用于验证测试集完整性）
        return expected, 0.01

    prompt = classify(report, question)

    start_time = time.time()
    try:
        response = await llm.generate_text_fast(prompt)
        latency = time.time() - start_time

        # 解析结果：检查前 10 个字符中是否包含"不能"
        actual = "不能" if "不能" in response[:10] else "能"
        return actual, latency
    except Exception as e:
        latency = time.time() - start_time
        print(f"  [ERROR] LLM 调用失败: {e}")
        return "error", latency


async def run_test_suite(test_data: Dict, max_cases: int = None) -> List[TestResult]:
    """运行完整测试套件"""
    llm = LLM()
    results = []

    test_cases = test_data["test_cases"]
    if max_cases:
        test_cases = test_cases[:max_cases]

    total_questions = sum(len(tc["questions"]) for tc in test_cases)
    print(f"开始测试：共 {len(test_cases)} 个报告，{total_questions} 个问题")
    print("=" * 80)

    current = 0
    for tc in test_cases:
        report_id = tc["id"]
        category = tc["category"]
        report = tc["report"]

        print(f"\n[{report_id}] {category} ({len(tc['questions'])} 个问题)")

        for q in tc["questions"]:
            current += 1
            question = q["question"]
            expected = q["label"]
            reason = q["reason"]

            actual, latency = await run_single_test(llm, report, question, expected)
            correct = actual == expected

            result = TestResult(
                id=current,
                category=category,
                question=question,
                expected=expected,
                actual=actual,
                correct=correct,
                reason=reason,
                latency=latency
            )
            results.append(result)

            # 输出结果
            status = "✅" if correct else "❌"
            print(f"  {status} [{current:3d}/{total_questions}] {question[:40]:<40s} | 预期: {expected} | 实际: {actual} | {latency:.2f}s")

    return results


def analyze_results(results: List[TestResult]) -> Dict[str, CategoryStats]:
    """分析测试结果"""
    stats = {}

    for r in results:
        # 总体统计
        if "总体" not in stats:
            stats["总体"] = CategoryStats()
        total_stats = stats["总体"]

        # 分类统计
        if r.category not in stats:
            stats[r.category] = CategoryStats()
        cat_stats = stats[r.category]

        for s in [total_stats, cat_stats]:
            s.total += 1
            s.latencies.append(r.latency)

            if r.correct:
                s.correct += 1

            # 混淆矩阵
            if r.expected == "能" and r.actual == "能":
                s.true_positive += 1
            elif r.expected == "能" and r.actual == "不能":
                s.false_negative += 1
            elif r.expected == "不能" and r.actual == "能":
                s.false_positive += 1
            elif r.expected == "不能" and r.actual == "不能":
                s.true_negative += 1

    return stats


def print_report(stats: Dict[str, CategoryStats], results: List[TestResult]):
    """打印测试报告"""
    print("\n" + "=" * 80)
    print("测试报告")
    print("=" * 80)

    # 总体统计
    total = stats["总体"]
    print(f"\n📊 总体统计")
    print(f"  总样本数: {total.total}")
    print(f"  正确数: {total.correct}")
    print(f"  准确率: {total.accuracy:.1%}")
    print(f"  精确率: {total.precision:.1%}")
    print(f"  召回率: {total.recall:.1%}")
    print(f"  F1 分数: {total.f1:.1%}")
    print(f"  平均延迟: {total.avg_latency:.2f}s")

    print(f"\n📋 混淆矩阵")
    print(f"  真阳性 (TP): {total.true_positive} | 实际能 -> 判能")
    print(f"  假阴性 (FN): {total.false_negative} | 实际能 -> 判不能")
    print(f"  假阳性 (FP): {total.false_positive} | 实际不能 -> 判能")
    print(f"  真阴性 (TN): {total.true_negative} | 实际不能 -> 判不能")

    # 分类统计
    print(f"\n📊 分类统计")
    print(f"  {'类别':<12s} | {'样本':>4s} | {'准确率':>6s} | {'精确率':>6s} | {'召回率':>6s} | {'F1':>6s} | {'延迟':>6s}")
    print(f"  {'-'*12}-+-{'-'*4}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}")

    for category, s in sorted(stats.items()):
        if category == "总体":
            continue
        print(f"  {category:<12s} | {s.total:>4d} | {s.accuracy:>5.1%} | {s.precision:>5.1%} | {s.recall:>5.1%} | {s.f1:>5.1%} | {s.avg_latency:>5.2f}s")

    # 错误案例分析
    errors = [r for r in results if not r.correct]
    if errors:
        print(f"\n❌ 错误案例分析 (共 {len(errors)} 条)")
        print(f"  {'#':>3s} | {'类别':<10s} | {'问题':<35s} | {'预期':>4s} | {'实际':>4s}")
        print(f"  {'-'*3}-+-{'-'*10}-+-{'-'*35}-+-{'-'*4}-+-{'-'*4}")

        for e in errors[:20]:  # 最多显示 20 条
            q = e.question[:30] + "..." if len(e.question) > 30 else e.question
            print(f"  {e.id:>3d} | {e.category:<10s} | {q:<35s} | {e.expected:>4s} | {e.actual:>4s}")

        if len(errors) > 20:
            print(f"  ... 还有 {len(errors) - 20} 条错误案例")

    # 误判类型分析
    print(f"\n📊 误判类型分析")

    fp_cases = [r for r in results if r.expected == "不能" and r.actual == "能"]
    fn_cases = [r for r in results if r.expected == "能" and r.actual == "不能"]

    print(f"\n  假阳性 (FP) - 实际不能回答，但判为能回答 ({len(fp_cases)} 条):")
    print(f"  这类错误会导致回答质量下降，可能产生幻觉")
    for e in fp_cases[:5]:
        print(f"    - [{e.category}] {e.question[:40]}...")
        print(f"      原因: {e.reason}")

    print(f"\n  假阴性 (FN) - 实际能回答，但判为不能 ({len(fn_cases)} 条):")
    print(f"  这类错误会导致不必要的搜索，增加延迟")
    for e in fn_cases[:5]:
        print(f"    - [{e.category}] {e.question[:40]}...")
        print(f"      原因: {e.reason}")


def save_results(results: List[TestResult], stats: Dict[str, CategoryStats], output_path: str):
    """保存测试结果"""
    output = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_cases": len(results),
            "accuracy": stats["总体"].accuracy,
            "precision": stats["总体"].precision,
            "recall": stats["总体"].recall,
            "f1": stats["总体"].f1,
            "avg_latency": stats["总体"].avg_latency
        },
        "results": [
            {
                "id": r.id,
                "category": r.category,
                "question": r.question,
                "expected": r.expected,
                "actual": r.actual,
                "correct": r.correct,
                "reason": r.reason,
                "latency": r.latency
            }
            for r in results
        ]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 测试结果已保存到: {output_path}")


async def main():
    """主函数"""
    # 加载测试数据
    test_data_path = Path(__file__).parent / "test_data" / "classification_test_set.json"
    if not test_data_path.exists():
        print(f"错误：测试数据文件不存在: {test_data_path}")
        return

    test_data = load_test_data(str(test_data_path))

    print("=" * 80)
    print("RAG 分类准确率测试")
    print("=" * 80)
    print(f"测试集版本: {test_data['metadata']['version']}")
    print(f"测试集描述: {test_data['metadata']['description']}")
    print(f"总测试用例: {test_data['metadata']['total_pairs']}")

    # 询问是否限制测试数量
    max_cases = None
    if "--quick" in sys.argv:
        max_cases = 2
        print(f"快速模式：只测试前 {max_cases} 个报告")

    # 运行测试
    results = await run_test_suite(test_data, max_cases)

    # 分析结果
    stats = analyze_results(results)

    # 打印报告
    print_report(stats, results)

    # 保存结果
    output_path = Path(__file__).parent / "test_data" / "classification_test_results.json"
    save_results(results, stats, str(output_path))


if __name__ == "__main__":
    asyncio.run(main())
