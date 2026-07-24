"""Agent E: 风控审查 — 材料真实性鉴定与反欺诈检测

P0 风控能力：
1. 人证一致性校验 — 文档姓名与报案姓名交叉比对
2. 发票号全局查重 — 同一发票号是否出现在不同案件中
3. 逻辑一致性校验 — 日期/金额等跨字段逻辑验证
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.protocol import A2AMessage
from app.database.models import AgentName, Document


class RiskControlAgent(BaseAgent):
    """Agent E: 风控审查 — 反欺诈检测与风险评分"""

    def __init__(self):
        self.agent_name = AgentName.E_RISK
        self.agent_label = "风控审查"

    def process(self, message: A2AMessage, db: Session) -> A2AMessage:
        trace_id = self.create_trace_record(db, message.case_id, message.payload)
        try:
            case_id = message.payload.get("case_id")
            payload = message.payload

            findings = []

            # 1. 人证一致性校验
            name_findings = self._check_name_consistency(payload)
            findings.extend(name_findings)

            # 2. 发票号查重
            invoice_findings = self._check_invoice_duplication(payload, db)
            findings.extend(invoice_findings)

            # 3. 逻辑一致性校验
            logic_findings = self._check_logic_consistency(payload)
            findings.extend(logic_findings)

            # 综合评分
            risk_score = sum({"low": 5, "medium": 20, "high": 40}.get(f["risk"], 10) for f in findings)
            risk_level = "low" if risk_score < 15 else ("medium" if risk_score < 35 else "high")

            output = {
                "case_id": case_id,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "risk_findings": findings,
                "suggestion": "建议通过" if risk_level == "low" else "建议人工重点审核",
            }

            self.complete_trace(db, trace_id, output, confidence=round(max(0.3, 1 - risk_score / 100), 2))
            return A2AMessage(
                message_id=f"msg_{case_id}_risk_out",
                source_agent="agent_e_risk",
                target_agent="agent_f_summary",
                case_id=case_id,
                message_type="result_forward",
                payload={**message.payload, **output},
                confidence=round(max(0.3, 1 - risk_score / 100), 2),
            )
        except Exception as e:
            self.fail_trace(db, trace_id, str(e))
            raise

    def _normalize_name(self, name: str) -> str:
        """姓名归一化：去空格、全角转半角"""
        return name.replace(" ", "").replace("　", "").strip()

    def _check_name_consistency(self, payload: dict) -> list[dict]:
        """① 人证一致性：文档姓名 vs 报案姓名"""
        insured_name = payload.get("insured_name", "")
        if not insured_name:
            return []

        docs: list[dict] = payload.get("documents", [])
        names_on_docs = []
        for d in docs:
            name = d.get("extracted_name") or d.get("document_name", "")
            if name:
                names_on_docs.append((d.get("doc_type", "unknown"), name))

        if not names_on_docs:
            return [{"rule": "人证一致性", "risk": "medium",
                      "detail": "影像材料未提供姓名信息，无法核验人证一致性"}]

        mismatches = []
        normalized_insured = self._normalize_name(insured_name)
        for doc_type, doc_name in names_on_docs:
            if self._normalize_name(doc_name) != normalized_insured:
                mismatches.append(f"{doc_type}姓名「{doc_name}」与报案姓名「{insured_name}」不一致")

        if mismatches:
            return [{"rule": "人证一致性", "risk": "high",
                      "detail": "; ".join(mismatches) + "，涉嫌伪造材料"}]

        return [{"rule": "人证一致性", "risk": "low",
                  "detail": f"所有文档姓名与报案人「{insured_name}」一致"}]

    def _check_invoice_duplication(self, payload: dict, db: Session) -> list[dict]:
        """② 发票号查重：全局检索相同发票号"""
        docs: list[dict] = payload.get("documents", [])
        case_id = payload.get("case_id")
        invoice_nos = []
        for d in docs:
            inv = d.get("invoice_no", "")
            if inv:
                invoice_nos.append(inv)

        if not invoice_nos:
            return []

        duplicates = []
        for inv in invoice_nos:
            existing = db.query(Document).filter(
                Document.invoice_no == inv,
                Document.case_id != case_id,
            ).first()
            if existing:
                duplicates.append(f"发票号「{inv}」已在案件 {existing.case_id} 中使用")

        if duplicates:
            return [{"rule": "发票号查重", "risk": "high",
                      "detail": "; ".join(duplicates) + "，涉嫌一票多赔"}]

        return [{"rule": "发票号查重", "risk": "low",
                  "detail": "所有发票号无重复"}]

    def _check_logic_consistency(self, payload: dict) -> list[dict]:
        """③ 逻辑一致性：日期/金额等跨字段校验"""
        findings = []
        incident_date_str = payload.get("incident_date", "")
        incident_date = None
        if incident_date_str:
            try:
                incident_date = datetime.strptime(
                    incident_date_str[:10], "%Y-%m-%d") if isinstance(incident_date_str, str) else None
            except ValueError:
                pass

        total_amount = payload.get("total_amount") or payload.get("medical_total", 0)

        # 金额合理性
        if total_amount and total_amount > 0:
            if total_amount > 1_000_000:
                findings.append({"rule": "金额合理性", "risk": "medium",
                                 "detail": f"医疗费用 {total_amount} 元超过百万，需核实真实性"})
            elif total_amount > 200_000:
                findings.append({"rule": "金额合理性", "risk": "low",
                                 "detail": f"医疗费用 {total_amount} 元为大额案件"})

        # 文档日期与出险日期逻辑
        docs: list[dict] = payload.get("documents", [])
        if incident_date:
            for d in docs:
                doc_date_str = d.get("document_date", "")
                if not doc_date_str:
                    continue
                try:
                    doc_date = datetime.strptime(
                        doc_date_str[:10], "%Y-%m-%d") if isinstance(doc_date_str, str) else None
                    if doc_date:
                        if doc_date > incident_date + timedelta(days=30):
                            findings.append({
                                "rule": "日期逻辑", "risk": "medium",
                                "detail": f"单据日期 {doc_date.date()} 晚于出险日期30天以上，需核实",
                            })
                        elif doc_date < incident_date - timedelta(days=7):
                            findings.append({
                                "rule": "日期逻辑", "risk": "medium",
                                "detail": f"单据日期 {doc_date.date()} 早于出险日期7天以上，需核实",
                            })
                except ValueError:
                    continue

        if not findings:
            findings.append({"rule": "逻辑一致性", "risk": "low",
                             "detail": "日期与金额逻辑无异常"})

        return findings
