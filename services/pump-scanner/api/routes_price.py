"""
价格代理路由 — 供 Flutter 实时价格查询

端点：
  GET /api/price/batch?chain={chain}&addresses={addr1,addr2,...}

优先 OKX DEX Market API，不可用时 fallback DexScreener。
Python 3.9 兼容。
"""

import logging
from typing import Dict

import aiohttp
from fastapi import APIRouter, Query, HTTPException

import okx_market_client as okx
from config import OKX_CHAIN_INDEX, DEXSCREENER_API

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/price", tags=["price"])

_TIMEOUT = aiohttp.ClientTimeout(total=10)


@router.get("/batch")
async def batch_price(
    chain: str = Query(..., description="链名: solana/bsc/base/eth"),
    addresses: str = Query(..., description="逗号分隔的 token 地址"),
):
    """
    批量获取 token 实时价格（OKX 优先，DexScreener fallback）
    """
    addr_list = [a.strip() for a in addresses.split(",") if a.strip()]
    if not addr_list:
        raise HTTPException(400, "addresses 不能为空")
    if len(addr_list) > 100:
        raise HTTPException(400, "单次最多查询 100 个地址")

    result = {}  # type: Dict[str, dict]
    source = "okx"

    # ── 1. 优先 OKX ──
    chain_index = OKX_CHAIN_INDEX.get(chain)
    if chain_index:
        try:
            okx_data = await okx.batch_price_info(chain_index, addr_list)
            for addr in addr_list:
                info = okx_data.get(addr.lower())
                if info and info["lastPriceUsd"] > 0:
                    result[addr.lower()] = {
                        "price": info["lastPriceUsd"],
                        "change5m": info["change5M"],
                        "change1h": info["change1H"],
                        "change4h": info["change4H"],
                        "change24h": info["change24H"],
                        "volume5m": info["volume5M"],
                        "volume1h": info["volume1H"],
                        "volume24h": info["volume24H"],
                        "marketCap": info["marketCap"],
                        "liquidity": info["liquidity"],
                        "holders": info["holders"],
                    }
        except Exception as e:
            log.warning(f"OKX price-info failed: {e}")

    # ── 2. OKX 命中不足 → DexScreener fallback ──
    missing = [a for a in addr_list if a.lower() not in result]
    if missing and len(missing) > len(addr_list) * 0.3:
        source = "dexscreener"
        try:
            async with aiohttp.ClientSession() as session:
                # DexScreener 批量端点: /tokens/v1/{addr1,addr2,...}
                for i in range(0, len(missing), 30):
                    batch = missing[i:i + 30]
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
            log.error(f"DexScreener fallback error: {e}")

    return {"data": result, "source": source}


def _dex_pair_to_response(pair: dict) -> dict:
    """将 DexScreener pair 转为统一响应格式"""
    vol = pair.get("volume", {})
    chg = pair.get("priceChange", {})
    txn = pair.get("txns", {})
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
