"""
Pump 实时信号 API

端点：
- GET /api/pump/signals — 当前实时信号池（APP 30s 轮询）
- GET /api/pump/stats   — 采集统计快照
"""

import logging
from fastapi import APIRouter

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pump", tags=["pump"])


@router.get("/signals")
async def get_pump_signals():
    """
    返回当前实时信号池。

    信号池特性：
    - 实时更新（每60s快照周期）
    - 符合条件自动进入（score >= 55, BC 3-35%）
    - 不再符合条件自动移出（涨过了/死了/超时）
    - 无固定大小，可能为空
    """
    from scanner_ref import get_scanner

    scanner = get_scanner()
    if scanner is not None:
        # 同进程:直读内存(实时,毫秒级)
        signals = scanner.get_signals()
        is_history = bool(signals and signals[0].get("is_history"))
        return {
            "signals": signals,
            "count": len(signals),
            "is_history": is_history,  # True = 当前无实时信号，展示最近 1h 历史回顾
        }

    # 独立 api 进程(脱钩自 main.py):scanner 不可用,DB fallback
    # 查最近 1h score>=55 + BC 3-35% 的 token_snapshots(每 mint 最新)
    # 引用 docs/runbook/pump-scanner-api.service
    from datetime import datetime, timezone, timedelta
    try:
        from database import get_db
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        res = get_db().table("token_snapshots") \
            .select("mint, snapshot_at, score, market_cap_sol, bc_progress_pct, "
                    "buy_count, sell_count, unique_buyers, smart_elite_count, "
                    "smart_verified_count, smart_money_net_sol") \
            .gte("snapshot_at", cutoff) \
            .gte("score", 55) \
            .gte("bc_progress_pct", 3) \
            .lte("bc_progress_pct", 35) \
            .order("score", desc=True) \
            .limit(50) \
            .execute()
        rows = res.data or []
        seen = set()
        signals = []
        for row in rows:
            mint = row.get("mint")
            if mint and mint not in seen:
                seen.add(mint)
                signals.append({**row, "is_history": True})
        signals = signals[:30]
        return {
            "signals": signals,
            "count": len(signals),
            "is_history": True,
            "source": "db_fallback",
        }
    except Exception as e:
        log.warning("pump signals DB fallback 失败: %s", e)
        return {"signals": [], "count": 0, "message": "scanner not ready",
                "error": str(e)[:100]}


@router.get("/stats")
async def get_pump_stats():
    """采集统计快照"""
    import pump_stats
    return pump_stats.snapshot()
