from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName


class LiabilityAgent(BaseAgent):
    """Agent C: 核责判断 - 模拟 RAG 条款匹配"""

    def __init__(self):
        self.agent_name = AgentName.C_LIABILITY
        self.agent_label = "核责判断"

    def process(self, message: A2AMessage) -> A2AMessage:
        trace_id = self.create_trace_record(message.case_id, message.payload)
        try:
            case_id = message.payload.get("case_id")
            diagnosis = message.payload.get("diagnosis", "")
            product = message.payload.get("insurance_product", "")

            liability_result = self._assess_liability(diagnosis, product)

            output = {
                "case_id": case_id,
                "diagnosis": diagnosis,
                "product": product,
                "liability": liability_result["conclusion"],
                "liability_detail": liability_result["detail"],
                "exclusions_checked": liability_result["exclusions"],
                "waiting_period_met": True,
            }

            self.complete_trace(trace_id, output, confidence=liability_result["confidence"])
            return A2AMessage(
                message_id=f"msg_{case_id}_liab_out",
                source_agent="agent_c_liability",
                target_agent="agent_d_calculation",
                case_id=case_id,
                message_type="result_forward",
                payload={**message.payload, **output},
                confidence=liability_result["confidence"],
            )
        except Exception as e:
            self.fail_trace(trace_id, str(e))
            raise

    def _assess_liability(self, diagnosis: str, product: str) -> dict:
        """模拟责任判定逻辑"""
        exclusions = [
            {"item": "先天性疾病", "matched": False, "detail": "诊断结论不涉及先天性疾病"},
            {"item": "既往症", "matched": False, "detail": "未发现既往症记录"},
            {"item": "等待期出险", "matched": False, "detail": "已过等待期90天"},
            {"item": "非定点医院", "matched": False, "detail": "就诊医院为定点医疗机构"},
            {"item": "责任免除项目", "matched": False, "detail": "不涉及责任免除项目"},
        ]

        # 根据诊断调整
        if "恶性肿瘤" in diagnosis:
            exclusions.append({"item": "特定药品费", "matched": True, "detail": "部分自费药不在保障范围"})

        is_covered = all(not e["matched"] for e in exclusions)
        confidence = 0.92 if is_covered else 0.85

        return {
            "conclusion": "属于保险责任" if is_covered else "部分项目需人工复核",
            "detail": f"诊断'{diagnosis}'在保障范围内" if is_covered else f"诊断'{diagnosis}'需进一步核实",
            "exclusions": exclusions,
            "confidence": confidence,
        }
