from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import Case, AgentTrace, CaseStatus
from app.agents.orchestrator import AgentOrchestrator
from app.schemas.agent import AgentTraceResponse
from app.schemas.case import CaseResponse
from app.core.response import BizError, ErrCode

router = APIRouter()
orchestrator = AgentOrchestrator()


@router.post("/{case_id}/run", response_model=dict)
def run_agents(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise BizError(ErrCode.CASE_NOT_FOUND, "案件不存在")
    if case.status not in (CaseStatus.DRAFT, CaseStatus.AGENTS_COMPLETED):
        raise BizError(ErrCode.CASE_INVALID_STATUS, f"当前状态 {case.status.value} 不允许执行 Agent 链路")

    error = orchestrator.run_chain(case_id, db)
    if error:
        raise BizError(50001, error)

    db.refresh(case)
    logger.info("Agent 链路执行完毕", case_id=case_id, case_no=case.case_no)
    return {"message": "Agent 链路执行完成", "case": CaseResponse.model_validate(case)}


@router.get("/{case_id}/traces", response_model=list[AgentTraceResponse])
def get_traces(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise BizError(ErrCode.CASE_NOT_FOUND, "案件不存在")
    return (
        db.query(AgentTrace)
        .filter(AgentTrace.case_id == case_id)
        .order_by(AgentTrace.id)
        .all()
    )
