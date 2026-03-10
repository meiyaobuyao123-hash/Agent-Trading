"""
推荐代币表现追踪器

每4小时运行：
  1. 从 daily_picks + hot_daily_picks 初始化新追踪行
  2. 对所有活跃行获取当前价格
  3. 更新 daily_highs 中对应天数的最高价
  4. 超过 30 天的行标记为停用

价格来源：
  - pump.fun 代币: pump.fun REST API → marketCapSol
  - 多链热币: DexScreener API → priceUsd
"""

import logging
import asyncio
import json
import aiohttp
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Dict, List, Any

from database import get_db, upsert_performance, get_active_performance
from config import PUMP_REST, DEXSCREENER_API

log = logging.getLogger(__name__)

TRACK_DAYS = 30
DEXSCREENER_DELAY = 0.3   # 请求间隔 (秒)
PUMP_API_DELAY = 0.5
BATCH_SIZE = 50


async def run_performance_tracker():
    """主入口，由 APScheduler 每 4 小时调用"""
    log.info("📊 表现追踪器启动...")

    try:
        # Step 1: 初始化新推荐的追踪行
        new_pump = _init_pump_picks()
        new_hot = _init_hot_picks()
        log.info(f"初始化新追踪: pump={new_pump}, hot={new_hot}")

        # Step 2: 获取价格并更新活跃行
        active_rows = get_active_performance()
        if not active_rows:
            log.info("无活跃追踪行，跳过价格更新")
            return

        log.info(f"活跃追踪行: {len(active_rows)}")

        async with aiohttp.ClientSession() as session:
            updated = await _update_prices(session, active_rows)
            log.info(f"价格更新完成: {updated} 个代币")

        # Step 3: 停用超过 30 天的行
        deactivated = _deactivate_old()
        if deactivated > 0:
            log.info(f"停用过期追踪: {deactivated} 个")

    except Exception as e:
        log.error(f"表现追踪器异常: {e}", exc_info=True)

    log.info("✅ 表现追踪器完成")


# ── Step 1: 初始化新推荐 ──────────────────────────────────────

def _init_pump_picks() -> int:
    """从 daily_picks 初始化 pump.fun 内盘追踪行"""
    db = get_db()
    cutoff = (date.today() - timedelta(days=TRACK_DAYS + 1)).isoformat()

    try:
        # 获取最近 31 天的 daily_picks
        picks_res = (
            db.table("daily_picks")
            .select("mint, pick_date, rank, score, bc_progress, market_cap_sol, pump_tokens(symbol, name)")
            .gte("pick_date", cutoff)
            .execute()
        )
        picks = picks_res.data
        if not picks:
            return 0

        # 获取已存在的追踪行
        existing = _get_existing_keys("pump")

        new_rows = []
        for p in picks:
            key = f"pump|{p['pick_date']}|solana|{p['mint']}"
            if key in existing:
                continue

            pt = p.get("pump_tokens") or {}
            mc_sol = float(p.get("market_cap_sol") or 0)
            if mc_sol <= 0:
                continue

            new_rows.append({
                "source": "pump",
                "pick_date": p["pick_date"],
                "chain": "solana",
                "address": p["mint"],
                "symbol": pt.get("symbol") or "",
                "name": pt.get("name") or "",
                "rank": p.get("rank"),
                "score": p.get("score"),
                "price_at_pick": mc_sol,
                "denomination": "sol",
                "daily_highs": {},
                "is_active": True,
                "tracking_days": 0,
                "snapshot_data": {
                    "bc_progress": p.get("bc_progress"),
                    "market_cap_sol": mc_sol,
                    "score": p.get("score"),
                },
            })

        if new_rows:
            upsert_performance(new_rows)

        return len(new_rows)

    except Exception as e:
        log.error(f"初始化 pump picks 失败: {e}")
        return 0


def _init_hot_picks() -> int:
    """从 hot_daily_picks 初始化多链热币追踪行"""
    db = get_db()
    cutoff = (date.today() - timedelta(days=TRACK_DAYS + 1)).isoformat()

    try:
        picks_res = (
            db.table("hot_daily_picks")
            .select("pick_date, chain, address, symbol, name, rank, score, "
                    "market_cap_usd, recommendation, snapshot")
            .gte("pick_date", cutoff)
            .execute()
        )
        picks = picks_res.data
        if not picks:
            return 0

        existing = _get_existing_keys("hot")

        new_rows = []
        for p in picks:
            key = f"hot|{p['pick_date']}|{p['chain']}|{p['address']}"
            if key in existing:
                continue

            # 从 snapshot JSONB 中提取推荐时价格
            snapshot = p.get("snapshot") or {}
            if isinstance(snapshot, str):
                try:
                    snapshot = json.loads(snapshot)
                except Exception:
                    snapshot = {}

            price_usd = float(snapshot.get("price_usd") or 0)
            if price_usd <= 0:
                # 尝试从 market_cap_usd 估算
                mc = float(p.get("market_cap_usd") or 0)
                if mc > 0:
                    price_usd = mc  # 用市值作为替代指标
                else:
                    continue

            new_rows.append({
                "source": "hot",
                "pick_date": p["pick_date"],
                "chain": p["chain"],
                "address": p["address"],
                "symbol": p.get("symbol") or "",
                "name": p.get("name") or "",
                "rank": p.get("rank"),
                "score": p.get("score"),
                "price_at_pick": price_usd,
                "denomination": "usd",
                "daily_highs": {},
                "is_active": True,
                "tracking_days": 0,
                "snapshot_data": {
                    "price_usd": price_usd,
                    "market_cap_usd": p.get("market_cap_usd"),
                    "recommendation": p.get("recommendation"),
                },
            })

        if new_rows:
            upsert_performance(new_rows)

        return len(new_rows)

    except Exception as e:
        log.error(f"初始化 hot picks 失败: {e}")
        return 0


def _get_existing_keys(source: str) -> set:
    """获取已存在的追踪行 key 集合"""
    db = get_db()
    try:
        res = (
            db.table("token_performance")
            .select("source, pick_date, chain, address")
            .eq("source", source)
            .execute()
        )
        return {
            f"{r['source']}|{r['pick_date']}|{r['chain']}|{r['address']}"
            for r in res.data
        }
    except Exception as e:
        log.error(f"获取已存在 keys 失败: {e}")
        return set()


# ── Step 2: 获取价格并更新 ──────────────────────────────────────

async def _update_prices(session: aiohttp.ClientSession, rows: List[Dict]) -> int:
    """获取所有活跃代币的当前价格并更新"""
    pump_rows = [r for r in rows if r["source"] == "pump"]
    hot_rows = [r for r in rows if r["source"] == "hot"]

    updated = 0

    # 更新 pump 代币
    for row in pump_rows:
        try:
            price = await _fetch_pump_price(session, row["address"])
            if price is not None and price > 0:
                _apply_price_update(row, price)
                updated += 1
            await asyncio.sleep(PUMP_API_DELAY)
        except Exception as e:
            log.warning(f"pump 价格获取失败 {row.get('symbol', row['address'][:8])}: {e}")

    # 更新 hot 代币
    for row in hot_rows:
        try:
            price = await _fetch_dexscreener_price(session, row["address"])
            if price is not None and price > 0:
                _apply_price_update(row, price)
                updated += 1
            await asyncio.sleep(DEXSCREENER_DELAY)
        except Exception as e:
            log.warning(f"hot 价格获取失败 {row.get('symbol', row['address'][:8])}: {e}")

    # 批量写入更新
    if rows:
        updates = []
        for r in rows:
            if r.get("_updated"):
                updates.append({
                    "source": r["source"],
                    "pick_date": r["pick_date"],
                    "chain": r["chain"],
                    "address": r["address"],
                    "price_at_pick": r["price_at_pick"],
                    "denomination": r.get("denomination", "usd"),
                    "current_price": r["current_price"],
                    "current_pct": r["current_pct"],
                    "current_updated_at": datetime.now(timezone.utc).isoformat(),
                    "daily_highs": r["daily_highs"],
                    "best_price": r.get("best_price"),
                    "best_pct": r.get("best_pct"),
                    "best_day": r.get("best_day"),
                    "tracking_days": r.get("tracking_days", 0),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
        if updates:
            upsert_performance(updates)

    return updated


def _apply_price_update(row: Dict, current_price: float):
    """将当前价格应用到追踪行"""
    price_at_pick = float(row["price_at_pick"])
    if price_at_pick <= 0:
        return

    # 计算当前涨跌幅
    current_pct = (current_price - price_at_pick) / price_at_pick * 100
    row["current_price"] = current_price
    row["current_pct"] = round(current_pct, 2)
    row["_updated"] = True

    # 确定当前是推荐后第几天
    try:
        pick_date = date.fromisoformat(str(row["pick_date"]))
    except (ValueError, TypeError):
        return

    day_number = (date.today() - pick_date).days
    row["tracking_days"] = day_number

    # 更新 daily_highs
    daily_highs = row.get("daily_highs") or {}
    if isinstance(daily_highs, str):
        try:
            daily_highs = json.loads(daily_highs)
        except Exception:
            daily_highs = {}

    if 1 <= day_number <= TRACK_DAYS:
        day_key = str(day_number)
        existing = daily_highs.get(day_key)

        if existing is None or current_price > float(existing.get("high", 0)):
            daily_highs[day_key] = {
                "high": current_price,
                "pct": round(current_pct, 2),
            }

    row["daily_highs"] = daily_highs

    # 更新全周期最佳
    best_price = float(row.get("best_price") or 0)
    if current_price > best_price:
        row["best_price"] = current_price
        row["best_pct"] = round(current_pct, 2)
        row["best_day"] = day_number


async def _fetch_pump_price(session: aiohttp.ClientSession, mint: str) -> Optional[float]:
    """从 pump.fun API 获取代币当前 marketCapSol"""
    try:
        async with session.get(
            f"{PUMP_REST}/coins/{mint}",
            timeout=aiohttp.ClientTimeout(total=8)
        ) as r:
            if r.status == 200:
                data = await r.json()
                mc = data.get("marketCapSol") or data.get("market_cap_sol")
                if mc is not None:
                    return float(mc)
                # 如果有 usdMarketCap 也可以用
                usd_mc = data.get("usdMarketCap")
                if usd_mc is not None:
                    return float(usd_mc)
            elif r.status == 429:
                log.warning("pump.fun API 429, 等待 10s")
                await asyncio.sleep(10)
    except Exception as e:
        log.warning(f"fetch pump price {mint[:8]} 失败: {e}")
    return None


async def _fetch_dexscreener_price(session: aiohttp.ClientSession, address: str) -> Optional[float]:
    """从 DexScreener API 获取代币当前 USD 价格"""
    try:
        async with session.get(
            f"{DEXSCREENER_API}/latest/dex/tokens/{address}",
            timeout=aiohttp.ClientTimeout(total=8)
        ) as r:
            if r.status == 200:
                data = await r.json()
                pairs = data.get("pairs") or []
                if pairs:
                    # 取第一个 pair 的价格（流动性最高的）
                    price_str = pairs[0].get("priceUsd")
                    if price_str:
                        return float(price_str)
            elif r.status == 429:
                log.warning("DexScreener API 429, 等待 5s")
                await asyncio.sleep(5)
    except Exception as e:
        log.warning(f"fetch dexscreener price {address[:8]} 失败: {e}")
    return None


# ── Step 3: 停用过期追踪 ──────────────────────────────────────

def _deactivate_old() -> int:
    """停用超过 30 天的追踪行"""
    db = get_db()
    cutoff = (date.today() - timedelta(days=TRACK_DAYS)).isoformat()

    try:
        res = (
            db.table("token_performance")
            .update({"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("is_active", True)
            .lt("pick_date", cutoff)
            .execute()
        )
        return len(res.data) if res.data else 0
    except Exception as e:
        log.error(f"停用过期追踪失败: {e}")
        return 0


# ── 手动运行 ──────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    asyncio.run(run_performance_tracker())
