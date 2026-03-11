"""
热币榜定时任务

  每2小时：run_hot_coin_scan()  — 全链扫描 + 打分 + 写入 hot_coins
  每天 UTC 02:00：run_hot_daily_picks() — 从 hot_coins 取 Top20 写入 hot_daily_picks
"""

import asyncio
import logging
from datetime import datetime, timezone, date
from typing import Dict, List

from hot_coin_fetcher import fetch_hot_coin_candidates
from hot_scorer import score_hot_coin
from database import upsert_hot_coins, save_hot_daily_picks

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 每2小时：扫描 + 打分 + 写库
# ─────────────────────────────────────────────────────────────

async def run_hot_coin_scan():
    """全链扫描热币，打分后 upsert 到 hot_coins 表"""
    log.info("🔥 热币榜扫描开始...")

    try:
        candidates = await fetch_hot_coin_candidates()
        if not candidates:
            log.info("暂无候选，本次跳过")
            return

        now_str = datetime.now(timezone.utc).isoformat()
        rows = []

        for c in candidates:
            result = score_hot_coin(c)

            rows.append({
                "chain":             c["chain"],
                "address":           c["address"],
                "name":              c.get("name"),
                "symbol":            c.get("symbol"),
                "pair_address":      c.get("pair_address"),
                "dex_id":            c.get("dex_id"),
                "price_usd":         c.get("price_usd"),
                "market_cap_usd":    c.get("market_cap_usd"),
                "liquidity_usd":     c.get("liquidity_usd"),
                "volume_24h_usd":    c.get("volume_24h_usd"),
                "volume_1h_usd":     c.get("volume_1h_usd"),
                "price_change_1h":   c.get("price_change_1h"),
                "price_change_6h":   c.get("price_change_6h"),
                "price_change_24h":  c.get("price_change_24h"),
                "buys_1h":           c.get("buys_1h"),
                "sells_1h":          c.get("sells_1h"),
                "buys_24h":          c.get("buys_24h"),
                "sells_24h":         c.get("sells_24h"),
                "pair_created_at":   (
                    c["pair_created_at"].isoformat()
                    if c.get("pair_created_at") else None
                ),
                "age_days":          c.get("age_days"),
                "holder_count":      c.get("holder_count"),
                "top10_holder_pct":  c.get("top10_holder_pct"),
                "top1_holder_pct":   c.get("top1_holder_pct"),
                "is_honeypot":       c.get("is_honeypot", False),
                "is_open_source":    c.get("is_open_source", True),
                "buy_tax":           c.get("buy_tax", 0.0),
                "sell_tax":          c.get("sell_tax", 0.0),
                "goplus_risk":       c.get("goplus_risk", False),
                "has_twitter":       c.get("has_twitter", False),
                "has_telegram":      c.get("has_telegram", False),
                "has_website":       c.get("has_website", False),
                "image_url":         c.get("image_url", ""),
                "score":             result.total,
                "score_m":           result.score_m,
                "score_q":           result.score_q,
                "score_p":           result.score_p,
                "score_detail":      result.detail,
                "recommendation":    result.recommendation,
                "scanned_at":        now_str,
            })

        upsert_hot_coins(rows)

        # 汇总日志
        strong = sum(1 for r in rows if r["recommendation"] == "strong")
        normal = sum(1 for r in rows if r["recommendation"] == "normal")
        by_chain = {}
        for r in rows:
            by_chain[r["chain"]] = by_chain.get(r["chain"], 0) + 1

        chain_summary = "  ".join(f"{k}={v}" for k, v in by_chain.items())
        log.info(
            f"✅ 热币榜更新完成: 强推={strong} 普通={normal} 总计={len(rows)}\n"
            f"   链分布: {chain_summary}"
        )

    except Exception as e:
        log.error(f"热币榜扫描失败: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────
# 每天 UTC 02:00：生成 Top20 日榜
# ─────────────────────────────────────────────────────────────

def run_hot_daily_picks():
    """
    从 hot_coins 中选出当日热币 Top20：
    - 排除 goplus_risk=True 的代币
    - 按 score 降序
    - 每链最多 8 个（避免单链霸榜）
    """
    from database import get_db

    log.info("📋 生成热币日榜 Top20...")
    try:
        db    = get_db()
        today = date.today().isoformat()

        # 拉取评分最高的 100 条（非蜜罐，有评分）
        res = (
            db.table("hot_coins")
            .select("*")
            .eq("goplus_risk", False)
            .eq("is_honeypot", False)
            .not_.is_("score", "null")
            .order("score", desc=True)
            .limit(100)
            .execute()
        )

        if not res.data:
            log.info("hot_coins 暂无数据，跳过日榜生成")
            return

        # 跨链分配：每链最多 8 个，总计最多 20 个
        chain_counts: Dict[str, int] = {}
        picks: List[dict] = []
        for row in res.data:
            chain = row["chain"]
            if chain_counts.get(chain, 0) >= 8:
                continue
            picks.append(row)
            chain_counts[chain] = chain_counts.get(chain, 0) + 1
            if len(picks) >= 20:
                break

        if not picks:
            log.info("暂无合格代币，跳过日榜生成")
            return

        daily_rows = []
        for rank, row in enumerate(picks, 1):
            daily_rows.append({
                "pick_date":       today,
                "chain":           row["chain"],
                "address":         row["address"],
                "name":            row.get("name"),
                "symbol":          row.get("symbol"),
                "rank":            rank,
                "score":           row["score"],
                "market_cap_usd":  row.get("market_cap_usd"),
                "price_change_24h": row.get("price_change_24h"),
                "recommendation":  row.get("recommendation"),
                "snapshot": {
                    "price_usd":       row.get("price_usd"),
                    "volume_24h_usd":  row.get("volume_24h_usd"),
                    "liquidity_usd":   row.get("liquidity_usd"),
                    "holder_count":    row.get("holder_count"),
                    "age_days":        row.get("age_days"),
                    "dex_id":          row.get("dex_id"),
                    "pair_address":    row.get("pair_address"),
                    "score_m":         row.get("score_m"),
                    "score_q":         row.get("score_q"),
                    "score_p":         row.get("score_p"),
                    "score_detail":    row.get("score_detail"),
                    "has_twitter":     row.get("has_twitter"),
                    "has_telegram":    row.get("has_telegram"),
                    "has_website":     row.get("has_website"),
                    "buy_tax":         row.get("buy_tax"),
                    "sell_tax":        row.get("sell_tax"),
                    "top10_holder_pct": row.get("top10_holder_pct"),
                    "top1_holder_pct":  row.get("top1_holder_pct"),
                },
            })

        save_hot_daily_picks(daily_rows)

        chain_summary = "  ".join(f"{k}={v}" for k, v in chain_counts.items())
        log.info(f"✅ 热币日榜生成完成: {len(daily_rows)} 个  链分布: {chain_summary}")

    except Exception as e:
        log.error(f"热币日榜生成失败: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────
# 单独运行测试
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import logging as _log
    _log.basicConfig(
        level=_log.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_hot_coin_scan())
