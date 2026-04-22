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
        # postgrest-py 不支持 .not_() / .neq()，客户端过滤
        # 放宽 recommendation 过滤：之前 != "skip" 导致 ETH 链（全部 skip）返回 0 个。
        # 改为 score >= 30（至少有动量信号的代币都展示），APP UI 按 recommendation
        # 显示颜色标签，用户自己判断。
        res = (
            db.table("hot_coins")
            .select("*")
            .eq("goplus_risk", False)
            .order("score", desc=True)
            .limit(limit * 3)  # 多拉一些，给客户端过滤余量
            .execute()
        )
        data = [
            r for r in (res.data or [])
            if (r.get("score") or 0) >= 30
        ][:limit]
        return {"data": data, "count": len(data)}
    except Exception as e:
        logger.error("get_hot_coins error: %s", e)
        return {"data": [], "count": 0}
