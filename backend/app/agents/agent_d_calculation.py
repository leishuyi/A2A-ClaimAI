import random
from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName


class CalculationAgent(BaseAgent):
    """Agent D: 理算 - 自动化理算"""

    def __init__(self):
        self.agent_name = AgentName.D_CALCULATION
        self.agent_label = "理算"

    def process(self, message: A2AMessage) -> A2AMessage:
        trace_id = self.create_trace_record(message.case_id, message.payload)
        try:
            case_id = message.payload.get("case_id")
            medical_total = message.payload.get("medical_total", 0)
            liability = message.payload.get("liability", "")

            items = self._calculate_items(medical_total)
            total_calculated = sum(item["amount"] for item in items)

            output = {
                "case_id": case_id,
                "medical_total": medical_total,
                "calculation_items": items,
                "calculated_amount": round(total_calculated, 2),
                "deductible": 0,
                "payment_ratio": 0.7 if "意外" in message.payload.get("insurance_product", "") else 0.8,
                "calculation_formula": items,
            }

            self.complete_trace(trace_id, output, confidence=0.94)
            return A2AMessage(
                message_id=f"msg_{case_id}_calc_out",
                source_agent="agent_d_calculation",
                target_agent="agent_e_risk",
                case_id=case_id,
                message_type="result_forward",
                payload={**message.payload, **output},
                confidence=0.94,
            )
        except Exception as e:
            self.fail_trace(trace_id, str(e))
            raise

    def _calculate_items(self, total: float) -> list[dict]:
        """模拟理算分项"""
        items = [
            {"category": "药品费", "original": round(total * 0.35, 2), "ratio": 0.8, "amount": round(total * 0.35 * 0.8, 2)},
            {"category": "检查费", "original": round(total * 0.25, 2), "ratio": 0.9, "amount": round(total * 0.25 * 0.9, 2)},
            {"category": "治疗费", "original": round(total * 0.20, 2), "ratio": 0.85, "amount": round(total * 0.20 * 0.85, 2)},
            {"category": "手术费", "original": round(total * 0.10, 2), "ratio": 1.0, "amount": round(total * 0.10, 2)},
            {"category": "床位费", "original": round(total * 0.10, 2), "ratio": 0.7, "amount": round(total * 0.10 * 0.7, 2)},
        ]
        return items
