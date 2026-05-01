"""
Memory WAL(Write-Ahead Log)— 关键 memory 写入可靠性
引用 docs/agent-pm/06-memory-spec.md §3.5
引用 migration 036_pending_approvals_wal.sql
引用 docs/agent-pm/17-tech-plan.md Phase 1

关键写入(必走 WAL):
  - episodic.trade_outcome / risk_lesson
  - semantic.approve_rule / auto-promote

流程:
  内存写请求
    ↓
  ① 写本地 WAL (memory_write_wal 表, < 10ms)
    ↓
  ② 异步入主 DB (agent_memory)
    ↓
  ③ 成功 → 标 flushed=true
  ③' 失败 → 进 memory_write_retry_queue
       ├─ 60s 退避重试
       ├─ 5min 退避重试
       ├─ 30min 退避重试
       └─ 3 次失败 → P1 告警(failed_p1_alerted=true)+ WAL 保留待人工

幂等键: hash(device_id + event_id + truncate_minute(ts))

状态:🔴 v0.1 占位(W7-W12 实施)
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import hashlib
import logging

log = logging.getLogger(__name__)


@dataclass
class WalEntry:
    wal_id: int
    device_id: str
    memory_type: str  # 'episodic' | 'semantic' | 'reflection'
    payload: dict[str, Any]
    idempotency_key: str
    flushed: bool = False


class MemoryWAL:
    """异步刷写 + 重试队列。FastAPI startup 时启动 background worker。"""

    def __init__(self) -> None:
        self._running = False

    async def write(
        self,
        device_id: str,
        memory_type: str,
        payload: dict[str, Any],
        event_id: str,
    ) -> int:
        """写 WAL(同步,< 10ms);返回 wal_id。"""
        idem_key = self._idempotency_key(device_id, event_id)
        # TODO: INSERT INTO memory_write_wal ON CONFLICT (idempotency_key) DO NOTHING
        log.debug("[WAL] write device=%s type=%s key=%s", device_id, memory_type, idem_key)
        return 0  # 占位

    async def flush_loop(self) -> None:
        """background worker: 每秒扫描 unflushed WAL → 写 agent_memory → 失败入 retry queue。"""
        while self._running:
            # TODO: SELECT unflushed → INSERT INTO agent_memory
            # TODO: 失败 → INSERT INTO memory_write_retry_queue
            pass

    async def retry_loop(self) -> None:
        """background worker: 每 30s 扫描 retry queue → 退避重试 → 3 次失败 P1 告警。"""
        while self._running:
            # TODO: SELECT * FROM memory_write_retry_queue WHERE next_retry_at < now() AND resolved = false
            pass

    @staticmethod
    def _idempotency_key(device_id: str, event_id: str) -> str:
        """hash(device_id + event_id + truncate_minute(now))"""
        ts_minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        raw = f"{device_id}:{event_id}:{ts_minute}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]


_wal: MemoryWAL | None = None


def get_wal() -> MemoryWAL:
    global _wal
    if _wal is None:
        _wal = MemoryWAL()
    return _wal
