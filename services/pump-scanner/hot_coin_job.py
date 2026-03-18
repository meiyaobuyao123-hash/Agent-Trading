"""
热币榜定时任务 — 分层更新策略 v2

  ┌──────────────┬────────────────────────────────────────────┬──────────┐
  │ 调度频率     │ 更新内容                                   │ 数据源   │
  ├──────────────┼────────────────────────────────────────────┼──────────┤
  │ 毫秒级       │ 价格变动 → PriceFeed 回调 → 重新打分       │ Helius   │
  │ (PriceFeed)  │ → 退出判定 → 节流写DB（5s）                │ DexScr   │
  ├──────────────┼────────────────────────────────────────────┼──────────┤
  │ 每30秒       │ DexScreener 全量刷新多时间帧数据 + 打分     │ DexScr   │
  ├──────────────┼────────────────────────────────────────────┼──────────┤
  │ 每10分钟     │ OKX toplist + GeckoTerminal trending/new   │ OKX      │
  │ (发现层)     │ → 去重 → 硬过滤 → 安全检测 → 入榜判定      │ Gecko    │
  ├──────────────┼────────────────────────────────────────────┼──────────┤
  │ 每天 02:00   │ 日榜 Top20                                 │ DB       │
  └──────────────┴────────────────────────────────────────────┴──────────┘

Python 3.9 兼容。
"""

import asyncio
import logging
from datetime import datetime, timezone, date
from typing import Dict, List

import aiohttp

from hot_coin_fetcher import fetch_hot_coin_candidates, refresh_okx_prices
from hot_scorer import score_hot_coin
from hot_coin_manager import hot_coin_manager
from gecko_discovery import fetch_gecko_candidates
from hot_coin_fetcher import apply_hard_filter, _check_goplus, _get_sol_top1_pct, _get_dexscreener_socials
from database import save_hot_daily_picks, get_db
from price_feed import price_feed
from config import HOT_CHAINS

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 每10分钟：多源发现（OKX + GeckoTerminal）→ Manager 入榜
# ─────────────────────────────────────────────────────────────

async def run_hot_coin_scan():
    """
    增量全链扫描热币（每10分钟）。
    OKX toplist + GeckoTerminal trending/new_pools 合并去重。
    通过 hot_coin_manager 管理入榜/退出。
    """
    log.info("热币榜扫描开始（OKX + GeckoTerminal 双源发现）...")

    try:
        # ── 1. OKX toplist 发现 ──
        okx_candidates = await fetch_hot_coin_candidates(incremental=True)
        log.info(f"  OKX 发现: {len(okx_candidates)} 个候选")

        # ── 2. GeckoTerminal 发现 ──
        gecko_candidates_raw: List[dict] = []
        try:
            async with aiohttp.ClientSession() as session:
                gecko_by_chain = await fetch_gecko_candidates(session)
                for chain, coins in gecko_by_chain.items():
                    gecko_candidates_raw.extend(coins)
            log.info(f"  GeckoTerminal 发现: {len(gecko_candidates_raw)} 个候选")
        except Exception as e:
            log.warning(f"  GeckoTerminal 发现失败（不影响 OKX）: {e}")

        # ── 3. 去重合并（OKX 优先，数据更全） ──
        seen: set = set()
        merged: List[dict] = []

        # OKX 先入
        for c in okx_candidates:
            addr = c["address"].lower()
            if addr not in seen:
                seen.add(addr)
                merged.append(c)

        # GeckoTerminal 补充
        gecko_new = 0
        for c in gecko_candidates_raw:
            addr = c["address"].lower()
            if addr not in seen:
                # GeckoTerminal 候选需要过硬过滤
                ok, reason = apply_hard_filter(c)
                if ok:
                    seen.add(addr)
                    merged.append(c)
                    gecko_new += 1

        log.info(f"  合并去重: OKX={len(okx_candidates)} + Gecko新增={gecko_new} → 总计 {len(merged)}")

        # ── 4. 对 GeckoTerminal 新增的做安全检测（GoPlus） ──
        if gecko_new > 0:
            await _enrich_gecko_candidates(merged, len(okx_candidates))

        # ── 5. 交给 Manager 处理入榜/退出 ──
        before_active = hot_coin_manager.get_active_count()
        before_entries = hot_coin_manager._total_entries
        before_exits = hot_coin_manager._total_exits

        hot_coin_manager.on_discovery_result(merged)

        new_entered = hot_coin_manager._total_entries - before_entries
        new_exited = hot_coin_manager._total_exits - before_exits

        stats = hot_coin_manager.get_stats()
        log.info(
            f"热币榜扫描完成: 活跃={stats['active']} "
            f"本轮入榜={new_entered} 退出={new_exited} "
            f"累计入榜={stats['total_entries']} 退出={stats['total_exits']} "
            f"链分布={stats['by_chain']}"
        )

        # 记录漏斗
        hot_coin_manager.record_funnel(
            discovered=len(okx_candidates) + len(gecko_candidates_raw),
            after_hard_filter=len(merged),
            entered=new_entered,
            exited=new_exited,
        )

    except Exception as e:
        log.error(f"热币榜扫描失败: {e}", exc_info=True)


async def _enrich_gecko_candidates(merged: List[dict], okx_count: int) -> None:
    """对 GeckoTerminal 新增候选做 GoPlus 安全检测"""
    async with aiohttp.ClientSession() as session:
        for i in range(okx_count, len(merged)):
            coin = merged[i]
            if coin.get("data_source") != "gecko_trending":
                continue

            chain = coin.get("chain", "")
            addr = coin["address"]
            goplus_chain = HOT_CHAINS.get(chain, {}).get("goplus_chain", "")

            if goplus_chain:
                gp = await _check_goplus(session, chain, addr, goplus_chain)
                if gp:
                    coin["is_honeypot"] = gp.get("is_honeypot", False)
                    coin["goplus_risk"] = gp.get("goplus_risk", False)
                    coin["top10_holder_pct"] = gp.get("top10_holder_pct")
                    coin["holder_count"] = gp.get("holder_count", 0)
                    coin["is_open_source"] = gp.get("is_open_source", True)
                    coin["buy_tax"] = gp.get("buy_tax", 0.0)
                    coin["sell_tax"] = gp.get("sell_tax", 0.0)
                await asyncio.sleep(0.35)

            # SOL Top1 持有者
            if chain == "solana":
                top1 = await _get_sol_top1_pct(session, addr)
                if top1 is not None:
                    coin["top1_holder_pct"] = top1
                await asyncio.sleep(0.1)

            # DexScreener 社交
            socials = await _get_dexscreener_socials(session, addr)
            if socials:
                coin["has_twitter"] = socials.get("has_twitter", False)
                coin["has_telegram"] = socials.get("has_telegram", False)
                coin["has_website"] = socials.get("has_website", False)
                if not coin.get("image_url") and socials.get("image_url"):
                    coin["image_url"] = socials["image_url"]
            await asyncio.sleep(0.2)


# ─────────────────────────────────────────────────────────────
# 每30秒：DexScreener 全量刷新 → Manager 打分+退出
# ─────────────────────────────────────────────────────────────

async def run_hot_price_refresh():
    """
    DexScreener 批量刷新活跃热币的全量市场数据，
    通过 Manager 重新打分+退出判定。
    """
    log.debug("DexScreener 市场数据刷新开始...")

    try:
        updated = await refresh_okx_prices()
        if not updated:
            log.debug("DexScreener 刷新无更新数据")
            return

        # 交给 Manager 全量刷新（含打分+退出判定）
        hot_coin_manager.on_full_refresh(updated)

        log.debug(f"DexScreener 刷新完成: {len(updated)} 个代币")

    except Exception as e:
        log.error(f"DexScreener 价格刷新失败: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────
# 每天 UTC 02:00：生成 Top20 日榜
# ─────────────────────────────────────────────────────────────

def run_hot_daily_picks():
    """从 hot_coins 中选出当日热币 Top20"""

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
