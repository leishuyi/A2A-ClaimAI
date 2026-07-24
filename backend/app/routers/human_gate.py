from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import Case, CaseStatus, AuditLog
from app.schemas.human_gate import ReviewRequest, ReviewResponse

router = APIRouter()


@router.post("/{case_id}/review", response_model=ReviewResponse)
def submit_review(case_id: int, data: ReviewRequest, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    if case.status != CaseStatus.PENDING_REVIEW:
        raise HTTPException(400, f"当前案件状态 {case.status.value} 不允许审核，仅待审核状态可操作")

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
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("/{case_id}/review", response_model=list[ReviewResponse])
def get_review_history(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    return db.query(AuditLog).filter(AuditLog.case_id == case_id).order_by(AuditLog.created_at.desc()).all()
