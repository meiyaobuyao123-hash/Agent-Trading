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
    # token_snapshots 没 score 列(scanner 内存算的),只能查 daily_picks(每日 Top20 推荐)
    # 引用 docs/runbook/pump-scanner-api.service
    from datetime import datetime, timezone, timedelta
    try:
        from database import get_db
        # daily_picks 是每日 UTC 00:05 生成的 pump Top20 推荐(source='pump')
        cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        res = get_db().table("daily_picks") \
            .select("mint, name, symbol, score, market_cap_sol, "
                    "bc_progress, image_url, twitter, telegram, website, "
                    "smart_money_count, recommendation, created_at") \
            .eq("source", "pump") \
            .gte("created_at", cutoff) \
            .order("created_at", desc=True) \
            .order("score", desc=True) \
            .limit(50) \
            .execute()
        rows = res.data or []
        # 按 mint 去重(同 mint 多日推荐取最新)
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
            "source": "db_fallback_daily_picks",
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
