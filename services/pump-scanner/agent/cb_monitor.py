"""
CB Monitor — 外部条件触发熔断器(CB07/CB08/CB09/CB11)
引用 docs/agent-pm/17-tech-plan.md Phase 0
引用 services/pump-scanner/agent/safety_engine.py CB 状态管理
引用 docs/agent-pm/08-safety-policy.md circuit_breakers

W3 D4 实施:
  CB07 单代币 1h 内 ≥ 5 次触发 → trip(数据源 agent_executions)
  CB08 pending_approvals expired 累积 > 20 → trip(数据源 pending_approvals)

W4-W6 后续:
  CB09 Memory WAL retry queue > 50 → trip
  CB11 copy_trade 目标 24h 亏 > 30% → trip

由 main.py APScheduler 注册每 5min 跑一次 run_cb_monitor()。
失败不阻断 Agent(safety 高可用)。
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
import logging

log = logging.getLogger(__name__)


@dataclass
class CBCheckResult:
    cb_id: str
    triggered: bool
    metric_value: float | int | None = None
    reason: str = ""


# ============================================================
# 数据查询接口(可替换,便于测试 mock)
# ============================================================

class CBDataSource:
    """CB 触发条件的数据查询接口。生产环境注入真实 DB,测试注入 mock。"""

    async def count_token_triggers_last_hour(self, token_address: str) -> int:
        """CB07:某 token 在过去 1h 内被策略触发的次数(查 agent_executions)。"""
        raise NotImplementedError("CBDataSource.count_token_triggers_last_hour W3 D5 接 Supabase")

    async def list_active_tokens(self) -> list[str]:
        """CB07:返回当前活跃的代币列表(过去 1h 有触发的)。"""
        raise NotImplementedError("CBDataSource.list_active_tokens W3 D5 接 Supabase")

    async def count_expired_approvals(self) -> int:
        """CB08:pending_approvals 累积 expired 数(查本地 PG)。"""
        raise NotImplementedError("CBDataSource.count_expired_approvals W3 D5 接本地 PG")


# 阈值常量(对齐 safety_policy.yaml)
CB07_TOKEN_TRIGGER_THRESHOLD = 5      # 1h 内 ≥ 5 次
CB08_EXPIRED_APPROVALS_THRESHOLD = 20  # 累积 > 20


# ============================================================
# 评估函数
# ============================================================

async def evaluate_cb07(data: CBDataSource) -> list[CBCheckResult]:
    """CB07 单代币重复触发熔断器。

    返回所有命中阈值的 token 对应的 CBCheckResult(triggered=True)。
    若 list_active_tokens 失败,返回空列表(降级)。
    """
    try:
        tokens = await data.list_active_tokens()
    except NotImplementedError:
        return []
    except Exception as e:
        log.warning("[CB07] list_active_tokens 失败: %s", e)
        return []

    results: list[CBCheckResult] = []
    for token in tokens:
        try:
            count = await data.count_token_triggers_last_hour(token)
        except Exception as e:
            log.warning("[CB07] count failed for %s: %s", token, e)
            continue
        if count >= CB07_TOKEN_TRIGGER_THRESHOLD:
            results.append(CBCheckResult(
                cb_id="CB07",
                triggered=True,
                metric_value=count,
                reason=f"代币 {token} 1h 内触发 {count} 次,达到 {CB07_TOKEN_TRIGGER_THRESHOLD} 次阈值",
            ))
    return results


async def evaluate_cb08(data: CBDataSource) -> Optional[CBCheckResult]:
    """CB08 HITL 队列累积 expired 熔断器。
    返回 1 个 CBCheckResult(triggered=True/False)或 None(数据源不可用)。
    """
    try:
        count = await data.count_expired_approvals()
    except NotImplementedError:
        return None
    except Exception as e:
        log.warning("[CB08] count_expired_approvals 失败: %s", e)
        return None

    if count > CB08_EXPIRED_APPROVALS_THRESHOLD:
        return CBCheckResult(
            cb_id="CB08",
            triggered=True,
            metric_value=count,
            reason=f"pending_approvals 累积 expired {count} 条,达到 {CB08_EXPIRED_APPROVALS_THRESHOLD} 条阈值",
        )
    return CBCheckResult(cb_id="CB08", triggered=False, metric_value=count)


# ============================================================
# 主调度
# ============================================================

async def run_cb_monitor(data: CBDataSource | None = None) -> dict:
    """主入口 — 由 APScheduler 每 5min 调一次。
    返回 {triggered: [cb_id], skipped: [cb_id], stats: {...}}。
    任何 CB 失败不阻断其他 CB 检查。
    """
    if data is None:
        data = _get_default_datasource()

    triggered: list[str] = []
    skipped: list[str] = []
    stats: dict = {}

    try:
        from agent.safety_engine import get_safety_engine
        engine = get_safety_engine()
    except Exception as e:
        log.warning("[CBMonitor] safety_engine 不可用,跳过本轮: %s", e)
        return {"triggered": [], "skipped": ["all"], "stats": {"engine_unavailable": True}}

    # CB07
    try:
        cb07_results = await evaluate_cb07(data)
        stats["cb07_token_count"] = len(cb07_results)
        for r in cb07_results:
            if r.triggered and not engine.is_breaker_active("CB07"):
                engine.trip_breaker("CB07", reason=r.reason)
                triggered.append("CB07")
                break  # 一个 token 触发就够了
    except Exception as e:
        log.warning("[CBMonitor] CB07 评估失败: %s", e)
        skipped.append("CB07")

    # CB08
    try:
        cb08_result = await evaluate_cb08(data)
        if cb08_result is None:
            skipped.append("CB08")
        else:
            stats["cb08_expired_count"] = cb08_result.metric_value
            if cb08_result.triggered and not engine.is_breaker_active("CB08"):
                engine.trip_breaker("CB08", reason=cb08_result.reason)
                triggered.append("CB08")
    except Exception as e:
        log.warning("[CBMonitor] CB08 评估失败: %s", e)
        skipped.append("CB08")

    if triggered:
        log.warning("[CBMonitor] tripped CBs: %s", triggered)

    return {"triggered": triggered, "skipped": skipped, "stats": stats}


# ============================================================
# 默认数据源(连真实 DB,W3 D5 实施)
# ============================================================

class _DefaultDataSource(CBDataSource):
    """生产环境数据源:agent_executions(Supabase)+ pending_approvals(本地 PG)。
    W3 D4 占位,W3 D5 接入。
    """
    pass


def _get_default_datasource() -> CBDataSource:
    return _DefaultDataSource()


# 便捷调度入口(APScheduler 直接调)
async def run_cb_monitor_scheduled():
    """APScheduler entry:不接受参数,内部用默认数据源。失败吞掉。"""
    try:
        result = await run_cb_monitor()
        log.info("[CBMonitor] tick: %s", result)
    except Exception as e:
        log.error("[CBMonitor] scheduled tick 异常: %s", e, exc_info=True)
