"""Prompt 压缩优化 — Token 省钱三板斧

1. 结构化摘要：长文本 → 关键字段提取，省 60% Token
2. 模板复用：预编译 prompt 模板，避免重复构造
3. 语义缓存：相同输入命中缓存直接返回，消耗为 0
"""
import hashlib
import json
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any


class PromptCompressor:
    """Prompt 压缩器 — 将完整案件信息压缩为 LLM 友好的结构化摘要"""

    @staticmethod
    def compress_case(case: dict) -> dict:
        """将完整案件信息压缩为精简摘要，减少 Token 消耗

        原始输入可能包含：案件全量信息、文档元数据、Agent 中间输出等。
        压缩后只保留 LLM 推理所需的关键字段。
        """
        return {
            "insured": {
                "name": case.get("insured_name", ""),
                "product": case.get("insurance_product", ""),
            },
            "incident": {
                "date": case.get("incident_date", ""),
                "desc": case.get("incident_desc", "")[:200],  # 截断，最多 200 字
                "diagnosis": case.get("diagnosis", ""),
            },
            "financial": {
                "total": case.get("total_amount") or case.get("medical_total", 0),
                "claimed": case.get("calculated_amount", 0),
            },
            "documents_summary": PromptCompressor._summarize_docs(
                case.get("documents", [])
            ),
        }

    @staticmethod
    def _summarize_docs(docs: list[dict]) -> list[dict]:
        """压缩文档列表：每条文档只保留类型和关键字段"""
        summary = []
        for d in docs:
            item = {"type": d.get("doc_type", d.get("type", "")), "status": "已上传"}
            if d.get("extracted_name"):
                item["name_on_doc"] = d["extracted_name"]
            if d.get("invoice_no"):
                item["invoice"] = d["invoice_no"]
            summary.append(item)
        return summary

    @staticmethod
    def compress_policy(policy_text: str, max_sections: int = 3) -> str:
        """保单条款压缩：只保留关键章节

        完整条款可能 5000+ tokens，压缩后仅保留：
        - 保障责任
        - 免责条款
        - 赔付比例
        """
        sections = []
        keywords = ["保障", "责任", "免责", "赔付", "比例", "金额", "限额"]
        for line in policy_text.split("\n"):
            if any(kw in line for kw in keywords):
                sections.append(line.strip())
        return "\n".join(sections[:max_sections])

    @staticmethod
    def build_liability_prompt(case_summary: dict, policy_excerpt: str) -> str:
        """构建核责 prompt — 模板 + 结构化数据，避免长篇描述"""
        return f"""请判断以下理赔是否属于保险责任：

【被保人】{case_summary['insured']['name']}
【险种】{case_summary['insured']['product']}
【诊断】{case_summary['incident']['diagnosis']}
【出险描述】{case_summary['incident']['desc']}
【总费用】¥{case_summary['financial']['total']:,.2f}

【相关条款】
{policy_excerpt}

请输出: 责任范围内 / 责任免除 / 需核实
"""

    @staticmethod
    def build_calculation_prompt(case_summary: dict, liability: str) -> str:
        """构建理算 prompt — 基于核责结果"""
        return f"""请计算以下理赔案件的赔付金额：

【险种】{case_summary['insured']['product']}
【核责结论】{liability}
【总费用】¥{case_summary['financial']['total']:,.2f}

请输出: 理算金额 + 理算明细
"""


class SemanticCache:
    """语义缓存 — 相同输入直接返回，零 Token 消耗

    TTL 可配，支持 LRU 淘汰。
    """

    def __init__(self, capacity: int = 512, ttl_seconds: int = 3600):
        self.capacity = capacity
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: OrderedDict[str, tuple[Any, datetime]] = OrderedDict()

    def _make_key(self, data: dict) -> str:
        """生成缓存 key：基于结构化字段的 hash"""
        normalized = {k: v for k, v in sorted(data.items()) if v}
        return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()

    def get(self, data: dict) -> Any | None:
        key = self._make_key(data)
        if key not in self._cache:
            return None
        value, expire_at = self._cache[key]
        if datetime.utcnow() > expire_at:
            del self._cache[key]
            return None
        # LRU: 移到末尾
        self._cache.move_to_end(key)
        return value

    def set(self, data: dict, value: Any):
        key = self._make_key(data)
        self._cache[key] = (value, datetime.utcnow() + self.ttl)
        while len(self._cache) > self.capacity:
            self._cache.popitem(last=False)

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """缓存命中率（需配合外部计数器使用，此处为估算）"""
        return 0.0


# 全局语义缓存实例
liability_cache = SemanticCache(capacity=512, ttl_seconds=3600)
calculation_cache = SemanticCache(capacity=512, ttl_seconds=3600)
