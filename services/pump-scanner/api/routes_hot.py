"""
Hot Coins API Routes
Provides endpoints for Flutter app to fetch hot coin data (replacing direct Supabase access)
"""
import logging
from typing import Optional
from fastapi import APIRouter, Query

from database import get_db

logger = logging.getLogger("routes_hot")
router = APIRouter(prefix="/api/hot-coins", tags=["hot_coins"])


@router.get("")
async def get_hot_coins(
    limit: int = Query(50, ge=1, le=200),
):
    """Get hot coins ordered by score, excluding risky and skipped tokens."""
    db = get_db()
    try:
        # 每链独立查 top N（解决全局排序导致 solana 高分淹没 ETH/base/bsc 的问题）
        per_chain_cap = max(limit // 4 + 5, 12)  # limit=50 → 每链最多 17
        all_rows = []
        for chain in ["solana", "base", "bsc", "eth"]:
            try:
                res = (
                    db.table("hot_coins")
                    .select("*")
                    .eq("chain", chain)
                    .eq("goplus_risk", False)
                    .gte("score", 30)
                    .order("score", desc=True)
                    .limit(per_chain_cap)
                    .execute()
                )
                all_rows.extend(res.data or [])
            except Exception as e:
                logger.debug("hot-coins chain=%s: %s", chain, e)

        # 全局按 score 排序展示
        all_rows.sort(key=lambda r: r.get("score") or 0, reverse=True)
        return {"data": all_rows[:limit], "count": min(len(all_rows), limit)}
    except Exception as e:
        logger.error("get_hot_coins error: %s", e)
        return {"data": [], "count": 0}
