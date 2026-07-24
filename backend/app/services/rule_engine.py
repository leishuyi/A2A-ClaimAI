"""规则引擎 — 前置过滤层

设计目标：
- 70% 的简单案件通过规则引擎直接判决，无需调用 LLM
- 规则判决的置信度高于 LLM 时，跳过 LLM 调用
- 降低 Token 消耗和响应延迟

规则优先级：精确匹配 > 范围匹配 > 兜底
"""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class RuleResult:
    liability: str                          # 责任归属: 责任范围内 | 责任免除 | 需人工审核
    confidence: float                       # 置信度 0-1
    rule_name: str                          # 匹配的规则名称
    calculated_amount: float | None = None  # 理算金额
    details: dict = field(default_factory=dict)
    needs_llm: bool = False                 # 是否需要 LLM 补充判断


class ClaimRule:
    """单条理赔规则"""

    def __init__(self, name: str, priority: int,
                 match_fn: Callable[[dict], bool],
                 exec_fn: Callable[[dict], RuleResult]):
        self.name = name
        self.priority = priority
        self.match_fn = match_fn
        self.exec_fn = exec_fn


class RuleEngine:
    """规则引擎 — 注册、匹配、执行"""

    def __init__(self):
        self._rules: list[ClaimRule] = []

    def register(self, rule: ClaimRule):
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, context: dict) -> RuleResult | None:
        """按优先级逐条匹配，命中即执行"""
        for rule in self._rules:
            if rule.match_fn(context):
                return rule.exec_fn(context)
        return None


# ── 预置规则 ──────────────────────────────────────────
# 规则 1: 门诊小额 — 金额 ≤ 2000，明确诊断
rule_outpatient_small = ClaimRule(
    name="门诊小额快速理赔",
    priority=100,
    match_fn=lambda ctx: (
        (ctx.get("total_amount") or ctx.get("medical_total", 0)) <= 2000
        and ctx.get("diagnosis", "") in ("急性上呼吸道感染", "门诊就诊")
    ),
    exec_fn=lambda ctx: RuleResult(
        liability="责任范围内",
        confidence=0.98,
        rule_name="门诊小额快速理赔",
        calculated_amount=(ctx.get("total_amount") or ctx.get("medical_total", 0)) * 0.7,
        details={"说明": "门诊小额，按 70% 比例赔付，免赔额 0"},
    ),
)

# 规则 2: 急性阑尾炎手术 — 住院医疗险A的典型场景
rule_appendectomy = ClaimRule(
    name="急性阑尾炎标准赔付",
    priority=90,
    match_fn=lambda ctx: (
        "阑尾" in (ctx.get("diagnosis") or "")
        and ctx.get("insurance_product") == "住院医疗险A"
    ),
    exec_fn=lambda ctx: RuleResult(
        liability="责任范围内",
        confidence=0.95,
        rule_name="急性阑尾炎标准赔付",
        calculated_amount=(ctx.get("total_amount") or ctx.get("medical_total", 0)) * 0.75,
        details={
            "说明": "急性阑尾炎属保障范围，扣除免赔额后按 75% 赔付",
            "免赔额": 500,
            "赔付比例": "75%",
        },
    ),
)

# 规则 3: 意外骨折 — 意外医疗险
rule_fracture = ClaimRule(
    name="意外骨折标准赔付",
    priority=85,
    match_fn=lambda ctx: (
        "骨折" in (ctx.get("diagnosis") or "")
        and ctx.get("insurance_product") == "意外医疗险"
    ),
    exec_fn=lambda ctx: RuleResult(
        liability="责任范围内",
        confidence=0.96,
        rule_name="意外骨折标准赔付",
        calculated_amount=(ctx.get("total_amount") or ctx.get("medical_total", 0)) * 0.9,
        details={"说明": "意外医疗险骨折门诊，按 90% 赔付，无免赔额"},
    ),
)

# 规则 4: 疑似欺诈 — 金额异常或姓名不匹配
rule_fraud_suspicion = ClaimRule(
    name="疑似欺诈标记",
    priority=95,
    match_fn=lambda ctx: (
        (ctx.get("total_amount") or ctx.get("medical_total", 0)) > 100000
        or ctx.get("name_mismatch", False)
    ),
    exec_fn=lambda ctx: RuleResult(
        liability="需人工审核",
        confidence=0.6,
        rule_name="疑似欺诈标记",
        needs_llm=True,
        details={"原因": "金额异常或人证不一致，需 LLM 辅助判断后人工审核"},
    ),
)

# 规则 5: 重疾 — 恶性肿瘤诊断
rule_critical_illness = ClaimRule(
    name="重疾案件转人工",
    priority=75,
    match_fn=lambda ctx: (
        "恶性" in (ctx.get("diagnosis") or "")
        or "癌" in (ctx.get("diagnosis") or "")
    ),
    exec_fn=lambda ctx: RuleResult(
        liability="需人工审核",
        confidence=0.7,
        rule_name="重疾案件转人工",
        needs_llm=True,
        details={"说明": "重疾案件需核实病理报告，建议 LLM 辅助后人工确认"},
    ),
)

# 规则 6: 兜底 — 其他所有案件走 LLM
rule_fallback = ClaimRule(
    name="兜底规则",
    priority=1,
    match_fn=lambda ctx: True,
    exec_fn=lambda ctx: RuleResult(
        liability="需 LLM 判断",
        confidence=0.5,
        rule_name="兜底规则",
        needs_llm=True,
        details={"说明": "无匹配规则，需要 LLM 处理"},
    ),
)


# ── 全局规则引擎实例 ──────────────────────────────
_default_engine = RuleEngine()
_default_engine.register(rule_outpatient_small)
_default_engine.register(rule_appendectomy)
_default_engine.register(rule_fracture)
_default_engine.register(rule_fraud_suspicion)
_default_engine.register(rule_critical_illness)
_default_engine.register(rule_fallback)


def get_rule_engine() -> RuleEngine:
    return _default_engine
