"""SSE 进度推送 — 报案提交后实时推送处理进度到前端

使用 Server-Sent Events，前端通过 EventSource 监听。
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from loguru import logger

router = APIRouter()

# 模拟进度状态（生产环境从 Agent 链路读取）
PROGRESS_STEPS = [
    {"step": 1, "label": "报案已提交", "detail": "案件已创建，等待系统处理"},
    {"step": 2, "label": "影像识别中", "detail": "AI 正在识别上传的影像材料"},
    {"step": 3, "label": "核责判断中", "detail": "正在匹配保单条款"},
    {"step": 4, "label": "理算中", "detail": "正在计算赔付金额"},
    {"step": 5, "label": "风控审查中", "detail": "正在进行反欺诈检测"},
    {"step": 6, "label": "结论汇总中", "detail": "正在生成审核报告"},
    {"step": 7, "label": "待审核", "detail": "处理完成，等待核赔人员审核"},
]


@router.get("/cases/{case_id}/progress")
async def stream_progress(case_id: int):
    """SSE 流式推送案件处理进度"""
    async def event_generator():
        for step in PROGRESS_STEPS:
            data = json.dumps({
                "case_id": case_id,
                "step": step["step"],
                "label": step["label"],
                "detail": step["detail"],
                "timestamp": asyncio.get_event_loop().time(),
            }, ensure_ascii=False)
            yield f"data: {data}\n\n"
            await asyncio.sleep(1.5)  # 模拟处理时间
        yield "data: {\"step\": \"done\", \"label\": \"完成\", \"detail\": \"审核报告已生成\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
