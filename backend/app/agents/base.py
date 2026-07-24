from abc import ABC, abstractmethod
from typing import Optional
from app.agents.protocol import A2AMessage
from app.database.models import AgentName, AgentStatus
from app.database.session import SessionLocal


class BaseAgent(ABC):
    """所有 Agent 的基类"""

    def __init__(self):
        self.agent_name: AgentName = NotImplemented
        self.agent_label: str = NotImplemented

    @abstractmethod
    def process(self, message: A2AMessage) -> A2AMessage:
        """处理传入消息，返回输出消息"""
        ...

    def create_trace_record(self, case_id: int, input_data: dict) -> int:
        """在 DB 创建 Agent 执行记录"""
        from app.database.models import AgentTrace

        db = SessionLocal()
        try:
            trace = AgentTrace(
                case_id=case_id,
                agent_name=self.agent_name,
                agent_label=self.agent_label,
                status=AgentStatus.RUNNING,
                input_data=input_data,
                started_at=__import__("datetime").datetime.utcnow(),
            )
            db.add(trace)
            db.commit()
            db.refresh(trace)
            return trace.id
        finally:
            db.close()

    def complete_trace(self, trace_id: int, output_data: dict, confidence: Optional[float] = None):
        """标记 Agent 执行完成"""
        from app.database.models import AgentTrace

        db = SessionLocal()
        try:
            trace = db.query(AgentTrace).filter(AgentTrace.id == trace_id).first()
            if trace:
                trace.status = AgentStatus.COMPLETED
                trace.output_data = output_data
                trace.confidence = confidence
                trace.completed_at = __import__("datetime").datetime.utcnow()
                db.commit()
        finally:
            db.close()

    def fail_trace(self, trace_id: int, error: str):
        """标记 Agent 执行失败"""
        from app.database.models import AgentTrace

        db = SessionLocal()
        try:
            trace = db.query(AgentTrace).filter(AgentTrace.id == trace_id).first()
            if trace:
                trace.status = AgentStatus.FAILED
                trace.output_data = {"error": error}
                trace.completed_at = __import__("datetime").datetime.utcnow()
                db.commit()
        finally:
            db.close()
