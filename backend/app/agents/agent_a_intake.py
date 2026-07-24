import datetime
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName, Case, Document


class IntakeAgent(BaseAgent):
    """Agent A: 报案受理 — 收集报案信息 + 影像材料元数据"""

    def __init__(self):
        self.agent_name = AgentName.A_INTAKE
        self.agent_label = "报案受理"

    def process(self, message: A2AMessage, db: Session) -> A2AMessage:
        trace_id = self.create_trace_record(db, message.case_id, message.payload)
        try:
            case_id = message.payload.get("case_id")
            case = db.query(Case).filter(Case.id == case_id).first()
            if not case:
                raise ValueError("案件不存在")

            # 加载影像材料元数据，供后续 Agent 做风控校验
            docs = db.query(Document).filter(Document.case_id == case_id).all()
            documents_meta = []
            for d in docs:
                doc_date = d.document_date.isoformat() if d.document_date else None
                documents_meta.append({
                    "doc_id": d.id,
                    "doc_type": d.doc_type.value if hasattr(d.doc_type, 'value') else str(d.doc_type),
                    "file_name": d.file_name,
                    "extracted_name": d.extracted_name,
                    "invoice_no": d.invoice_no,
                    "document_date": doc_date,
                })

            output = {
                "case_id": case_id,
                "case_no": case.case_no,
                "insured_name": case.insured_name,
                "insurance_product": case.insurance_product,
                "incident_desc": case.incident_desc,
                "incident_date": case.incident_date.isoformat() if case.incident_date else None,
                "total_amount": case.total_amount,
                "documents": documents_meta,
                "status": "报案已受理",
                "validation_passed": True,
            }

            self.complete_trace(db, trace_id, output, confidence=0.98)
            return A2AMessage(
                message_id=f"msg_{case_id}_intake_out",
                source_agent="agent_a_intake",
                target_agent="agent_b_doc_parser",
                case_id=case_id,
                message_type="result_forward",
                payload=output,
                confidence=0.98,
            )
        except Exception as e:
            self.fail_trace(db, trace_id, str(e))
            raise
