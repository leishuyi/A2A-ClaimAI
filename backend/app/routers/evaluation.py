"""意图识别路由 — 分类 + 评估指标

- GET /api/v1/intent/classify?text=... → 意图分类 + 实体提取
- GET /api/v1/evaluation/intent       → 评估报告
- POST /api/v1/evaluation/intent/run  → 重新运行评估
"""
import json
from pathlib import Path

from fastapi import APIRouter, Query

from app.core.response import ApiResponse
from app.services.intent_classifier import IntentClassifier
from tests.evaluation_data import build_dataset, get_intent_distribution
from tests.test_intent_evaluation import run_full_evaluation

router = APIRouter()
classifier = IntentClassifier()
REPORT_PATH = Path(__file__).parent.parent.parent / "tests" / "evaluation_report.json"

INTENT_LABELS = {
    "claim": "报案理赔",
    "progress": "进度查询",
    "upload": "材料上传",
    "consult": "咨询条款",
    "complaint": "投诉",
}


@router.get("/intent/classify", response_model=ApiResponse)
def classify_intent(text: str = Query(..., min_length=1, max_length=200)):
    """意图分类：输入自然语言 → 意图类型 + 置信度 + 提取的实体"""
    result = classifier.classify(text)
    return ApiResponse(data={
        "intent": result.intent,
        "intent_label": INTENT_LABELS.get(result.intent, result.intent),
        "confidence": result.confidence,
        "matched_patterns": result.matched_patterns,
        "extracted_entities": result.extracted_entities,
    })


@router.get("/evaluation/intent", response_model=ApiResponse)
def get_intent_evaluation():
    """获取意图识别评估结果"""
    report = run_full_evaluation(verbose=False)
    return ApiResponse(data=report)


@router.post("/evaluation/intent/run", response_model=ApiResponse)
def run_intent_evaluation():
    """重新运行意图识别评估"""
    report = run_full_evaluation(verbose=False)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return ApiResponse(data=report)


@router.get("/evaluation/intent/dataset", response_model=ApiResponse)
def get_evaluation_dataset():
    """获取评估数据集信息"""
    data = build_dataset(include_edge_cases=False)
    dist = get_intent_distribution(data)
    return ApiResponse(data={
        "total": len(data),
        "distribution": dist,
        "samples": [{"text": t[:30], "intent": i} for t, i in data[:10]],
    })
