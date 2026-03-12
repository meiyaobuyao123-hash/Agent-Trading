"""
热币榜定时任务 — 分层更新策略

按各数据源实际更新频率分层调度：

  ┌──────────────┬──────────────────────────────────────────────┬──────────┐
  │ 调度频率     │ 更新内容                                     │ 数据源   │
  ├──────────────┼──────────────────────────────────────────────┼──────────┤
  │ 每5秒        │ price, mc, liq, volume(5M/1H/4H/24H),       │ OKX      │
  │              │ change(5M/1H/4H/24H), txs, holders + 打分   │          │
  │              │ → 所有字段来自同一 price-info 接口，免费搭载  │          │
  ├──────────────┼──────────────────────────────────────────────┼──────────┤
  │ 每10分钟     │ 增量发现 (trending/new pools)                │ Gecko    │
  │ (增量模式)   │ 仅新代币: GoPlus/Helius/DexScreener 富化    │ GoPlus   │
  │              │ 已入库代币: 复用DB安全/社交 + OKX新价格打分  │ Helius   │
  │              │ ~30s/轮 (vs 全量3-5min)                     │ DexScr   │
  ├──────────────┼──────────────────────────────────────────────┼──────────┤
  │ 每天 02:00   │ 日榜 Top20                                  │ DB       │
  └──────────────┴──────────────────────────────────────────────┴──────────┘

  Flutter 实时价格：通过 /api/price/batch 代理，每次请求直取 OKX 最新价格，无缓存。
  OKX lastPriceUsd 为毫秒级更新（每笔链上成交即刷新）。
"""

import asyncio
import logging
from datetime import datetime, timezone, date
from typing import Dict, List

from hot_coin_fetcher import fetch_hot_coin_candidates, refresh_okx_prices
from hot_scorer import score_hot_coin
from database import upsert_hot_coins, save_hot_daily_picks, get_db

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 每10分钟：增量发现（GeckoTerminal → 仅新代币富化 → 打分）
# 已入库代币复用 DB 安全/社交数据 + OKX 最新价格 → 重新打分
# ─────────────────────────────────────────────────────────────

async def run_hot_coin_scan():
    """
    增量全链扫描热币（每10分钟）。
    已入库代币跳过 GoPlus/Helius/DexScreener，复用 DB 缓存的安全/社交数据。
    仅新发现的代币走完整富化流程。
    """
    log.info("热币榜扫描开始（增量模式）...")

    try:
        candidates = await fetch_hot_coin_candidates(incremental=True)
        if not candidates:
            log.info("暂无候选，本次跳过")
            return

        rows = _score_and_format(candidates)
        upsert_hot_coins(rows)
        _log_summary("热币榜更新完成", rows)

    except Exception as e:
        log.error(f"热币榜扫描失败: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────
# 每5秒：OKX 全字段刷新 + 重新打分
# OKX price-info 一次返回所有字段（price/mc/liq/volume/change/holders）
# 价格 = 毫秒级（每笔成交），5M窗口 = 5分钟聚合，holders = 5-15min延迟
# 单轮耗时：OKX 4链 ≈ 2s + 打分 ≈ 0.1s + DB写 ≈ 0.5s ≈ 3s
# ─────────────────────────────────────────────────────────────

async def run_hot_price_refresh():
    """
    OKX 批量刷新已入库代币的全量市场数据（5s 周期），重新打分后更新。
    表现追踪由 performance_tracker.py 独立秒级循环处理，不在此重复。
    """
    log.debug("OKX 市场数据刷新开始...")

    try:
        updated = await refresh_okx_prices()
        if not updated:
            log.debug("OKX 刷新无更新数据")
            return

        rows = _score_and_format(updated)
        upsert_hot_coins(rows)

        log.debug(f"OKX 刷新完成: {len(rows)} 个代币已重新打分")

    except Exception as e:
        log.error(f"OKX 价格刷新失败: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────
# 通用：打分 + 格式化
# ─────────────────────────────────────────────────────────────

def _score_and_format(candidates: List[dict]) -> List[dict]:
    """对候选列表打分并格式化为 DB 行"""
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
            "volume_5m_usd":     c.get("volume_5m_usd"),
            "volume_4h_usd":     c.get("volume_4h_usd"),
            "price_change_1h":   c.get("price_change_1h"),
            "price_change_6h":   c.get("price_change_6h"),
            "price_change_24h":  c.get("price_change_24h"),
            "price_change_5m":   c.get("price_change_5m"),
            "price_change_4h":   c.get("price_change_4h"),
            "buys_1h":           c.get("buys_1h"),
            "sells_1h":          c.get("sells_1h"),
            "buys_24h":          c.get("buys_24h"),
            "sells_24h":         c.get("sells_24h"),
            "pair_created_at":   (
                c["pair_created_at"].isoformat()
                if hasattr(c.get("pair_created_at"), "isoformat") else
                c.get("pair_created_at")
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
            "image_url":         c.get("image_url") or c.get("token_logo_url", ""),
            "circ_supply":       c.get("circ_supply"),
            "token_logo_url":    c.get("token_logo_url", ""),
            "score":             result.total,
            "score_m":           result.score_m,
            "score_q":           result.score_q,
            "score_p":           result.score_p,
            "score_detail":      result.detail,
            "recommendation":    result.recommendation,
            "scanned_at":        now_str,
        })

    return rows


def _log_summary(title: str, rows: List[dict]):
    """输出汇总日志"""
    strong = sum(1 for r in rows if r["recommendation"] == "strong")
    normal = sum(1 for r in rows if r["recommendation"] == "normal")
    by_chain = {}  # type: Dict[str, int]
    for r in rows:
        by_chain[r["chain"]] = by_chain.get(r["chain"], 0) + 1

    chain_summary = "  ".join(f"{k}={v}" for k, v in by_chain.items())
    log.info(
        f"{title}: 强推={strong} 普通={normal} 总计={len(rows)}\n"
        f"   链分布: {chain_summary}"
    )


# ─────────────────────────────────────────────────────────────
# 每天 UTC 02:00：生成 Top20 日榜
# ─────────────────────────────────────────────────────────────

def run_hot_daily_picks():
    """从 hot_coins 中选出当日热币 Top20"""
    from database import get_db

    log.info("生成热币日榜 Top20...")
    try:
        db = get_db()
        today = date.today().isoformat()

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

        chain_counts = {}  # type: Dict[str, int]
        picks = []  # type: List[dict]
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
                "pick_date":        today,
                "chain":            row["chain"],
                "address":          row["address"],
                "name":             row.get("name"),
                "symbol":           row.get("symbol"),
                "rank":             rank,
                "score":            row["score"],
                "market_cap_usd":   row.get("market_cap_usd"),
                "price_change_24h": row.get("price_change_24h"),
                "recommendation":   row.get("recommendation"),
                "snapshot": {
                    "price_usd":        row.get("price_usd"),
                    "volume_24h_usd":   row.get("volume_24h_usd"),
                    "liquidity_usd":    row.get("liquidity_usd"),
                    "holder_count":     row.get("holder_count"),
                    "age_days":         row.get("age_days"),
                    "dex_id":           row.get("dex_id"),
                    "pair_address":     row.get("pair_address"),
                    "score_m":          row.get("score_m"),
                    "score_q":          row.get("score_q"),
                    "score_p":          row.get("score_p"),
                    "score_detail":     row.get("score_detail"),
                    "has_twitter":      row.get("has_twitter"),
                    "has_telegram":     row.get("has_telegram"),
                    "has_website":      row.get("has_website"),
                    "buy_tax":          row.get("buy_tax"),
                    "sell_tax":         row.get("sell_tax"),
                    "top10_holder_pct": row.get("top10_holder_pct"),
                    "top1_holder_pct":  row.get("top1_holder_pct"),
                },
            })

        save_hot_daily_picks(daily_rows)

        chain_summary = "  ".join(f"{k}={v}" for k, v in chain_counts.items())
        log.info(f"热币日榜生成完成: {len(daily_rows)} 个  链分布: {chain_summary}")

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
