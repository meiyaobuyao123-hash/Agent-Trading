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
        # postgrest-py 不支持 .not_() / .neq()（supabase-py 特有），
        # 改用客户端过滤
        res = (
            db.table("hot_coins")
            .select("*")
            .eq("goplus_risk", False)
            .order("score", desc=True)
            .limit(limit * 2)
            .execute()
        )
        data = [
            r for r in (res.data or [])
            if r.get("score") is not None and r.get("recommendation") != "skip"
        ][:limit]
        return {"data": data, "count": len(data)}
    except Exception as e:
        logger.error("get_hot_coins error: %s", e)
        return {"data": [], "count": 0}
