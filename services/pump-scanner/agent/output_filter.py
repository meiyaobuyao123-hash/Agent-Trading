"""
Output Filter — LLM 输出禁用表达 / Constitutional 校验(C1-C5)
引用 docs/agent-pm/08-safety-policy.md C1-C5
引用 safety_policy.yaml constitutional

任何 LLM 输出在交付给前端前必经此过滤:
  - C1 blocklist regex 拦截(稳的 / 百倍 / moon / ape in 等)
  - C2 thesis.risks ≥ 2 条具体风险(schema 校验)
  - C3 evidence 必须引真实数据源(字段非空+链路可追溯)
  - C4 persona 白话校验(LLM-as-judge,异步采样)
  - C5 HITL 决策路径完整性

状态:🔴 v0.1 占位(W3-W4 实施)
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import logging

log = logging.getLogger(__name__)

# C1 blocklist(初版,会和 safety_policy.yaml C1 同步)
C1_BLOCKLIST_REGEX = re.compile(
    r"(稳的|百倍|千倍|暴涨|错过就亏|guaranteed|to the moon|ape in|10\s*x|100\s*x)",
    re.IGNORECASE,
)


@dataclass
class FilterResult:
    passed: bool
    violations: list[str]
    sanitized_text: str | None = None


def filter_output(text: str, persona: str = "中级") -> FilterResult:
    """对 LLM 输出做 C1 同步检查;C4 异步走 LLM judge,不阻塞用户。
    返回 sanitized 版本(C1 命中 → 替换为 [禁用])或者直接 fail。
    """
    violations: list[str] = []

    # C1 blocklist
    matches = C1_BLOCKLIST_REGEX.findall(text)
    if matches:
        violations.append(f"C1 命中禁用表达: {matches}")

    if violations:
        return FilterResult(
            passed=False,
            violations=violations,
            sanitized_text=C1_BLOCKLIST_REGEX.sub("[禁用]", text),
        )

    return FilterResult(passed=True, violations=[], sanitized_text=text)


def filter_thesis_schema(thesis: dict) -> FilterResult:
    """对 thesis JSON 做 C2/C3 schema 校验。"""
    violations: list[str] = []

    risks = thesis.get("risks", [])
    if not isinstance(risks, list) or len(risks) < 2:
        violations.append("C2: thesis.risks 必须 ≥ 2 条具体风险")

    evidence = thesis.get("evidence", [])
    if not evidence:
        violations.append("C3: thesis.evidence 不能为空(必须引真实数据源)")

    conviction = thesis.get("conviction", 0)
    direction = thesis.get("direction")
    if conviction < 0.5 and direction not in ("hold", "avoid", "neutral"):
        violations.append("PRD 硬约束: conviction<0.5 时 direction 必为 hold/avoid")

    return FilterResult(passed=not violations, violations=violations)


# TODO: filter_user_input — Prompt Injection 防御(XML 包裹 + blocklist + 长度 ≤ 2000 字)
# TODO: filter_persona_tone — C4 LLM-as-judge 异步采样
