import datetime
from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName, AgentStatus
from app.database.session import SessionLocal
from app.database.models import Case


class IntakeAgent(BaseAgent):
    """Agent A: 报案受理 - 接收报案信息，初始化案件"""

    def __init__(self):
        self.agent_name = AgentName.A_INTAKE
        self.agent_label = "报案受理"

    def process(self, message: A2AMessage) -> A2AMessage:
        trace_id = self.create_trace_record(message.case_id, message.payload)
        try:
            case_id = message.payload.get("case_id")
            db = SessionLocal()
            try:
                case = db.query(Case).filter(Case.id == case_id).first()
                if not case:
                    raise ValueError("案件不存在")

                output = {
                    "case_id": case_id,
                    "case_no": case.case_no,
                    "insured_name": case.insured_name,
                    "insurance_product": case.insurance_product,
                    "incident_desc": case.incident_desc,
                    "incident_date": case.incident_date.isoformat() if case.incident_date else None,
                    "status": "报案已受理",
                    "validation_passed": True,
                }

                self.complete_trace(trace_id, output, confidence=0.98)
                return A2AMessage(
                    message_id=f"msg_{case_id}_intake_out",
                    source_agent="agent_a_intake",
                    target_agent="agent_b_doc_parser",
                    case_id=case_id,
                    message_type="result_forward",
                    payload=output,
                    confidence=0.98,
                )
            finally:
                db.close()
        except Exception as e:
            self.fail_trace(trace_id, str(e))
            raise
