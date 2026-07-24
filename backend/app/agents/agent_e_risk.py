import random
from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName


class RiskControlAgent(BaseAgent):
    """Agent E: 风控审查 - 反欺诈检测"""

    def __init__(self):
        self.agent_name = AgentName.E_RISK
        self.agent_label = "风控审查"

    def process(self, message: A2AMessage) -> A2AMessage:
        trace_id = self.create_trace_record(message.case_id, message.payload)
        try:
            case_id = message.payload.get("case_id")
            diagnosis = message.payload.get("diagnosis", "")
            medical_total = message.payload.get("medical_total", 0)
            calculated = message.payload.get("calculated_amount", 0)

            risk_score, risk_level, findings = self._assess_risk(diagnosis, medical_total)

            output = {
                "case_id": case_id,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "risk_findings": findings,
                "suggestion": "建议通过" if risk_level == "low" else "建议人工重点审核",
            }

            self.complete_trace(trace_id, output, confidence=round(1 - risk_score / 100, 2))
            return A2AMessage(
                message_id=f"msg_{case_id}_risk_out",
                source_agent="agent_e_risk",
                target_agent="agent_f_summary",
                case_id=case_id,
                message_type="result_forward",
                payload={**message.payload, **output},
                confidence=round(1 - risk_score / 100, 2),
            )
        except Exception as e:
            self.fail_trace(trace_id, str(e))
            raise

    def _assess_risk(self, diagnosis: str, total: float) -> tuple:
        """模拟风险评估"""
        findings = [
            {"rule": "首次出险", "risk": "low", "detail": "该客户首次申请理赔"},
            {"rule": "就诊机构合规", "risk": "low", "detail": "就诊机构为二级甲等医院"},
            {"rule": "费用合理性", "risk": "low", "detail": "费用处于合理区间"},
        ]

        if total > 30000:
            findings.append({"rule": "大额案件", "risk": "medium", "detail": f"医疗费用{total}元，需关注"})

        if "恶性肿瘤" in diagnosis:
            findings.append({"rule": "重疾案件", "risk": "medium", "detail": "重疾诊断需核实病理报告"})

        risk_score = sum({"low": 5, "medium": 15, "high": 30}.get(f["risk"], 10) for f in findings)
        risk_level = "low" if risk_score < 20 else ("medium" if risk_score < 40 else "high")

        return risk_score, risk_level, findings
