"""
价格代理路由 — 供 Flutter 实时价格查询

端点：
  GET /api/price/batch?chain={chain}&addresses={addr1,addr2,...}

DexScreener 批量查询（OKX price-info 需白名单暂不可用）。
Python 3.9 兼容。
"""

import logging
from typing import Dict

import aiohttp
from fastapi import APIRouter, Query, HTTPException

from config import DEXSCREENER_API

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/price", tags=["price"])

_TIMEOUT = aiohttp.ClientTimeout(total=10)


@router.get("/batch")
async def batch_price(
    chain: str = Query(..., description="链名: solana/bsc/base/eth"),
    addresses: str = Query(..., description="逗号分隔的 token 地址"),
):
    """
    批量获取 token 实时价格（DexScreener）
    """
    addr_list = [a.strip() for a in addresses.split(",") if a.strip()]
    if not addr_list:
        raise HTTPException(400, "addresses 不能为空")
    if len(addr_list) > 100:
        raise HTTPException(400, "单次最多查询 100 个地址")

    result = {}  # type: Dict[str, dict]

    try:
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(addr_list), 30):
                batch = addr_list[i:i + 30]
                joined = ",".join(batch)
                url = f"{DEXSCREENER_API}/tokens/v1/{joined}"
                try:
                    async with session.get(url, timeout=_TIMEOUT) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            pairs = data if isinstance(data, list) else data.get("pairs", [])
                            for pair in pairs:
                                base = pair.get("baseToken", {})
                                addr_lower = (base.get("address") or "").lower()
                                if not addr_lower or addr_lower in result:
                                    continue
                                result[addr_lower] = _dex_pair_to_response(pair)
                except Exception as e:
                    log.debug(f"DexScreener batch {i}: {e}")

                # 未命中的逐个查
                still_missing = [a for a in batch if a.lower() not in result]
                for addr in still_missing:
                    try:
                        single_url = f"{DEXSCREENER_API}/latest/dex/tokens/{addr}"
                        async with session.get(single_url, timeout=_TIMEOUT) as resp:
                            if resp.status == 200:
                                d = await resp.json()
                                ps = d.get("pairs") or []
                                if ps:
                                    result[addr.lower()] = _dex_pair_to_response(ps[0])
                    except Exception:
                        pass
    except Exception as e:
        log.error(f"Price batch error: {e}")

    return {"data": result, "source": "dexscreener"}


def _dex_pair_to_response(pair: dict) -> dict:
    """将 DexScreener pair 转为统一响应格式"""
    vol = pair.get("volume", {})
    chg = pair.get("priceChange", {})
    liq = pair.get("liquidity", {})

    def _f(v) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    return {
        "price": _f(pair.get("priceUsd")),
        "change5m": _f(chg.get("m5")),
        "change1h": _f(chg.get("h1")),
        "change4h": 0.0,
        "change24h": _f(chg.get("h24")),
        "volume5m": _f(vol.get("m5")),
        "volume1h": _f(vol.get("h1")),
        "volume24h": _f(vol.get("h24")),
        "marketCap": _f(pair.get("marketCap") or pair.get("fdv")),
        "liquidity": _f(liq.get("usd")),
        "holders": 0,
    }
