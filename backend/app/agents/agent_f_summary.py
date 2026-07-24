from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName


class SummaryAgent(BaseAgent):
    """Agent F: 结论汇总 — 聚合所有 Agent 输出，生成审核报告"""

    def __init__(self):
        self.agent_name = AgentName.F_SUMMARY
        self.agent_label = "结论汇总"

    def process(self, message: A2AMessage, db: Session) -> A2AMessage:
        trace_id = self.create_trace_record(db, message.case_id, message.payload)
        try:
            p = message.payload
            case_id = p.get("case_id")
            insured = p.get("insured_name", "未知")
            diagnosis = p.get("diagnosis", "")
            medical_total = p.get("medical_total", 0)
            calculated = p.get("calculated_amount", 0)
            liability = p.get("liability", "未判定")
            risk_level = p.get("risk_level", "low")
            risk_score = p.get("risk_score", 0)

            summary = {
                "case_id": case_id,
                "case_summary": f"【案件摘要】出险人 {insured}，诊断 {diagnosis}，"
                                f"医疗费用 ¥{medical_total:,.2f}，理算金额 ¥{calculated:,.2f}",
                "all_agents_completed": True,
                "overall_confidence": 0.95,
                "risk_level": risk_level,
                "calculated_amount": calculated,
                "suggestion": "建议通过" if risk_level in ("low",) else "建议人工审核",
                "audit_trail": {
                    "agent_a_intake": p.get("case_no", ""),
                    "agent_b_doc_parser": {"diagnosis": diagnosis},
                    "agent_c_liability": liability,
                    "agent_d_calculation": calculated,
                    "agent_e_risk": {"score": risk_score, "level": risk_level},
                },
            }

            self.complete_trace(db, trace_id, summary, confidence=0.95)
            return A2AMessage(
                message_id=f"msg_{case_id}_sum_out",
                source_agent="agent_f_summary",
                target_agent="human_gate",
                case_id=case_id,
                message_type="result_forward",
                payload={**p, **summary},
                confidence=0.95,
            )
        except Exception as e:
            self.fail_trace(db, trace_id, str(e))
            raise
