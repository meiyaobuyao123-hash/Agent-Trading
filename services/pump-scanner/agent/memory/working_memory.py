"""
短期记忆 — 24h 滑动窗口，内存存储

PRD-005 M12: 最近 200 条事件，24h 滑动窗口（不每日清零）。
每次决策前取最近 10 条注入 prompt。

Python 3.9 兼容。
"""

import time
from collections import deque
from typing import List, Dict, Any

MAX_ITEMS = 200
WINDOW_SEC = 86400  # 24h


class WorkingMemory:
    """短期记忆 — deque + 24h 滑动窗口"""

    def __init__(self, maxlen: int = MAX_ITEMS, window_sec: float = WINDOW_SEC):
        self._events: deque = deque(maxlen=maxlen)
        self._window_sec = window_sec

    def add(self, event: Dict[str, Any]) -> None:
        """写入一条事件到短期记忆"""
        event["_ts"] = time.time()
        self._events.append(event)

    def get_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近 n 条事件（24h 滑动窗口内）

        返回按时间正序排列（最旧在前，最新在后）。
        """
        now = time.time()
        cutoff = now - self._window_sec
        valid = [e for e in self._events if e.get("_ts", 0) >= cutoff]
        return valid[-n:] if len(valid) > n else valid

    def size(self) -> int:
        """当前事件总数（含过期未清理的）"""
        return len(self._events)

    def size_valid(self) -> int:
        """24h 窗口内有效事件数"""
        now = time.time()
        cutoff = now - self._window_sec
        return sum(1 for e in self._events if e.get("_ts", 0) >= cutoff)

    def clear(self) -> None:
        """清空所有事件"""
        self._events.clear()
