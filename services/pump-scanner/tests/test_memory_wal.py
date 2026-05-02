"""
Memory WAL 单元测试 — W3 D5+ autonomous-loop 续 14

跑法:python3 -m pytest tests/test_memory_wal.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.memory import wal as wal_mod  # noqa: E402
from agent.memory.wal import (  # noqa: E402
    BACKOFF_SCHEDULE_S,
    MAX_ATTEMPT,
    MemoryWAL,
    get_wal,
    reset_wal_for_test,
)


def _make_fake_pg_conn():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = None
    return conn, cur


VALID_UUID = "00000000-0000-0000-0000-000000000001"


# ── _idempotency_key ────────────────────────────────────────

def test_idempotency_key_deterministic_within_minute():
    """同 minute 内同 device + event 产同 key。"""
    a = MemoryWAL._idempotency_key(VALID_UUID, "ev-1")
    b = MemoryWAL._idempotency_key(VALID_UUID, "ev-1")
    assert a == b
    assert len(a) == 32


def test_idempotency_key_different_for_different_event():
    a = MemoryWAL._idempotency_key(VALID_UUID, "ev-1")
    b = MemoryWAL._idempotency_key(VALID_UUID, "ev-2")
    assert a != b


# ── write() ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_write_invalid_memory_type_returns_none():
    w = MemoryWAL()
    r = await w.write(VALID_UUID, "wrong_type", {}, "ev-1")
    assert r is None


@pytest.mark.asyncio
async def test_write_non_uuid_device_skipped():
    """非 UUID device_id → skip(避免表 NOT NULL UUID 报错)。"""
    w = MemoryWAL()
    r = await w.write("system", "semantic", {}, "ev-1")
    assert r is None


@pytest.mark.asyncio
async def test_write_disabled_returns_none():
    w = MemoryWAL()
    w.disable()
    r = await w.write(VALID_UUID, "semantic", {}, "ev-1")
    assert r is None


@pytest.mark.asyncio
async def test_write_returns_wal_id_on_insert():
    w = MemoryWAL()
    conn, cur = _make_fake_pg_conn()
    cur.fetchone.return_value = (123,)  # RETURNING wal_id
    with patch("local_db._get_conn", return_value=conn):
        r = await w.write(VALID_UUID, "semantic", {"x": 1}, "ev-1")
    assert r == 123


@pytest.mark.asyncio
async def test_write_on_conflict_returns_existing_id():
    """ON CONFLICT → INSERT 不返回 → 二次 SELECT 返已存在 id。"""
    w = MemoryWAL()
    conn, cur = _make_fake_pg_conn()
    cur.fetchone.side_effect = [None, (777,)]  # INSERT返空,SELECT 返 777
    with patch("local_db._get_conn", return_value=conn):
        r = await w.write(VALID_UUID, "semantic", {}, "ev-dup")
    assert r == 777


@pytest.mark.asyncio
async def test_write_db_failure_returns_none():
    w = MemoryWAL()
    with patch("local_db._get_conn", side_effect=Exception("PG down")):
        r = await w.write(VALID_UUID, "semantic", {}, "ev-x")
    assert r is None


# ── flush_once() ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_flush_once_no_unflushed_returns_zero():
    w = MemoryWAL()
    conn, cur = _make_fake_pg_conn()
    cur.fetchall.return_value = []
    with patch("local_db._get_conn", return_value=conn):
        r = await w.flush_once()
    assert r == {"scanned": 0, "flushed": 0, "failed": 0}


@pytest.mark.asyncio
async def test_flush_once_success_marks_flushed():
    w = MemoryWAL()
    conn, cur = _make_fake_pg_conn()
    cur.fetchall.return_value = [
        (1, VALID_UUID, "semantic", {"type": "semantic", "content": "rule1"}),
        (2, VALID_UUID, "episodic", {"type": "episodic", "content": "trade"}),
    ]
    fake_supa = MagicMock()
    fake_supa.table.return_value.insert.return_value.execute.return_value = MagicMock()
    with patch("local_db._get_conn", return_value=conn), \
         patch("database.get_db", return_value=fake_supa):
        r = await w.flush_once()
    assert r["scanned"] == 2
    assert r["flushed"] == 2
    assert r["failed"] == 0


@pytest.mark.asyncio
async def test_flush_once_main_db_failure_enqueues_retry():
    w = MemoryWAL()
    conn, cur = _make_fake_pg_conn()
    cur.fetchall.return_value = [
        (1, VALID_UUID, "semantic", {"type": "semantic"}),
    ]
    # 主表写失败
    fake_supa = MagicMock()
    fake_supa.table.return_value.insert.return_value.execute.side_effect = Exception("Supabase 503")
    with patch("local_db._get_conn", return_value=conn), \
         patch("database.get_db", return_value=fake_supa):
        r = await w.flush_once()
    assert r["scanned"] == 1
    assert r["flushed"] == 0
    assert r["failed"] == 1


@pytest.mark.asyncio
async def test_flush_once_select_failure_returns_zero():
    w = MemoryWAL()
    with patch("local_db._get_conn", side_effect=Exception("PG down")):
        r = await w.flush_once()
    assert r == {"scanned": 0, "flushed": 0, "failed": 0}


# ── retry_once() ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_once_recovers_when_main_db_succeeds():
    w = MemoryWAL()
    conn, cur = _make_fake_pg_conn()
    cur.fetchall.return_value = [
        (10, 1, 0, VALID_UUID, "semantic", {"type": "semantic", "content": "x"}),
    ]
    fake_supa = MagicMock()
    fake_supa.table.return_value.insert.return_value.execute.return_value = MagicMock()
    with patch("local_db._get_conn", return_value=conn), \
         patch("database.get_db", return_value=fake_supa):
        r = await w.retry_once()
    assert r["scanned"] == 1
    assert r["recovered"] == 1
    assert r["still_failing"] == 0


@pytest.mark.asyncio
async def test_retry_once_still_failing_below_max_increments_attempt():
    w = MemoryWAL()
    conn, cur = _make_fake_pg_conn()
    # attempt_count=0 → 失败后变 1,next_retry = 5min
    cur.fetchall.return_value = [
        (10, 1, 0, VALID_UUID, "semantic", {}),
    ]
    fake_supa = MagicMock()
    fake_supa.table.return_value.insert.return_value.execute.side_effect = Exception("502")
    with patch("local_db._get_conn", return_value=conn), \
         patch("database.get_db", return_value=fake_supa):
        r = await w.retry_once()
    assert r["still_failing"] == 1
    assert r["recovered"] == 0
    assert r["p1_alerted"] == 0


@pytest.mark.asyncio
async def test_retry_once_p1_alert_at_max_attempt():
    """attempt_count=2 → 第 3 次失败 → 标 P1 (still_failing+1, p1_alerted+1)。"""
    w = MemoryWAL()
    conn, cur = _make_fake_pg_conn()
    cur.fetchall.return_value = [
        (10, 1, 2, VALID_UUID, "semantic", {}),  # already attempted 2 times
    ]
    fake_supa = MagicMock()
    fake_supa.table.return_value.insert.return_value.execute.side_effect = Exception("still down")
    with patch("local_db._get_conn", return_value=conn), \
         patch("database.get_db", return_value=fake_supa):
        r = await w.retry_once()
    assert r["still_failing"] == 1
    assert r["p1_alerted"] == 1


@pytest.mark.asyncio
async def test_retry_once_no_pending_returns_zero():
    w = MemoryWAL()
    conn, cur = _make_fake_pg_conn()
    cur.fetchall.return_value = []
    with patch("local_db._get_conn", return_value=conn):
        r = await w.retry_once()
    assert r["scanned"] == 0


# ── _write_to_main_db ───────────────────────────────────────

@pytest.mark.asyncio
async def test_write_to_main_db_success():
    w = MemoryWAL()
    fake = MagicMock()
    fake.table.return_value.insert.return_value.execute.return_value = MagicMock()
    with patch("database.get_db", return_value=fake):
        ok, err = await w._write_to_main_db(
            wal_id=1, device_id=VALID_UUID, memory_type="semantic",
            payload={"type": "semantic", "content": "rule"},
        )
    assert ok is True
    assert err is None


@pytest.mark.asyncio
async def test_write_to_main_db_failure_returns_error():
    w = MemoryWAL()
    fake = MagicMock()
    fake.table.return_value.insert.return_value.execute.side_effect = Exception("permission denied")
    with patch("database.get_db", return_value=fake):
        ok, err = await w._write_to_main_db(
            wal_id=1, device_id=VALID_UUID, memory_type="semantic",
            payload={},
        )
    assert ok is False
    assert "permission denied" in err


# ── singleton ──────────────────────────────────────────────

def test_get_wal_singleton():
    reset_wal_for_test()
    a = get_wal()
    b = get_wal()
    assert a is b


# ── BACKOFF_SCHEDULE constants ──────────────────────────────

def test_backoff_schedule_three_levels():
    assert BACKOFF_SCHEDULE_S == [60, 300, 1800]
    assert MAX_ATTEMPT == 3
