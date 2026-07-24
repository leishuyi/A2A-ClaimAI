"""Agent B: 材料解析 — 模拟 OCR + 多模态信息提取

当前为 MVP 模拟实现：
- 从 payload 读取文档元数据并传递
- 模拟 OCR 提取诊断信息
- 后续可对接 PaddleOCR / 多模态 LLM
"""
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
            docs_meta = message.payload.get("documents", [])

            # 模拟文档解析结果
            parsed_docs = []
            for d in docs_meta:
                parsed_docs.append({
                    "type": d.get("doc_type", "unknown"),
                    "file_name": d.get("file_name", ""),
                    "extracted_name": d.get("extracted_name"),
                    "invoice_no": d.get("invoice_no"),
                    "document_date": d.get("document_date"),
                    "status": "已识别",
                    "confidence": 0.95,
                })

            # 如果无影像材料，使用默认模拟
            if not parsed_docs:
                parsed_docs = [
                    {"type": "身份证", "status": "已识别", "confidence": 0.99},
                    {"type": "诊断证明", "status": "已识别", "confidence": 0.97},
                    {"type": "费用发票", "status": "已识别", "confidence": 0.95},
                ]

            extracted = {
                "case_id": case_id,
                "insured_name": insured,
                "documents_parsed": parsed_docs,
                "diagnosis": self._extract_diagnosis(incident_desc),
                "hospital_name": "模拟三甲医院",
                "admission_date": message.payload.get("incident_date"),
            }

            confidence = min((d.get("confidence", 0.9) for d in parsed_docs), default=0.9)
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
