from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import Case, AgentTrace
from app.agents.orchestrator import AgentOrchestrator
from app.schemas.agent import AgentTraceResponse
from app.schemas.case import CaseResponse

router = APIRouter()
orchestrator = AgentOrchestrator()


@router.post("/{case_id}/run", response_model=dict)
def run_agents(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    if case.status not in ("draft", "agents_completed"):
        raise HTTPException(400, f"当前案件状态 {case.status} 不允许执行Agent链路")

    error = orchestrator.run_chain(case_id)
    if error:
        raise HTTPException(500, error)

    db.refresh(case)
    return {"message": "Agent 链路执行完成", "case": CaseResponse.model_validate(case)}


@router.get("/{case_id}/traces", response_model=list[AgentTraceResponse])
def get_traces(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    return db.query(AgentTrace).filter(AgentTrace.case_id == case_id).order_by(AgentTrace.id).all()
