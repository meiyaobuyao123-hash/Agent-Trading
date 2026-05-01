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

    # 独立 api 进程(脱钩自 main.py):scanner 不在本进程
    # 读取顺序: Redis (主, 5s 新鲜) → 文件 (兜底, 最差 60s) → 空
    # 引用 docs/runbook/pump-scanner-api.service + main.py signal_pool_dump_loop
    import json
    import os
    from datetime import datetime, timezone

    # ── 1. Redis 主路径 ───────────────────────────────────────
    try:
        from agent.redis_client import safe_get_async, KEY_PUMP_SIGNAL_POOL
        raw = await safe_get_async(KEY_PUMP_SIGNAL_POOL)
        if raw:
            data = json.loads(raw)
            signals = data.get("signals", [])
            ts_str = data.get("ts")
            dump_age_ms = None
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    dump_age_ms = int((datetime.now(timezone.utc) - ts).total_seconds() * 1000)
                except Exception:
                    pass
            return {
                "signals": signals,
                "count": len(signals),
                "is_history": data.get("is_history", False),
                "source": "redis",
                "dump_age_ms": dump_age_ms,
            }
    except Exception as e:
        log.warning("Redis 读 signal_pool 失败,降级到文件: %s", e)

    # ── 2. 文件兜底 ───────────────────────────────────────────
    DUMP_PATH = "/tmp/pump_signal_pool.json"
    try:
        if not os.path.exists(DUMP_PATH):
            return {"signals": [], "count": 0, "is_history": False, "source": "none",
                    "message": "信号池还未生成(Redis 不可用 + 文件未写)"}
        mtime = datetime.fromtimestamp(os.path.getmtime(DUMP_PATH), tz=timezone.utc)
        age_ms = int((datetime.now(timezone.utc) - mtime).total_seconds() * 1000)
        if age_ms > 300_000:
            log.warning("pump signal_pool 文件陈旧 %ds", age_ms // 1000)
        with open(DUMP_PATH, "r") as f:
            data = json.load(f)
        signals = data.get("signals", [])
        return {
            "signals": signals,
            "count": len(signals),
            "is_history": data.get("is_history", False),
            "source": "file",
            "dump_age_ms": age_ms,
        }
    except Exception as e:
        log.warning("读 signal pool 文件失败: %s", e)
        return {"signals": [], "count": 0, "source": "none", "message": "scanner not ready",
                "error": str(e)[:100]}


@router.get("/stats")
async def get_pump_stats():
    """采集统计快照"""
    import pump_stats
    return pump_stats.snapshot()
