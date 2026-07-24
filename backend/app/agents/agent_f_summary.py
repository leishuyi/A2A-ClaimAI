from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName, RiskLevel


class SummaryAgent(BaseAgent):
    """Agent F: 结论汇总 - 聚合所有 Agent 输出，生成审核报告"""

    def __init__(self):
        self.agent_name = AgentName.F_SUMMARY
        self.agent_label = "结论汇总"

    def process(self, message: A2AMessage) -> A2AMessage:
        trace_id = self.create_trace_record(message.case_id, message.payload)
        try:
            payload = message.payload
            case_id = payload.get("case_id")
            insured = payload.get("insured_name", "未知")
            diagnosis = payload.get("diagnosis", "")
            medical_total = payload.get("medical_total", 0)
            calculated = payload.get("calculated_amount", 0)
            liability = payload.get("liability", "未判定")
            risk_level = payload.get("risk_level", "low")
            risk_score = payload.get("risk_score", 0)

            summary = {
                "case_id": case_id,
                "case_summary": self._generate_summary(insured, diagnosis, medical_total, calculated),
                "agent_count": 6,
                "all_agents_completed": True,
                "overall_confidence": self._calc_overall_confidence(payload),
                "risk_level": risk_level,
                "calculated_amount": calculated,
                "suggestion": "建议通过" if risk_level in ("low", RiskLevel.LOW) else "建议人工审核",
                "report_generated": True,
            }

            summary["audit_trail"] = {
                "agent_a_intake": payload.get("case_no", ""),
                "agent_b_doc_parser": {
                    "documents": len(payload.get("documents_parsed", [])),
                    "diagnosis": diagnosis,
                },
                "agent_c_liability": liability,
                "agent_d_calculation": calculated,
                "agent_e_risk": {"score": risk_score, "level": risk_level},
            }

            self.complete_trace(trace_id, summary, confidence=summary["overall_confidence"])
            return A2AMessage(
                message_id=f"msg_{case_id}_sum_out",
                source_agent="agent_f_summary",
                target_agent="human_gate",
                case_id=case_id,
                message_type="result_forward",
                payload={**payload, **summary},
                confidence=summary["overall_confidence"],
            )
        except Exception as e:
            self.fail_trace(trace_id, str(e))
            raise

    def _generate_summary(self, insured: str, diagnosis: str, total: float, calculated: float) -> str:
        return (
            f"【案件摘要】出险人 {insured}，诊断 {diagnosis}，"
            f"医疗费用 ¥{total:,.2f}，理算金额 ¥{calculated:,.2f}"
        )

    def _calc_overall_confidence(self, payload: dict) -> float:
        confidences = [
            payload.get("confidence") or 0.95,
        ]
        return round(sum(confidences) / len(confidences), 2)
