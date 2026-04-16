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
        res = (
            db.table("hot_coins")
            .select(
                "chain, address, name, symbol, pair_address, dex_id, "
                "price_usd, market_cap_usd, liquidity_usd, "
                "volume_24h_usd, volume_1h_usd, volume_5m_usd, volume_4h_usd, "
                "price_change_1h, price_change_5m, price_change_4h, price_change_6h, price_change_24h, "
                "buys_1h, sells_1h, buys_24h, sells_24h, "
                "age_days, holder_count, top10_holder_pct, top1_holder_pct, "
                "goplus_risk, has_twitter, has_telegram, has_website, image_url, "
                "score, score_m, score_q, score_p, recommendation, scanned_at"
            )
            .eq("goplus_risk", False)
            .not_("score", "is", "null")
            .neq("recommendation", "skip")
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
        return {"data": res.data or [], "count": len(res.data or [])}
    except Exception as e:
        logger.error("get_hot_coins error: %s", e)
        return {"data": [], "count": 0}
