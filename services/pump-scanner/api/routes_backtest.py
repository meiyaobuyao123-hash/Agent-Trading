"""
热币模拟盘看板 API

GET /api/data/hot-sim?mode=repeat    — 每次都买模式统计
GET /api/data/hot-sim?mode=unique    — 每币只买一次模式统计
GET /api/data/hot-sim/compare        — 两种模式对比
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from database import get_db

router = APIRouter(prefix="/api/data", tags=["data-sim"])
log = logging.getLogger(__name__)


def _get_stats(mode: str, source: str = "") -> dict:
    db = get_db()
    try:
        q = db.table("hot_sim_trades").select("*").eq("mode", mode)
        if source:
            q = q.eq("source", source)
        res = q.order("entered_at", desc=True).execute()
    except Exception as e:
        return {"error": str(e)}

    rows = res.data or []
    if not rows:
        return {"mode": mode, "total_trades": 0, "message": "暂无数据，等待热币入榜触发"}

    open_trades = [r for r in rows if r.get("status") == "open"]
    tp_trades = [r for r in rows if r.get("status") == "tp"]
    sl_trades = [r for r in rows if r.get("status") == "sl"]
    closed = tp_trades + sl_trades

    total_pnl = sum(float(r.get("pnl_usd") or 0) for r in closed)
    # open 仓位的浮动盈亏不计入已实现 PNL

    win_rate = len(tp_trades) / len(closed) * 100 if closed else 0
    total_invested = len(rows) * 10.0

    return {
        "mode": mode,
        "mode_label": "每次都买" if mode == "repeat" else "每币只买一次",
        "config": {"buy_amount": 10, "tp_pct": 15, "sl_pct": 15},
        "summary": {
            "total_trades": len(rows),
            "open_trades": len(open_trades),
            "closed_trades": len(closed),
            "wins": len(tp_trades),
            "losses": len(sl_trades),
            "win_rate": round(win_rate, 1),
            "total_invested": round(total_invested, 2),
            "realized_pnl": round(total_pnl, 2),
            "roi_pct": round(total_pnl / total_invested * 100, 1) if total_invested > 0 else 0,
        },
        "recent_trades": [{
            "symbol": r.get("symbol", "?"),
            "chain": r.get("chain", ""),
            "entry_price": r.get("entry_price"),
            "exit_price": r.get("exit_price"),
            "pnl_pct": r.get("pnl_pct"),
            "pnl_usd": r.get("pnl_usd"),
            "status": r.get("status"),
            "score": r.get("score_at_entry"),
            "entered_at": r.get("entered_at"),
            "exited_at": r.get("exited_at"),
        } for r in rows[:30]],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/hot-sim")
async def hot_sim(
    mode: str = Query("repeat", regex="^(repeat|unique)$"),
    source: str = Query("", regex="^(|hot|smart_money|pump|btc_eth)$"),
):
    return _get_stats(mode, source)


@router.get("/hot-sim/compare")
async def hot_sim_compare(source: str = Query("", regex="^(|hot|smart_money|pump|btc_eth)$")):
    return {
        "repeat": _get_stats("repeat", source),
        "unique": _get_stats("unique", source),
    }
