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
    from main import get_scanner

    scanner = get_scanner()
    if scanner is None:
        return {"signals": [], "count": 0, "message": "scanner not ready"}

    signals = scanner.get_signals()
    return {
        "signals": signals,
        "count": len(signals),
    }


@router.get("/stats")
async def get_pump_stats():
    """采集统计快照"""
    import pump_stats
    return pump_stats.snapshot()
