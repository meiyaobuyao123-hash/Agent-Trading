"""
Cost Guard — LLM 月预算软/硬限熔断(CB04)
引用 docs/agent-pm/13-cost-budget.md
引用 docs/agent-pm/17-tech-plan.md Phase 0
引用 safety_policy.yaml CB04

预算约束(@100 DAU):
  全局月度: ≤ $1500
  单 device 日: ≤ $1.50
  分 Skill: S01-S03 各 $0.48 / DAU 月;S07 日复盘 $4.50

降级分级(CB04):
  70% → L3 Opus 自动降 Sonnet
  85% → L3 全 Sonnet + L2 降 Sonnet
  95% → C2 → L2(只触发简版分析);C7 简化复盘
  100% → 拒绝新请求(硬停)
  150% → BLOCKED 全局(待人工)

状态:🔴 v0.1 占位(W3-W4 实施)
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import logging

log = logging.getLogger(__name__)


class DegradationLevel(int, Enum):
    NORMAL = 0       # < 70%
    SOFT_DEGRADE = 1 # 70-85% (Opus → Sonnet)
    HARD_DEGRADE = 2 # 85-95% (全 Sonnet)
    EMERGENCY = 3    # 95-100% (简版只跑 L2)
    HARD_STOP = 4    # 100% (拒绝新请求)
    BLOCKED = 5      # 150% (全局 BLOCKED 待人工)


@dataclass
class BudgetStatus:
    monthly_used_usd: float
    monthly_limit_usd: float = 1500.0
    daily_used_usd_avg: float = 0.0
    pct: float = 0.0
    level: DegradationLevel = DegradationLevel.NORMAL


class CostGuard:
    """单例;FastAPI startup 时初始化,每分钟刷新一次。"""

    def __init__(self) -> None:
        self._status: BudgetStatus | None = None

    async def refresh(self) -> BudgetStatus:
        # TODO: 查 prompt_invocations 当月 sum(cost_usd)
        # TODO: 配合 agent_global_state 持久化 level
        raise NotImplementedError("CostGuard Phase 0 W3 实施")

    def current_level(self) -> DegradationLevel:
        if self._status is None:
            return DegradationLevel.NORMAL
        return self._status.level

    def model_for(self, intended_model: str) -> str:
        """按当前降级 level 决定实际用哪个 model。"""
        level = self.current_level()
        if level >= DegradationLevel.HARD_STOP:
            raise RuntimeError(f"CostGuard hard stop: level={level.name}")
        # TODO: 实施降级映射(opus→sonnet→haiku)
        return intended_model

    def can_run_l3(self) -> bool:
        return self.current_level() < DegradationLevel.EMERGENCY

    def can_chat(self) -> bool:
        return self.current_level() < DegradationLevel.HARD_STOP


_guard: CostGuard | None = None


def get_cost_guard() -> CostGuard:
    global _guard
    if _guard is None:
        _guard = CostGuard()
    return _guard
