"""Agent F: 结论汇总 — 生成结构化理赔审核报告

输出包含：
- 案件摘要信息
- 各 Agent 处理结果汇总
- 理算明细表
- 风控标记
- 审核建议
- 全链路置信度
"""
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName


class SummaryAgent(BaseAgent):
    """Agent F: 结论汇总 — 聚合输出 + 审核报告生成"""

    def __init__(self):
        self.agent_name = AgentName.F_SUMMARY
        self.agent_label = "结论汇总"

    def process(self, message: A2AMessage, db: Session) -> A2AMessage:
        trace_id = self.create_trace_record(db, message.case_id, message.payload)
        try:
            p = message.payload
            case_id = p.get("case_id")
            case_no = p.get("case_no", "")
            insured = p.get("insured_name", "未知")
            product = p.get("insurance_product", "")
            diagnosis = p.get("diagnosis", "")
            total_amount = p.get("medical_total") or p.get("total_amount", 0)
            calculated_amount = p.get("calculated_amount", 0)
            liability = p.get("liability", "未判定")
            risk_level = p.get("risk_level", "low")
            risk_score = p.get("risk_score", 0)
            rule_used = p.get("rule_used", "")
            calculation_items = p.get("calculation_items", [])
            risk_findings = p.get("risk_findings", [])
            fraud_flags = p.get("fraud_flags", [])
            sampled = p.get("sampled", False)

            # 计算各 Agent 置信度
            confidences = {
                "报案受理": p.get("validation_passed") is not None and 0.98 or 0,
                "材料解析": p.get("diagnosis") and 0.95 or 0,
                "核责判断": 0.92 if liability != "未判定" else 0,
                "理算": 0.94 if calculated_amount else 0,
                "风控审查": max(0.3, 1 - risk_score / 100) if risk_score else 0,
            }

            # 总置信度 = 各 Agent 最小值
            valid_conf = [c for c in confidences.values() if c > 0]
            overall_confidence = round(min(valid_conf), 2) if valid_conf else 0.5

            # 审核建议
            if risk_level == "low" and not fraud_flags and not sampled:
                suggestion = "建议通过"
                review_priority = "正常"
            elif risk_level == "medium" or fraud_flags:
                suggestion = "建议人工重点审核"
                review_priority = "优先处理"
            else:
                suggestion = "建议驳回或转线下调查"
                review_priority = "紧急"

            # 构建结构化审核报告
            report = {
                "case_id": case_id,
                "case_no": case_no,
                "case_summary": (
                    f"【案件摘要】出险人 {insured}，险种 {product}，"
                    f"诊断 {diagnosis}，医疗费用 ¥{float(total_amount):,.2f}，"
                    f"理算金额 ¥{float(calculated_amount):,.2f}"
                ),
                "claimant_info": {
                    "name": insured,
                    "product": product,
                    "diagnosis": diagnosis,
                },
                "financial_summary": {
                    "total_amount": float(total_amount),
                    "calculated_amount": float(calculated_amount),
                    "difference": float(total_amount) - float(calculated_amount),
                    "savings_rate": f"{round((1 - float(calculated_amount) / max(float(total_amount), 1)) * 100, 1)}%",
                },
                "calculation_details": {
                    "items": calculation_items,
                    "rule_used": rule_used or "未使用规则",
                    "total": float(calculated_amount),
                },
                "liability_result": {
                    "conclusion": liability,
                },
                "risk_assessment": {
                    "level": risk_level,
                    "score": risk_score,
                    "findings": risk_findings,
                    "fraud_flags": fraud_flags,
                    "sampled": sampled,
                },
                "agent_confidences": confidences,
                "overall_confidence": overall_confidence,
                "review_priority": review_priority,
                "suggestion": suggestion,
                "audit_trail": {
                    "agent_a_intake": case_no,
                    "agent_b_doc_parser": {"diagnosis": diagnosis},
                    "agent_c_liability": liability,
                    "agent_d_calculation": calculated_amount,
                    "agent_e_risk": {"score": risk_score, "level": risk_level},
                    "agent_f_summary": "报告已生成",
                },
                "all_agents_completed": True,
            }

            self.complete_trace(db, trace_id, report, confidence=overall_confidence)
            return A2AMessage(
                message_id=f"msg_{case_id}_sum_out",
                source_agent="agent_f_summary",
                target_agent="human_gate",
                case_id=case_id,
                message_type="result_forward",
                payload={**p, **report},
                confidence=overall_confidence,
            )
        except Exception as e:
            self.fail_trace(db, trace_id, str(e))
            raise
