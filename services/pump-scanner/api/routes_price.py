"""
价格代理路由 — 供 Flutter 实时价格查询

端点：
  GET /api/price/batch?chain={chain}&addresses={addr1,addr2,...}

内部调用 OKX DEX Market API，无缓存直取最新价格。
OKX lastPriceUsd 为毫秒级更新（每笔成交即刷新）。
Python 3.9 兼容。
"""

import logging
from typing import Dict

from fastapi import APIRouter, Query, HTTPException

import okx_market_client as okx
from config import OKX_CHAIN_INDEX

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/price", tags=["price"])


@router.get("/batch")
async def batch_price(
    chain: str = Query(..., description="链名: solana/bsc/base/eth"),
    addresses: str = Query(..., description="逗号分隔的 token 地址"),
):
    """
    批量获取 token 实时价格（OKX 数据源，无缓存直取最新）

    返回：
    {
      "data": {
        "地址": {
          "price": 0.0123,
          "change5m": 1.5,
          "change1h": -2.3,
          "change4h": 5.1,
          "change24h": 12.0,
          "volume5m": 1234.56,
          "volume1h": 5678.90,
          "marketCap": 1000000,
          "liquidity": 50000,
          "holders": 500
        }
      },
      "source": "okx"
    }
    """
    chain_index = OKX_CHAIN_INDEX.get(chain)
    if not chain_index:
        raise HTTPException(400, f"不支持的链: {chain}")

    addr_list = [a.strip() for a in addresses.split(",") if a.strip()]
    if not addr_list:
        raise HTTPException(400, "addresses 不能为空")
    if len(addr_list) > 100:
        raise HTTPException(400, "单次最多查询 100 个地址")

    # 直接调用 OKX，无缓存
    try:
        okx_data = await okx.batch_price_info(chain_index, addr_list)
    except Exception as e:
        log.error(f"OKX price-info error: {e}")
        raise HTTPException(502, "OKX API 请求失败")

    # 格式化响应
    result = {}  # type: Dict[str, dict]
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

    return {"data": result, "source": "okx"}
