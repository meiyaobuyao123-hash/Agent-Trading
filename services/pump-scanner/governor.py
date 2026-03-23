"""
Governor -- Optimizer Agent 的调度器和安全守卫

PRD-010 升级：
- 三模块轮转：pump(day%9<3) -> hot(day%9<6) -> agent(day%9>=6)
- 紧急触发：win_rate<40% 或 max_drawdown>10% -> 立即 agent 优化
- 紧急后冷却：跳过下次正常轮转
- 回滚保护：连续恶化 -> 自动回滚
"""

import asyncio
import logging
from datetime import date, timedelta, datetime, timezone

from database import get_db
from optimizer_agent import run_optimization, run_hot_optimization, apply_proposal, TARGETS
from optimizer_tools import tool_read_metrics, tool_read_config

log = logging.getLogger(__name__)

# 冷却状态存储（进程内存级，重启后清除）
_cooldown_until = None  # type: datetime | None


async def run_governor():
    """
    Governor 主入口（由 APScheduler 每3天调用）。

    PRD-010: 三模块轮转 + 紧急触发 + 冷却机制。
    """
    log.info("[Governor] 开始检查...")

    try:
        # 1. 收集当前指标快照（每次都做）
        _save_daily_metrics()

        # 2. 检查是否有未审批的方案（避免重复生成）
        db = get_db()
        pending = db.table("optimization_proposals") \
            .select("id") \
            .eq("status", "pending") \
            .execute()

        if pending.data:
            log.info("[Governor] %d 个待审批方案，跳过新优化", len(pending.data))
            return {
                "status": "pending_proposals",
                "pending_count": len(pending.data),
            }

        # 3. 检查回滚保护
        if _should_rollback():
            log.warning("[Governor] 连续3次优化后指标恶化，触发回滚")
            _auto_rollback()
            return {"status": "rolled_back"}

        # 4. 紧急触发检查 (PRD-010: 优先于正常轮转)
        emergency = _check_emergency_trigger()
        if emergency:
            if _is_in_cooldown():
                log.info("[Governor] Emergency skipped: in cooldown until %s",
                         _cooldown_until)
                return {"status": "emergency_cooldown"}

            log.warning("[Governor] Emergency trigger: %s", emergency)
            _set_cooldown(days=6)  # 紧急后跳过下次正常轮转
            result = await _run_mode("agent")
            return {
                "status": "emergency_optimization",
                "trigger": emergency,
                "result": result,
            }

        # 5. 正常轮转：day%9 决定模式
        day_of_year = date.today().timetuple().tm_yday
        cycle_pos = day_of_year % 9

        if cycle_pos < 3:
            mode = "pump"
        elif cycle_pos < 6:
            mode = "hot"
        else:
            mode = "agent"

        # 冷却检查（紧急优化后跳过下次正常轮）
        if _is_in_cooldown() and mode != "agent":
            log.info("[Governor] Skipping %s: post-emergency cooldown", mode)
            return {"status": "cooldown_skip", "skipped_mode": mode}

        # 6. 读取指标判断是否需要优化（pump/hot 仅在不达标时运行）
        if mode in ("pump", "hot"):
            metrics = tool_read_metrics(days=7)
            perf = metrics.get("performance", {})
            hit_rate = perf.get("hit_rate", 0)
            recall = perf.get("recall", 0)
            f1 = perf.get("f1_score", 0)

            log.info("[Governor] Metrics: hit_rate=%.2f%%, recall=%.2f%%, f1=%.4f",
                     hit_rate * 100, recall * 100, f1)

            targets_met = (
                hit_rate >= TARGETS["hit_rate_7d"]
                and recall >= TARGETS["recall_7d"]
                and f1 >= TARGETS["f1_7d"]
            )
            if targets_met:
                log.info("[Governor] Targets met, skip %s optimization", mode)
                return {"status": "targets_met", "mode": mode, "metrics": perf}

        # 7. 运行优化
        result = await _run_mode(mode)
        log.info("[Governor] %s Optimizer done: %s", mode, result)

        return {"status": "optimization_run", "mode": mode, "result": result}

    except Exception as e:
        log.error("[Governor] Exception: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


async def _run_mode(mode: str) -> dict:
    """运行指定模式的优化。"""
    if mode == "pump":
        log.info("[Governor] Starting Pump Optimizer Agent...")
        return await asyncio.to_thread(run_optimization)
    elif mode == "hot":
        log.info("[Governor] Starting Hot Coin Optimizer Agent...")
        return await asyncio.to_thread(run_hot_optimization)
    elif mode == "agent":
        log.info("[Governor] Starting Agent Full-Chain Optimizer...")
        from optimizer_agent import run_agent_optimization
        return await asyncio.to_thread(run_agent_optimization)
    else:
        raise ValueError("Unknown optimization mode: %s" % mode)


# ============================================================
# 紧急触发 (PRD-010)
# ============================================================

def _check_emergency_trigger() -> str:
    """
    检查紧急触发条件。
    返回触发原因字符串，无触发则返回空字符串。
    """
    try:
        from agent.performance_analytics import get_strategy_performance
        # get_strategy_performance is async, run it sync
        loop = asyncio.new_event_loop()
        try:
            perf = loop.run_until_complete(
                get_strategy_performance("all", days=7)
            )
        finally:
            loop.close()

        win_rate = perf.get("win_rate", 0)
        max_drawdown = perf.get("max_drawdown_pct", 0)

        if win_rate > 0 and win_rate < 0.40:
            return "win_rate=%.1f%% < 40%%" % (win_rate * 100)
        if max_drawdown > 10:
            return "max_drawdown=%.1f%% > 10%%" % max_drawdown

    except Exception as e:
        log.warning("[Governor] Emergency check failed (ok if no trades): %s", e)

    return ""


# ============================================================
# 冷却机制 (PRD-010 Q14)
# ============================================================

def _is_in_cooldown() -> bool:
    """检查是否在冷却期内。"""
    global _cooldown_until
    if _cooldown_until is None:
        return False
    return datetime.now(timezone.utc) < _cooldown_until


def _set_cooldown(days: int = 6):
    """设置冷却期（紧急优化后跳过下次正常轮）。"""
    global _cooldown_until
    _cooldown_until = datetime.now(timezone.utc) + timedelta(days=days)
    log.info("[Governor] Cooldown set until %s", _cooldown_until.isoformat())


def _clear_cooldown():
    """清除冷却（测试用）。"""
    global _cooldown_until
    _cooldown_until = None


# ============================================================
# 每日指标快照
# ============================================================

def _save_daily_metrics():
    """保存每日指标快照到 optimization_metrics_history"""
    db = get_db()
    today = date.today().isoformat()

    existing = db.table("optimization_metrics_history") \
        .select("id") \
        .eq("snapshot_date", today) \
        .execute()

    if existing.data:
        return

    try:
        metrics = tool_read_metrics(days=1)
        perf = metrics.get("performance", {})
        config = tool_read_config()

        db.table("optimization_metrics_history").insert({
            "snapshot_date": today,
            "pump_picks_count": perf.get("total_picks", 0),
            "pump_graduated": perf.get("total_graduated", 0),
            "pump_hit_count": perf.get("hit_count", 0),
            "pump_miss_count": perf.get("miss_count", 0),
            "pump_hit_rate": perf.get("hit_rate", 0),
            "pump_recall": perf.get("recall", 0),
            "pump_precision": perf.get("precision", 0),
            "pump_f1": perf.get("f1_score", 0),
            "scorer_params": config.get("current_params"),
        }).execute()

        log.info("[Governor] Daily metrics snapshot saved: %s", today)
    except Exception as e:
        log.error("[Governor] Failed to save daily metrics: %s", e)


# ============================================================
# 回滚保护
# ============================================================

def _should_rollback() -> bool:
    """检查是否需要回滚（最近3次优化后连续恶化）"""
    db = get_db()

    applied = db.table("optimization_proposals") \
        .select("id, applied_at") \
        .eq("status", "applied") \
        .order("applied_at", desc=True) \
        .limit(3) \
        .execute()

    if len(applied.data) < 3:
        return False

    history = db.table("optimization_metrics_history") \
        .select("snapshot_date, pump_f1") \
        .order("snapshot_date", desc=True) \
        .limit(7) \
        .execute()

    if len(history.data) < 4:
        return False

    f1_values = [float(h.get("pump_f1") or 0) for h in history.data[:4]]
    declining = all(f1_values[i] < f1_values[i + 1] for i in range(3))

    return declining


def _auto_rollback():
    """自动回滚到最近一次 applied 方案之前的参数"""
    db = get_db()

    latest = db.table("optimization_proposals") \
        .select("*") \
        .eq("status", "applied") \
        .order("applied_at", desc=True) \
        .limit(1) \
        .execute()

    if not latest.data:
        log.warning("[Governor] No proposal to rollback")
        return

    proposal = latest.data[0]
    params_before = proposal.get("params_before") or {}

    if not params_before:
        log.warning("[Governor] Proposal has no params_before, cannot rollback")
        return

    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))

    for param, value in params_before.items():
        from optimizer_agent import _apply_config_change
        _apply_config_change(base_dir, param, value)

    db.table("optimization_proposals").update({
        "status": "rolled_back",
        "rolled_back_at": datetime.now(timezone.utc).isoformat(),
        "rollback_reason": "连续3次优化后指标恶化，自动回滚",
    }).eq("id", proposal["id"]).execute()

    log.warning("[Governor] Rolled back proposal #%s", proposal["id"])
