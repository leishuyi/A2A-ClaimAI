"""Agent 编排器：按状态机调度 6-Agent 链路。

参考 grid-qa 的架构模式：
- DI session（由路由层注入，非自行创建）
- EventBus 事件发布
- loguru 结构化日志
"""
import datetime
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.protocol import A2AMessage
from app.agents.agent_a_intake import IntakeAgent
from app.agents.agent_b_doc_parser import DocParserAgent
from app.agents.agent_c_liability import LiabilityAgent
from app.agents.agent_d_calculation import CalculationAgent
from app.agents.agent_e_risk import RiskControlAgent
from app.agents.agent_f_summary import SummaryAgent
from app.database.models import Case, CaseStatus, AuditLog
from app.events import event_bus


class AgentOrchestrator:
    """Agent 编排器 — 负责任务链调度、状态管理、事件发布。"""

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

    def run_chain(self, case_id: int, db: Session) -> Optional[str]:
        """执行完整 Agent 链路，返回错误信息（None 表示成功）。"""
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            return "案件不存在"

        case.status = CaseStatus.PROCESSING
        db.commit()
        logger.info("开始执行 Agent 链路", case_id=case_id, case_no=case.case_no)

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
                result = agent.process(msg, db)
                payload = result.payload

                # 事件总线：Agent 完成
                event_bus.publish("agent.completed", {
                    "case_id": case_id,
                    "agent": agent_key,
                    "label": agent_label,
                    "confidence": result.confidence,
                })
            except Exception as e:
                error_msg = f"{agent_label} 执行失败: {str(e)}"
                logger.error(error_msg, case_id=case_id, agent=agent_key)
                case.status = CaseStatus.DRAFT
                db.commit()
                return error_msg

        # 全链路完成 → 待人工审核
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

        logger.info("Agent 链路执行完成", case_id=case_id, status=str(case.status.value),
                   amount=case.calculated_amount, risk=str(case.risk_level.value))

        # 事件总线：案件待审核
        event_bus.publish("case.pending_review", {
            "case_id": case_id,
            "case_no": case.case_no,
            "risk_level": case.risk_level.value,
            "calculated_amount": case.calculated_amount,
        })

        return None
