import random
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName


class DocParserAgent(BaseAgent):
    """Agent B: 材料解析 — 模拟 OCR + 多模态信息提取"""

    def __init__(self):
        self.agent_name = AgentName.B_DOC_PARSER
        self.agent_label = "材料解析"

    def process(self, message: A2AMessage, db: Session) -> A2AMessage:
        trace_id = self.create_trace_record(db, message.case_id, message.payload)
        try:
            case_id = message.payload.get("case_id")
            insured = message.payload.get("insured_name", "未知")
            incident_desc = message.payload.get("incident_desc", "")

            extracted = {
                "case_id": case_id,
                "insured_name": insured,
                "documents_parsed": [
                    {"type": "身份证", "status": "已识别", "confidence": round(random.uniform(0.95, 0.99), 2)},
                    {"type": "诊断证明", "status": "已识别", "confidence": round(random.uniform(0.90, 0.98), 2)},
                    {"type": "费用发票", "status": "已识别", "confidence": round(random.uniform(0.92, 0.97), 2)},
                    {"type": "住院病历", "status": "已识别", "confidence": round(random.uniform(0.78, 0.92), 2)},
                ],
                "diagnosis": self._extract_diagnosis(incident_desc),
                "medical_total": round(random.uniform(3000, 50000), 2),
                "hospital_name": "模拟三甲医院",
                "admission_date": message.payload.get("incident_date"),
            }

            confidence = min(d["confidence"] for d in extracted["documents_parsed"])
            self.complete_trace(db, trace_id, extracted, confidence=confidence)
            return A2AMessage(
                message_id=f"msg_{case_id}_doc_out",
                source_agent="agent_b_doc_parser",
                target_agent="agent_c_liability",
                case_id=case_id,
                message_type="result_forward",
                payload={**message.payload, **extracted},
                confidence=confidence,
            )
        except Exception as e:
            self.fail_trace(db, trace_id, str(e))
            raise

    def _extract_diagnosis(self, desc: str) -> str:
        if "阑尾" in desc or "阑尾炎" in desc:
            return "急性阑尾炎"
        if "骨折" in desc:
            return "闭合性骨折"
        if "肺炎" in desc:
            return "肺部感染"
        if "癌" in desc or "肿瘤" in desc:
            return "恶性肿瘤"
        return "门诊就诊"
