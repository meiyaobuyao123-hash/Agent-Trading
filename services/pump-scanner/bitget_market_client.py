"""
Bitget Wallet DEX 市场数据客户端
— OKX toplist / price-info 报错时的 fallback

接口设计与 okx_market_client.py 对齐，使调用方可零改动切换。

Bitget Wallet Web3 API：
  Base URL : https://web3.bitget.com
  Auth     : Bearer token（demo key 公开，无需申请）
  Chains   : sol / eth / bsc / base

Python 3.9 兼容。
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────
_BASE_URL = "https://web3.bitget.com"
# Bitget Wallet Skill demo key（公开，无需注册）
_DEMO_KEY = "bitget-wallet-skill-demo"

_TIMEOUT = aiohttp.ClientTimeout(total=12)

# OKX chainIndex → Bitget chain identifier
_CHAIN_MAP: Dict[str, str] = {
    "501":   "sol",    # Solana
    "1":     "eth",    # Ethereum
    "56":    "bsc",    # BNB Chain
    "8453":  "base",   # Base
}

# Bitget timeframe → OKX label
_TF_MAP = [
    ("5m",  "5m"),
    ("1h",  "1h"),
    ("4h",  "4h"),
    ("24h", "24h"),
]


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_DEMO_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "AgentTrading/1.0",
    }


# ═══════════════════════════════════════════════════════════
# Toplist — 镜像 okx_market_client.get_toplist_multi_timeframe
# ═══════════════════════════════════════════════════════════

async def get_toplist_multi_timeframe(
    chain_index: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> Dict[str, dict]:
    """
    获取 Bitget Wallet 热币排行榜（多时间帧），
    返回格式与 okx_market_client.get_toplist_multi_timeframe 完全相同。

    OKX 返回空/报错时调用此函数作为 fallback。
    """
    chain = _CHAIN_MAP.get(chain_index)
    if not chain:
        log.debug(f"[Bitget] 不支持 chain_index={chain_index}")
        return {}

    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    result: Dict[str, dict] = {}
    tf_hits: Dict[str, set] = {}

    try:
        for tf_label, tf_param in _TF_MAP:
            for sort_field in ["volume", "change"]:
                items = await _fetch_ranking(session, chain, tf_param, sort_field)
                for item in items:
                    addr = (item.get("contractAddress") or item.get("address") or "").lower()
                    if not addr:
                        continue

                    if addr not in tf_hits:
                        tf_hits[addr] = set()
                    tf_hits[addr].add(tf_label)

                    if addr not in result:
                        result[addr] = _init_token_entry(addr, item)

                    _fill_timeframe(result[addr], item, tf_label)

                    # 更新基础价格字段（取最新非零值）
                    _update_base_fields(result[addr], item)

    except Exception as e:
        log.warning(f"[Bitget] toplist {chain}: {e}")
    finally:
        if own_session and session:
            await session.close()

    for addr, data in result.items():
        data["timeframe_hits"] = len(tf_hits.get(addr, set()))
        data["timeframe_labels"] = sorted(tf_hits.get(addr, set()))

    log.info(f"[Bitget] toplist {chain}: {len(result)} 个代币")
    return result


async def _fetch_ranking(
    session: aiohttp.ClientSession,
    chain: str,
    timeframe: str,
    sort_by: str,
) -> List[dict]:
    """调用 Bitget Wallet 排行榜接口"""
    # Bitget Wallet market ranking endpoint
    url = f"{_BASE_URL}/bgw-pro/market/v1/token/ranking"
    params = {
        "chain":     chain,
        "timeframe": timeframe,   # "5m" | "1h" | "4h" | "24h"
        "sortBy":    sort_by,     # "volume" | "change"
        "limit":     "100",
    }
    try:
        async with session.get(
            url, headers=_headers(), params=params, timeout=_TIMEOUT
        ) as resp:
            if resp.status == 404:
                # 尝试备用路径
                return await _fetch_ranking_v2(session, chain, timeframe, sort_by)
            if resp.status != 200:
                log.debug(f"[Bitget] ranking HTTP {resp.status}")
                return []
            data = await resp.json()
            code = data.get("code", data.get("status", ""))
            if str(code) not in ("0", "200", ""):
                log.debug(f"[Bitget] ranking code={code}: {data.get('msg', '')}")
                return []
            return data.get("data") or data.get("list") or data.get("tokens") or []
    except Exception as e:
        log.debug(f"[Bitget] ranking {chain}/{timeframe}/{sort_by}: {e}")
        return []


async def _fetch_ranking_v2(
    session: aiohttp.ClientSession,
    chain: str,
    timeframe: str,
    sort_by: str,
) -> List[dict]:
    """备用排行榜路径"""
    url = f"{_BASE_URL}/bgw-pro/market/token/rankList"
    params = {
        "chain":      chain,
        "timeWindow": timeframe,
        "sortField":  sort_by,
        "limit":      "100",
    }
    try:
        async with session.get(
            url, headers=_headers(), params=params, timeout=_TIMEOUT
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data.get("data") or data.get("list") or []
    except Exception:
        return []


def _init_token_entry(addr: str, item: dict) -> dict:
    """初始化代币条目（对齐 OKX 格式）"""
    first_trade = item.get("firstTradeTime") or item.get("createTime")
    age_days = None
    if first_trade:
        try:
            ts_ms = int(first_trade)
            created = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            age_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
        except Exception:
            pass

    def _f(key: str) -> float:
        try:
            return float(item.get(key) or 0)
        except (ValueError, TypeError):
            return 0.0

    return {
        "address":         addr,
        "symbol":          item.get("symbol") or item.get("tokenSymbol") or "",
        "price_usd":       _f("price") or _f("priceUsd") or _f("lastPriceUsd"),
        "market_cap_usd":  _f("marketCap") or _f("mc"),
        "liquidity_usd":   _f("liquidity") or _f("liq"),
        "holders":         int(item.get("holders") or item.get("holderCount") or 0),
        "token_logo_url":  item.get("logoUrl") or item.get("tokenLogoUrl") or "",
        "first_trade_time": first_trade,
        "age_days":        age_days,
        # 初始化各时间帧字段
        "volume_5m": 0.0, "volume_1h": 0.0, "volume_4h": 0.0, "volume_24h": 0.0,
        "change_5m": 0.0, "change_1h": 0.0, "change_4h": 0.0, "change_24h": 0.0,
        "txs_buy_5m": 0, "txs_sell_5m": 0,
        "txs_buy_1h": 0, "txs_sell_1h": 0,
        "txs_buy_4h": 0, "txs_sell_4h": 0,
        "txs_buy_24h": 0, "txs_sell_24h": 0,
        "unique_traders_5m": 0, "unique_traders_1h": 0,
        "unique_traders_4h": 0, "unique_traders_24h": 0,
    }


def _fill_timeframe(entry: dict, item: dict, tf_label: str) -> None:
    """将 item 的量价数据填入对应时间帧字段"""
    def _f(key: str) -> float:
        try:
            return float(item.get(key) or 0)
        except (ValueError, TypeError):
            return 0.0

    # Bitget 可能使用 volume/change/txsBuy/txsSell 字段
    vol = _f("volume") or _f("vol")
    chg = _f("change") or _f("priceChange")
    buy = int(item.get("txsBuy") or item.get("buys") or 0)
    sell = int(item.get("txsSell") or item.get("sells") or 0)
    traders = int(item.get("uniqueTraders") or 0)

    vk = f"volume_{tf_label}"
    ck = f"change_{tf_label}"
    bk = f"txs_buy_{tf_label}"
    sk = f"txs_sell_{tf_label}"
    tk = f"unique_traders_{tf_label}"

    entry[vk] = max(entry.get(vk, 0.0), vol)
    if chg != 0:
        entry[ck] = chg
    entry[bk] = max(entry.get(bk, 0), buy)
    entry[sk] = max(entry.get(sk, 0), sell)
    entry[tk] = max(entry.get(tk, 0), traders)


def _update_base_fields(entry: dict, item: dict) -> None:
    """用最新非零值更新基础字段"""
    def _f(key: str) -> float:
        try:
            return float(item.get(key) or 0)
        except (ValueError, TypeError):
            return 0.0

    p = _f("price") or _f("priceUsd") or _f("lastPriceUsd")
    mc = _f("marketCap") or _f("mc")
    liq = _f("liquidity") or _f("liq")
    holders = int(item.get("holders") or item.get("holderCount") or 0)

    if p > 0:
        entry["price_usd"] = p
    if mc > 0:
        entry["market_cap_usd"] = mc
    if liq > 0:
        entry["liquidity_usd"] = liq
    if holders > entry.get("holders", 0):
        entry["holders"] = holders


# ═══════════════════════════════════════════════════════════
# Price Info — 镜像 okx_market_client.batch_price_info
# （用于 refresh_okx_prices fallback）
# ═══════════════════════════════════════════════════════════

async def batch_price_info(
    chain_index: str,
    addresses: List[str],
    session: Optional[aiohttp.ClientSession] = None,
) -> Dict[str, dict]:
    """
    批量获取代币价格信息。
    返回 {address_lower: {price_usd, market_cap, volume_24h, ...}}
    格式与 okx_market_client.batch_price_info 对齐。
    """
    if not addresses:
        return {}

    chain = _CHAIN_MAP.get(chain_index)
    if not chain:
        return {}

    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    result: Dict[str, dict] = {}

    try:
        for i in range(0, len(addresses), 50):
            batch = addresses[i:i + 50]
            batch_result = await _fetch_price_batch(session, chain, batch)
            result.update(batch_result)
            if i + 50 < len(addresses):
                await asyncio.sleep(0.3)
    except Exception as e:
        log.warning(f"[Bitget] batch_price_info {chain}: {e}")
    finally:
        if own_session and session:
            await session.close()

    return result


async def _fetch_price_batch(
    session: aiohttp.ClientSession,
    chain: str,
    addresses: List[str],
) -> Dict[str, dict]:
    """批量价格查询"""
    # 尝试 v1 端点
    url = f"{_BASE_URL}/bgw-pro/market/v1/token/batchPrice"
    body = {"chain": chain, "addresses": addresses}
    try:
        async with session.post(
            url, headers=_headers(), json=body, timeout=_TIMEOUT
        ) as resp:
            if resp.status == 404:
                return await _fetch_price_batch_v2(session, chain, addresses)
            if resp.status != 200:
                return {}
            data = await resp.json()
            items = data.get("data") or data.get("list") or []
            return {
                (item.get("address") or item.get("contractAddress") or "").lower():
                _parse_price_item(item)
                for item in items
                if item.get("address") or item.get("contractAddress")
            }
    except Exception as e:
        log.debug(f"[Bitget] price batch: {e}")
        return {}


async def _fetch_price_batch_v2(
    session: aiohttp.ClientSession,
    chain: str,
    addresses: List[str],
) -> Dict[str, dict]:
    """备用批量价格端点"""
    url = f"{_BASE_URL}/bgw-pro/market/token/batchInfo"
    params = {
        "chain": chain,
        "addresses": ",".join(addresses),
    }
    try:
        async with session.get(
            url, headers=_headers(), params=params, timeout=_TIMEOUT
        ) as resp:
            if resp.status != 200:
                return {}
            data = await resp.json()
            items = data.get("data") or []
            return {
                (item.get("address") or "").lower(): _parse_price_item(item)
                for item in items if item.get("address")
            }
    except Exception:
        return {}


def _parse_price_item(item: dict) -> dict:
    """解析单个价格项（对齐 OKX price-info 格式）"""
    def _f(key: str) -> float:
        try:
            return float(item.get(key) or 0)
        except (ValueError, TypeError):
            return 0.0

    return {
        "lastPriceUsd":       _f("price") or _f("priceUsd") or _f("lastPriceUsd"),
        "marketCap":          _f("marketCap") or _f("mc"),
        "liquidity":          _f("liquidity") or _f("liq"),
        "holders":            int(item.get("holders") or item.get("holderCount") or 0),
        "volume5M":           _f("volume5M") or _f("vol5m"),
        "volume1H":           _f("volume1H") or _f("vol1h"),
        "volume4H":           _f("volume4H") or _f("vol4h"),
        "volume24H":          _f("volume24H") or _f("vol24h"),
        "change5M":           _f("change5M") or _f("priceChange5m"),
        "change1H":           _f("change1H") or _f("priceChange1h"),
        "change4H":           _f("change4H") or _f("priceChange4h"),
        "change24H":          _f("change24H") or _f("priceChange24h"),
        "txsBuy5M":           int(item.get("txsBuy5M") or 0),
        "txsSell5M":          int(item.get("txsSell5M") or 0),
        "txsBuy1H":           int(item.get("txsBuy1H") or 0),
        "txsSell1H":          int(item.get("txsSell1H") or 0),
        "txsBuy24H":          int(item.get("txsBuy24H") or 0),
        "txsSell24H":         int(item.get("txsSell24H") or 0),
        "tokenLogoUrl":       item.get("logoUrl") or item.get("tokenLogoUrl") or "",
    }


import asyncio  # noqa: E402 (放最后避免循环导入问题)
