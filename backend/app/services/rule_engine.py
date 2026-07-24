"""规则引擎 — 前置过滤 + 防骗保安全层

核心机制：
1. 规则匹配：按优先级逐条匹配，命中即执行
2. 防骗保校验：规则命中前检查异常模式
3. 随机抽检：规则批准的简单案件按比例进人工复核

防骗保策略：
- 资料完整性：必须有对应影像材料
- 异常金额：整金额(1999/2000)、金额异常分布
- 时间模式：周末/夜间报案提高抽检率
- 额度累积：同一被保人短期内多案累计
- 随机抽检：按风险分层设置抽检比例
"""
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from loguru import logger


@dataclass
class RuleContext:
    """规则评估上下文 — 包含案件数据和防骗保信息"""
    # 案件数据
    total_amount: float = 0
    diagnosis: str = ""
    insurance_product: str = ""
    name_mismatch: bool = False
    has_uploaded_docs: bool = False       # 是否有上传的影像材料
    doc_types: list[str] = field(default_factory=list)  # 已上传的文档类型列表

    # 防骗保特征
    created_hour: int = 0                 # 报案小时（0-23）
    created_weekday: int = 0              # 报案星期（0=周一）
    is_round_amount: bool = False         # 金额是否为整百/整千
    claimant_history_count: int = 0       # 该被保人近期报案次数
    claimant_history_total: float = 0     # 该被保人近期累计理算金额


@dataclass
class RuleResult:
    liability: str
    confidence: float
    rule_name: str
    calculated_amount: float | None = None
    needs_llm: bool = False
    sampled: bool = False                 # 是否被抽检（规则批准但抽中人工复核）
    sample_reason: str = ""               # 抽检原因
    fraud_flags: list[str] = field(default_factory=list)


class ClaimRule:
    def __init__(self, name: str, priority: int,
                 match_fn: Callable[[RuleContext], bool],
                 exec_fn: Callable[[RuleContext], RuleResult],
                 required_docs: list[str] | None = None):
        self.name = name
        self.priority = priority
        self.match_fn = match_fn
        self.exec_fn = exec_fn
        self.required_docs = required_docs or []


class AntiFraudGuard:
    """防骗保校验层 — 每个规则命中后执行的安全检查"""

    @staticmethod
    def check(ctx: RuleContext, rule: ClaimRule) -> list[str]:
        """执行安全检查，返回所有触发的风险标记"""
        flags = []

        # 1. 资料完整性
        if rule.required_docs and not all(d in ctx.doc_types for d in rule.required_docs):
            flags.append(f"缺少必要资料: {rule.required_docs}")

        # 2. 无影像材料
        if not ctx.has_uploaded_docs:
            flags.append("无上传影像材料")

        # 3. 异常金额
        if ctx.is_round_amount:
            flags.append("金额为整百/整千")

        # 4. 非工作时间报案
        if ctx.created_hour < 6 or ctx.created_hour > 22:
            flags.append("非工作时间报案")

        # 5. 周末报案
        if ctx.created_weekday >= 5:
            flags.append("周末报案")

        # 6. 频繁报案
        if ctx.claimant_history_count >= 3:
            flags.append(f"近期频繁报案({ctx.claimant_history_count}次)")

        # 7. 累计额度超限
        if ctx.claimant_history_total > 50000:
            flags.append(f"近期累计理算金额超限(¥{ctx.claimant_history_total:,.0f})")

        return flags

    @staticmethod
    def should_sample(flags: list[str], base_rate: float = 0.05) -> tuple[bool, str]:
        """决定是否抽检：基于风险标记调整抽检率"""
        rate = base_rate
        reasons = []

        for flag in flags:
            if "非工作时间" in flag:
                rate = max(rate, 0.30)
                reasons.append("非工作时间")
            if "周末" in flag:
                rate = max(rate, 0.25)
                reasons.append("周末报案")
            if "频繁报案" in flag:
                rate = max(rate, 0.50)
                reasons.append("频繁报案")
            if "无上传影像" in flag:
                rate = max(rate, 0.80)
                reasons.append("无影像材料")
            if "金额为整" in flag:
                rate = max(rate, 0.20)
                reasons.append("异常金额")
            if "累计额度" in flag:
                rate = max(rate, 0.60)
                reasons.append("额度超限")
            if "缺" in flag and "资料" in flag:
                rate = 1.0  # 缺资料必抽检
                reasons.append("缺资料")

        sampled = random.random() < rate
        return sampled, f"抽检率{rate:.0%}触发: {'; '.join(reasons)}" if sampled else ""


class RuleEngine:
    def __init__(self):
        self._rules: list[ClaimRule] = []

    def register(self, rule: ClaimRule):
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, ctx: RuleContext) -> RuleResult | None:
        """按优先级逐条匹配 → 命中后执行防骗保校验 + 抽检"""
        for rule in self._rules:
            if rule.match_fn(ctx):
                # 执行防骗保检查
                fraud_flags = AntiFraudGuard.check(ctx, rule)

                # 执行规则
                result = rule.exec_fn(ctx)
                result.fraud_flags = fraud_flags

                # 抽检决定
                if fraud_flags:
                    sampled, reason = AntiFraudGuard.should_sample(fraud_flags)
                    result.sampled = sampled
                    result.sample_reason = reason
                    if sampled:
                        result.needs_llm = True
                        logger.info("规则命中但被抽检", rule=rule.name,
                                    flags=fraud_flags, reason=reason)

                logger.info("规则引擎评估", rule=rule.name,
                            sampled=result.sampled, flags=len(fraud_flags))
                return result
        return None


# ── 预置规则 ──────────────────────────────────────────

rule_outpatient_small = ClaimRule(
    name="门诊小额快速理赔",
    priority=100,
    required_docs=["invoice"],  # 必须有发票
    match_fn=lambda ctx: (
        ctx.total_amount <= 2000
        and ctx.diagnosis in ("急性上呼吸道感染", "门诊就诊")
    ),
    exec_fn=lambda ctx: RuleResult(
        liability="责任范围内",
        confidence=0.98,
        rule_name="门诊小额快速理赔",
        calculated_amount=ctx.total_amount * 0.7,
    ),
)

rule_appendectomy = ClaimRule(
    name="急性阑尾炎标准赔付",
    priority=90,
    required_docs=["diagnosis", "invoice"],
    match_fn=lambda ctx: (
        "阑尾" in ctx.diagnosis
        and ctx.insurance_product == "住院医疗险A"
    ),
    exec_fn=lambda ctx: RuleResult(
        liability="责任范围内",
        confidence=0.95,
        rule_name="急性阑尾炎标准赔付",
        calculated_amount=ctx.total_amount * 0.75,
    ),
)

rule_fracture = ClaimRule(
    name="意外骨折标准赔付",
    priority=85,
    required_docs=["diagnosis", "invoice"],
    match_fn=lambda ctx: (
        "骨折" in ctx.diagnosis
        and ctx.insurance_product == "意外医疗险"
    ),
    exec_fn=lambda ctx: RuleResult(
        liability="责任范围内",
        confidence=0.96,
        rule_name="意外骨折标准赔付",
        calculated_amount=ctx.total_amount * 0.9,
    ),
)

rule_fraud_suspicion = ClaimRule(
    name="疑似欺诈标记",
    priority=95,
    match_fn=lambda ctx: (
        ctx.total_amount > 100000
        or ctx.name_mismatch
    ),
    exec_fn=lambda ctx: RuleResult(
        liability="需人工审核",
        confidence=0.6,
        rule_name="疑似欺诈标记",
        needs_llm=True,
    ),
)

rule_critical_illness = ClaimRule(
    name="重疾案件转人工",
    priority=75,
    match_fn=lambda ctx: (
        "恶性" in ctx.diagnosis
        or "癌" in ctx.diagnosis
    ),
    exec_fn=lambda ctx: RuleResult(
        liability="需人工审核",
        confidence=0.7,
        rule_name="重疾案件转人工",
        needs_llm=True,
    ),
)

rule_fallback = ClaimRule(
    name="兜底规则",
    priority=1,
    match_fn=lambda ctx: True,
    exec_fn=lambda ctx: RuleResult(
        liability="需 LLM 判断",
        confidence=0.5,
        rule_name="兜底规则",
        needs_llm=True,
    ),
)


# ── 全局实例 ──
_default_engine = RuleEngine()
_default_engine.register(rule_outpatient_small)
_default_engine.register(rule_appendectomy)
_default_engine.register(rule_fracture)
_default_engine.register(rule_fraud_suspicion)
_default_engine.register(rule_critical_illness)
_default_engine.register(rule_fallback)


def get_rule_engine() -> RuleEngine:
    return _default_engine
