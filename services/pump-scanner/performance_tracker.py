"""
推荐代币表现追踪器 — 秒级更新

运行模式：asyncio 常驻协程，持续循环：
  hot 代币 → 直调 OKX API（~2-3s/周期），不经 DB 中转
  pump 代币 → pump.fun API（~5s/周期）
  内存缓存 daily_highs → 每 30s 批量落盘 DB

每5分钟慢速检查：
  初始化新推荐 + 停用 >30天的追踪行

架构：
  ┌─ DexScreener API ──────────┐    ┌─ pump.fun API ─────┐
  │ batch prices (2-3s)        │    │ /coins/{mint} 逐个  │
  └──────────┬─────────────────┘    └──────────┬──────────┘
             │                                  │
             ▼                                  ▼
  ┌──────────────────────────────────────────────────────┐
  │     内存 _daily_highs_cache (dict)                    │
  │     每次比较 current > existing.high → 更新           │
  └──────────────────┬───────────────────────────────────┘
                     │ 每 30s flush
                     ▼
  ┌──────────────────────────────────────────────────────┐
  │     Supabase token_performance 表                     │
  └──────────────────────────────────────────────────────┘
"""

import logging
import asyncio
import json
import aiohttp
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Dict, List

from database import get_db, upsert_performance, get_active_performance
from config import PUMP_REST

log = logging.getLogger(__name__)

TRACK_DAYS = 30

# ── 内存缓存 ──────────────────────────────────────────────
# key = "source|pick_date|chain|address"
# value = row dict (含 daily_highs, best_price 等)
_cache = {}           # type: Dict[str, dict]
_cache_dirty = set()  # type: set  # 有更新的 key 集合
_last_flush = 0.0     # 上次落盘时间
_FLUSH_INTERVAL = 30  # 每 30 秒落盘一次

# 慢速检查
_INIT_INTERVAL = 300  # 每 5 分钟初始化+停用
_last_init = 0.0


def _cache_key(row: dict) -> str:
    return f"{row['source']}|{row['pick_date']}|{row['chain']}|{row['address']}"


# ══════════════════════════════════════════════════════════════
#  主入口：常驻协程
# ══════════════════════════════════════════════════════════════

async def run_performance_loop():
    """
    常驻协程，由 main.py 用 asyncio.create_task() 启动。
    无限循环：OKX 价格 → 更新 daily_highs → pump 价格 → flush DB
    """
    global _last_flush, _last_init

    log.info("📊 表现追踪器启动 — 秒级模式")

    # 首次加载缓存
    _load_cache()
    _last_init = asyncio.get_event_loop().time()
    _last_flush = asyncio.get_event_loop().time()

    # 复用 session，避免每秒创建/销毁开销
    session = aiohttp.ClientSession()

    try:
        while True:
            try:
                now = asyncio.get_event_loop().time()

                # ── 慢速路径：初始化 + 停用（每 5 分钟） ──
                if now - _last_init >= _INIT_INTERVAL:
                    _run_init_and_cleanup()
                    _last_init = now

                # ── 快速路径：拉价格 + 更新内存 ──
                # Hot 代币：直调 OKX API
                hot_updated = await _tick_hot(session)

                # Pump 代币：pump.fun API
                pump_updated = await _tick_pump(session)

                # ── 定期落盘 ──
                if now - _last_flush >= _FLUSH_INTERVAL and _cache_dirty:
                    _flush_to_db()
                    _last_flush = now

                total = hot_updated + pump_updated
                if total > 0:
                    log.debug(f"📊 秒级追踪: hot={hot_updated} pump={pump_updated} dirty={len(_cache_dirty)}")

                # 短暂休眠，避免空转
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                # 优雅关闭：最后一次落盘
                if _cache_dirty:
                    _flush_to_db()
                log.info("📊 表现追踪器停止")
                break
            except Exception as e:
                log.error(f"表现追踪循环异常: {e}", exc_info=True)
                await asyncio.sleep(5)
    finally:
        await session.close()


# ── 兼容 APScheduler 的入口（如果不用常驻协程模式） ──

async def run_performance_tracker():
    """APScheduler 兼容入口，每次调用执行一轮追踪"""
    global _last_flush, _last_init

    if not _cache:
        _load_cache()
        _last_init = asyncio.get_event_loop().time()
        _last_flush = asyncio.get_event_loop().time()

    try:
        now = asyncio.get_event_loop().time()

        # 慢速检查
        if now - _last_init >= _INIT_INTERVAL:
            _run_init_and_cleanup()
            _last_init = now

        async with aiohttp.ClientSession() as session:
            await _tick_hot(session)
            await _tick_pump(session)

        # 落盘
        if now - _last_flush >= _FLUSH_INTERVAL and _cache_dirty:
            _flush_to_db()
            _last_flush = now

    except Exception as e:
        log.error(f"表现追踪异常: {e}", exc_info=True)


# ══════════════════════════════════════════════════════════════
#  Hot 代币：直调 OKX API（秒级）
# ══════════════════════════════════════════════════════════════

async def _tick_hot(session: aiohttp.ClientSession) -> int:
    """DexScreener 批量获取价格（OKX price-info 需白名单暂不可用）"""
    hot_rows = [v for v in _cache.values() if v["source"] == "hot" and v.get("is_active")]
    if not hot_rows:
        return 0

    # 按链分组
    by_chain = {}  # type: Dict[str, List[dict]]
    for row in hot_rows:
        chain = row["chain"]
        by_chain.setdefault(chain, []).append(row)

    updated = 0
    for chain, rows in by_chain.items():
        addresses = [r["address"] for r in rows]
        dex_prices = await _dexscreener_batch_prices(session, addresses)

        for row in rows:
            addr_lower = row["address"].lower()
            price = dex_prices.get(addr_lower, 0.0)
            if price > 0 and _apply_price_update(row, price):
                updated += 1

    return updated


async def _dexscreener_batch_prices(
    session: aiohttp.ClientSession,
    addresses: List[str],
) -> Dict[str, float]:
    """DexScreener 批量获取价格（仅 price）"""
    result = {}  # type: Dict[str, float]
    from config import DEXSCREENER_API

    for i in range(0, len(addresses), 30):
        batch = addresses[i:i + 30]
        joined = ",".join(batch)
        try:
            url = f"{DEXSCREENER_API}/tokens/v1/{joined}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    # 逐个查
                    for addr in batch:
                        p = await _dexscreener_single_price(session, addr)
                        if p > 0:
                            result[addr.lower()] = p
                    continue
                data = await resp.json()
                pairs = data if isinstance(data, list) else data.get("pairs", [])
                for pair in pairs:
                    base = pair.get("baseToken", {})
                    addr_lower = (base.get("address") or "").lower()
                    try:
                        p = float(pair.get("priceUsd") or 0)
                    except (ValueError, TypeError):
                        p = 0.0
                    if addr_lower and p > 0 and addr_lower not in result:
                        result[addr_lower] = p
        except Exception as e:
            log.debug(f"DexScreener batch price {i}: {e}")
            for addr in batch:
                p = await _dexscreener_single_price(session, addr)
                if p > 0:
                    result[addr.lower()] = p

        if i + 30 < len(addresses):
            await asyncio.sleep(0.5)

    return result


async def _dexscreener_single_price(
    session: aiohttp.ClientSession,
    address: str,
) -> float:
    """单个代币 DexScreener 价格"""
    from config import DEXSCREENER_API
    try:
        url = f"{DEXSCREENER_API}/latest/dex/tokens/{address}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return 0.0
            data = await resp.json()
            pairs = data.get("pairs") or []
            if pairs:
                return float(pairs[0].get("priceUsd") or 0)
    except Exception:
        pass
    return 0.0


# ══════════════════════════════════════════════════════════════
#  Pump 代币：pump.fun API（秒级）
# ══════════════════════════════════════════════════════════════

async def _tick_pump(session: aiohttp.ClientSession) -> int:
    """逐个调用 pump.fun API"""
    pump_rows = [v for v in _cache.values() if v["source"] == "pump" and v.get("is_active")]
    if not pump_rows:
        return 0

    updated = 0
    for row in pump_rows[:20]:  # 每轮最多20个，控制总耗时
        try:
            price = await _fetch_pump_price(session, row["address"])
            if price is not None and price > 0:
                if _apply_price_update(row, price):
                    updated += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            log.warning(f"pump 价格失败 {row.get('symbol', '?')}: {e}")

    return updated


async def _fetch_pump_price(session: aiohttp.ClientSession, mint: str) -> Optional[float]:
    """从 pump.fun API 获取代币当前 marketCapSol"""
    try:
        async with session.get(
            f"{PUMP_REST}/coins/{mint}",
            timeout=aiohttp.ClientTimeout(total=5)
        ) as r:
            if r.status == 200:
                data = await r.json()
                mc = data.get("marketCapSol") or data.get("market_cap_sol")
                if mc is not None:
                    return float(mc)
                usd_mc = data.get("usdMarketCap")
                if usd_mc is not None:
                    return float(usd_mc)
            elif r.status == 429:
                await asyncio.sleep(3)
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════
#  核心：价格更新 + daily_highs（纯内存操作）
# ══════════════════════════════════════════════════════════════

def _apply_price_update(row: dict, current_price: float) -> bool:
    """
    将当前价格应用到追踪行，更新 daily_highs + best。
    纯内存操作，不写 DB。返回 True 表示有新的 high。
    """
    price_at_pick = float(row.get("price_at_pick") or 0)
    if price_at_pick <= 0:
        return False

    current_pct = (current_price - price_at_pick) / price_at_pick * 100
    row["current_price"] = current_price
    row["current_pct"] = round(current_pct, 2)

    try:
        pick_date = date.fromisoformat(str(row["pick_date"]))
    except (ValueError, TypeError):
        return False

    day_number = (date.today() - pick_date).days
    row["tracking_days"] = day_number

    # 更新 daily_highs
    daily_highs = row.get("daily_highs") or {}
    if isinstance(daily_highs, str):
        try:
            daily_highs = json.loads(daily_highs)
        except Exception:
            daily_highs = {}

    new_high = False
    if 0 <= day_number <= TRACK_DAYS:
        day_key = f"D{day_number}"
        existing = daily_highs.get(day_key)
        if existing is None or current_price > float(existing.get("high", 0)):
            daily_highs[day_key] = {
                "high": round(current_price, 10),
                "pct": round(current_pct, 2),
                "at": datetime.now(timezone.utc).isoformat(),
            }
            new_high = True

    row["daily_highs"] = daily_highs

    # 全周期最佳
    best_price = float(row.get("best_price") or 0)
    if best_price <= 0 or current_price > best_price:
        row["best_price"] = current_price
        row["best_pct"] = round(current_pct, 2)
        row["best_day"] = day_number
        new_high = True

    # 标记 dirty
    key = _cache_key(row)
    _cache_dirty.add(key)

    return new_high


# ══════════════════════════════════════════════════════════════
#  缓存管理
# ══════════════════════════════════════════════════════════════

def _load_cache():
    """从 DB 加载所有活跃追踪行到内存"""
    global _cache
    rows = get_active_performance()
    _cache = {}
    for r in rows:
        key = _cache_key(r)
        # 确保 daily_highs 是 dict
        dh = r.get("daily_highs") or {}
        if isinstance(dh, str):
            try:
                dh = json.loads(dh)
            except Exception:
                dh = {}
        r["daily_highs"] = dh
        _cache[key] = r
    log.info(f"📊 缓存加载: {len(_cache)} 条追踪行 (hot={sum(1 for v in _cache.values() if v['source']=='hot')}, pump={sum(1 for v in _cache.values() if v['source']=='pump')})")


def _flush_to_db():
    """将 dirty 行批量写回 DB"""
    global _cache_dirty
    if not _cache_dirty:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    updates = []
    for key in list(_cache_dirty):
        row = _cache.get(key)
        if not row:
            continue
        updates.append({
            "source": row["source"],
            "pick_date": row["pick_date"],
            "chain": row["chain"],
            "address": row["address"],
            "price_at_pick": row["price_at_pick"],
            "denomination": row.get("denomination", "usd"),
            "current_price": row.get("current_price"),
            "current_pct": row.get("current_pct"),
            "current_updated_at": now_iso,
            "daily_highs": row.get("daily_highs"),
            "best_price": row.get("best_price"),
            "best_pct": row.get("best_pct"),
            "best_day": row.get("best_day"),
            "tracking_days": row.get("tracking_days", 0),
            "updated_at": now_iso,
        })

    if updates:
        upsert_performance(updates)
        log.info(f"📊 落盘: {len(updates)} 条 dirty 行写入 DB")

    _cache_dirty.clear()


# ══════════════════════════════════════════════════════════════
#  慢速路径：初始化 + 停用
# ══════════════════════════════════════════════════════════════

def _run_init_and_cleanup():
    """初始化新推荐 + 停用过期行 + 刷新缓存"""
    new_pump = _init_pump_picks()
    new_hot = _init_hot_picks()
    if new_pump or new_hot:
        log.info(f"📊 初始化新追踪: pump={new_pump}, hot={new_hot}")

    deactivated = _deactivate_old()
    if deactivated:
        log.info(f"📊 停用过期追踪: {deactivated}")

    # 刷新缓存（包含新行）
    _load_cache()


def _init_pump_picks() -> int:
    """从 daily_picks 初始化 pump.fun 内盘追踪行"""
    db = get_db()
    cutoff = (date.today() - timedelta(days=TRACK_DAYS + 1)).isoformat()

    try:
        picks_res = (
            db.table("daily_picks")
            .select("mint, pick_date, rank, score, bc_progress, market_cap_sol, pump_tokens(symbol, name)")
            .gte("pick_date", cutoff)
            .execute()
        )
        picks = picks_res.data
        if not picks:
            return 0

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

            snapshot = p.get("snapshot") or {}
            if isinstance(snapshot, str):
                try:
                    snapshot = json.loads(snapshot)
                except Exception:
                    snapshot = {}

            price_usd = float(snapshot.get("price_usd") or 0)
            if price_usd <= 0:
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
    db = get_db()
    try:
        res = (
            db.table("token_performance")
            .select("source, pick_date, chain, address")
            .eq("source", source)
            .execute()
        )
        return {f"{r['source']}|{r['pick_date']}|{r['chain']}|{r['address']}" for r in res.data}
    except Exception as e:
        log.error(f"获取已存在 keys 失败: {e}")
        return set()


def _deactivate_old() -> int:
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    asyncio.run(run_performance_loop())
