import hashlib
import datetime

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import Case, CaseStatus, AuditLog
from app.schemas.human_gate import ReviewRequest, ReviewResponse
from app.core.response import BizError, ErrCode

router = APIRouter()


def _idempotency_key(case_id: int, action: str, operator: str) -> str:
    """生成幂等键，防止重复审核提交。"""
    raw = f"{case_id}:{action}:{operator}:{datetime.date.today().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@router.post("/{case_id}/review", response_model=ReviewResponse)
def submit_review(case_id: int, data: ReviewRequest, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise BizError(ErrCode.CASE_NOT_FOUND, "案件不存在")
    if case.status != CaseStatus.PENDING_REVIEW:
        raise BizError(ErrCode.CASE_INVALID_STATUS, f"当前状态 {case.status.value} 不允许审核")

    # 幂等检查：同一天同一操作人同一操作不可重复提交
    ikey = _idempotency_key(case_id, data.action, data.operator)
    existing = db.query(AuditLog).filter(AuditLog.idempotency_key == ikey).first()
    if existing:
        logger.warning("重复审核请求已拦截", case_id=case_id, action=data.action, operator=data.operator)
        return existing

    action_map = {
        "approve": CaseStatus.APPROVED,
        "reject": CaseStatus.REJECTED,
        "modify": CaseStatus.APPROVED,
    }
    case.status = action_map[data.action]

    if data.action == "modify" and data.modified_amount is not None:
        case.calculated_amount = data.modified_amount

    log = AuditLog(
        case_id=case_id,
        action=data.action,
        comment=data.comment,
        operator=data.operator,
        idempotency_key=ikey,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    logger.info("人工审核完成", case_id=case_id, case_no=case.case_no,
                action=data.action, operator=data.operator)
    return log


@router.get("/{case_id}/review", response_model=list[ReviewResponse])
def get_review_history(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise BizError(ErrCode.CASE_NOT_FOUND, "案件不存在")
    return (
        db.query(AuditLog)
        .filter(AuditLog.case_id == case_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )
