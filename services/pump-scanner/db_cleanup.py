"""
数据库清理任务 — 控制 Supabase 免费版存储

运行时机：每 6 小时（APScheduler 调度）

清理策略：
  token_trades:       保留 3 天（最大表，分批删除避免超时）
  token_snapshots:    保留 14 天
  btc_eth_indicators: 保留 7 天
  btc_eth_alerts:     保留 30 天（非活跃）
  kol_tweets:         保留 30 天
  hot_funnel_stats:   保留 30 天
  token_performance:  保留 90 天（已完成追踪）
  pump_tokens + token_outcomes: 保留 30 天（先删 outcomes 再删 tokens）
"""

import logging
import time as _time
from datetime import datetime, timezone, timedelta

from database import get_db

log = logging.getLogger(__name__)

# 简单清理：(表名, 时间列, 保留天数, 额外过滤)
SIMPLE_RULES = [
    ("token_snapshots",    "snapshot_at", 14,  None),
    ("btc_eth_indicators", "ts",          7,   None),
    ("btc_eth_alerts",     "created_at",  30,  {"is_active": False}),
    ("kol_tweets",         "created_at",  30,  None),
    ("hot_funnel_stats",   "recorded_at", 30,  None),
    ("token_performance",  "created_at",  90,  {"is_active": False}),
    ("agent_risk_events",  "created_at",  30,  None),  # PRD-005
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_db_cleanup()
