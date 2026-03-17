"""
Governor — 优化 Agent 的调度器和安全守卫

职责：
1. 每3天检查指标是否达标
2. 不达标时启动 Optimizer Agent
3. 收集每日指标快照
4. 回滚保护：连续恶化 → 自动回滚
"""

import logging
from datetime import date, timedelta, datetime, timezone

from database import get_db
from optimizer_agent import run_optimization, apply_proposal, TARGETS
from optimizer_tools import tool_read_metrics, tool_read_config

log = logging.getLogger(__name__)


async def run_governor():
    """
    Governor 主入口（由 APScheduler 每3天调用）。
    检查指标 → 必要时启动 Optimizer Agent。
    """
    log.info("🏛️ Governor 开始检查...")

    try:
        # 1. 收集当前指标快照（每次都做，不管是否触发优化）
        _save_daily_metrics()

        # 2. 读取7天指标
        metrics = tool_read_metrics(days=7)
        perf = metrics.get("performance", {})
        hit_rate = perf.get("hit_rate", 0)
        recall = perf.get("recall", 0)
        f1 = perf.get("f1_score", 0)

        log.info(
            f"🏛️ 当前指标: hit_rate={hit_rate:.2%}, "
            f"recall={recall:.2%}, f1={f1:.4f}"
        )

        # 3. 检查是否达标
        targets_met = (
            hit_rate >= TARGETS["hit_rate_7d"] and
            recall >= TARGETS["recall_7d"] and
            f1 >= TARGETS["f1_7d"]
        )

        if targets_met:
            log.info("🏛️ ✅ 所有指标达标，跳过优化")
            return {"status": "targets_met", "metrics": perf}

        # 4. 检查是否有未审批的方案（避免重复生成）
        db = get_db()
        pending = db.table("optimization_proposals") \
            .select("id") \
            .eq("status", "pending") \
            .execute()

        if pending.data:
            log.info(f"🏛️ ⏳ 有 {len(pending.data)} 个待审批方案，跳过新优化")
            return {
                "status": "pending_proposals",
                "pending_count": len(pending.data),
            }

        # 5. 检查回滚保护：最近3次优化结果是否连续恶化
        if _should_rollback():
            log.warning("🏛️ ⚠️ 连续3次优化后指标恶化，触发回滚")
            _auto_rollback()
            return {"status": "rolled_back"}

        # 6. 启动 Optimizer Agent
        log.info("🏛️ 🚀 指标未达标，启动 Optimizer Agent...")
        result = run_optimization()
        log.info(f"🏛️ Optimizer 完成: {result}")

        return {"status": "optimization_run", "result": result}

    except Exception as e:
        log.error(f"🏛️ Governor 异常: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def _save_daily_metrics():
    """保存每日指标快照到 optimization_metrics_history"""
    db = get_db()
    today = date.today().isoformat()

    # 检查今天是否已保存
    existing = db.table("optimization_metrics_history") \
        .select("id") \
        .eq("snapshot_date", today) \
        .execute()

    if existing.data:
        return  # 已有

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

        log.info(f"📊 每日指标快照已保存: {today}")
    except Exception as e:
        log.error(f"保存每日指标失败: {e}")


def _should_rollback() -> bool:
    """检查是否需要回滚（最近3次优化后连续恶化）"""
    db = get_db()

    # 获取最近3次 applied 的方案
    applied = db.table("optimization_proposals") \
        .select("id, applied_at") \
        .eq("status", "applied") \
        .order("applied_at", desc=True) \
        .limit(3) \
        .execute()

    if len(applied.data) < 3:
        return False

    # 获取最近7天的每日指标
    history = db.table("optimization_metrics_history") \
        .select("snapshot_date, pump_f1") \
        .order("snapshot_date", desc=True) \
        .limit(7) \
        .execute()

    if len(history.data) < 4:
        return False

    # 简单检查：最近3天 F1 是否连续下降
    f1_values = [float(h.get("pump_f1") or 0) for h in history.data[:4]]
    declining = all(f1_values[i] < f1_values[i+1] for i in range(3))

    return declining


def _auto_rollback():
    """自动回滚到最近一次 applied 方案之前的参数"""
    db = get_db()

    # 找到最近的 applied 方案
    latest = db.table("optimization_proposals") \
        .select("*") \
        .eq("status", "applied") \
        .order("applied_at", desc=True) \
        .limit(1) \
        .execute()

    if not latest.data:
        log.warning("没有可回滚的方案")
        return

    proposal = latest.data[0]
    params_before = proposal.get("params_before") or {}

    if not params_before:
        log.warning("方案没有保存之前的参数，无法回滚")
        return

    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 恢复参数
    for param, value in params_before.items():
        from optimizer_agent import _apply_config_change
        _apply_config_change(base_dir, param, value)

    # 标记方案为回滚
    db.table("optimization_proposals").update({
        "status": "rolled_back",
        "rolled_back_at": datetime.now(timezone.utc).isoformat(),
        "rollback_reason": "连续3次优化后指标恶化，自动回滚",
    }).eq("id", proposal["id"]).execute()

    log.warning(f"🔙 已回滚方案 #{proposal['id']}，参数恢复到之前状态")
