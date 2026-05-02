"""
HITL 5/15/60min 超时升级测试 — R37 P0-3
跑法:python3 -m pytest tests/test_hitl_timeout_loop.py -v

验证:
  1. is_approval_degraded() — None / 空 / 含 hitl_15min_degraded
  2. scan_and_escalate() local_db 不可用 → 返 0 不抛
  3. scan_and_escalate() PG 连接失败 → errors>=1 不抛
  4. scan_and_escalate() 真 PG path(mock _get_conn)— 5min 重推 + 15min 降级 + 60min 过期 计数正确
  5. _try_send_repush 失败不抛
"""
from __future__ import annotations
import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ── is_approval_degraded ─────────────────────────────────────


def test_is_degraded_none():
    from agent.loops.hitl_timeout_loop import is_approval_degraded
    assert is_approval_degraded(None) is False


def test_is_degraded_empty():
    from agent.loops.hitl_timeout_loop import is_approval_degraded
    assert is_approval_degraded("") is False


def test_is_degraded_unrelated_reason():
    from agent.loops.hitl_timeout_loop import is_approval_degraded
    assert is_approval_degraded("user_rejected") is False


def test_is_degraded_marker_present():
    from agent.loops.hitl_timeout_loop import is_approval_degraded
    assert is_approval_degraded("hitl_15min_degraded:notify_only") is True


def test_is_degraded_marker_with_other():
    from agent.loops.hitl_timeout_loop import is_approval_degraded
    assert is_approval_degraded("hitl_15min_degraded;manual_override") is True


# ── scan_and_escalate fail-safe ──────────────────────────────


@pytest.mark.asyncio
async def test_scan_returns_zeros_when_local_db_unavailable():
    from agent.loops import hitl_timeout_loop as ht
    # patch the import inside scan_and_escalate to fail
    import builtins
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "local_db":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=_fake_import):
        counts = await ht.scan_and_escalate()
    assert counts == {"repushed": 0, "degraded": 0, "expired": 0, "errors": 0}


@pytest.mark.asyncio
async def test_scan_increments_errors_on_pg_connect_fail():
    from agent.loops import hitl_timeout_loop as ht
    fake_local_db = MagicMock()
    fake_local_db._get_conn.side_effect = ConnectionError("pg down")
    with patch.dict(sys.modules, {"local_db": fake_local_db}):
        counts = await ht.scan_and_escalate()
    assert counts["errors"] >= 1


# ── scan_and_escalate happy path ─────────────────────────────


def _mock_conn_with_results(expired=None, degraded=None, repushed=None):
    """构造 mock conn 让 cursor.fetchall() 按调用顺序返指定 rows。
    顺序:1) expire UPDATE...RETURNING  2) audit insert(per row)
          3) degrade UPDATE...RETURNING  4) audit insert(per row)
          5) repush UPDATE...RETURNING
    """
    expired = expired or []
    degraded = degraded or []
    repushed = repushed or []

    # 全部 cursor 共享一个,但 fetchall 按顺序返
    fetch_results = [expired, degraded, repushed]
    fetch_idx = [0]

    def _fetchall():
        i = fetch_idx[0]
        fetch_idx[0] += 1
        return fetch_results[i] if i < len(fetch_results) else []

    cur = MagicMock()
    cur.fetchall.side_effect = _fetchall
    cur.execute = MagicMock()
    cur.__enter__ = lambda self: cur
    cur.__exit__ = lambda *a: None

    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


@pytest.mark.asyncio
async def test_scan_counts_all_three_categories():
    from agent.loops import hitl_timeout_loop as ht
    expired = [("appr-1", "dev-1", "strat-1", 100.0)]
    degraded = [("appr-2", "dev-2", "strat-2"), ("appr-3", "dev-3", "strat-3")]
    repushed = [("appr-4", "dev-4", "strat-4", 50.0)]
    conn = _mock_conn_with_results(expired, degraded, repushed)
    fake_local_db = MagicMock()
    fake_local_db._get_conn.return_value = conn

    with patch.dict(sys.modules, {"local_db": fake_local_db}):
        with patch(
            "agent.loops.hitl_timeout_loop._try_send_repush",
            new_callable=AsyncMock,
        ) as mock_push:
            counts = await ht.scan_and_escalate()

    assert counts["expired"] == 1
    assert counts["degraded"] == 2
    assert counts["repushed"] == 1
    assert mock_push.call_count == 1  # 一次推送


@pytest.mark.asyncio
async def test_scan_zero_when_all_empty():
    from agent.loops import hitl_timeout_loop as ht
    conn = _mock_conn_with_results([], [], [])
    fake_local_db = MagicMock()
    fake_local_db._get_conn.return_value = conn

    with patch.dict(sys.modules, {"local_db": fake_local_db}):
        with patch(
            "agent.loops.hitl_timeout_loop._try_send_repush",
            new_callable=AsyncMock,
        ):
            counts = await ht.scan_and_escalate()

    assert counts["expired"] == 0
    assert counts["degraded"] == 0
    assert counts["repushed"] == 0
    assert counts["errors"] == 0


@pytest.mark.asyncio
async def test_repush_failure_swallowed():
    """5min 重推失败不抛(push_resent_at 已写,下次 cron 不会重试)。"""
    from agent.loops import hitl_timeout_loop as ht
    repushed = [("appr-1", "dev-1", "strat-1", 50.0)]
    conn = _mock_conn_with_results([], [], repushed)
    fake_local_db = MagicMock()
    fake_local_db._get_conn.return_value = conn

    async def _failing_push(*args, **kwargs):
        raise RuntimeError("push service down")

    with patch.dict(sys.modules, {"local_db": fake_local_db}):
        # _try_send_repush 内部已 try/except,不会冒泡
        with patch(
            "agent.loops.hitl_timeout_loop.send_push", side_effect=_failing_push,
            create=True,
        ):
            counts = await ht.scan_and_escalate()
    assert counts["repushed"] == 1  # SQL UPDATE 算成功
    assert counts["errors"] == 0


# ── 时间常数 sanity check ────────────────────────────────────


def test_time_constants():
    from agent.loops import hitl_timeout_loop as ht
    assert ht.REPUSH_AFTER_MIN == 5
    assert ht.DEGRADE_AFTER_MIN == 15
    # 60min expire 由 expires_at 字段控制(创建时 set,T09 默认 5min 但可配 60)
