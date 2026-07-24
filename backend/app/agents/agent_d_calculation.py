"""Agent D: 理算 — 基于保单条款和规则引擎的赔付计算

策略：
1. 优先使用规则引擎（覆盖 70% 简单案件）
2. 无匹配规则时调用 LLM（模拟，后续接真实 LLM）
3. 输出结构化理算明细 + 条款依据
"""
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName
from app.services.rule_engine import get_rule_engine, RuleContext


class CalculationAgent(BaseAgent):
    """Agent D: 理算 — 基于规则的赔付计算"""

    def __init__(self):
        self.agent_name = AgentName.D_CALCULATION
        self.agent_label = "理算"

    def process(self, message: A2AMessage, db: Session) -> A2AMessage:
        trace_id = self.create_trace_record(db, message.case_id, message.payload)
        try:
            p = message.payload
            case_id = p.get("case_id")
            medical_total = p.get("medical_total") or p.get("total_amount", 0)
            diagnosis = p.get("diagnosis", "")
            product = p.get("insurance_product", "")
            liability = p.get("liability", "")

            # 构建规则上下文
            ctx = RuleContext(
                total_amount=float(medical_total or 0),
                diagnosis=diagnosis,
                insurance_product=product,
                has_uploaded_docs=len(p.get("documents", [])) > 0,
                doc_types=[d.get("doc_type", "") for d in p.get("documents", [])],
            )

            # 规则引擎计算
            rule_result = get_rule_engine().evaluate(ctx)

            if rule_result and rule_result.calculated_amount is not None:
                # 规则引擎命中，使用规则结果
                items = self._generate_items(medical_total, rule_result.rule_name)
                total = rule_result.calculated_amount
                rule_used = rule_result.rule_name
                confidence = rule_result.confidence
            else:
                # 兜底计算：按险种默认比例
                ratio = 0.7 if "意外" in product else 0.75 if "住院" in product else 0.5
                deductible = 500 if "住院" in product else 0
                total = max(0, float(medical_total) * ratio - deductible)
                items = self._generate_items(medical_total, f"默认{ratio:.0%}比例")
                rule_used = "兜底比例"
                confidence = 0.85

            output = {
                "case_id": case_id,
                "medical_total": float(medical_total),
                "calculation_items": items,
                "calculated_amount": round(total, 2),
                "deductible": deductible if 'deductible' in dir() else 0,
                "payment_ratio": ratio if 'ratio' in dir() else 0.7,
                "rule_used": rule_used,
                "calculation_basis": f"依据保单条款及规则'{rule_used}'，医疗费用¥{float(medical_total):,.2f}，"
                                    f"扣除免赔额后按{ratio:.0%}赔付",
            }

            self.complete_trace(db, trace_id, output, confidence=round(confidence, 2))
            return A2AMessage(
                message_id=f"msg_{case_id}_calc_out",
                source_agent="agent_d_calculation",
                target_agent="agent_e_risk",
                case_id=case_id, message_type="result_forward",
                payload={**message.payload, **output},
                confidence=round(confidence, 2),
            )
        except Exception as e:
            self.fail_trace(db, trace_id, str(e))
            raise

    def _generate_items(self, total: float, rule: str) -> list[dict]:
        """生成分项理算明细"""
        if total <= 0:
            return []
        # 按医疗费用结构比例拆分
        ratios = [
            ("药品费", 0.35, 0.8),
            ("检查费", 0.25, 0.9),
            ("治疗费", 0.20, 0.85),
            ("手术费", 0.10, 1.0),
            ("床位费", 0.10, 0.7),
        ]
        return [
            {
                "category": cat,
                "original": round(total * r_orig, 2),
                "ratio": r_pay,
                "amount": round(total * r_orig * r_pay, 2),
                "basis": f"按{rule}，{cat}赔付比例{r_pay:.0%}",
            }
            for cat, r_orig, r_pay in ratios
        ]
