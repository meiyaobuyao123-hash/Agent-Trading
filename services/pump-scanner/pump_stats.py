"""
内盘采集计数器（进程内共享）

collector.py 实时递增，pump_report_job.py 定时读取并重置。
所有计数器按日期分桶，跨天自动归零。
"""

import threading
from datetime import date, timezone, datetime


_lock = threading.Lock()
_today: str = ""
_counters: dict = {}


def _ensure_today():
    """检查日期，跨天自动清零"""
    global _today, _counters
    d = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if d != _today:
        _today = d
        _counters = {
            "ws_creates": 0,           # WS 收到的全部 create 事件（市场总量）
            "trade_track_full": 0,     # 交易追踪池满，未追踪交易（但已写DB）
            "enrich_triggered": 0,     # 初筛通过，触发 enrich
            "enrich_success": 0,       # REST enrich 成功
            "enrich_fail": 0,          # REST enrich 失败
            "ws_new_reconnects": 0,    # newToken WS 重连次数
            "ws_trade_reconnects": 0,  # trade WS 重连次数
            "snapshots_written": 0,    # 写入快照数
            "hard_filter_pass": 0,     # 通过硬过滤数
            "hard_filter_fail": 0,     # 未通过硬过滤数
            "signal_entered": 0,       # 进入信号池数
            "signal_exited": 0,        # 移出信号池数
        }


def incr(key: str, n: int = 1):
    """递增计数器"""
    with _lock:
        _ensure_today()
        _counters[key] = _counters.get(key, 0) + n


def snapshot() -> dict:
    """读取当日计数快照（不清零）"""
    with _lock:
        _ensure_today()
        return {"date": _today, **_counters.copy()}
