"""
每日任务：从当天快照中选出 Top 10，写入 daily_picks 表

运行时机：每天 UTC 00:00（或手动触发）
"""

import logging
from datetime import date, datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from database import get_db, save_daily_picks, cleanup_old_trades
from scorer import score, ScoreResult
from features import TokenFeatures, hard_filter

log = logging.getLogger(__name__)


def run_daily_job(pick_date: Optional[date] = None):
    if pick_date is None:
        # 任务在 UTC 00:05 运行，应取前一天的数据
        pick_date = (datetime.now(timezone.utc) - timedelta(hours=1)).date()

    log.info(f"开始生成 {pick_date} 日推荐...")

    db = get_db()

    # 取目标日期所有候选快照（BC进度在窗口内）
    since = datetime.combine(pick_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    until = since + timedelta(days=1)

    res = (
        db.table("token_snapshots")
        .select("""
            mint,
            bc_progress,
            market_cap_sol,
            buy_sell_ratio_count,
            buy_sell_ratio_vol,
            inflow_rate_sol_pm,
            bc_progress_rate,
            dev_sold,
            dev_sold_pct,
            large_buy_count,
            unique_buyers,
            reply_count,
            inflow_acceleration,
            smart_money_count,
            smart_money_net_sol,
            smart_elite_count,
            smart_verified_count,
            smart_watching_count,
            pump_tokens(name, symbol, twitter, telegram, website,
                        creator_prev_tokens, creator_success_rate)
        """)
        .gte("snapshot_at", since.isoformat())
        .lt("snapshot_at", until.isoformat())
        .gte("bc_progress", 3.0)
        .lte("bc_progress", 35.0)
        .execute()
    )

    if not res.data:
        log.warning("今日无候选快照")
        return

    # 按 mint 聚合（取最新快照）
    best: Dict[str, dict] = {}
    for row in res.data:
        mint = row["mint"]
        if mint not in best or row["bc_progress"] > best[mint]["bc_progress"]:
            best[mint] = row

    # 构建 TokenFeatures 并打分
    scored: List[Tuple[float, str, ScoreResult, dict]] = []
    for mint, snap in best.items():
        info = snap.get("pump_tokens") or {}
        f = _snap_to_features(mint, snap, info)
        passed, _ = hard_filter(f)
        if not passed:
            continue
        result = score(f)
        if result.recommendation != "skip":
            scored.append((result.total, mint, result, snap))

    # 降序取 Top 10
    scored.sort(key=lambda x: x[0], reverse=True)
    top10 = scored[:10]

    if not top10:
        log.warning("今日无达标推荐")
        return

    picks = []
    for rank, (total, mint, result, snap) in enumerate(top10, start=1):
        picks.append({
            "pick_date":      pick_date.isoformat(),
            "mint":           mint,
            "rank":           rank,
            "score":          total,
            "score_detail":   result.detail,
            "bc_progress":    snap.get("bc_progress"),
            "market_cap_sol": snap.get("market_cap_sol"),
        })
        log.info(f"  #{rank} {snap.get('pump_tokens', {}).get('symbol','?'):8s} "
                 f"BC={snap.get('bc_progress'):.1f}% 分={total}")

    save_daily_picks(picks)
    cleanup_old_trades()

    log.info(f"✅ 今日 Top {len(picks)} 已写入 daily_picks")
    return picks


def _snap_to_features(mint: str, snap: dict, info: dict) -> TokenFeatures:
    """从快照行还原 TokenFeatures（用于重新打分）"""
    return TokenFeatures(
        mint=mint,
        name=info.get("name", ""),
        symbol=info.get("symbol", ""),
        bc_progress=snap.get("bc_progress", 0),
        market_cap_sol=snap.get("market_cap_sol", 0),
        buy_count=snap.get("buy_count", 0),
        sell_count=snap.get("sell_count", 0),
        buy_volume_sol=snap.get("buy_volume_sol", 0),
        sell_volume_sol=snap.get("sell_volume_sol", 0),
        unique_buyers=snap.get("unique_buyers", 0),
        unique_sellers=snap.get("unique_sellers", 0),
        buy_sell_ratio_count=snap.get("buy_sell_ratio_count", 0),
        buy_sell_ratio_vol=snap.get("buy_sell_ratio_vol", 0),
        inflow_rate_sol_pm=snap.get("inflow_rate_sol_pm", 0),
        bc_speed_pct_per_hour=snap.get("bc_progress_rate", 0),
        dev_sold=snap.get("dev_sold", False),
        dev_sold_pct=snap.get("dev_sold_pct", 0),
        large_buy_count=snap.get("large_buy_count", 0),
        reply_count=snap.get("reply_count", 0),
        # 聪明钱 + 加速度（从快照恢复）
        # 列不存在时(None) → 给中性值而非 0（避免扣35分）
        inflow_acceleration=float(snap.get("inflow_acceleration") if snap.get("inflow_acceleration") is not None else 0.25),
        smart_money_count=int(snap.get("smart_money_count") or 0),
        smart_money_net_sol=float(snap.get("smart_money_net_sol") if snap.get("smart_money_net_sol") is not None else 0.5),
        smart_elite_count=int(snap.get("smart_elite_count") or 0),
        smart_verified_count=int(snap.get("smart_verified_count") if snap.get("smart_verified_count") is not None else 1),
        smart_watching_count=int(snap.get("smart_watching_count") or 0),
        # Social
        has_twitter=bool(info.get("twitter")),
        has_telegram=bool(info.get("telegram")),
        has_website=bool(info.get("website")),
        social_score=int(bool(info.get("twitter"))) +
                     int(bool(info.get("telegram"))) +
                     int(bool(info.get("website"))),
        creator_prev_tokens=int(info.get("creator_prev_tokens", 0)),
        creator_success_rate=float(info.get("creator_success_rate") or 0),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_daily_job()
