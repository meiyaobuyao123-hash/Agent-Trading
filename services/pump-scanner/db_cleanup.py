"""
数据库清理任务 — 控制 Supabase 免费版存储 + 本地 PG TTL

运行时机：每 6 小时（APScheduler 调度）

清理策略（Supabase）：
  token_trades:       保留 3 天（最大表，分批删除避免超时）
  token_snapshots:    保留 14 天
  btc_eth_indicators: 保留 7 天
  btc_eth_alerts:     保留 30 天（非活跃）
  kol_tweets:         保留 30 天
  hot_funnel_stats:   保留 30 天
  token_performance:  保留 90 天（已完成追踪）
  pump_tokens + token_outcomes: 保留 30 天（先删 outcomes 再删 tokens）

清理策略（本地 PostgreSQL，agent_trading_local）— W3 加：
  security_audit_log:        90 天
  pending_approvals:         decided_at + 30 天（已决策的）
  memory_write_wal:          flushed=true + 7 天
  memory_write_retry_queue:  resolved=true + 7 天
  conversation_states:       expires_at + 24h（完结/过期）
  prompt_versions:           status=retired + 30 天
  prompt_invocations:        30 天滚动
  agent_thesis:              30 天（L3+conviction>0.8 例外保 90 天）
  eval_results:              90 天

引用 docs/agent-pm/17-tech-plan.md 增量决策(2026-05-01)
"""

import logging
import time as _time
from datetime import datetime, timezone, timedelta

from database import get_db

log = logging.getLogger(__name__)

# 简单清理：(表名, 时间列, 保留天数, 额外过滤)
SIMPLE_RULES = [
    # ── 高频写入表（优先清理）──
    ("smart_money_signals", "scan_time",   3,   None),   # 最大表！无限增长→3天
    ("smart_money_txns",    "scan_time",   3,   None),   # 实时交易记录→3天
    ("token_snapshots",     "snapshot_at", 5,   None),   # 14天→5天
    # ── 中频表 ──
    ("btc_eth_indicators",  "ts",          7,   None),
    ("token_performance",   "created_at",  30,  {"is_active": False}),  # 90天→30天
    ("token_kol_mentions",  "created_at",  14,  None),   # 先删依赖
    ("kol_tweets",          "created_at",  14,  None),   # 30天→14天
    ("kol_signals",         "detected_at", 14,  None),   # 新增
    # ── 低频表 ──
    ("btc_eth_alerts",      "created_at",  30,  {"is_active": False}),
    ("hot_funnel_stats",    "recorded_at", 30,  None),
    ("agent_risk_events",   "created_at",  30,  None),
    ("agent_alerts",        "created_at",  30,  {"is_read": True}),  # 新增：已读告警30天
    ("agent_memory",        "created_at",  60,  {"type": "episodic"}),  # 新增：中期记忆60天
]


def _delete_in_batches(db, table: str, time_col: str, cutoff: str,
                        extra: dict = None, batch_size: int = 500) -> int:
    """分批删除，避免 Supabase statement timeout"""
    total = 0
    for _ in range(50):  # 最多 50 轮
        try:
            # 找一批要删的 ID
            q = db.table(table).select("id").lt(time_col, cutoff)
            if extra:
                for k, v in extra.items():
                    q = q.eq(k, v)
            res = q.limit(batch_size).execute()
            ids = [r["id"] for r in (res.data or [])]
            if not ids:
                break
            # 按 ID 删除
            db.table(table).delete().in_("id", ids).execute()
            total += len(ids)
            _time.sleep(0.3)  # 防止打满 Supabase
        except Exception as e:
            log.warning(f"  {table} 分批删除异常: {e}")
            break
    return total


def run_db_cleanup():
    """清理过期数据，控制 Supabase 存储"""
    log.info("=== DB 清理开始 ===")
    db = get_db()
    total_deleted = 0

    # 1. token_trades — 最大表，必须分批
    cutoff_3d = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    try:
        cnt = db.table("token_trades").select("*", count="exact") \
            .lt("traded_at", cutoff_3d).limit(0).execute()
        count = cnt.count or 0
        if count > 0:
            deleted = _delete_in_batches(db, "token_trades", "traded_at", cutoff_3d)
            total_deleted += deleted
            log.info(f"  token_trades: 删除 {deleted:,d}/{count:,d} 行（>3 天）")
    except Exception as e:
        log.warning(f"  token_trades: {e}")

    # 2. 简单清理规则
    for table, time_col, retain_days, extra_filters in SIMPLE_RULES:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retain_days)).isoformat()
        try:
            q = db.table(table).select("*", count="exact").lt(time_col, cutoff)
            if extra_filters:
                for k, v in extra_filters.items():
                    q = q.eq(k, v)
            res = q.limit(0).execute()
            count = res.count or 0
            if count == 0:
                continue

            if count > 2000:
                deleted = _delete_in_batches(db, table, time_col, cutoff, extra_filters)
            else:
                d = db.table(table).delete().lt(time_col, cutoff)
                if extra_filters:
                    for k, v in extra_filters.items():
                        d = d.eq(k, v)
                d.execute()
                deleted = count

            total_deleted += deleted
            log.info(f"  {table}: 删除 {deleted:,d} 行（>{retain_days} 天）")
        except Exception as e:
            log.warning(f"  {table}: {e}")

    # 3. pump_tokens + token_outcomes（外键依赖）
    cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        # 先找要删的 mint
        old_tokens = db.table("pump_tokens").select("mint") \
            .lt("created_at", cutoff_30d).eq("complete", False).limit(500).execute()
        mints = [r["mint"] for r in (old_tokens.data or [])]
        if mints:
            # 先删 token_outcomes
            try:
                db.table("token_outcomes").delete().in_("mint", mints).execute()
            except Exception:
                pass
            # 再删 token_snapshots（如果有 mint 外键）
            try:
                db.table("token_snapshots").delete().in_("mint", mints).execute()
            except Exception:
                pass
            # 再删 token_trades
            try:
                db.table("token_trades").delete().in_("mint", mints).execute()
            except Exception:
                pass
            # 最后删 pump_tokens
            db.table("pump_tokens").delete().in_("mint", mints).execute()
            total_deleted += len(mints)
            log.info(f"  pump_tokens+依赖: 删除 {len(mints)} 个代币及关联数据（>30 天未毕业）")
    except Exception as e:
        log.warning(f"  pump_tokens: {e}")

    log.info(f"=== DB 清理完成: 共删除 {total_deleted:,d} 行 ===")
    return total_deleted


# ============================================================
# 本地 PG TTL 清理(W3 加,8 张新表)
# 引用 docs/agent-pm/17-tech-plan.md 增量决策(2026-05-01)
# ============================================================

# (table, sql, retain_days, label) — sql 用 %s 占位 cutoff
LOCAL_PG_RULES = [
    (
        "security_audit_log",
        "DELETE FROM security_audit_log WHERE ts < %s",
        90,
        "security_audit_log >90d",
    ),
    (
        "pending_approvals",
        "DELETE FROM pending_approvals WHERE decided_at < %s AND status != 'pending'",
        30,
        "pending_approvals decided>30d",
    ),
    (
        "memory_write_wal",
        "DELETE FROM memory_write_wal WHERE flushed = true AND flushed_at < %s",
        7,
        "memory_write_wal flushed>7d",
    ),
    (
        "memory_write_retry_queue",
        "DELETE FROM memory_write_retry_queue WHERE resolved = true AND created_at < %s",
        7,
        "memory_write_retry_queue resolved>7d",
    ),
    (
        "conversation_states",
        "DELETE FROM conversation_states WHERE expires_at < %s",
        1,  # 1 天 = 完结后 24h
        "conversation_states expired>24h",
    ),
    (
        "prompt_versions",
        "DELETE FROM prompt_versions WHERE status = 'retired' AND retired_at < %s",
        30,
        "prompt_versions retired>30d",
    ),
    (
        "prompt_invocations",
        "DELETE FROM prompt_invocations WHERE ts < %s",
        30,
        "prompt_invocations >30d",
    ),
    (
        # agent_thesis: 30 天默认,L3 高 conviction>0.8 保留 90 天例外
        "agent_thesis",
        """DELETE FROM agent_thesis
           WHERE ts < %s
             AND NOT (level = 'L3' AND conviction > 0.8 AND ts >= NOW() - INTERVAL '90 days')""",
        30,
        "agent_thesis >30d (L3 高 conviction 例外 90d)",
    ),
    (
        "eval_results",
        "DELETE FROM eval_results WHERE ts < %s",
        90,
        "eval_results >90d",
    ),
]


def run_local_pg_cleanup() -> int:
    """清理本地 PostgreSQL 8 张表。
    每张表独立事务;某张表失败不影响其他;返回总删除数。
    """
    log.info("=== 本地 PG 清理开始 ===")
    try:
        from local_db import _get_conn
    except ImportError as e:
        log.warning("local_db 不可用,跳过本地 PG 清理: %s", e)
        return 0

    try:
        conn = _get_conn()
    except Exception as e:
        log.warning("本地 PG 连接失败,跳过清理: %s", e)
        return 0

    total = 0
    now = datetime.now(timezone.utc)
    for table, sql, retain_days, label in LOCAL_PG_RULES:
        cutoff = now - timedelta(days=retain_days)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (cutoff,))
                deleted = cur.rowcount or 0
            if deleted > 0:
                total += deleted
                log.info("  [local-pg] %s: 删除 %d 行", label, deleted)
        except Exception as e:
            # 表不存在(migration 未跑)忽略
            msg = str(e).lower()
            if "does not exist" in msg or "undefined" in msg:
                log.debug("  [local-pg] %s 表不存在,跳过", table)
            else:
                log.warning("  [local-pg] %s 清理失败: %s", table, e)

    log.info("=== 本地 PG 清理完成: 共 %d 行 ===", total)
    return total


def run_full_cleanup() -> int:
    """全量清理(Supabase + 本地 PG),供 main.py APScheduler 调度。"""
    return run_db_cleanup() + run_local_pg_cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_full_cleanup()
