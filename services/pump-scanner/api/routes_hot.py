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
        # 按链分组均衡返回：之前按全局 score 排序会让 solana 占满 50 条，
        # ETH/base 挤不进来。改成先拉全部 score>=30 的，再按链分配配额，
        # 每链最多 limit//4 + 缓冲，确保每条链都有代币展示。
        res = (
            db.table("hot_coins")
            .select("*")
            .eq("goplus_risk", False)
            .order("score", desc=True)
            .limit(500)  # 拉较多，足够分到各链
            .execute()
        )
        rows = [r for r in (res.data or []) if (r.get("score") or 0) >= 30]

        # 按链分组，每链限额
        per_chain_cap = max(limit // 4 + 5, 10)  # e.g. limit=50 → 每链最多 17
        by_chain: dict = {}
        for r in rows:
            ch = r.get("chain", "")
            if ch not in by_chain:
                by_chain[ch] = []
            if len(by_chain[ch]) < per_chain_cap:
                by_chain[ch].append(r)

        # 合并（保持 score 排序，但限额均衡）
        data = []
        for ch_rows in by_chain.values():
            data.extend(ch_rows)
        data.sort(key=lambda r: r.get("score") or 0, reverse=True)

        return {"data": data[:limit], "count": min(len(data), limit)}
    except Exception as e:
        logger.error("get_hot_coins error: %s", e)
        return {"data": [], "count": 0}
