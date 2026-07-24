"""意图识别评估测试

运行: pytest tests/test_intent_evaluation.py -v
评估: accuracy / precision / recall / f1 / confusion_matrix
"""
import json
import sys
from pathlib import Path

# 确保能找到 app 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.intent_classifier import IntentClassifier, IntentEvaluator
from tests.evaluation_data import build_dataset, get_intent_distribution


class TestIntentClassifier:
    """意图分类器单元测试"""

    def setup_method(self):
        self.classifier = IntentClassifier()

    def test_classify_claim(self):
        result = self.classifier.classify("我要报销医疗费")
        assert result.intent == "claim"
        assert result.confidence > 0.3

    def test_classify_progress(self):
        result = self.classifier.classify("我的理赔到哪了")
        assert result.intent == "progress"
        assert result.confidence > 0.3

    def test_classify_upload(self):
        result = self.classifier.classify("我要上传发票照片")
        assert result.intent == "upload"
        assert result.confidence > 0.3

    def test_classify_consult(self):
        result = self.classifier.classify("这个病能报销吗")
        assert result.intent == "consult"
        assert result.confidence > 0.3

    def test_classify_complaint(self):
        result = self.classifier.classify("我要投诉")
        assert result.intent == "complaint"
        assert result.confidence > 0.3

    def test_empty_text(self):
        result = self.classifier.classify("")
        assert result.intent == "claim"
        assert result.confidence == 0.0

    def test_whitespace_text(self):
        result = self.classifier.classify("   ")
        assert result.intent == "claim"
        assert result.confidence == 0.0

    def test_entity_extraction_amount(self):
        result = self.classifier.classify("住院花了12500元")
        assert "amount" in result.extracted_entities
        assert "12500" in result.extracted_entities["amount"][0]

    def test_batch_classify(self):
        texts = ["我要报销", "查进度", "上传发票"]
        results = self.classifier.predict_batch(texts)
        assert len(results) == 3

    def test_confidence_discrimination(self):
        """高置信度匹配 vs 低置信度匹配"""
        high = self.classifier.classify("我要报销医疗费住院费用")
        low = self.classifier.classify("报销")
        assert high.confidence > low.confidence


class TestIntentEvaluator:
    """评估指标测试"""

    def test_evaluate_perfect(self):
        y_true = ["claim", "progress", "upload"]
        y_pred = ["claim", "progress", "upload"]
        report = IntentEvaluator.evaluate(y_true, y_pred)
        assert report["accuracy"] == 1.0
        assert report["macro_f1"] == 1.0

    def test_evaluate_half(self):
        y_true = ["claim", "progress", "upload", "consult"]
        y_pred = ["claim", "claim", "upload", "consult"]
        report = IntentEvaluator.evaluate(y_true, y_pred)
        assert report["accuracy"] == 0.75

    def test_confusion_matrix_shape(self):
        y_true = ["claim", "progress", "upload"]
        y_pred = ["claim", "progress", "upload"]
        report = IntentEvaluator.evaluate(y_true, y_pred)
        n = len(report["labels"])
        assert len(report["confusion_matrix"]) == n
        assert len(report["confusion_matrix"][0]) == n


# ── 全量评估运行 ──────────────────────────────────────────

def run_full_evaluation(verbose: bool = True) -> dict:
    """在完整数据集上运行评估"""
    classifier = IntentClassifier()
    data = build_dataset(include_edge_cases=True, shuffle=False)

    texts = [item[0] for item in data]
    y_true = [item[1] for item in data]
    results = classifier.predict_batch(texts)
    y_pred = [r.intent for r in results]
    confidences = [r.confidence for r in results]

    report = IntentEvaluator.evaluate(y_true, y_pred, confidences)

    if verbose:
        IntentEvaluator.print_report(report)

    return report


if __name__ == "__main__":
    print("=" * 60)
    print("意图识别评估")
    print("=" * 60)
    data = build_dataset(include_edge_cases=True)
    print(f"数据集大小: {len(data)} 条")
    print(f"意图分布: {get_intent_distribution(data)}")
    print()
    report = run_full_evaluation(verbose=True)

    # 导出 JSON 报告
    report_path = Path(__file__).parent / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已导出: {report_path}")
