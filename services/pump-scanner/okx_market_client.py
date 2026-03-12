"""
OKX DEX Market API v6 Python 客户端

端点：
  POST /api/v6/dex/market/price-info       — 批量价格/市场数据（≤100 token）
  GET  /api/v6/dex/market/candles           — K线数据（1s~1M）
  POST /api/v6/dex/market/token/basic-info  — token基础信息

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
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
         f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"
    return {
        "OK-ACCESS-KEY": OKX_API_KEY,
        "OK-ACCESS-SIGN": _sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": OKX_PASSPHRASE,
        "Content-Type": "application/json",
    }


# ═══════════════════════════════════════════════════════════
# POST /api/v6/dex/market/price-info
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
    """测试 OKX API 连通性"""
    try:
        async with aiohttp.ClientSession() as session:
            # 查一个已知的 SOL token (USDC)
            result = await batch_price_info(
                "501",
                ["EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"],
                session=session,
            )
            if result:
                log.info("OKX Market API 连通性测试通过")
                return True
            else:
                log.warning("OKX Market API 连通性测试失败: 无数据返回")
                return False
    except Exception as e:
        log.error(f"OKX Market API 连通性测试异常: {e}")
        return False
