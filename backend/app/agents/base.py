import datetime
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.protocol import A2AMessage
from app.database.models import AgentName, AgentStatus, AgentTrace


class BaseAgent(ABC):
    """所有 Agent 的基类 — 支持 DI session 和 duration_ms 追踪。"""

    def __init__(self):
        self.agent_name: AgentName = NotImplemented
        self.agent_label: str = NotImplemented

    @abstractmethod
    def process(self, message: A2AMessage) -> A2AMessage:
        ...

    def create_trace_record(self, db: Session, case_id: int, input_data: dict) -> int:
        trace = AgentTrace(
            case_id=case_id,
            agent_name=self.agent_name,
            agent_label=self.agent_label,
            status=AgentStatus.RUNNING,
            input_data=input_data,
            started_at=datetime.datetime.utcnow(),
        )
        db.add(trace)
        db.commit()
        db.refresh(trace)
        logger.debug("Agent 开始执行", agent=self.agent_label, case_id=case_id, trace_id=trace.id)
        return trace.id

    def complete_trace(self, db: Session, trace_id: int, output_data: dict, confidence: Optional[float] = None):
        trace = db.query(AgentTrace).filter(AgentTrace.id == trace_id).first()
        if trace:
            now = datetime.datetime.utcnow()
            trace.status = AgentStatus.COMPLETED
            trace.output_data = output_data
            trace.confidence = confidence
            trace.completed_at = now
            if trace.started_at:
                trace.duration_ms = int((now - trace.started_at).total_seconds() * 1000)
            db.commit()
            logger.info("Agent 执行完成", agent=self.agent_label, trace_id=trace_id,
                       confidence=confidence, duration_ms=trace.duration_ms)

    def fail_trace(self, db: Session, trace_id: int, error: str):
        trace = db.query(AgentTrace).filter(AgentTrace.id == trace_id).first()
        if trace:
            now = datetime.datetime.utcnow()
            trace.status = AgentStatus.FAILED
            trace.output_data = {"error": error}
            trace.completed_at = now
            if trace.started_at:
                trace.duration_ms = int((now - trace.started_at).total_seconds() * 1000)
            db.commit()
            logger.error("Agent 执行失败", agent=self.agent_label, trace_id=trace_id, error=error)
