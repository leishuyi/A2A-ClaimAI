import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from loguru import logger
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import Case, CaseStatus, RiskLevel
from app.schemas.case import CaseCreate, CaseResponse
from app.core.response import BizError, ErrCode

router = APIRouter()

CASE_NO_PREFIX = "CL"


def generate_case_no(db: Session) -> str:
    today = datetime.date.today().strftime("%Y%m%d")
    count = (
        db.query(Case)
        .filter(Case.case_no.like(f"{CASE_NO_PREFIX}{today}%"))
        .count()
    )
    return f"{CASE_NO_PREFIX}{today}{count + 1:04d}"


@router.post("", response_model=CaseResponse)
def create_case(data: CaseCreate, db: Session = Depends(get_db)):
    case = Case(
        case_no=generate_case_no(db),
        insured_name=data.insured_name,
        insurance_product=data.insurance_product,
        incident_desc=data.incident_desc,
        incident_date=datetime.datetime.strptime(data.incident_date, "%Y-%m-%d"),
        status=CaseStatus.DRAFT,
        risk_level=RiskLevel.LOW,
        total_amount=data.total_amount,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    logger.info("新建报案", case_no=case.case_no, insured_name=case.insured_name)
    return case


@router.get("", response_model=dict)
def list_cases(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    db: Session = Depends(get_db),
):
    q = db.query(Case).filter(Case.deleted_at.is_(None))

    if status:
        q = q.filter(Case.status == status)

    total = q.count()
    items = (
        q.order_by(Case.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [CaseResponse.model_validate(c) for c in items],
    }


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.deleted_at.is_(None)).first()
    if not case:
        raise BizError(ErrCode.CASE_NOT_FOUND, "案件不存在")
    return case
