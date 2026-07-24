import datetime
from typing import Optional

from app.agents.protocol import A2AMessage
from app.agents.agent_a_intake import IntakeAgent
from app.agents.agent_b_doc_parser import DocParserAgent
from app.agents.agent_c_liability import LiabilityAgent
from app.agents.agent_d_calculation import CalculationAgent
from app.agents.agent_e_risk import RiskControlAgent
from app.agents.agent_f_summary import SummaryAgent
from app.database.models import Case, CaseStatus, AuditLog
from app.database.session import SessionLocal


class AgentOrchestrator:
    """Agent 编排器：按状态机调度 Agent 链路"""

    AGENT_CHAIN = [
        ("agent_a_intake", "报案受理"),
        ("agent_b_doc_parser", "材料解析"),
        ("agent_c_liability", "核责判断"),
        ("agent_d_calculation", "理算"),
        ("agent_e_risk", "风控审查"),
        ("agent_f_summary", "结论汇总"),
    ]

    def __init__(self):
        self.agents = {
            "agent_a_intake": IntakeAgent(),
            "agent_b_doc_parser": DocParserAgent(),
            "agent_c_liability": LiabilityAgent(),
            "agent_d_calculation": CalculationAgent(),
            "agent_e_risk": RiskControlAgent(),
            "agent_f_summary": SummaryAgent(),
        }

    def run_chain(self, case_id: int) -> Optional[str]:
        """执行完整 Agent 链路，返回错误信息（如果有）"""
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.id == case_id).first()
            if not case:
                return "案件不存在"

            case.status = CaseStatus.PROCESSING
            db.commit()

            payload: dict = {"case_id": case_id}

            for agent_key, agent_label in self.AGENT_CHAIN:
                agent = self.agents[agent_key]
                msg = A2AMessage(
                    message_id=f"msg_{case_id}_{agent_key}_{datetime.datetime.utcnow().timestamp()}",
                    source_agent=agent_key,
                    target_agent="",
                    case_id=case_id,
                    message_type="request",
                    payload=payload,
                )

                try:
                    result = agent.process(msg)
                    payload = result.payload
                except Exception as e:
                    error_msg = f"{agent_label} 执行失败: {str(e)}"
                    case.status = CaseStatus.DRAFT
                    db.commit()

                    log = AuditLog(
                        case_id=case_id,
                        action="agent_failed",
                        comment=error_msg,
                        operator="system",
                    )
                    db.add(log)
                    db.commit()
                    return error_msg

            # Agent 链路完成 → 待人工审核
            case.status = CaseStatus.PENDING_REVIEW
            case.calculated_amount = payload.get("calculated_amount")
            case.risk_level = payload.get("risk_level", case.risk_level)

            log = AuditLog(
                case_id=case_id,
                action="agents_completed",
                comment="全链路 Agent 处理完成，等待人工审核",
                operator="system",
            )
            db.add(log)
            db.commit()
            return None

        finally:
            db.close()
