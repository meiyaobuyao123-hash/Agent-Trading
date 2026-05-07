"""
Safety Engine — runtime check 入口(完整实施 v0.3)
引用 docs/agent-pm/08-safety-policy.md + docs/agent-pm/17-tech-plan.md Phase 0
引用 safety_policy.yaml v0.3

加载 safety_policy.yaml → 30 HR + 13 CB + 5 C 全部 implemented
fail-safe: 加载失败 → 整个 Agent BLOCKED(CB12)

调用方:
  - agent/trade_executor.py: T08 execute_swap pre_condition 全校验(W4 接入)
  - agent/loops/notify_loop.py: 触发前(W7 接入)
  - agent/loops/chat_loop.py: LLM 调用前(W7 接入)
  - api/routes_*: 中间件层(W4 接入)

核心 API:
  engine.check_trade(ctx) → list[CheckResult]      # 跑全部 active CB + implemented HR
  engine.check_constitutional(text, ...) → list[CheckResult]  # 跑 5 C
  engine.trip_breaker(cb_id, reason)               # 主动触发熔断
  engine.release_breaker(cb_id)                    # 主动解除
  engine.is_breaker_active(cb_id) → bool
  engine.get_active_breakers() → dict
  engine.set_state_persister(fn)                   # 注入 DB 持久化回调(W3 D3 接 agent_global_state)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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


@dataclass
class BreakerState:
    cb_id: str
    name: str
    tripped_at: datetime
    auto_release_at: datetime | None    # None = 永久待人工
    reason: str
    severity: str                        # 'blocked' | 'degraded'


# ============================================================
# C 规则 + 部分 HR 的 Python 函数注册
# ============================================================

def c2_thesis_risks_min_2(ctx: dict) -> bool:
    thesis = ctx.get("thesis", {}) or {}
    risks = thesis.get("risks", [])
    if not isinstance(risks, list):
        return True
    return len(risks) < 2


def c3_thesis_evidence_non_empty(ctx: dict) -> bool:
    thesis = ctx.get("thesis", {}) or {}
    evidence = thesis.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        return True
    for ev in evidence:
        if not isinstance(ev, dict) or not ev.get("source"):
            return True
    return False


def c4_persona_tone(ctx: dict) -> bool:
    """同步 path 占位;异步 LLM judge 由 eval 跑"""
    return False


def c5_hitl_completeness(ctx: dict) -> bool:
    if not ctx.get("hitl_required"):
        return False
    return not (
        ctx.get("approval_id")
        and ctx.get("signature")
        and ctx.get("audit_log_id")
    )


def hr01_within_strategy_max(ctx: dict) -> bool:
    """R47 P7 — 触发: 单笔金额超过策略 max_position_usd。

    R47 P7 调整:无 max_position_usd 注入 → 不触发(无封顶模式)。
    若策略显式设了 max_position,仍按策略上限拦。

    paper 模式不检查(paper 不烧真钱)。
    """
    if ctx.get("mode") == "paper":
        return False
    amount = ctx.get("amount_usd")
    if amount is None:
        return False
    cap = ctx.get("max_position_usd")
    if cap is None:
        return False  # R47 P7 — 无封顶,不触发
    try:
        return float(amount) > float(cap)
    except (TypeError, ValueError):
        return False


def hr10_within_authorization(ctx: dict) -> bool:
    """触发: 单笔超过用户授权额度。
    auth_single_trade_max 缺失视为无授权(触发,要求显式提供)。
    """
    amount = ctx.get("amount_usd")
    cap = ctx.get("auth_single_trade_max")
    if amount is None:
        return False  # 没在交易上下文,跳过
    if cap is None:
        return True   # 缺授权,触发
    try:
        return float(amount) > float(cap)
    except (TypeError, ValueError):
        return True


def hr11_credentials_revoked(ctx: dict) -> bool:
    """触发: device.credentials_revoked_at 非空且当前是真金交易。
    paper / notify 不触发。
    """
    if ctx.get("mode") not in ("auto", "live"):
        return False
    return bool(ctx.get("credentials_revoked_at"))


def hr24_slippage_within_limit(ctx: dict) -> bool:
    """触发: 滑点 > 用户配置上限。"""
    slip = ctx.get("slippage_pct")
    cap = ctx.get("max_slippage_pct")
    if slip is None or cap is None:
        return False
    try:
        return float(slip) > float(cap)
    except (TypeError, ValueError):
        return False


CHECK_FUNCTIONS: dict[str, Callable[[dict], bool]] = {
    "c2_thesis_risks_min_2":         c2_thesis_risks_min_2,
    "c3_thesis_evidence_non_empty":  c3_thesis_evidence_non_empty,
    "c4_persona_tone":               c4_persona_tone,
    "c5_hitl_completeness":          c5_hitl_completeness,
    "hr01_within_strategy_max":      hr01_within_strategy_max,    # R47 P6
    "hr10_within_authorization":     hr10_within_authorization,
    "hr11_credentials_revoked":      hr11_credentials_revoked,
    "hr24_slippage_within_limit":    hr24_slippage_within_limit,
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
        fn = CHECK_FUNCTIONS.get(check.get("fn", ""))
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

class SafetyEngine:
    """单例(by get_safety_engine());不直接实例化生产代码。"""

    def __init__(self) -> None:
        self.hard_rules: list[dict] = []
        self.circuit_breakers: list[dict] = []
        self.constitutional: list[dict] = []
        self.hr_to_cb_map: dict[str, str] = {}
        self.loaded: bool = False
        self.load_error: str | None = None
        self._active_breakers: dict[str, BreakerState] = {}
        self._cb_index: dict[str, dict] = {}    # cb_id → yaml entry
        # DB 持久化回调(W3 D3 注入,接 agent_global_state 表)
        self._state_persister: Callable[[dict], None] | None = None

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
            self.hr_to_cb_map = policy.get("hr_to_cb_map", {}) or {}
            self._cb_index = {cb["id"]: cb for cb in self.circuit_breakers if "id" in cb}
            self.loaded = True
            self.load_error = None
            log.info(
                "[SafetyEngine] loaded HR=%d CB=%d C=%d hr→cb=%d",
                len(self.hard_rules),
                len(self.circuit_breakers),
                len(self.constitutional),
                len(self.hr_to_cb_map),
            )
        except Exception as e:
            self.load_error = str(e)
            self.loaded = False
            log.critical(
                "[SafetyEngine] FAIL-SAFE: policy load failed → BLOCKED. err=%s", e
            )

    def set_state_persister(self, fn: Callable[[dict], None] | None) -> None:
        """注入 DB 持久化回调(每次状态变化时调用)。fn(state_dict) 由调用方实现。"""
        self._state_persister = fn

    # ----- HR + CB 统一检查入口 -----
    def check_trade(self, ctx: dict) -> list[CheckResult]:
        """对一笔潜在交易跑 active CB + implemented HR;返回所有 BLOCK 结果。
        加载失败时返回 CB12 fail-safe。
        过程中 HR 触发可能 trip 新 CB(yaml.trips_breaker 字段)。
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

        # 1. 自动释放过期 CB
        self._release_expired_breakers()

        # 2. 检查所有 active CB(blocked 级 → BLOCK,degraded → BLOCK 但带标记)
        results: list[CheckResult] = []
        for cb_id, state in self._active_breakers.items():
            results.append(
                CheckResult(
                    rule_id=cb_id,
                    rule_name=f"CB active: {state.name}",
                    outcome=CheckOutcome.BLOCK,
                    reason=state.reason,
                    severity=state.severity,
                )
            )

        # 3. 跑 HR(即使 CB 已 active,也跑完拿全部违规列表给上层审计)
        for rule in self.hard_rules:
            if not rule.get("implemented"):
                continue
            check = rule.get("check")
            if not check:
                continue
            if _eval_check(check, ctx):
                rid = rule["id"]
                results.append(
                    CheckResult(
                        rule_id=rid,
                        rule_name=rule["name"],
                        outcome=CheckOutcome.BLOCK,
                        reason=_format_message(rule.get("message", ""), ctx),
                        severity=rule.get("severity", "BLOCK"),
                    )
                )
                # HR 触发 → 自动 trip CB(trips_breaker 字段优先,fallback 到 hr_to_cb_map)
                cb_id = rule.get("trips_breaker") or self.hr_to_cb_map.get(rid)
                if cb_id and cb_id not in self._active_breakers:
                    self.trip_breaker(cb_id, reason=f"triggered by {rid}")

        return results

    # ----- Constitutional 检查(LLM 输出过滤) -----
    def check_constitutional(self, text: str, persona: str = "中级",
                             thesis: dict | None = None,
                             hitl_ctx: dict | None = None) -> list[CheckResult]:
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

    # ============================================================
    # CB 状态管理
    # ============================================================

    def trip_breaker(self, cb_id: str, reason: str) -> BreakerState | None:
        """触发熔断;若 cb_id 不在 yaml 注册则忽略。
        幂等:重复 trip 同一 cb 不更新 tripped_at(保留首次触发时间)。
        """
        cb = self._cb_index.get(cb_id)
        if cb is None:
            log.warning("[SafetyEngine] trip 未注册的 CB: %s", cb_id)
            return None

        if cb_id in self._active_breakers:
            return self._active_breakers[cb_id]  # 幂等

        now = datetime.now(timezone.utc)
        auto_min = cb.get("auto_release_after_min")
        auto_release_at = (
            now + timedelta(minutes=auto_min) if auto_min else None
        )
        state = BreakerState(
            cb_id=cb_id,
            name=cb.get("name", cb_id),
            tripped_at=now,
            auto_release_at=auto_release_at,
            reason=reason,
            severity=cb.get("severity", "blocked"),
        )
        self._active_breakers[cb_id] = state
        log.warning(
            "[SafetyEngine] CB tripped: %s (%s) auto_release=%s",
            cb_id, reason, auto_release_at,
        )
        self._notify_state_change()
        return state

    def release_breaker(self, cb_id: str, manual: bool = True) -> bool:
        """解除熔断。manual=True 表示人工解除(写 audit log);auto=自动到期。"""
        if cb_id not in self._active_breakers:
            return False
        state = self._active_breakers.pop(cb_id)
        log.info(
            "[SafetyEngine] CB released: %s (was: %s) manual=%s",
            cb_id, state.reason, manual,
        )
        self._notify_state_change()
        return True

    def is_breaker_active(self, cb_id: str) -> bool:
        self._release_expired_breakers()
        return cb_id in self._active_breakers

    def get_active_breakers(self) -> dict[str, BreakerState]:
        self._release_expired_breakers()
        return dict(self._active_breakers)

    def get_global_state(self) -> str:
        """Agent 全局状态:'normal' / 'degraded' / 'blocked'
        - 任一 blocked 级 CB → blocked
        - 任一 degraded 级 CB → degraded
        - 否则 normal
        """
        self._release_expired_breakers()
        if any(s.severity == "blocked" for s in self._active_breakers.values()):
            return "blocked"
        if any(s.severity == "degraded" for s in self._active_breakers.values()):
            return "degraded"
        return "normal"

    def _release_expired_breakers(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            cb_id for cb_id, s in self._active_breakers.items()
            if s.auto_release_at and s.auto_release_at <= now
        ]
        for cb_id in expired:
            state = self._active_breakers.pop(cb_id)
            log.info("[SafetyEngine] CB auto-released: %s (after %s)",
                     cb_id, state.auto_release_at)
        if expired:
            self._notify_state_change()

    def _notify_state_change(self) -> None:
        """每次 active_breakers 变化时,通知 DB 持久化层。"""
        if self._state_persister is None:
            return
        try:
            payload = {
                "state": self.get_global_state(),
                "active_breakers": [
                    {
                        "cb_id": s.cb_id,
                        "name": s.name,
                        "tripped_at": s.tripped_at.isoformat(),
                        "auto_release_at": (
                            s.auto_release_at.isoformat()
                            if s.auto_release_at else None
                        ),
                        "reason": s.reason,
                        "severity": s.severity,
                    }
                    for s in self._active_breakers.values()
                ],
            }
            self._state_persister(payload)
        except Exception as e:
            log.warning("[SafetyEngine] state persister failed: %s", e)


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
