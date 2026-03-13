"""
OKX DEX Market API v6 Python 客户端

端点：
  GET  /api/v6/dex/market/token/toplist    — 代币排名（按涨幅/成交量/市值）
  GET  /api/v6/dex/market/token/search     — 代币搜索
  POST /api/v6/dex/market/price-info       — 批量价格/市场数据（≤100 token，需白名单）
  GET  /api/v6/dex/market/candles           — K线数据（1s~1M）
  POST /api/v6/dex/market/token/basic-info  — token基础信息（需白名单）

签名：HMAC SHA256（与 apps/web/lib/okx/client.ts 一致）
Python 3.9 兼容。
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE, OKX_API_BASE

log = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=15)


# ═══════════════════════════════════════════════════════════
# 签名
# ═══════════════════════════════════════════════════════════

def _sign(timestamp: str, method: str, path: str, body: str = "") -> str:
    """HMAC SHA256 签名 → Base64"""
    message = timestamp + method.upper() + path + body
    mac = hmac.new(
        OKX_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    )
    return base64.b64encode(mac.digest()).decode("utf-8")


def _headers(method: str, path: str, body: str = "") -> Dict[str, str]:
    """构建 OKX 请求头"""
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    return {
        "OK-ACCESS-KEY": OKX_API_KEY,
        "OK-ACCESS-SIGN": _sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": OKX_PASSPHRASE,
        "Content-Type": "application/json",
    }


# ═══════════════════════════════════════════════════════════
# GET /api/v6/dex/market/token/toplist — 代币排名（发现）
# ═══════════════════════════════════════════════════════════

# sortBy: 2=涨幅, 5=成交量, 6=市值
# timeFrame: 1=5m, 2=1h, 3=4h, 4=24h

async def get_toplist(
    chain_index: str,
    sort_by: str = "5",
    time_frame: str = "4",
    session: Optional[aiohttp.ClientSession] = None,
) -> List[dict]:
    """
    获取代币排名列表（最多 100 个）

    返回 [{
        chainIndex, tokenContractAddress, tokenSymbol,
        price, marketCap, liquidity, holders,
        volume, change, txsBuy, txsSell, uniqueTraders,
        tokenLogoUrl, firstTradeTime,
    }]
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    try:
        path = (
            f"/api/v6/dex/market/token/toplist"
            f"?chains={chain_index}"
            f"&sortBy={sort_by}"
            f"&timeFrame={time_frame}"
        )
        hdrs = _headers("GET", path)

        async with session.get(
            f"{OKX_API_BASE}{path}",
            headers=hdrs,
            timeout=_TIMEOUT,
        ) as resp:
            if resp.status != 200:
                log.warning(f"OKX toplist HTTP {resp.status}")
                return []

            data = await resp.json()
            code = data.get("code")
            if code == "50011":
                log.warning("OKX toplist 限速(50011)，稍后重试")
                return []
            if str(code) != "0":
                log.warning(f"OKX toplist error code={code}: {data.get('msg')}")
                return []

            return data.get("data") or []

    except Exception as e:
        log.warning(f"OKX toplist: {e}")
        return []
    finally:
        if own_session and session:
            await session.close()


async def get_toplist_multi_sort(
    chain_index: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> Dict[str, dict]:
    """
    按成交量+涨幅两个维度拉取 toplist，合并去重。
    返回 {address_lower: parsed_item}
    """
    result = {}  # type: Dict[str, dict]

    # 按成交量排名
    vol_list = await get_toplist(chain_index, sort_by="5", time_frame="4", session=session)
    for item in vol_list:
        addr = (item.get("tokenContractAddress") or "").lower()
        if addr and addr not in result:
            result[addr] = _parse_toplist_item(item)

    await _sleep(2.0)  # 限速保护

    # 按涨幅排名
    chg_list = await get_toplist(chain_index, sort_by="2", time_frame="4", session=session)
    for item in chg_list:
        addr = (item.get("tokenContractAddress") or "").lower()
        if addr and addr not in result:
            result[addr] = _parse_toplist_item(item)

    return result


async def get_toplist_multi_timeframe(
    chain_index: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> Dict[str, dict]:
    """
    多时间帧 + 多排序维度合并拉取。
    4 个时间帧(5m/1h/4h/24h) × 2 个排序(成交量+涨幅) = 8 次调用。
    合并到同一 address 下，填充各时间帧字段。

    返回 {address_lower: {
        address, symbol, price_usd, market_cap_usd, liquidity_usd, holders,
        token_logo_url, first_trade_time, age_days,
        volume_5m, volume_1h, volume_4h, volume_24h,
        change_5m, change_1h, change_4h, change_24h,
        txs_buy_5m, txs_sell_5m, txs_buy_1h, txs_sell_1h,
        txs_buy_4h, txs_sell_4h, txs_buy_24h, txs_sell_24h,
        unique_traders_5m, unique_traders_1h, unique_traders_4h, unique_traders_24h,
        timeframe_hits: int  (出现在几个时间帧中，1~4)
    }}
    """
    # timeFrame: 1=5m, 2=1h, 3=4h, 4=24h
    TF_MAP = [
        ("1", "5m"),
        ("2", "1h"),
        ("3", "4h"),
        ("4", "24h"),
    ]

    result = {}  # type: Dict[str, dict]
    # 跟踪每个地址出现在哪些时间帧
    tf_hits = {}  # type: Dict[str, set]

    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    try:
        for tf_code, tf_label in TF_MAP:
            for sort_by in ["5", "2"]:  # 成交量 + 涨幅
                items = await get_toplist(
                    chain_index, sort_by=sort_by, time_frame=tf_code, session=session
                )
                for item in items:
                    addr = (item.get("tokenContractAddress") or "").lower()
                    if not addr:
                        continue

                    # 记录时间帧命中
                    if addr not in tf_hits:
                        tf_hits[addr] = set()
                    tf_hits[addr].add(tf_label)

                    if addr not in result:
                        # 首次出现：初始化基础字段
                        parsed = _parse_toplist_item(item)
                        result[addr] = {
                            "address": parsed["address"],
                            "symbol": parsed["symbol"],
                            "price_usd": parsed["price_usd"],
                            "market_cap_usd": parsed["market_cap_usd"],
                            "liquidity_usd": parsed["liquidity_usd"],
                            "holders": parsed["holders"],
                            "token_logo_url": parsed["token_logo_url"],
                            "first_trade_time": parsed["first_trade_time"],
                            "age_days": parsed["age_days"],
                            # 各时间帧数据，初始为 0
                            "volume_5m": 0.0, "volume_1h": 0.0,
                            "volume_4h": 0.0, "volume_24h": 0.0,
                            "change_5m": 0.0, "change_1h": 0.0,
                            "change_4h": 0.0, "change_24h": 0.0,
                            "txs_buy_5m": 0, "txs_sell_5m": 0,
                            "txs_buy_1h": 0, "txs_sell_1h": 0,
                            "txs_buy_4h": 0, "txs_sell_4h": 0,
                            "txs_buy_24h": 0, "txs_sell_24h": 0,
                            "unique_traders_5m": 0, "unique_traders_1h": 0,
                            "unique_traders_4h": 0, "unique_traders_24h": 0,
                        }

                    # 填充对应时间帧数据（取最大值，因为同一 tf 可能被 vol 和 chg 两次拉到）
                    def _f(key):
                        # type: (str) -> float
                        try:
                            return float(item.get(key) or 0)
                        except (ValueError, TypeError):
                            return 0.0

                    vol_key = "volume_" + tf_label
                    chg_key = "change_" + tf_label
                    buy_key = "txs_buy_" + tf_label
                    sell_key = "txs_sell_" + tf_label
                    trader_key = "unique_traders_" + tf_label

                    cur = result[addr]
                    cur[vol_key] = max(cur[vol_key], _f("volume"))
                    cur[chg_key] = _f("change") if _f("change") != 0 else cur[chg_key]
                    cur[buy_key] = max(cur[buy_key], int(item.get("txsBuy") or 0))
                    cur[sell_key] = max(cur[sell_key], int(item.get("txsSell") or 0))
                    cur[trader_key] = max(cur[trader_key], int(item.get("uniqueTraders") or 0))

                    # 更新基础字段（取最新的非零值）
                    if _f("price") > 0:
                        cur["price_usd"] = _f("price")
                    if _f("marketCap") > 0:
                        cur["market_cap_usd"] = _f("marketCap")
                    if _f("liquidity") > 0:
                        cur["liquidity_usd"] = _f("liquidity")
                    if int(item.get("holders") or 0) > cur["holders"]:
                        cur["holders"] = int(item.get("holders") or 0)

                await _sleep(2.0)  # OKX 限速保护（8次调用/链，避免429）

        # 写入 timeframe_hits
        for addr, data in result.items():
            data["timeframe_hits"] = len(tf_hits.get(addr, set()))
            data["timeframe_labels"] = sorted(tf_hits.get(addr, set()))

    finally:
        if own_session and session:
            await session.close()

    return result


def _parse_toplist_item(item: dict) -> dict:
    """解析 toplist 单项为统一格式"""
    def _f(key: str) -> float:
        try:
            return float(item.get(key) or 0)
        except (ValueError, TypeError):
            return 0.0

    first_trade = item.get("firstTradeTime")
    age_days = None  # type: Optional[float]
    if first_trade:
        try:
            ts_ms = int(first_trade)
            created = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            age_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
        except (ValueError, TypeError, OSError):
            pass

    return {
        "address": item.get("tokenContractAddress") or "",
        "symbol": item.get("tokenSymbol") or "",
        "price_usd": _f("price"),
        "market_cap_usd": _f("marketCap"),
        "liquidity_usd": _f("liquidity"),
        "holders": int(item.get("holders") or 0),
        "volume_24h": _f("volume"),
        "change_24h": _f("change"),
        "txs_buy": int(item.get("txsBuy") or 0),
        "txs_sell": int(item.get("txsSell") or 0),
        "unique_traders": int(item.get("uniqueTraders") or 0),
        "token_logo_url": item.get("tokenLogoUrl") or "",
        "first_trade_time": first_trade,
        "age_days": age_days,
    }


# ═══════════════════════════════════════════════════════════
# POST /api/v6/dex/market/price-info（需白名单，暂不可用）
# ═══════════════════════════════════════════════════════════

async def batch_price_info(
    chain_index: str,
    addresses: List[str],
    session: Optional[aiohttp.ClientSession] = None,
) -> Dict[str, dict]:
    """
    批量获取 token 市场数据（最多 100 个/批）

    返回 {address_lower: {
        lastPriceUsd, marketCap, liquidity, holders,
        volume5M, volume1H, volume4H, volume24H,
        change5M, change1H, change4H, change24H,
        txsBuy5M, txsSell5M, txsBuy1H, txsSell1H,
        txsBuy24H, txsSell24H,
        circulatingSupply, buyTaxRate, sellTaxRate,
        tokenLogoUrl,
    }}
    """
    if not addresses:
        return {}

    result = {}  # type: Dict[str, dict]
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    try:
        # 每批最多 100 个
        for i in range(0, len(addresses), 100):
            batch = addresses[i:i + 100]
            path = "/api/v6/dex/market/price-info"
            body_data = {
                "chainIndex": chain_index,
                "tokenContractAddress": ",".join(batch),
            }
            body_str = json.dumps(body_data)
            hdrs = _headers("POST", path, body_str)

            try:
                async with session.post(
                    f"{OKX_API_BASE}{path}",
                    headers=hdrs,
                    data=body_str,
                    timeout=_TIMEOUT,
                ) as resp:
                    if resp.status != 200:
                        log.warning(f"OKX price-info HTTP {resp.status}")
                        continue

                    data = await resp.json()
                    if data.get("code") != "0":
                        log.debug(f"OKX price-info code={data.get('code')}: {data.get('msg')}")
                        continue

                    for item in (data.get("data") or []):
                        addr = (item.get("tokenContractAddress") or "").lower()
                        if not addr:
                            continue
                        result[addr] = _parse_price_info(item)

            except Exception as e:
                log.warning(f"OKX price-info batch {i}: {e}")

            # 批次间冷却
            if i + 100 < len(addresses):
                await _sleep(0.3)

    finally:
        if own_session and session:
            await session.close()

    return result


def _parse_price_info(item: dict) -> dict:
    """解析单个 price-info 响应项"""
    def _f(key: str) -> float:
        return float(item.get(key) or 0)

    return {
        "lastPriceUsd":       _f("lastPriceUsd"),
        "marketCap":          _f("marketCap"),
        "liquidity":          _f("liquidity"),
        "holders":            int(item.get("holders") or 0),
        "volume5M":           _f("volume5M"),
        "volume1H":           _f("volume1H"),
        "volume4H":           _f("volume4H"),
        "volume24H":          _f("volume24H"),
        "change5M":           _f("change5M"),
        "change1H":           _f("change1H"),
        "change4H":           _f("change4H"),
        "change24H":          _f("change24H"),
        "txsBuy5M":           int(item.get("txsBuy5M") or 0),
        "txsSell5M":          int(item.get("txsSell5M") or 0),
        "txsBuy1H":           int(item.get("txsBuy1H") or 0),
        "txsSell1H":          int(item.get("txsSell1H") or 0),
        "txsBuy4H":           int(item.get("txsBuy4H") or 0),
        "txsSell4H":          int(item.get("txsSell4H") or 0),
        "txsBuy24H":          int(item.get("txsBuy24H") or 0),
        "txsSell24H":         int(item.get("txsSell24H") or 0),
        "circulatingSupply":  _f("circulatingSupply"),
        "buyTaxRate":         _f("buyTaxRate"),
        "sellTaxRate":        _f("sellTaxRate"),
        "tokenLogoUrl":       item.get("tokenLogoUrl") or "",
    }


# ═══════════════════════════════════════════════════════════
# GET /api/v6/dex/market/candles
# ═══════════════════════════════════════════════════════════

async def get_candles(
    chain_index: str,
    token_address: str,
    bar: str = "1H",
    limit: int = 100,
    session: Optional[aiohttp.ClientSession] = None,
) -> List[dict]:
    """
    获取 K 线数据

    bar: 1s, 1m, 5m, 15m, 30m, 1H, 4H, 1D, 1W, 1M
    返回 [{ts, open, high, low, close, vol, volUsd}]
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    try:
        path = (
            f"/api/v6/dex/market/candles"
            f"?chainIndex={chain_index}"
            f"&tokenContractAddress={token_address}"
            f"&bar={bar}"
            f"&limit={limit}"
        )
        hdrs = _headers("GET", path)

        async with session.get(
            f"{OKX_API_BASE}{path}",
            headers=hdrs,
            timeout=_TIMEOUT,
        ) as resp:
            if resp.status != 200:
                log.warning(f"OKX candles HTTP {resp.status}")
                return []

            data = await resp.json()
            if data.get("code") != "0":
                log.warning(f"OKX candles error: {data.get('msg')}")
                return []

            candles = []
            for row in (data.get("data") or []):
                if isinstance(row, list) and len(row) >= 7:
                    candles.append({
                        "ts":      row[0],
                        "open":    float(row[1]),
                        "high":    float(row[2]),
                        "low":     float(row[3]),
                        "close":   float(row[4]),
                        "vol":     float(row[5]),
                        "volUsd":  float(row[6]),
                    })
            return candles

    except Exception as e:
        log.warning(f"OKX candles: {e}")
        return []
    finally:
        if own_session and session:
            await session.close()


# ═══════════════════════════════════════════════════════════
# POST /api/v6/dex/market/token/basic-info
# ═══════════════════════════════════════════════════════════

async def get_basic_info(
    chain_index: str,
    addresses: List[str],
    session: Optional[aiohttp.ClientSession] = None,
) -> Dict[str, dict]:
    """
    批量获取 token 基础信息

    返回 {address_lower: {name, symbol, logoUrl, communityRecognized}}
    """
    if not addresses:
        return {}

    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    result = {}  # type: Dict[str, dict]

    try:
        path = "/api/v6/dex/market/token/basic-info"
        body_data = {
            "chainIndex": chain_index,
            "tokenContractAddress": ",".join(addresses),
        }
        body_str = json.dumps(body_data)
        hdrs = _headers("POST", path, body_str)

        async with session.post(
            f"{OKX_API_BASE}{path}",
            headers=hdrs,
            data=body_str,
            timeout=_TIMEOUT,
        ) as resp:
            if resp.status != 200:
                return {}

            data = await resp.json()
            if data.get("code") != "0":
                return {}

            for item in (data.get("data") or []):
                addr = (item.get("tokenContractAddress") or "").lower()
                if addr:
                    result[addr] = {
                        "name":     item.get("tokenName") or "",
                        "symbol":   item.get("tokenSymbol") or "",
                        "logoUrl":  item.get("tokenLogoUrl") or "",
                        "communityRecognized": item.get("communityRecognized", False),
                    }

    except Exception as e:
        log.warning(f"OKX basic-info: {e}")
    finally:
        if own_session and session:
            await session.close()

    return result


# ═══════════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════════

async def _sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)


async def test_connectivity() -> bool:
    """测试 OKX API 连通性（使用 toplist 端点）"""
    try:
        async with aiohttp.ClientSession() as session:
            result = await get_toplist("501", sort_by="5", time_frame="4", session=session)
            if result:
                log.info("OKX Market API 连通性测试通过 (toplist %d tokens)", len(result))
                return True
            else:
                log.warning("OKX Market API 连通性测试失败: 无数据返回")
                return False
    except Exception as e:
        log.error(f"OKX Market API 连通性测试异常: {e}")
        return False
