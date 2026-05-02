"""
Memory WAL(Write-Ahead Log)— 关键 memory 写入可靠性

引用 docs/agent-pm/06-memory-spec.md §3.5
引用 services/pump-scanner/migrations/local_pg/036_pending_approvals_wal.sql
引用 docs/agent-pm/17-tech-plan.md Phase 1

关键写入(必走 WAL):
  - episodic.trade_outcome / risk_lesson
  - semantic.approve_rule / auto-promote(try_promote_strict)

流程:
  内存写请求
    ↓
  ① write():INSERT memory_write_wal(同步,< 50ms)+ ON CONFLICT(idempotency_key) DO NOTHING
    ↓
  ② flush_loop():SELECT unflushed → INSERT agent_memory(Supabase) → mark flushed=true
    ↓
  ③ 失败 → INSERT memory_write_retry_queue(next_retry_at = now + 60s)
    ↓
  ④ retry_loop():
       attempt_count=0 → 60s 退避
       attempt_count=1 → 5min 退避
       attempt_count=2 → 30min 退避
       attempt_count >= 3 → 标 failed_p1_alerted=true(由 alert cron 发 P1)+ WAL 保留待人工

幂等键:hash(device_id + event_id + truncate_minute(ts))

W3 D5+ autonomous-loop 续 14 真实施(替代 W1 占位)。
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import time as _time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


# 退避配置
BACKOFF_SCHEDULE_S = [60, 300, 1800]   # 60s / 5min / 30min
MAX_ATTEMPT = 3                         # 第 3 次失败 → P1
FLUSH_BATCH_SIZE = 50                   # flush_loop 每次最多刷 50 条
RETRY_BATCH_SIZE = 50

VALID_MEMORY_TYPES = ("episodic", "semantic", "reflection")


@dataclass
class WalEntry:
    wal_id: int
    device_id: str
    memory_type: str
    payload: Dict[str, Any]
    idempotency_key: str
    flushed: bool = False


class MemoryWAL:
    """异步刷写 + 重试队列。"""

    def __init__(self) -> None:
        self._enabled: bool = True

    # ── public API ──────────────────────────────────────────

    async def write(
        self,
        device_id: str,
        memory_type: str,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
    ) -> Optional[int]:
        """同步写 WAL(< 50ms);返回 wal_id 或 None(失败)。

        idempotency_key = hash(device + event_id + minute_trunc),同 minute 内
        重复事件 ON CONFLICT 跳过(返回已存在 wal_id)。
        """
        if memory_type not in VALID_MEMORY_TYPES:
            log.warning("[WAL] invalid memory_type: %s", memory_type)
            return None
        if not self._enabled:
            return None

        idem_key = self._idempotency_key(device_id, event_id or "")

        # device_id 必须 UUID(WAL 表 NOT NULL UUID)
        import re
        if not re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            device_id, re.IGNORECASE,
        ):
            log.debug("[WAL] non-UUID device_id, skip: %s", device_id)
            return None

        try:
            from local_db import _get_conn
            conn = _get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memory_write_wal
                      (device_id, memory_type, payload, idempotency_key)
                    VALUES (%s, %s, %s::jsonb, %s)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING wal_id
                    """,
                    (device_id, memory_type, json.dumps(payload, default=str), idem_key),
                )
                row = cur.fetchone()
                if row:
                    return int(row[0])
                # ON CONFLICT 命中:返已存在的 wal_id
                cur.execute(
                    "SELECT wal_id FROM memory_write_wal WHERE idempotency_key = %s",
                    (idem_key,),
                )
                row = cur.fetchone()
                return int(row[0]) if row else None
        except Exception as e:
            log.warning("[WAL] write failed: %s", e)
            return None

    async def flush_once(self, batch_size: int = FLUSH_BATCH_SIZE) -> Dict[str, int]:
        """单次 flush:扫 unflushed → 写主表(agent_memory)→ mark flushed。

        Returns: {scanned, flushed, failed}
        """
        scanned = 0
        flushed = 0
        failed = 0
        try:
            from local_db import _get_conn
            conn = _get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT wal_id, device_id, memory_type, payload
                    FROM memory_write_wal
                    WHERE flushed = false
                    ORDER BY ts
                    LIMIT %s
                    """,
                    (batch_size,),
                )
                rows = cur.fetchall()
        except Exception as e:
            log.warning("[WAL] flush_once SELECT failed: %s", e)
            return {"scanned": 0, "flushed": 0, "failed": 0}

        for wal_id, device_id, mem_type, payload in rows:
            scanned += 1
            ok, err = await self._write_to_main_db(
                wal_id=int(wal_id), device_id=str(device_id),
                memory_type=mem_type,
                payload=payload if isinstance(payload, dict) else {},
            )
            if ok:
                flushed += 1
                # mark flushed
                try:
                    from local_db import _get_conn as _gc
                    conn2 = _gc()
                    with conn2.cursor() as cur2:
                        cur2.execute(
                            "UPDATE memory_write_wal SET flushed = true, flushed_at = now() WHERE wal_id = %s",
                            (wal_id,),
                        )
                except Exception as e:
                    log.warning("[WAL] mark flushed failed wal=%s: %s", wal_id, e)
            else:
                failed += 1
                # 入 retry queue
                self._enqueue_retry(wal_id=int(wal_id), error=err or "unknown")

        if scanned:
            log.info("[WAL flush] scanned=%d flushed=%d failed=%d",
                     scanned, flushed, failed)
        return {"scanned": scanned, "flushed": flushed, "failed": failed}

    async def retry_once(self, batch_size: int = RETRY_BATCH_SIZE) -> Dict[str, int]:
        """单次 retry:扫到期重试条目 → 重写主表 → 成功 mark resolved / 失败累 attempt。

        Returns: {scanned, recovered, still_failing, p1_alerted}
        """
        scanned = 0
        recovered = 0
        still_failing = 0
        p1_alerted = 0

        try:
            from local_db import _get_conn
            conn = _get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT q.retry_id, q.wal_id, q.attempt_count,
                           w.device_id, w.memory_type, w.payload
                    FROM memory_write_retry_queue q
                    JOIN memory_write_wal w ON w.wal_id = q.wal_id
                    WHERE q.resolved = false
                      AND q.next_retry_at <= now()
                    ORDER BY q.next_retry_at
                    LIMIT %s
                    """,
                    (batch_size,),
                )
                rows = cur.fetchall()
        except Exception as e:
            log.warning("[WAL] retry_once SELECT failed: %s", e)
            return {"scanned": 0, "recovered": 0, "still_failing": 0, "p1_alerted": 0}

        for retry_id, wal_id, attempt_count, device_id, mem_type, payload in rows:
            scanned += 1
            ok, err = await self._write_to_main_db(
                wal_id=int(wal_id), device_id=str(device_id),
                memory_type=mem_type,
                payload=payload if isinstance(payload, dict) else {},
            )
            if ok:
                recovered += 1
                # mark resolved + WAL flushed
                try:
                    from local_db import _get_conn as _gc
                    conn2 = _gc()
                    with conn2.cursor() as cur2:
                        cur2.execute(
                            "UPDATE memory_write_retry_queue SET resolved = true WHERE retry_id = %s",
                            (retry_id,),
                        )
                        cur2.execute(
                            "UPDATE memory_write_wal SET flushed = true, flushed_at = now() WHERE wal_id = %s",
                            (wal_id,),
                        )
                except Exception as e:
                    log.warning("[WAL] retry mark resolved failed: %s", e)
                continue

            # 仍失败 → 累 attempt + 设下次 next_retry_at
            new_attempt = int(attempt_count) + 1
            still_failing += 1
            try:
                from local_db import _get_conn as _gc
                conn2 = _gc()
                with conn2.cursor() as cur2:
                    if new_attempt >= MAX_ATTEMPT:
                        # 标 P1 告警(待 alert cron 处理)
                        cur2.execute(
                            """
                            UPDATE memory_write_retry_queue
                            SET attempt_count = %s, last_error = %s,
                                failed_p1_alerted = false  -- 等 alert cron 标 true
                            WHERE retry_id = %s
                            """,
                            (new_attempt, str(err)[:300], retry_id),
                        )
                        p1_alerted += 1
                    else:
                        next_at = datetime.now(timezone.utc) + timedelta(
                            seconds=BACKOFF_SCHEDULE_S[new_attempt],
                        )
                        cur2.execute(
                            """
                            UPDATE memory_write_retry_queue
                            SET attempt_count = %s, next_retry_at = %s,
                                last_error = %s
                            WHERE retry_id = %s
                            """,
                            (new_attempt, next_at, str(err)[:300], retry_id),
                        )
            except Exception as e:
                log.warning("[WAL] retry update failed: %s", e)

        if scanned:
            log.info(
                "[WAL retry] scanned=%d recovered=%d still=%d p1=%d",
                scanned, recovered, still_failing, p1_alerted,
            )
        return {
            "scanned": scanned, "recovered": recovered,
            "still_failing": still_failing, "p1_alerted": p1_alerted,
        }

    # ── helpers ──────────────────────────────────────────────

    async def _write_to_main_db(
        self, wal_id: int, device_id: str, memory_type: str, payload: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """写主表 — semantic/episodic/reflection 都走 agent_memory(Supabase)。

        payload 期望有 type/content/structured_data 等 agent_memory 列。
        缺失字段补默认值。
        """
        try:
            from database import get_db
            db = get_db()

            row = {
                "user_id": device_id,
                "type": payload.get("type") or memory_type,
                "content": payload.get("content", "")[:1000],
                "structured_data": payload.get("structured_data") or {},
                "is_active": payload.get("is_active", True),
                "importance": payload.get("importance", 5),
                "trigger_source": payload.get("trigger_source"),
                "chain": payload.get("chain"),
            }
            # semantic 特有字段
            for f in ("shadow_mode_until", "wilson_ci_lower", "match_count",
                      "propose_count_so_far", "comply_win", "comply_lose",
                      "violate_win", "violate_lose"):
                if f in payload:
                    row[f] = payload[f]

            db.table("agent_memory").insert(row).execute()
            return True, None
        except Exception as e:
            return False, str(e)[:300]

    def _enqueue_retry(self, wal_id: int, error: str) -> None:
        """把失败的 wal 入 retry queue(初次 attempt_count=0,next_retry_at=now+60s)。"""
        try:
            from local_db import _get_conn
            conn = _get_conn()
            next_at = datetime.now(timezone.utc) + timedelta(seconds=BACKOFF_SCHEDULE_S[0])
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memory_write_retry_queue
                      (wal_id, attempt_count, next_retry_at, last_error)
                    VALUES (%s, 0, %s, %s)
                    """,
                    (wal_id, next_at, error[:300]),
                )
        except Exception as e:
            log.warning("[WAL] enqueue_retry failed: %s", e)

    @staticmethod
    def _idempotency_key(device_id: str, event_id: str) -> str:
        ts_minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        raw = f"{device_id}:{event_id}:{ts_minute}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def disable(self) -> None:
        """测试用:禁用 WAL(write 直接 noop)。"""
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True


# ── singleton ────────────────────────────────────────────


_wal: Optional[MemoryWAL] = None


def get_wal() -> MemoryWAL:
    global _wal
    if _wal is None:
        _wal = MemoryWAL()
    return _wal


def reset_wal_for_test() -> None:
    global _wal
    _wal = None
