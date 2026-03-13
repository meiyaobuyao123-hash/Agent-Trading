"""
Smart Money Signal API Routes
Provides endpoints for Flutter app to fetch smart money data
"""
import logging
from typing import Optional
from fastapi import APIRouter, Query

from database import get_db

logger = logging.getLogger("routes_smart_money")
router = APIRouter(prefix="/api/smart-money", tags=["smart_money"])


@router.get("/signals")
async def get_signals(
    chain: Optional[str] = Query(None, description="Filter by chain: solana, eth, bsc, base"),
    min_heat: float = Query(0, description="Minimum heat score"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get aggregated smart money signals, ordered by heat score."""
    db = get_db()
    query = db.table("smart_money_signals") \
        .select("*") \
        .gte("heat_score", min_heat) \
        .order("heat_score", desc=True) \
        .limit(limit)

    if chain:
        query = query.eq("chain", chain)

    try:
        res = query.execute()
        return {"data": res.data, "count": len(res.data)}
    except Exception as e:
        logger.error("get_signals error: %s", e)
        return {"data": [], "count": 0}


@router.get("/wallets")
async def get_wallets(
    tier: Optional[str] = Query(None, description="Filter by tier: elite, verified, watching"),
    limit: int = Query(100, ge=1, le=500),
):
    """Get tracked smart wallets."""
    db = get_db()
    query = db.table("smart_wallets") \
        .select("wallet, tier, win_rate, total_trades, avg_profit_pct, last_seen, is_seed") \
        .eq("is_blacklisted", False) \
        .order("win_rate", desc=True) \
        .limit(limit)

    if tier:
        query = query.eq("tier", tier)

    try:
        res = query.execute()
        return {"data": res.data, "count": len(res.data)}
    except Exception as e:
        logger.error("get_wallets error: %s", e)
        return {"data": [], "count": 0}


@router.get("/token/{chain}/{address}")
async def get_token_signals(chain: str, address: str):
    """Get smart money activity for a specific token."""
    db = get_db()
    res = db.table("smart_money_signals") \
        .select("*") \
        .eq("chain", chain) \
        .eq("token_address", address) \
        .maybe_single() \
        .execute()
    return {"data": res.data}


@router.get("/txns/{chain}/{token_address}")
async def get_token_txns(
    chain: str,
    token_address: str,
    tx_type: Optional[str] = Query(None, description="Filter: buy or sell"),
    limit: int = Query(100, ge=1, le=500),
):
    """Get individual smart money transactions for a token."""
    db = get_db()
    query = db.table("smart_money_txns") \
        .select("wallet_address, wallet_tier, tx_type, volume_usd, "
                "market_cap_at_tx, price_at_tx, tx_time") \
        .eq("chain", chain) \
        .eq("token_address", token_address) \
        .order("tx_time", desc=True) \
        .limit(limit)

    if tx_type:
        query = query.eq("tx_type", tx_type)

    try:
        res = query.execute()
    except Exception as e:
        logger.error("get_token_txns error: %s", e)
        return {"data": [], "summary": {
            "total_inflow": 0, "total_outflow": 0, "net_flow": 0,
            "unique_buyers": 0, "unique_sellers": 0,
            "buy_count": 0, "sell_count": 0,
        }}

    rows = res.data or []
    buys = [t for t in rows if t.get("tx_type") == "buy"]
    sells = [t for t in rows if t.get("tx_type") == "sell"]

    total_in = sum(t.get("volume_usd") or 0 for t in buys)
    total_out = sum(t.get("volume_usd") or 0 for t in sells)

    summary = {
        "total_inflow": round(total_in, 2),
        "total_outflow": round(total_out, 2),
        "net_flow": round(total_in - total_out, 2),
        "unique_buyers": len(set(t["wallet_address"] for t in buys)),
        "unique_sellers": len(set(t["wallet_address"] for t in sells)),
        "buy_count": len(buys),
        "sell_count": len(sells),
    }

    return {"data": rows, "summary": summary}
