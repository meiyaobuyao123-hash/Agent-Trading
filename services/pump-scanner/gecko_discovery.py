"""
GeckoTerminal 发现层 — trending + new_pools

补充 OKX toplist 的覆盖盲区。
免费 30 req/min，每链 trending(5页=100) + new_pools(5页=100) = 200 候选。
4 链 = ~800 个候选（与 OKX 400 个合并去重后约 600-800 独立代币）。

Python 3.9 兼容。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp

log = logging.getLogger(__name__)

_BASE = "https://api.geckoterminal.com/api/v2"
_TIMEOUT = aiohttp.ClientTimeout(total=12)
_HEADERS = {"Accept": "application/json"}

# GeckoTerminal network ID → 我们的链名
_CHAIN_MAP: Dict[str, str] = {
    "solana": "solana",
    "bsc": "bsc",
    "base": "base",
    "eth": "eth",
}

# 反向映射
_GECKO_NET: Dict[str, str] = {
    "solana": "solana",
    "bsc": "bsc",
    "base": "base",
    "eth": "eth",
}

# 每个端点拉几页（每页 20 个，免费最多 10 页）
_PAGES_PER_ENDPOINT = 5


async def fetch_gecko_candidates(
    session: aiohttp.ClientSession,
) -> Dict[str, List[dict]]:
    """
    从 GeckoTerminal 拉取 trending + new_pools。
    返回 {chain: [candidate_dict, ...]}，格式与 hot_coin_fetcher 对齐。
    """
    result: Dict[str, List[dict]] = {}

    for our_chain, gecko_net in _GECKO_NET.items():
        candidates: List[dict] = []
        seen_addrs: set = set()

        # ── trending_pools ──
        trending = await _fetch_pools(
            session, gecko_net, "trending_pools", _PAGES_PER_ENDPOINT
        )
        for pool in trending:
            coin = _parse_pool(pool, our_chain)
            if coin and coin["address"].lower() not in seen_addrs:
                seen_addrs.add(coin["address"].lower())
                candidates.append(coin)

        await asyncio.sleep(1)

        # ── new_pools ──
        new_pools = await _fetch_pools(
            session, gecko_net, "new_pools", _PAGES_PER_ENDPOINT
        )
        for pool in new_pools:
            coin = _parse_pool(pool, our_chain)
            if coin and coin["address"].lower() not in seen_addrs:
                seen_addrs.add(coin["address"].lower())
                candidates.append(coin)

        log.info(f"[Gecko] {our_chain}: trending={len(trending)} new_pools={len(new_pools)} → {len(candidates)} 独立候选")
        result[our_chain] = candidates

        await asyncio.sleep(2)  # 链间冷却

    return result


async def _fetch_pools(
    session: aiohttp.ClientSession,
    network: str,
    endpoint: str,
    max_pages: int,
) -> List[dict]:
    """拉取指定端点的多页 pool 数据"""
    pools: List[dict] = []

    for page in range(1, max_pages + 1):
        url = f"{_BASE}/networks/{network}/{endpoint}?page={page}"
        try:
            async with session.get(url, headers=_HEADERS, timeout=_TIMEOUT) as resp:
                if resp.status == 429:
                    log.warning(f"[Gecko] 429 限速，等待 30s")
                    await asyncio.sleep(30)
                    continue
                if resp.status != 200:
                    log.debug(f"[Gecko] {network}/{endpoint} page={page} HTTP {resp.status}")
                    break

                data = await resp.json()
                items = data.get("data", [])
                if not items:
                    break
                pools.extend(items)

        except Exception as e:
            log.debug(f"[Gecko] {network}/{endpoint} page={page}: {e}")
            break

        await asyncio.sleep(2.5)  # 30 req/min → ~2s/req 安全间隔

    return pools


def _parse_pool(pool: dict, chain: str) -> Optional[dict]:
    """将 GeckoTerminal pool 解析为统一候选格式"""
    attrs = pool.get("attributes", {})
    if not attrs:
        return None

    # base_token 是我们关注的代币
    base_addr = attrs.get("base_token_address", "")
    if not base_addr:
        # 尝试从 relationships 获取
        rels = pool.get("relationships", {})
        base_token = rels.get("base_token", {}).get("data", {})
        if base_token:
            # ID 格式: "network_address"
            token_id = base_token.get("id", "")
            parts = token_id.split("_", 1)
            if len(parts) == 2:
                base_addr = parts[1]

    if not base_addr:
        return None

    # 价格
    price_usd = _f(attrs.get("base_token_price_usd"))
    if price_usd <= 0:
        return None

    # 成交量
    vol = attrs.get("volume_usd", {})
    # 涨幅
    chg = attrs.get("price_change_percentage", {})
    # 交易笔数
    txn = attrs.get("transactions", {})
    # 流动性
    liq_usd = _f(attrs.get("reserve_in_usd")) / 2 if attrs.get("reserve_in_usd") else 0

    # 市值（GeckoTerminal 有时有 fdv_usd 或 market_cap_usd）
    mc = _f(attrs.get("market_cap_usd")) or _f(attrs.get("fdv_usd"))

    # 创建时间
    pool_created = attrs.get("pool_created_at", "")
    age_days = None
    if pool_created:
        try:
            created = datetime.fromisoformat(pool_created.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
        except Exception:
            pass

    # 名称
    name = attrs.get("name", "")
    # 尝试提取 base token symbol（name 通常是 "TOKEN / SOL" 格式）
    symbol = name.split("/")[0].strip() if "/" in name else name

    # 买卖笔数
    buys_1h = 0
    sells_1h = 0
    buys_24h = 0
    sells_24h = 0
    if isinstance(txn, dict):
        h1 = txn.get("h1", {})
        h24 = txn.get("h24", {})
        if isinstance(h1, dict):
            buys_1h = int(h1.get("buys", 0))
            sells_1h = int(h1.get("sells", 0))
        if isinstance(h24, dict):
            buys_24h = int(h24.get("buys", 0))
            sells_24h = int(h24.get("sells", 0))

    return {
        "address": base_addr,
        "name": name,
        "symbol": symbol,
        "chain": chain,
        "pair_address": attrs.get("address", ""),
        "dex_id": attrs.get("dex_id", ""),
        "price_usd": price_usd,
        "market_cap_usd": mc,
        "liquidity_usd": liq_usd,
        "volume_5m_usd": _f(vol.get("m5")),
        "volume_1h_usd": _f(vol.get("h1")),
        "volume_4h_usd": 0,
        "volume_24h_usd": _f(vol.get("h24")),
        "price_change_5m": _f(chg.get("m5")),
        "price_change_1h": _f(chg.get("h1")),
        "price_change_4h": 0,
        "price_change_6h": _f(chg.get("h6")),
        "price_change_24h": _f(chg.get("h24")),
        "buys_1h": buys_1h,
        "sells_1h": sells_1h,
        "buys_24h": buys_24h,
        "sells_24h": sells_24h,
        "buys_5m": 0,
        "sells_5m": 0,
        "pair_created_at": pool_created,
        "age_days": age_days,
        "holder_count": 0,
        "okx_holders": 0,
        "top10_holder_pct": None,
        "is_honeypot": False,
        "is_open_source": True,
        "buy_tax": 0,
        "sell_tax": 0,
        "goplus_risk": False,
        "has_twitter": False,
        "has_telegram": False,
        "has_website": False,
        "image_url": attrs.get("image_url", ""),
        "token_logo_url": "",
        "circ_supply": 0,
        "timeframe_hits": 1,
        "data_source": "gecko_trending",
    }


def _f(v) -> float:
    """安全 float 转换"""
    if v is None:
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0
