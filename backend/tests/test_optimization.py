"""规则引擎与优化模块测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.rule_engine import get_rule_engine, RuleResult, ClaimRule
from app.services.prompt_compressor import PromptCompressor, SemanticCache


class TestRuleEngine:
    def setup_method(self):
        self.engine = get_rule_engine()

    def test_outpatient_small(self):
        r = self.engine.evaluate({"total_amount": 500, "diagnosis": "急性上呼吸道感染", "insurance_product": "住院医疗险A"})
        assert r is not None
        assert r.rule_name == "门诊小额快速理赔"
        assert not r.needs_llm
        assert r.confidence > 0.9
        assert r.calculated_amount == 350.0

    def test_appendectomy(self):
        r = self.engine.evaluate({"total_amount": 12500, "diagnosis": "急性阑尾炎", "insurance_product": "住院医疗险A"})
        assert r is not None
        assert r.rule_name == "急性阑尾炎标准赔付"
        assert not r.needs_llm
        assert r.calculated_amount == 9375.0

    def test_critical_illness_needs_llm(self):
        r = self.engine.evaluate({"total_amount": 80000, "diagnosis": "恶性肿瘤", "insurance_product": "重疾险"})
        assert r is not None
        assert r.rule_name == "重疾案件转人工"
        assert r.needs_llm

    def test_fraud_suspicion(self):
        r = self.engine.evaluate({"total_amount": 500000, "diagnosis": "骨折", "insurance_product": "意外医疗险", "name_mismatch": True})
        assert r is not None
        assert r.rule_name == "疑似欺诈标记"
        assert r.needs_llm

    def test_fallback_no_match(self):
        r = self.engine.evaluate({"total_amount": 15000, "diagnosis": "罕见病", "insurance_product": "住院医疗险B"})
        assert r is not None
        assert r.rule_name == "兜底规则"
        assert r.needs_llm

    def test_custom_rule(self):
        custom = ClaimRule("自定义", 50, match_fn=lambda ctx: ctx.get("test") == "yes",
                           exec_fn=lambda ctx: RuleResult("通过", 1.0, "自定义"))
        self.engine.register(custom)
        r = self.engine.evaluate({"test": "yes"})
        assert r is not None
        assert r.rule_name == "自定义"


class TestPromptCompressor:
    def test_compress_case(self):
        case = {"insured_name": "张三", "insurance_product": "住院医疗险A",
                "diagnosis": "急性阑尾炎", "total_amount": 12500,
                "incident_desc": "A" * 500}
        compressed = PromptCompressor.compress_case(case)
        assert compressed["insured"]["name"] == "张三"
        assert len(compressed["incident"]["desc"]) <= 200

    def test_compress_policy(self):
        policy = "\n".join(["第1条 保障范围", "第2条 免责条款", "第3条 赔付比例", "第4条 其他"])
        compressed = PromptCompressor.compress_policy(policy, max_sections=3)
        assert "保障" in compressed
        assert "免责" in compressed

    def test_build_prompt(self):
        summary = {"insured": {"name": "张三", "product": "住院医疗险A"},
                   "incident": {"date": "2024-07-20", "desc": "急性阑尾炎", "diagnosis": "急性阑尾炎"},
                   "financial": {"total": 12500, "claimed": 0},
                   "documents_summary": []}
        prompt = PromptCompressor.build_liability_prompt(summary, "保障住院医疗")
        assert "张三" in prompt
        assert "急性阑尾炎" in prompt


class TestSemanticCache:
    def test_hit_and_miss(self):
        cache = SemanticCache(capacity=10, ttl_seconds=60)
        cache.set({"a": 1}, "result_a")
        assert cache.get({"a": 1}) == "result_a"
        assert cache.get({"a": 2}) is None

    def test_eviction(self):
        cache = SemanticCache(capacity=2, ttl_seconds=60)
        cache.set({"k": 1}, "v1")
        cache.set({"k": 2}, "v2")
        cache.set({"k": 3}, "v3")
        assert cache.get({"k": 1}) is None  # 被淘汰
        assert cache.get({"k": 3}) == "v3"

    def test_lru_order(self):
        cache = SemanticCache(capacity=2, ttl_seconds=60)
        cache.set({"k": 1}, "v1")
        cache.set({"k": 2}, "v2")
        cache.get({"k": 1})  # 访问 k1，k1 变为最近使用
        cache.set({"k": 3}, "v3")  # 淘汰 k2
        assert cache.get({"k": 2}) is None
        assert cache.get({"k": 1}) == "v1"

    def test_ttl_expiry(self):
        import time
        cache = SemanticCache(capacity=10, ttl_seconds=1)
        cache.set({"k": 1}, "v1")
        assert cache.get({"k": 1}) == "v1"
        time.sleep(1.5)
        assert cache.get({"k": 1}) is None
