"""
Token detail API — Top Holders, Fund Flow 等
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query

from api._cache import cached

router = APIRouter(prefix="/api/token", tags=["token"])
log = logging.getLogger(__name__)


@router.get("/{chain}/{address}/top-holders")
@cached(ttl=300)  # 5分钟缓存 — 持仓数据每小时才变
async def get_top_holders(chain: str, address: str, limit: int = Query(10, le=20)):
    """获取代币 Top N 持仓地址"""
    try:
        from hot_coin_fetcher import fetch_top_holders
        holders = await fetch_top_holders(chain, address, limit=limit)
        return {"holders": holders, "chain": chain, "address": address}
    except Exception as e:
        log.warning("top-holders %s/%s: %s", chain, address[:8], e)
        return {"holders": [], "chain": chain, "address": address, "error": str(e)}
