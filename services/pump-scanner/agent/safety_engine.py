"""
Safety Engine — runtime check 入口(完整实施 v0.2)
引用 docs/agent-pm/08-safety-policy.md + docs/agent-pm/17-tech-plan.md Phase 0
引用 safety_policy.yaml v0.2

加载 safety_policy.yaml → 构建 30 HR + 13 CB + 5 C 规则集(目前 10 HR + 5 C 实施)
fail-safe: 加载失败 → 整个 Agent BLOCKED(CB12)

调用方:
  - agent/trade_executor.py: T08 execute_swap pre_condition 全校验(W4 接入)
  - agent/loops/notify_loop.py: 触发前(W7 接入)
  - agent/loops/chat_loop.py: LLM 调用前(W7 接入)
  - api/routes_*: 中间件层(W4 接入)

调用约定:
  ctx = {
      "amount_usd": 250.0,
      "daily_total_usd": 1500,
      "strategy_position_pct": 0.05,
      "liquidity_usd": 50000,
      "is_honeypot": False,
      "regime": "TRENDING_UP",       # CRISIS / TRENDING_UP / ...
      "action": "buy",                # buy / sell / hold
      "token_address": "...",
      "blacklist_tokens": ["..."],
      "seconds_since_last_trade": 90,
      "hitl_required": False,
      "hitl_approved": True,
      "agent_global_state": "normal", # normal / blocked / degraded
  }
  results = engine.check_trade(ctx)
  if any(r.outcome == BLOCK for r in results):
      raise SafetyBlocked(results)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from pathlib import Path
import logging
import re

import yaml

log = logging.getLogger(__name__)

POLICY_PATH = Path(__file__).parent / "safety_policy.yaml"


class CheckOutcome(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class CheckResult:
    rule_id: str
    rule_name: str
    outcome: CheckOutcome
    reason: str | None = None
    severity: str = "BLOCK"


# ============================================================
# C 规则的 Python 函数注册(yaml type=function 时按 fn 名查这里)
# ============================================================

def c2_thesis_risks_min_2(ctx: dict) -> bool:
    """触发: risks 长度 < 2"""
    thesis = ctx.get("thesis", {}) or {}
    risks = thesis.get("risks", [])
    if not isinstance(risks, list):
        return True  # 类型错也触发
    return len(risks) < 2


def c3_thesis_evidence_non_empty(ctx: dict) -> bool:
    """触发: evidence 为空 / 无 source 字段"""
    thesis = ctx.get("thesis", {}) or {}
    evidence = thesis.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        return True
    # 每条 evidence 必须有 source(防 LLM 编造)
    for ev in evidence:
        if not isinstance(ev, dict) or not ev.get("source"):
            return True
    return False


def c4_persona_tone(ctx: dict) -> bool:
    """同步 path 占位;异步 LLM judge 由 eval 跑"""
    return False  # 不触发


def c5_hitl_completeness(ctx: dict) -> bool:
    """触发: HITL 必需但缺 approval_id / signature / audit_log_id 之一"""
    if not ctx.get("hitl_required"):
        return False
    return not (
        ctx.get("approval_id")
        and ctx.get("signature")
        and ctx.get("audit_log_id")
    )


C_FUNCTIONS: dict[str, Callable[[dict], bool]] = {
    "c2_thesis_risks_min_2": c2_thesis_risks_min_2,
    "c3_thesis_evidence_non_empty": c3_thesis_evidence_non_empty,
    "c4_persona_tone": c4_persona_tone,
    "c5_hitl_completeness": c5_hitl_completeness,
}


# ============================================================
# 通用 Check Evaluator
# ============================================================

_OPS_2: dict[str, Callable[[Any, Any], bool]] = {
    "gt":          lambda a, b: a is not None and a > b,
    "gte":         lambda a, b: a is not None and a >= b,
    "lt":          lambda a, b: a is not None and a < b,
    "lte":         lambda a, b: a is not None and a <= b,
    "eq":          lambda a, b: a == b,
    "ne":          lambda a, b: a != b,
    "in":          lambda a, b: a in (b or []),
    "not_in":      lambda a, b: a not in (b or []),
    "contains":    lambda a, b: b in (a or ""),
    "starts_with": lambda a, b: isinstance(a, str) and a.startswith(b),
}


def _eval_check(check: dict, ctx: dict) -> bool:
    """对单条 check 求值;返回 True = 触发(命中规则)。"""
    if not check:
        return False
    t = check.get("type")

    if t == "simple":
        actual = ctx.get(check["field"])
        op = check["op"]
        # value 可能直接来自 yaml 静态值,或来自 ctx 的另一个字段
        if "value_field" in check:
            value = ctx.get(check["value_field"], [])
        else:
            value = check.get("value")
        fn = _OPS_2.get(op)
        if fn is None:
            log.warning("unknown op: %s", op)
            return False
        try:
            return bool(fn(actual, value))
        except TypeError:
            return False

    if t == "boolean":
        return bool(ctx.get(check["field"]))

    if t == "compound":
        op = check.get("op", "AND").upper()
        items = check.get("items", [])
        if op == "AND":
            return all(_eval_check(it, ctx) for it in items)
        if op == "OR":
            return any(_eval_check(it, ctx) for it in items)
        if op == "NOT":
            return not _eval_check(items[0], ctx) if items else False
        return False

    if t == "regex":
        text = ctx.get(check["field"], "") or ""
        flags_str = check.get("flags", "")
        flags = 0
        for f in str(flags_str).replace(",", " ").split():
            flags |= getattr(re, f.strip(), 0)
        try:
            return bool(re.search(check["pattern"], str(text), flags))
        except re.error as e:
            log.warning("bad regex in check: %s", e)
            return False

    if t == "function":
        fn = C_FUNCTIONS.get(check.get("fn", ""))
        if fn is None:
            log.warning("unknown function: %s", check.get("fn"))
            return False
        try:
            return bool(fn(ctx))
        except Exception as e:
            log.warning("function check raised: %s", e)
            return False

    log.warning("unknown check type: %s", t)
    return False


def _format_message(template: str, ctx: dict) -> str:
    """简单 ${field} 替换。"""
    if not template:
        return ""
    out = template
    for key, val in ctx.items():
        out = out.replace(f"${{{key}}}", str(val))
    return out


# ============================================================
# Engine 主体
# ============================================================

@dataclass
class SafetyEngine:
    hard_rules: list[dict] = field(default_factory=list)
    circuit_breakers: list[dict] = field(default_factory=list)
    constitutional: list[dict] = field(default_factory=list)
    loaded: bool = False
    load_error: str | None = None
    _active_breakers: set[str] = field(default_factory=set)

    def load(self, path: Path | None = None) -> None:
        p = path or POLICY_PATH
        try:
            with p.open("r", encoding="utf-8") as f:
                policy = yaml.safe_load(f)
            if not isinstance(policy, dict):
                raise ValueError("policy 根必须是 dict")
            self.hard_rules = policy.get("hard_rules", []) or []
            self.circuit_breakers = policy.get("circuit_breakers", []) or []
            self.constitutional = policy.get("constitutional", []) or []
            self.loaded = True
            self.load_error = None
            log.info(
                "[SafetyEngine] loaded HR=%d CB=%d C=%d",
                len(self.hard_rules),
                len(self.circuit_breakers),
                len(self.constitutional),
            )
        except Exception as e:
            self.load_error = str(e)
            self.loaded = False
            log.critical(
                "[SafetyEngine] FAIL-SAFE: policy load failed → BLOCKED. err=%s", e
            )

    # ----- HR 检查入口(trade_executor 调) -----
    def check_trade(self, ctx: dict) -> list[CheckResult]:
        """对一笔潜在交易跑全部 implemented HR;返回所有 BLOCK 结果。
        加载失败时直接返回 CB12 fail-safe。
        """
        if not self.loaded:
            return [
                CheckResult(
                    rule_id="CB12",
                    rule_name="safety_policy 加载失败 fail-safe BLOCKED",
                    outcome=CheckOutcome.BLOCK,
                    reason=self.load_error or "policy not loaded",
                )
            ]

        results: list[CheckResult] = []
        for rule in self.hard_rules:
            if not rule.get("implemented"):
                continue
            check = rule.get("check")
            if not check:
                continue
            if _eval_check(check, ctx):
                results.append(
                    CheckResult(
                        rule_id=rule["id"],
                        rule_name=rule["name"],
                        outcome=CheckOutcome.BLOCK,
                        reason=_format_message(rule.get("message", ""), ctx),
                        severity=rule.get("severity", "BLOCK"),
                    )
                )
        return results

    # ----- Constitutional 检查(LLM 输出过滤) -----
    def check_constitutional(self, text: str, persona: str = "中级",
                             thesis: dict | None = None,
                             hitl_ctx: dict | None = None) -> list[CheckResult]:
        """对 LLM 输出 + thesis + hitl 上下文跑 C1-C5。"""
        if not self.loaded:
            return []

        ctx = {
            "text": text or "",
            "persona": persona,
            "thesis": thesis or {},
        }
        if hitl_ctx:
            ctx.update(hitl_ctx)

        results: list[CheckResult] = []
        for rule in self.constitutional:
            if not rule.get("implemented"):
                continue
            # partial 也跑(C4 只是同步路径不触发)
            check = rule.get("check")
            if not check:
                continue
            if _eval_check(check, ctx):
                results.append(
                    CheckResult(
                        rule_id=rule["id"],
                        rule_name=rule["name"],
                        outcome=CheckOutcome.BLOCK,
                        reason=rule.get("message"),
                        severity="BLOCK",
                    )
                )
        return results

    # ----- CB 状态查询 -----
    def is_breaker_active(self, cb_id: str) -> bool:
        return cb_id in self._active_breakers

    def trip_breaker(self, cb_id: str, reason: str) -> None:
        log.warning("[SafetyEngine] CB tripped: %s (%s)", cb_id, reason)
        self._active_breakers.add(cb_id)
        # TODO: 写 agent_global_state + security_audit_log

    def release_breaker(self, cb_id: str) -> None:
        self._active_breakers.discard(cb_id)


# 全局单例
_engine: SafetyEngine | None = None


def get_safety_engine() -> SafetyEngine:
    global _engine
    if _engine is None:
        _engine = SafetyEngine()
        _engine.load()
    return _engine


def reset_safety_engine_singleton() -> None:
    """测试用:重置单例。"""
    global _engine
    _engine = None
