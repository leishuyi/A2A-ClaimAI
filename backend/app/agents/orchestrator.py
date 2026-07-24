"""Agent 编排器 — 支持串行/并行混合调度

编排策略：
- 串行: A → B → (C ‖ D) → E → F
- 并行段: C(核责) 和 D(理算) 互不依赖，可同时执行
- 受 feature_agent_parallel 开关控制
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
from app.database.models import Case, CaseStatus, AuditLog
from app.events import event_bus
from app.services.rule_engine import get_rule_engine


class AgentOrchestrator:
    """Agent 编排器 — 串行/并行混合调度"""

    # 串行段（基础依赖）
    SERIAL_CHAIN = [
        ("agent_a_intake", "报案受理"),
        ("agent_b_doc_parser", "材料解析"),
    ]

    # 并行段（互不依赖）
    PARALLEL_GROUP = [
        ("agent_c_liability", "核责判断"),
        ("agent_d_calculation", "理算"),
    ]

    # 串行段（依赖前面全部结果）
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

    def run_chain(self, case_id: int, db: Session) -> Optional[str]:
        """执行 Agent 链路，返回错误信息"""
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
        # 在进入 LLM 前先用规则引擎判断
        rule_ctx = {
            "total_amount": payload.get("total_amount") or payload.get("medical_total", 0),
            "diagnosis": payload.get("diagnosis", ""),
            "insurance_product": payload.get("insurance_product", ""),
            "name_mismatch": False,
        }
        rule_result = get_rule_engine().evaluate(rule_ctx)

        if rule_result and not rule_result.needs_llm:
            # 规则引擎直接判决，不调用 LLM Agent
            logger.info("规则引擎命中", rule=rule_result.rule_name,
                        confidence=rule_result.confidence)
            payload["liability"] = rule_result.liability
            payload["calculated_amount"] = rule_result.calculated_amount
            payload["rule_engine_hit"] = True
            payload["rule_name"] = rule_result.rule_name
            # 跳过 C/D 并行段，直接走风控
            # 但需要记录 mock trace 以保持链路完整性
            for agent_key, agent_label in self.PARALLEL_GROUP:
                agent = self.agents[agent_key]
                msg = A2AMessage(
                    message_id=f"msg_{case_id}_{agent_key}_rule_skip",
                    source_agent=agent_key, target_agent="",
                    case_id=case_id, message_type="request",
                    payload=payload,
                )
                try:
                    result = agent.process(msg, db)
                    payload = result.payload
                    event_bus.publish("agent.completed", {
                        "case_id": case_id, "agent": agent_key,
                        "label": agent_label, "confidence": rule_result.confidence,
                    })
                except Exception as e:
                    error = f"{agent_label} 执行失败: {str(e)}"
                    return self._fail(case, db, error)
        else:
            # ── Phase 2 alt: 并行段 C ‖ D ──
            if settings.feature_agent_parallel:
                error = self._run_parallel(self.PARALLEL_GROUP, payload, case_id, db)
            else:
                error = self._run_serial(self.PARALLEL_GROUP, payload, case_id, db)
            if error:
                return self._fail(case, db, error)

        # ── Phase 3: 串行段 E → F ──
        error = self._run_serial(self.SERIAL_TAIL, payload, case_id, db)
        if error:
            return self._fail(case, db, error)

        # ── 完成 ──
        return self._finish(case, payload, db)

    def _run_serial(self, chain: list[tuple], payload: dict,
                    case_id: int, db: Session) -> Optional[str]:
        """串行执行 Agent 列表"""
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
                payload = result.payload
                event_bus.publish("agent.completed", {
                    "case_id": case_id, "agent": agent_key,
                    "label": agent_label, "confidence": result.confidence,
                })
            except Exception as e:
                return f"{agent_label} 执行失败: {str(e)}"
        return None

    def _run_parallel(self, group: list[tuple], payload: dict,
                      case_id: int, db: Session) -> Optional[str]:
        """并行执行一组 Agent"""
        logger.info("并行执行 Agent", agents=[a for a, _ in group])

        with ThreadPoolExecutor(max_workers=len(group)) as executor:
            future_map = {}
            for agent_key, agent_label in group:
                agent = self.agents[agent_key]
                msg = A2AMessage(
                    message_id=f"msg_{case_id}_{agent_key}_parallel",
                    source_agent=agent_key, target_agent="",
                    case_id=case_id, message_type="request",
                    payload=payload,  # 共享同一份输入
                )
                future = executor.submit(agent.process, msg, db)
                future_map[future] = (agent_key, agent_label)

            merged = dict(payload)
            for future in as_completed(future_map):
                agent_key, agent_label = future_map[future]
                try:
                    result = future.result()
                    merged.update(result.payload)
                    event_bus.publish("agent.completed", {
                        "case_id": case_id, "agent": agent_key,
                        "label": agent_label, "confidence": result.confidence,
                    })
                except Exception as e:
                    return f"{agent_label} 并行执行失败: {str(e)}"

        payload.update(merged)
        return None

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
            case_id=case.id,
            action="agents_completed",
            comment="全链路 Agent 处理完成，等待人工审核",
            operator="system",
        )
        db.add(log)
        db.commit()

        logger.info("Agent 链路执行完成", case_id=case.id, status=str(case.status.value),
                    amount=case.calculated_amount, risk=str(case.risk_level.value))

        event_bus.publish("case.pending_review", {
            "case_id": case.id,
            "case_no": case.case_no,
            "risk_level": case.risk_level.value,
            "calculated_amount": case.calculated_amount,
        })
