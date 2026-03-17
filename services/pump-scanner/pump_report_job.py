"""
内盘每日数据报表

每天 UTC 00:30 运行（在 daily_picks 之后），汇总前一天的漏斗数据。
数据写入 pump_daily_report 表，供 Admin/App 展示。
"""

import logging
from datetime import date, datetime, timezone, timedelta

from database import get_db
import pump_stats

log = logging.getLogger(__name__)


def run_pump_report(report_date: date = None):
    """生成指定日期的内盘数据报表"""
    if report_date is None:
        # UTC 00:30 运行 → 取前一天
        report_date = (datetime.now(timezone.utc) - timedelta(hours=1)).date()

    log.info(f"生成内盘报表: {report_date}")

    db = get_db()
    since = datetime.combine(report_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    until = since + timedelta(days=1)
    since_iso = since.isoformat()
    until_iso = until.isoformat()

    # ── L1~L3: 采集层（来自实时计数器 + DB）──────────────
    stats = pump_stats.snapshot()

    # 如果计数器日期不匹配（跨天或服务重启），从 DB 补数据
    use_counter = (stats.get("date") == report_date.isoformat())

    if use_counter:
        ws_creates = stats["ws_creates"]
        ws_dropped = stats.get("trade_track_full", 0)  # 交易追踪池满（但已写DB）
        rest_success = stats.get("enrich_success", 0)   # enrich 成功数
        rest_fallback = stats.get("enrich_fail", 0)     # enrich 失败数
        enrich_triggered = stats.get("enrich_triggered", 0)
        ws_reconnects = stats["ws_new_reconnects"] + stats["ws_trade_reconnects"]
        snapshots_written = stats["snapshots_written"]
        filter_pass = stats["hard_filter_pass"]
        filter_fail = stats["hard_filter_fail"]
        signal_entered = stats.get("signal_entered", 0)
        signal_exited = stats.get("signal_exited", 0)
    else:
        # 计数器不可用，从 DB 推算
        ws_creates = 0
        ws_dropped = 0
        rest_success = 0
        rest_fallback = 0
        enrich_triggered = 0
        ws_reconnects = 0
        snapshots_written = 0
        filter_pass = 0
        filter_fail = 0
        signal_entered = 0
        signal_exited = 0

    # ── L2: 我们抓到多少（pump_tokens 当日入库）─────────
    try:
        res = db.table("pump_tokens").select("mint", count="exact").gte(
            "created_at", since_iso
        ).lt("created_at", until_iso).execute()
        tokens_saved = res.count or 0
    except Exception:
        tokens_saved = 0

    # 如果没有计数器数据，用 DB 数据估算
    if not use_counter:
        ws_creates = tokens_saved  # 最少这么多
        # 有 twitter/description 的视为 REST 成功
        try:
            res2 = db.table("pump_tokens").select("mint", count="exact").gte(
                "created_at", since_iso
            ).lt("created_at", until_iso).not_.is_(
                "twitter", "null"
            ).execute()
            rest_success = res2.count or 0
            rest_fallback = tokens_saved - rest_success
        except Exception:
            rest_success = tokens_saved
            rest_fallback = 0

    # ── L4: 进入观察（快照去重代币数）──────────────────
    try:
        res = db.table("token_snapshots").select("mint").gte(
            "snapshot_at", since_iso
        ).lt("snapshot_at", until_iso).execute()
        snapshot_mints = set(r["mint"] for r in res.data) if res.data else set()
        observed_tokens = len(snapshot_mints)
    except Exception:
        snapshot_mints = set()
        observed_tokens = 0

    if not use_counter and observed_tokens > 0:
        # 从快照总数估算
        snapshots_written = len(res.data) if res.data else 0

    # ── L5: 推荐给用户（daily_picks）──────────────────
    try:
        res = db.table("daily_picks").select("mint, score").eq(
            "pick_date", report_date.isoformat()
        ).execute()
        picks = res.data or []
        picks_count = len(picks)
        pick_mints = set(r["mint"] for r in picks)
        # 分数分布
        strong = sum(1 for r in picks if (r.get("score") or 0) >= 75)
        normal = sum(1 for r in picks if 55 <= (r.get("score") or 0) < 75)
    except Exception:
        picks_count = 0
        pick_mints = set()
        strong = 0
        normal = 0

    # ── L6: 真的毕业了（graduated_at 在当天）────────────
    try:
        res = db.table("pump_tokens").select("mint, created_at, graduated_at").eq(
            "complete", True
        ).gte("graduated_at", since_iso).lt("graduated_at", until_iso).execute()
        graduated = res.data or []
        graduated_count = len(graduated)
        graduated_mints = set(r["mint"] for r in graduated)
    except Exception:
        graduated = []
        graduated_count = 0
        graduated_mints = set()

    # ── L7: 推中了 & L8: 漏掉了 ─────────────────────
    hits = pick_mints & graduated_mints
    hit_count = len(hits)
    miss_count = len(graduated_mints - pick_mints)
    false_pos = len(pick_mints - graduated_mints)

    hit_rate = round(hit_count / max(1, picks_count), 3)
    miss_rate = round(miss_count / max(1, graduated_count), 3)

    # ── 质量指标 ────────────────────────────────────
    # 平均毕业耗时
    grad_hours = []
    for g in graduated:
        try:
            c = datetime.fromisoformat(g["created_at"].replace("Z", "+00:00"))
            gr = datetime.fromisoformat(g["graduated_at"].replace("Z", "+00:00"))
            grad_hours.append((gr - c).total_seconds() / 3600)
        except Exception:
            pass
    avg_grad_hours = round(sum(grad_hours) / max(1, len(grad_hours)), 1) if grad_hours else None

    # REST 成功率
    total_fetches = rest_success + rest_fallback
    rest_success_pct = round(rest_success / max(1, total_fetches), 3)

    # 每分钟快照数
    minutes_in_day = 1440
    avg_snapshots_per_min = round(snapshots_written / minutes_in_day, 1) if snapshots_written > 0 else 0

    # ── 组装报表 ────────────────────────────────────
    report = {
        "report_date": report_date.isoformat(),
        "funnel": {
            "ws_creates": ws_creates,
            "ws_dropped": ws_dropped,
            "tokens_saved": tokens_saved,
            "enrich_triggered": enrich_triggered if use_counter else 0,
            "enrich_success": rest_success,
            "enrich_fail": rest_fallback,
            "observed_tokens": observed_tokens,
            "snapshots_written": snapshots_written,
            "picks_count": picks_count,
            "graduated_count": graduated_count,
            "hit_count": hit_count,
            "miss_count": miss_count,
        },
        "scores": {
            "strong": strong,
            "normal": normal,
            "skip": picks_count - strong - normal,
        },
        "accuracy": {
            "hit_rate": hit_rate,
            "miss_rate": miss_rate,
            "false_positive_count": false_pos,
        },
        "quality": {
            "avg_grad_hours": avg_grad_hours,
        },
        "health": {
            "ws_reconnects": ws_reconnects,
            "rest_success_pct": rest_success_pct,
            "avg_snapshots_per_min": avg_snapshots_per_min,
        },
        "signals": {
            "entered": signal_entered,
            "exited": signal_exited,
        },
    }

    # ── 写入 DB ─────────────────────────────────────
    row = {
        "report_date": report_date.isoformat(),
        "ws_creates": ws_creates,
        "tokens_saved": tokens_saved,
        "rest_success": rest_success,
        "rest_fallback": rest_fallback,
        "observed_tokens": observed_tokens,
        "snapshots_written": snapshots_written,
        "picks_count": picks_count,
        "graduated_count": graduated_count,
        "hit_count": hit_count,
        "miss_count": miss_count,
        "hit_rate": hit_rate,
        "miss_rate": miss_rate,
        "avg_grad_hours": avg_grad_hours,
        "ws_reconnects": ws_reconnects,
        "rest_success_pct": rest_success_pct,
        "report_json": report,
    }

    try:
        db.table("pump_daily_report").upsert(
            row, on_conflict="report_date"
        ).execute()
        log.info(
            f"内盘报表已生成: {report_date}\n"
            f"  新币出现={ws_creates}  抓到={tokens_saved}  "
            f"REST成功={rest_success}  兜底={rest_fallback}\n"
            f"  进入观察={observed_tokens}  推荐={picks_count}  "
            f"毕业={graduated_count}\n"
            f"  推中={hit_count}  漏掉={miss_count}  "
            f"命中率={hit_rate:.1%}  漏选率={miss_rate:.1%}"
        )
    except Exception as e:
        log.error(f"报表写入失败: {e}", exc_info=True)

    return report


if __name__ == "__main__":
    import logging as _log
    _log.basicConfig(level=_log.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    # 手动跑指定日期
    from datetime import date as _date
    run_pump_report(_date(2026, 3, 12))
