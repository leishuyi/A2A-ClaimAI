import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import Case, CaseStatus, RiskLevel
from app.schemas.case import CaseCreate, CaseResponse

router = APIRouter()

CASE_NO_PREFIX = "CL"


def generate_case_no(db: Session) -> str:
    today = datetime.date.today().strftime("%Y%m%d")
    count = db.query(Case).filter(Case.case_no.like(f"{CASE_NO_PREFIX}{today}%")).count()
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
    return case


@router.get("", response_model=list[CaseResponse])
def list_cases(db: Session = Depends(get_db)):
    return db.query(Case).order_by(Case.created_at.desc()).all()


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    return case
