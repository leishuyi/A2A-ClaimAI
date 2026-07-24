"""意图识别分类器 — 规则 + 关键词匹配

支持 5 种理赔场景意图：
- claim: 报案/报销
- progress: 查进度
- upload: 上传材料
- consult: 咨询条款
- complaint: 投诉

评估指标：准确率(Accuracy)、精确率(Precision)、召回率(Recall)、F1
"""
import re
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class IntentResult:
    intent: str
    confidence: float
    matched_patterns: list[str] = field(default_factory=list)
    extracted_entities: dict = field(default_factory=dict)


class IntentClassifier:
    """意图分类器 — 基于关键词 + 正则规则"""

    INTENTS: ClassVar[list[str]] = ["claim", "progress", "upload", "consult", "complaint"]

    # 关键词规则
    KEYWORD_RULES: ClassVar[dict[str, list[str]]] = {
        "claim": [
            "报销", "理赔", "报案", "赔付", "赔偿", "申请", "医疗费",
            "住院费", "医药费", "看病", "手术", "花费", "花了", "发票",
        ],
        "progress": [
            "进度", "到哪", "查一下", "怎么样了", "结果", "还没好",
            "多久", "什么时候", "查查", "状态", "下来", "到账",
        ],
        "upload": [
            "上传", "补充", "补交", "提交材料", "影像", "拍照",
            "扫描件", "补材料", "补传", "补几张",
        ],
        "consult": [
            "咨询", "能不能报", "可以报销吗", "算不算", "属于", "包含",
            "范围", "规定", "条款", "请问", "什么意思",
        ],
        "complaint": [
            "投诉", "不满", "差评", "态度", "太慢", "投诉电话",
            "举报", "不满意", "太差",
        ],
    }

    # 模式规则（正则，优先级高于关键词）
    PATTERN_RULES: ClassVar[list[tuple[str, str, float]]] = [
        # (模式, 意图, 权重)
        (r"(到哪|到哪了|进度|到哪一步)", "progress", 0.9),
        (r"(能不能|可以…吗|算不算|属于…吗)", "consult", 0.85),
        (r"(投诉|举报|差评|太差)", "complaint", 0.95),
        (r"(上传|补充|补交|补材料)", "upload", 0.9),
    ]

    # 否定模式（降低得分）
    NEGATIVE_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (r".*吗$", "claim"),      # "能报销吗" → 不是claim而是consult
        (r".*(?:能|可以|算).*吗", "claim"),
    ]

    # 实体提取规则
    ENTITY_PATTERNS: ClassVar[dict[str, str]] = {
        r"(\d+(?:\.\d+)?)\s*元": "amount",
        r"(\d+(?:\.\d+)?)\s*块": "amount",
        r"姓[名叫]?\s*(\S{1,4})": "name",
        r"(?:案件|单号|编号)[号:：]?\s*(\S+)": "case_no",
    }

    def classify(self, text: str) -> IntentResult:
        """对输入文本进行意图分类"""
        if not text or not text.strip():
            return IntentResult(intent="claim", confidence=0.0)

        # 1. 先检查模式规则（高优先级）
        for pattern, intent, weight in self.PATTERN_RULES:
            if re.search(pattern, text):
                return IntentResult(
                    intent=intent,
                    confidence=weight,
                    matched_patterns=[f"pattern:{pattern}"],
                    extracted_entities=self._extract_entities(text),
                )

        # 2. 关键词打分
        scores = {intent: 0.0 for intent in self.INTENTS}
        matched_keywords = []
        for intent, keywords in self.KEYWORD_RULES.items():
            for kw in keywords:
                if kw in text:
                    scores[intent] += 1.0
                    matched_keywords.append(kw)

        # 3. 问句惩罚：以"吗/么"结尾或含"能不能/可以...吗"时，优先 consult
        if re.search(r".*[吗么]$", text.strip()):
            scores["claim"] *= 0.2
            scores["consult"] += 2.0
        if re.search(r"(能不能|可不可以|能否|能报销|可以报销)", text):
            scores["claim"] *= 0.2
            scores["consult"] += 2.5
        if re.search(r"(算不算|属于|包含|范围)", text):
            scores["consult"] += 1.0

        # 4. 短文本中性词处理
        if len(text) <= 3 and scores["claim"] > 0 and sum(scores.values()) <= 1:
            scores["claim"] = 0.6

        total = sum(scores.values())
        if total == 0:
            # 无任何匹配时猜测
            if any(c in text for c in ["查", "看", "找", "哪"]):
                return IntentResult(intent="progress", confidence=0.35)
            return IntentResult(intent="claim", confidence=0.3)

        # 5. 取最高分
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]
        sorted_scores = sorted(scores.values(), reverse=True)
        second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0

        # 6. 置信度：区分度越高，置信度越高
        ratio = best_score / total if total > 0 else 0
        margin = (best_score - second_score) / max(best_score, 0.01)
        text_penalty = 0.65 if (len(text) <= 4 and len(matched_keywords) <= 1) else 1.0
        confidence = ratio * (0.5 + 0.5 * min(margin, 1.0)) * text_penalty
        confidence = max(0.3, min(0.98, confidence))

        entities = self._extract_entities(text)
        return IntentResult(
            intent=best_intent,
            confidence=round(confidence, 2),
            matched_patterns=matched_keywords,
            extracted_entities=entities,
        )

    def _extract_entities(self, text: str) -> dict:
        """从文本中提取关键实体"""
        entities = {}
        for pattern, entity_type in self.ENTITY_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                if entity_type not in entities:
                    entities[entity_type] = []
                entities[entity_type].extend(matches[:3])
        return entities

    def predict_batch(self, texts: list[str]) -> list[IntentResult]:
        """批量分类"""
        return [self.classify(t) for t in texts]


class IntentEvaluator:
    """意图评估器 — 计算精度、召回、F1、混淆矩阵"""

    @staticmethod
    def evaluate(
        y_true: list[str],
        y_pred: list[str],
        confidences: list[float] | None = None,
    ) -> dict:
        """计算评估指标"""
        from collections import Counter

        # 获取所有意图标签
        labels = sorted(set(y_true) | set(y_pred))
        n = len(y_true)

        if n == 0:
            return {"accuracy": 0.0, "precision": {}, "recall": {}, "f1": {}, "confusion_matrix": []}

        # 准确率
        correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        accuracy = correct / n

        # 混淆矩阵
        label_to_idx = {l: i for i, l in enumerate(labels)}
        matrix = [[0] * len(labels) for _ in range(len(labels))]
        for t, p in zip(y_true, y_pred):
            matrix[label_to_idx[t]][label_to_idx[p]] += 1

        # 逐标签精确率/召回率/F1
        precision = {}
        recall = {}
        f1 = {}
        for i, label in enumerate(labels):
            tp = matrix[i][i]
            fp = sum(matrix[j][i] for j in range(len(labels)) if j != i)
            fn = sum(matrix[i][j] for j in range(len(labels)) if j != i)

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1_score = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

            precision[label] = round(prec, 4)
            recall[label] = round(rec, 4)
            f1[label] = round(f1_score, 4)

        # 宏观平均
        macro_f1 = sum(f1.values()) / len(f1) if f1 else 0.0

        # 置信度分析（如果提供）
        confidence_analysis = {}
        if confidences:
            correct_conf = [c for c, t, p in zip(confidences, y_true, y_pred) if t == p]
            wrong_conf = [c for c, t, p in zip(confidences, y_true, y_pred) if t != p]
            confidence_analysis = {
                "avg_confidence_correct": round(sum(correct_conf) / len(correct_conf), 4) if correct_conf else 0,
                "avg_confidence_wrong": round(sum(wrong_conf) / len(wrong_conf), 4) if wrong_conf else 0,
                "confidence_gap": round(
                    (sum(correct_conf) / len(correct_conf) - sum(wrong_conf) / len(wrong_conf))
                    if correct_conf and wrong_conf else 0, 4
                ),
            }

        return {
            "total_samples": n,
            "correct": correct,
            "accuracy": round(accuracy, 4),
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "macro_f1": round(macro_f1, 4),
            "labels": labels,
            "confusion_matrix": matrix,
            "confidence_analysis": confidence_analysis,
        }

    @staticmethod
    def print_report(report: dict):
        """打印可读的评估报告"""
        print("=" * 60)
        print(f"意图分类评估报告")
        print("=" * 60)
        print(f"样本数: {report['total_samples']}")
        print(f"准确率: {report['accuracy']:.2%}")
        print(f"Macro F1: {report['macro_f1']:.2%}")
        print()

        # 逐标签指标
        print(f"{'标签':<15} {'精确率':<10} {'召回率':<10} {'F1':<10}")
        print("-" * 45)
        for label in report["labels"]:
            print(f"{label:<15} {report['precision'][label]:.2%}      {report['recall'][label]:.2%}      {report['f1'][label]:.2%}")

        # 混淆矩阵
        print()
        print("混淆矩阵:")
        header = f"{'':>12}" + "".join(f"{l:>8}" for l in report["labels"])
        print(header)
        for i, label in enumerate(report["labels"]):
            row = f"{label:>10}  " + "".join(f"{report['confusion_matrix'][i][j]:>8}" for j in range(len(report["labels"])))
            print(row)

        if report.get("confidence_analysis"):
            ca = report["confidence_analysis"]
            print()
            print("置信度分析:")
            print(f"  正确预测平均置信度: {ca['avg_confidence_correct']:.2%}")
            print(f"  错误预测平均置信度: {ca['avg_confidence_wrong']:.2%}")
            print(f"  置信度差距: {ca['confidence_gap']:.2%}")

        print("=" * 60)
