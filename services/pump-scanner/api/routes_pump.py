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
    # main.py 每 60s 把 _signal_pool 写到文件,api 进程读
    # 引用 docs/runbook/pump-scanner-api.service + main.py signal_pool_dump_loop
    import json
    import os
    DUMP_PATH = "/tmp/pump_signal_pool.json"
    try:
        if not os.path.exists(DUMP_PATH):
            return {"signals": [], "count": 0, "is_history": False,
                    "message": "信号池文件还未生成(scanner 启动后 60s 内首次)"}
        # 文件 mtime 检查(超过 5min 视为陈旧)
        from datetime import datetime, timezone
        mtime = datetime.fromtimestamp(os.path.getmtime(DUMP_PATH), tz=timezone.utc)
        age_s = (datetime.now(timezone.utc) - mtime).total_seconds()
        if age_s > 300:
            log.warning("pump signal_pool dump 文件陈旧 %ds", int(age_s))
        with open(DUMP_PATH, "r") as f:
            data = json.load(f)
        signals = data.get("signals", [])
        return {
            "signals": signals,
            "count": len(signals),
            "is_history": data.get("is_history", False),
            "source": "file_ipc",
            "dump_age_s": int(age_s),
        }
    except Exception as e:
        log.warning("读 signal pool 文件失败: %s", e)
        return {"signals": [], "count": 0, "message": "scanner not ready",
                "error": str(e)[:100]}


@router.get("/stats")
async def get_pump_stats():
    """采集统计快照"""
    import pump_stats
    return pump_stats.snapshot()
