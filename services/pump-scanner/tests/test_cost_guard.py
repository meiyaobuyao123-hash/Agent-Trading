"""
Cost Guard 单元测试 — W3 D5+ autonomous-loop 续 15

跑法:python3 -m pytest tests/test_cost_guard.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import cost_guard as cg_mod  # noqa: E402
from agent.cost_guard import (  # noqa: E402
    CostGuard,
    DegradationLevel,
    LEVEL_THRESHOLDS,
    MODEL_DOWNGRADES,
    _level_for_pct,
    get_cost_guard,
    reset_for_test,
)


def _make_fake_pg_conn(cost_sum: float):
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = None
    cur.fetchone.return_value = (cost_sum,)
    return conn, cur


# ── _level_for_pct ──────────────────────────────────────────

def test_level_normal():
    assert _level_for_pct(0.0) == DegradationLevel.NORMAL
    assert _level_for_pct(0.69) == DegradationLevel.NORMAL


def test_level_soft_degrade():
    assert _level_for_pct(0.70) == DegradationLevel.SOFT_DEGRADE
    assert _level_for_pct(0.84) == DegradationLevel.SOFT_DEGRADE


def test_level_hard_degrade():
    assert _level_for_pct(0.85) == DegradationLevel.HARD_DEGRADE
    assert _level_for_pct(0.94) == DegradationLevel.HARD_DEGRADE


def test_level_emergency():
    assert _level_for_pct(0.95) == DegradationLevel.EMERGENCY
    assert _level_for_pct(0.99) == DegradationLevel.EMERGENCY


def test_level_hard_stop():
    assert _level_for_pct(1.00) == DegradationLevel.HARD_STOP
    assert _level_for_pct(1.49) == DegradationLevel.HARD_STOP


def test_level_blocked():
    assert _level_for_pct(1.50) == DegradationLevel.BLOCKED
    assert _level_for_pct(2.0) == DegradationLevel.BLOCKED


# ── refresh ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_calculates_pct_correctly():
    g = CostGuard()
    g.set_monthly_budget(1000.0)
    conn, cur = _make_fake_pg_conn(cost_sum=750.0)  # 75%
    with patch("local_db._get_conn", return_value=conn):
        s = await g.refresh(force=True)
    assert s.monthly_used_usd == 750.0
    assert s.pct == 0.75
    assert s.level == DegradationLevel.SOFT_DEGRADE


@pytest.mark.asyncio
async def test_refresh_cached_within_ttl():
    g = CostGuard()
    g.set_monthly_budget(1000.0)
    g._status.refreshed_at = __import__("time").time()  # 刚 refresh 过
    g._status.monthly_used_usd = 100
    conn, cur = _make_fake_pg_conn(cost_sum=999.0)  # 真值改变了但应该缓存命中
    with patch("local_db._get_conn", return_value=conn):
        s = await g.refresh(force=False)
    # 没真查 DB → status 不变
    assert s.monthly_used_usd == 100


@pytest.mark.asyncio
async def test_refresh_db_failure_keeps_old_status():
    g = CostGuard()
    g._status.monthly_used_usd = 500
    g._status.level = DegradationLevel.SOFT_DEGRADE
    with patch("local_db._get_conn", side_effect=Exception("PG down")):
        s = await g.refresh(force=True)
    # 不抛错,保持原状态
    assert s.monthly_used_usd == 500


# ── check_before_call ───────────────────────────────────────

@pytest.mark.asyncio
async def test_check_before_call_normal_passes():
    g = CostGuard()
    g.set_monthly_budget(1000.0)
    conn, cur = _make_fake_pg_conn(cost_sum=100.0)  # 10%
    with patch("local_db._get_conn", return_value=conn):
        allowed, model, reason = await g.check_before_call(
            intended_model="claude-opus-4-7", intended_level="L2",
        )
    assert allowed is True
    assert model == "claude-opus-4-7"
    assert "NORMAL" in reason


@pytest.mark.asyncio
async def test_check_before_call_soft_degrades_opus_to_sonnet():
    g = CostGuard()
    g.set_monthly_budget(1000.0)
    conn, cur = _make_fake_pg_conn(cost_sum=750.0)  # 75% SOFT
    with patch("local_db._get_conn", return_value=conn):
        allowed, model, reason = await g.check_before_call(
            intended_model="claude-opus-4-7", intended_level="L3",
        )
    assert allowed is True
    assert model == "claude-sonnet-4-6"
    assert "SOFT_DEGRADE" in reason


@pytest.mark.asyncio
async def test_check_before_call_hard_degrade_double_downgrade():
    """HARD_DEGRADE:opus → sonnet → haiku(双跳)。"""
    g = CostGuard()
    g.set_monthly_budget(1000.0)
    conn, cur = _make_fake_pg_conn(cost_sum=900.0)  # 90% HARD
    with patch("local_db._get_conn", return_value=conn):
        allowed, model, reason = await g.check_before_call(
            intended_model="claude-opus-4-7", intended_level="L3",
        )
    assert allowed is True
    assert "haiku" in model.lower()
    assert "HARD_DEGRADE" in reason


@pytest.mark.asyncio
async def test_check_before_call_emergency_blocks_l3():
    g = CostGuard()
    g.set_monthly_budget(1000.0)
    conn, cur = _make_fake_pg_conn(cost_sum=970.0)  # 97% EMERGENCY
    with patch("local_db._get_conn", return_value=conn):
        allowed, model, reason = await g.check_before_call(
            intended_model="claude-opus-4-7", intended_level="L3",
        )
    assert allowed is False
    assert "L3 disabled" in reason


@pytest.mark.asyncio
async def test_check_before_call_emergency_l2_forced_haiku():
    g = CostGuard()
    g.set_monthly_budget(1000.0)
    conn, cur = _make_fake_pg_conn(cost_sum=970.0)  # 97% EMERGENCY
    with patch("local_db._get_conn", return_value=conn):
        allowed, model, reason = await g.check_before_call(
            intended_model="claude-sonnet-4-6", intended_level="L2",
        )
    assert allowed is True
    assert "haiku" in model.lower()
    assert "EMERGENCY" in reason


@pytest.mark.asyncio
async def test_check_before_call_hard_stop_rejects():
    g = CostGuard()
    g.set_monthly_budget(1000.0)
    conn, cur = _make_fake_pg_conn(cost_sum=1100.0)  # 110% HARD_STOP
    with patch("local_db._get_conn", return_value=conn):
        allowed, model, reason = await g.check_before_call(
            intended_model="claude-haiku-4-5-20251001", intended_level="L1",
        )
    assert allowed is False
    assert "HARD_STOP" in reason


@pytest.mark.asyncio
async def test_check_before_call_blocked_rejects():
    g = CostGuard()
    g.set_monthly_budget(1000.0)
    conn, cur = _make_fake_pg_conn(cost_sum=1600.0)  # 160% BLOCKED
    with patch("local_db._get_conn", return_value=conn):
        allowed, model, reason = await g.check_before_call(
            intended_model="claude-haiku-4-5-20251001", intended_level="L1",
        )
    assert allowed is False
    assert "BLOCKED" in reason


@pytest.mark.asyncio
async def test_check_before_call_disabled_always_allows():
    g = CostGuard()
    g.disable()
    allowed, model, reason = await g.check_before_call(
        intended_model="claude-opus-4-7", intended_level="L3",
    )
    assert allowed is True
    assert model == "claude-opus-4-7"
    assert "disabled" in reason


# ── model_for ───────────────────────────────────────────────

def test_model_for_normal_keeps():
    g = CostGuard()
    g._status.level = DegradationLevel.NORMAL
    assert g.model_for("claude-opus-4-7") == "claude-opus-4-7"


def test_model_for_soft_degrades():
    g = CostGuard()
    g._status.level = DegradationLevel.SOFT_DEGRADE
    assert g.model_for("claude-opus-4-7") == "claude-sonnet-4-6"


def test_model_for_emergency_returns_haiku():
    g = CostGuard()
    g._status.level = DegradationLevel.EMERGENCY
    assert g.model_for("claude-sonnet-4-6") == "claude-haiku-4-5-20251001"


def test_model_for_hard_stop_raises():
    g = CostGuard()
    g._status.level = DegradationLevel.HARD_STOP
    g._status.pct = 1.10
    with pytest.raises(RuntimeError):
        g.model_for("claude-haiku-4-5-20251001")


# ── can_chat / can_run_l3 ───────────────────────────────────

def test_can_chat_blocked_at_hard_stop():
    g = CostGuard()
    g._status.level = DegradationLevel.HARD_STOP
    assert g.can_chat() is False


def test_can_chat_normal_allows():
    g = CostGuard()
    g._status.level = DegradationLevel.NORMAL
    assert g.can_chat() is True


def test_can_run_l3_blocked_at_emergency():
    g = CostGuard()
    g._status.level = DegradationLevel.EMERGENCY
    assert g.can_run_l3() is False


def test_can_run_l3_hard_degrade_still_allows():
    g = CostGuard()
    g._status.level = DegradationLevel.HARD_DEGRADE
    assert g.can_run_l3() is True


# ── singleton ──────────────────────────────────────────────

def test_get_cost_guard_singleton():
    reset_for_test()
    a = get_cost_guard()
    b = get_cost_guard()
    assert a is b


# ── MODEL_DOWNGRADES ────────────────────────────────────────

def test_model_downgrades_chain():
    """opus → sonnet → haiku;haiku 不再降。"""
    sonnet = MODEL_DOWNGRADES.get("claude-opus-4-7")
    assert "sonnet" in sonnet
    haiku = MODEL_DOWNGRADES.get(sonnet)
    assert "haiku" in haiku
    assert "claude-haiku-4-5-20251001" not in MODEL_DOWNGRADES


# ── LEVEL_THRESHOLDS sanity ─────────────────────────────────

def test_level_thresholds_monotonic():
    """阈值必须单调递增。"""
    th = LEVEL_THRESHOLDS
    assert th["SOFT_DEGRADE"] < th["HARD_DEGRADE"] < th["EMERGENCY"] < th["HARD_STOP"] < th["BLOCKED"]
