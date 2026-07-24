"""Agent 编排器 — 支持串行/并行混合调度

编排策略：
- 串行: A → B → (C ‖ D) → E → F
- 并行段互不依赖，使用独立 DB Session 保证线程安全
- 规则引擎命中时跳过 C/D 直接走风控
"""
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.agents.protocol import A2AMessage
from app.agents.agent_a_intake import IntakeAgent
from app.agents.agent_b_doc_parser import DocParserAgent
from app.agents.agent_c_liability import LiabilityAgent
from app.agents.agent_d_calculation import CalculationAgent
from app.agents.agent_e_risk import RiskControlAgent
from app.agents.agent_f_summary import SummaryAgent
from app.database.models import Case, CaseStatus, AuditLog, AgentTrace, AgentStatus
from app.database.session import SessionLocal
from app.events import event_bus
from app.services.rule_engine import get_rule_engine, RuleContext

# Agent 间传递的 key 白名单 — 只传递必要字段，控制 payload 膨胀
PAYLOAD_KEYS = {
    "case_id", "case_no", "insured_name", "insurance_product",
    "incident_desc", "incident_date", "total_amount",
    "diagnosis", "medical_total",
    "liability", "calculated_amount",
    "risk_level", "risk_score",
    "rule_engine_hit", "rule_name",
    "fraud_flags", "sampled",
}


class AgentOrchestrator:
    """Agent 编排器 — 串行/并行混合调度"""

    SERIAL_CHAIN = [
        ("agent_a_intake", "报案受理"),
        ("agent_b_doc_parser", "材料解析"),
    ]

    PARALLEL_GROUP = [
        ("agent_c_liability", "核责判断"),
        ("agent_d_calculation", "理算"),
    ]

    SERIAL_TAIL = [
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

    def _clean_payload(self, payload: dict) -> dict:
        """精简 payload：只保留白名单内的 key"""
        return {k: v for k, v in payload.items() if k in PAYLOAD_KEYS}

    def run_chain(self, case_id: int, db: Session) -> Optional[str]:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            return "案件不存在"

        case.status = CaseStatus.PROCESSING
        db.commit()
        logger.info("开始执行 Agent 链路", case_id=case_id, case_no=case.case_no)

        payload: dict = {"case_id": case_id}

        # ── Phase 1: 串行段 A → B ──
        error = self._run_serial(self.SERIAL_CHAIN, payload, case_id, db)
        if error:
            return self._fail(case, db, error)

        # ── Phase 2: 规则引擎前置过滤 ──
        docs_meta = payload.get("documents", [])
        now = datetime.datetime.utcnow()
        ctx = RuleContext(
            total_amount=payload.get("total_amount") or payload.get("medical_total", 0) or 0,
            diagnosis=payload.get("diagnosis", ""),
            insurance_product=payload.get("insurance_product", ""),
            has_uploaded_docs=len(docs_meta) > 0,
            doc_types=[d.get("doc_type", d.get("type", "")) for d in docs_meta],
            created_hour=now.hour,
            created_weekday=now.weekday(),
            is_round_amount=(payload.get("total_amount", 0) or 0) % 100 == 0,
        )
        rule_result = get_rule_engine().evaluate(ctx)

        if rule_result and not rule_result.needs_llm:
            # 规则命中 → 跳过 C/D 执行，只写 Trace 记录
            logger.info("规则引擎命中，跳过 Agent C/D", rule=rule_result.rule_name)
            payload["liability"] = rule_result.liability
            payload["fraud_flags"] = rule_result.fraud_flags
            payload["sampled"] = rule_result.sampled
            payload["calculated_amount"] = rule_result.calculated_amount
            payload["rule_engine_hit"] = True
            payload["rule_name"] = rule_result.rule_name

            for agent_key, agent_label in self.PARALLEL_GROUP:
                trace = AgentTrace(
                    case_id=case_id, agent_name=agent_key, agent_label=agent_label,
                    status=AgentStatus.COMPLETED,
                    output_data={"rule_skipped": rule_result.rule_name,
                                 "calculated_amount": rule_result.calculated_amount},
                    confidence=rule_result.confidence,
                    started_at=now, completed_at=datetime.datetime.utcnow(),
                    duration_ms=0,
                )
                db.add(trace)
                event_bus.publish("agent.completed", {
                    "case_id": case_id, "agent": agent_key,
                    "label": agent_label, "confidence": rule_result.confidence,
                })
            db.commit()
        else:
            # 规则未命中 → 执行 C/D（串行或并行）
            payload = self._clean_payload(payload)
            if settings.feature_agent_parallel:
                error = self._run_parallel(self.PARALLEL_GROUP, payload, case_id)
            else:
                error = self._run_serial(self.PARALLEL_GROUP, payload, case_id, db)
            if error:
                return self._fail(case, db, error)

        # ── Phase 3: E → F ──
        payload = self._clean_payload(payload)
        error = self._run_serial(self.SERIAL_TAIL, payload, case_id, db)
        if error:
            return self._fail(case, db, error)

        return self._finish(case, payload, db)

    def _run_serial(self, chain: list[tuple], payload: dict,
                    case_id: int, db: Session) -> Optional[str]:
        for agent_key, agent_label in chain:
            agent = self.agents[agent_key]
            msg = A2AMessage(
                message_id=f"msg_{case_id}_{agent_key}",
                source_agent=agent_key, target_agent="",
                case_id=case_id, message_type="request",
                payload=payload,
            )
            try:
                result = agent.process(msg, db)
                payload.update(result.payload)
                event_bus.publish("agent.completed", {
                    "case_id": case_id, "agent": agent_key,
                    "label": agent_label, "confidence": result.confidence,
                })
            except Exception as e:
                return f"{agent_label} 执行失败: {str(e)}"
        return None

    def _run_parallel(self, group: list[tuple], payload: dict,
                      case_id: int) -> Optional[str]:
        """并行执行 Agent 组 — 每个 Agent 使用独立 DB Session 保证线程安全"""
        logger.info("并行执行 Agent", agents=[a for a, _ in group])

        with ThreadPoolExecutor(max_workers=len(group)) as executor:
            future_map = {}
            for agent_key, agent_label in group:
                agent = self.agents[agent_key]
                msg = A2AMessage(
                    message_id=f"msg_{case_id}_{agent_key}_parallel",
                    source_agent=agent_key, target_agent="",
                    case_id=case_id, message_type="request",
                    payload=dict(payload),  # 拷贝，避免竞争
                )
                future = executor.submit(self._run_agent_thread, agent, msg, agent_key, agent_label)
                future_map[future] = agent_key

            merged = dict(payload)
            for future in as_completed(future_map):
                agent_key = future_map[future]
                try:
                    result_payload, err = future.result()
                    if err:
                        return f"{agent_key} 并行执行失败: {err}"
                    merged.update(result_payload)
                except Exception as e:
                    return f"{agent_key} 异常: {str(e)}"

        payload.update(merged)
        return None

    def _run_agent_thread(self, agent, msg, agent_key, agent_label) -> tuple:
        """在独立线程中运行 Agent — 创建独立 DB Session"""
        db = SessionLocal()
        try:
            result = agent.process(msg, db)
            db.commit()
            event_bus.publish("agent.completed", {
                "case_id": msg.case_id, "agent": agent_key,
                "label": agent_label, "confidence": result.confidence,
            })
            return result.payload, None
        except Exception as e:
            db.rollback()
            return None, str(e)
        finally:
            db.close()

    def _fail(self, case: Case, db: Session, error: str) -> str:
        case.status = CaseStatus.DRAFT
        db.commit()
        logger.error("Agent 链路失败", case_id=case.id, error=error)
        return error

    def _finish(self, case: Case, payload: dict, db: Session) -> None:
        case.status = CaseStatus.PENDING_REVIEW
        case.calculated_amount = payload.get("calculated_amount")
        case.risk_level = payload.get("risk_level", case.risk_level)

        log = AuditLog(
            case_id=case.id, action="agents_completed",
            comment="全链路 Agent 处理完成，等待人工审核", operator="system",
        )
        db.add(log)
        db.commit()

        logger.info("Agent 链路执行完成", case_id=case.id, amount=case.calculated_amount, risk=str(case.risk_level.value))

        event_bus.publish("case.pending_review", {
            "case_id": case.id, "case_no": case.case_no,
            "risk_level": case.risk_level.value, "calculated_amount": case.calculated_amount,
        })
