"""
Cost Guard — LLM 月预算软/硬限熔断(CB04)

引用 docs/agent-pm/13-cost-budget.md
引用 docs/agent-pm/17-tech-plan.md Phase 0
引用 safety_policy.yaml CB04
引用 services/pump-scanner/migrations/local_pg/038_prompt_versions.sql(prompt_invocations)

预算约束(@ 100 DAU,默认 $1500/月,可 env 覆盖):
  全局月度: <= MONTHLY_BUDGET_USD

降级 5 级(CB04 对齐 17-tech-plan.md):
  NORMAL       (< 70%)   model 不变
  SOFT_DEGRADE (70-85%)  Opus → Sonnet
  HARD_DEGRADE (85-95%)  全 Sonnet(L2 也降);Sonnet → Haiku 可选
  EMERGENCY    (95-100%) C2 → L2 简版;L3 不开新案
  HARD_STOP    (100-150%) 拒绝新 LLM 请求
  BLOCKED      (>= 150%) 全局 BLOCKED + safety_engine 强制 trip,待人工

W3 D5+ autonomous-loop 续 15 真实施(替代 W1 占位)。
"""
from __future__ import annotations
import logging
import os
import time as _time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


# 默认 $1500/月(对齐 17-tech-plan.md @ 100 DAU)
MONTHLY_BUDGET_USD = float(os.getenv("LLM_MONTHLY_BUDGET_USD", "1500"))

# 降级阈值(占用百分比)
LEVEL_THRESHOLDS = {
    "SOFT_DEGRADE": 0.70,
    "HARD_DEGRADE": 0.85,
    "EMERGENCY": 0.95,
    "HARD_STOP": 1.00,
    "BLOCKED": 1.50,
}

# 缓存 TTL — 避免每次 LLM 调都查 PG
REFRESH_INTERVAL_S = 60


# 降级 model 映射
MODEL_DOWNGRADES = {
    "claude-opus-4-7":              "claude-sonnet-4-6",
    "claude-opus-latest":           "claude-sonnet-4-6",
    "claude-sonnet-4-6":            "claude-haiku-4-5-20251001",
    "claude-sonnet-latest":         "claude-haiku-4-5-20251001",
    # haiku 已是最便宜,不再降
}


class DegradationLevel(int, Enum):
    NORMAL = 0
    SOFT_DEGRADE = 1     # 70-85%
    HARD_DEGRADE = 2     # 85-95%
    EMERGENCY = 3        # 95-100%
    HARD_STOP = 4        # 100-150%
    BLOCKED = 5          # >= 150%


@dataclass
class BudgetStatus:
    monthly_used_usd: float = 0.0
    monthly_limit_usd: float = MONTHLY_BUDGET_USD
    pct: float = 0.0
    level: DegradationLevel = DegradationLevel.NORMAL
    refreshed_at: float = 0.0


def _level_for_pct(pct: float) -> DegradationLevel:
    if pct >= LEVEL_THRESHOLDS["BLOCKED"]:
        return DegradationLevel.BLOCKED
    if pct >= LEVEL_THRESHOLDS["HARD_STOP"]:
        return DegradationLevel.HARD_STOP
    if pct >= LEVEL_THRESHOLDS["EMERGENCY"]:
        return DegradationLevel.EMERGENCY
    if pct >= LEVEL_THRESHOLDS["HARD_DEGRADE"]:
        return DegradationLevel.HARD_DEGRADE
    if pct >= LEVEL_THRESHOLDS["SOFT_DEGRADE"]:
        return DegradationLevel.SOFT_DEGRADE
    return DegradationLevel.NORMAL


class CostGuard:
    """单例。每 60s 自动 refresh from prompt_invocations.cost_usd 当月 SUM。"""

    def __init__(self) -> None:
        self._status: BudgetStatus = BudgetStatus()
        self._enabled: bool = True
        self._budget: float = MONTHLY_BUDGET_USD

    def set_monthly_budget(self, budget_usd: float) -> None:
        """运行时改预算(测试用 / Admin Kill Switch 临时调整)。"""
        self._budget = float(budget_usd)
        self._status.monthly_limit_usd = self._budget

    def disable(self) -> None:
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True

    # ── refresh ─────────────────────────────────────────────

    async def refresh(self, force: bool = False) -> BudgetStatus:
        """从本地 PG prompt_invocations 表查当月 SUM(cost_usd)。

        失败 swallow → status 保持上次值(避免 PG 抖动让 cost guard 报"无成本")。
        """
        now_ts = _time.time()
        if not force and (now_ts - self._status.refreshed_at) < REFRESH_INTERVAL_S:
            return self._status

        try:
            from local_db import _get_conn
            conn = _get_conn()
            with conn.cursor() as cur:
                # 当月初(UTC)
                now = datetime.now(timezone.utc)
                month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                cur.execute(
                    """
                    SELECT COALESCE(SUM(cost_usd), 0)
                    FROM prompt_invocations
                    WHERE ts >= %s
                    """,
                    (month_start,),
                )
                row = cur.fetchone()
                used = float(row[0] or 0)
        except Exception as e:
            log.debug("[cost_guard] refresh failed (keeping old): %s", e)
            return self._status

        pct = (used / self._budget) if self._budget > 0 else 0.0
        self._status = BudgetStatus(
            monthly_used_usd=round(used, 4),
            monthly_limit_usd=self._budget,
            pct=round(pct, 4),
            level=_level_for_pct(pct),
            refreshed_at=now_ts,
        )
        if self._status.level >= DegradationLevel.SOFT_DEGRADE:
            log.warning(
                "[cost_guard] level=%s used=$%.2f pct=%.1f%% (budget $%.0f)",
                self._status.level.name, used, pct * 100, self._budget,
            )
        return self._status

    # ── public API ──────────────────────────────────────────

    def current_status(self) -> BudgetStatus:
        return self._status

    def current_level(self) -> DegradationLevel:
        return self._status.level

    async def check_before_call(
        self,
        intended_model: str,
        intended_level: str = "L2",
    ) -> "tuple[bool, str, str]":
        """LLM 调用前检查。

        Args:
          intended_model: 想用的 model id
          intended_level: 'L1'/'L2'/'L3'(L3 在 EMERGENCY 时禁)

        Returns:
          (allowed, actual_model, reason)
            allowed:False → 不能调 LLM(caller 该 fallback rule_engine)
            actual_model:可能被降级的 model
            reason:解释
        """
        if not self._enabled:
            return True, intended_model, "cost_guard_disabled"

        await self.refresh()
        level = self.current_level()

        if level == DegradationLevel.BLOCKED:
            return False, intended_model, f"BLOCKED ({self._status.pct*100:.1f}%)"
        if level == DegradationLevel.HARD_STOP:
            return False, intended_model, f"HARD_STOP ({self._status.pct*100:.1f}%)"

        # EMERGENCY:L3 拒;L1/L2 用 haiku
        if level == DegradationLevel.EMERGENCY:
            if intended_level == "L3":
                return False, intended_model, "EMERGENCY: L3 disabled"
            actual = "claude-haiku-4-5-20251001"
            return True, actual, f"EMERGENCY: forced haiku ({self._status.pct*100:.1f}%)"

        # HARD_DEGRADE:全 Sonnet(L2 也降;Sonnet → Haiku 可选)
        if level == DegradationLevel.HARD_DEGRADE:
            actual = MODEL_DOWNGRADES.get(intended_model, intended_model)
            # 二次降:sonnet → haiku
            actual = MODEL_DOWNGRADES.get(actual, actual)
            return True, actual, f"HARD_DEGRADE: forced {actual} ({self._status.pct*100:.1f}%)"

        # SOFT_DEGRADE:Opus → Sonnet
        if level == DegradationLevel.SOFT_DEGRADE:
            actual = MODEL_DOWNGRADES.get(intended_model, intended_model)
            if actual != intended_model:
                return True, actual, f"SOFT_DEGRADE: {intended_model} → {actual}"
            return True, intended_model, f"SOFT_DEGRADE: keep {intended_model}"

        return True, intended_model, "NORMAL"

    def model_for(self, intended_model: str) -> str:
        """同步版本(不 refresh,用 last cached level)。给 sync caller 用。"""
        level = self.current_level()
        if level >= DegradationLevel.HARD_STOP:
            raise RuntimeError(f"CostGuard {level.name}: budget {self._status.pct*100:.1f}%")
        if level == DegradationLevel.EMERGENCY:
            return "claude-haiku-4-5-20251001"
        if level == DegradationLevel.HARD_DEGRADE:
            actual = MODEL_DOWNGRADES.get(intended_model, intended_model)
            return MODEL_DOWNGRADES.get(actual, actual)
        if level == DegradationLevel.SOFT_DEGRADE:
            return MODEL_DOWNGRADES.get(intended_model, intended_model)
        return intended_model

    def can_chat(self) -> bool:
        return self.current_level() < DegradationLevel.HARD_STOP

    def can_run_l3(self) -> bool:
        return self.current_level() < DegradationLevel.EMERGENCY


# ── singleton ────────────────────────────────────────────


_guard: Optional[CostGuard] = None


def get_cost_guard() -> CostGuard:
    global _guard
    if _guard is None:
        _guard = CostGuard()
    return _guard


def reset_for_test() -> None:
    global _guard
    _guard = None
