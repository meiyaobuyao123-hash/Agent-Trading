"""
Reflect Loop 单元测试 — W3 D5+ autonomous-loop 续 10

跑法:python3 -m pytest tests/test_reflect_loop.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loops import reflect_loop  # noqa: E402
from agent.loops.reflect_loop import (  # noqa: E402
    ReflectLoop,
    ReflectResult,
    get_reflect_loop,
    reset_loop_for_test,
)


# ── _aggregate_compliance_samples ───────────────────────────

def test_aggregate_chain_match_comply():
    loop = ReflectLoop()
    trades = [
        {"chain": "SOL", "pnl_pct": 5.0, "regime": "BREAKOUT"},
        {"chain": "SOL", "pnl_pct": 8.0, "regime": "TRENDING_UP"},
        {"chain": "ETH", "pnl_pct": -3.0, "regime": "RANGING"},
    ]
    comply, violate, regimes = loop._aggregate_compliance_samples(
        rule_condition="chain=SOL AND score>70",
        trades=trades,
    )
    assert comply == [5.0, 8.0]
    assert violate == [-3.0]
    assert "BREAKOUT" in regimes


def test_aggregate_skips_none_pnl():
    """pnl_pct=None(开仓未平)→ 跳过。"""
    loop = ReflectLoop()
    trades = [
        {"chain": "SOL", "pnl_pct": 5.0},
        {"chain": "SOL", "pnl_pct": None},
        {"chain": "ETH", "pnl_pct": -2.0},
    ]
    comply, violate, _ = loop._aggregate_compliance_samples(
        "chain=SOL", trades=trades,
    )
    assert comply == [5.0]
    assert violate == [-2.0]


def test_aggregate_no_chain_match_all_violate():
    loop = ReflectLoop()
    trades = [{"chain": "BSC", "pnl_pct": 1.0}]
    comply, violate, _ = loop._aggregate_compliance_samples("chain=SOL", trades)
    assert comply == []
    assert violate == [1.0]


# ── run_cycle: emergency path ───────────────────────────────

@pytest.mark.asyncio
async def test_run_cycle_emergency_threshold_not_met():
    loop = ReflectLoop()
    fake_mem = MagicMock()
    fake_mem.reflection.should_emergency_reflect.return_value = False
    with patch("agent.memory.get_memory_manager", return_value=fake_mem):
        r = await loop.run_cycle(
            trigger="emergency",
            emergency_pnl_pct=-5.0,  # 没到 -25
            emergency_amount_usd=100.0,
        )
    assert r.ok is False
    assert "emergency_threshold_not_met" in (r.error or "")


@pytest.mark.asyncio
async def test_run_cycle_emergency_threshold_met_proceeds():
    loop = ReflectLoop()
    fake_mem = MagicMock()
    fake_mem.reflection.should_emergency_reflect.return_value = True
    fake_mem.reflection.run_reflection = AsyncMock(return_value={
        "winning_pattern": "x", "losing_pattern": "y", "new_rules": [],
    })
    fake_mem.semantic.get_all_active.return_value = []
    fake_mem.reflection.deduplicate_proposed_rules.return_value = []
    fake_mem.episodic.add.return_value = "ref-1"
    with patch("agent.memory.get_memory_manager", return_value=fake_mem), \
         patch.object(loop, "_gather_recent_trades",
                      AsyncMock(return_value=[{"chain": "SOL", "pnl_pct": -30}])):
        r = await loop.run_cycle(
            trigger="emergency",
            emergency_pnl_pct=-30.0,
            emergency_amount_usd=100.0,
        )
    assert r.ok is True
    assert r.trigger == "emergency"


# ── run_cycle: no trades ────────────────────────────────────

@pytest.mark.asyncio
async def test_run_cycle_no_trades_returns_ok_with_message():
    loop = ReflectLoop()
    fake_mem = MagicMock()
    with patch("agent.memory.get_memory_manager", return_value=fake_mem), \
         patch.object(loop, "_gather_recent_trades",
                      AsyncMock(return_value=[])):
        r = await loop.run_cycle(trigger="daily")
    assert r.ok is True
    assert "no_trades" in (r.error or "")
    assert r.trades_analyzed == 0


# ── run_cycle: LLM failure ──────────────────────────────────

@pytest.mark.asyncio
async def test_run_cycle_llm_returns_none_marks_failed():
    loop = ReflectLoop()
    fake_mem = MagicMock()
    fake_mem.semantic.get_all_active.return_value = []
    fake_mem.reflection.run_reflection = AsyncMock(return_value=None)
    with patch("agent.memory.get_memory_manager", return_value=fake_mem), \
         patch.object(loop, "_gather_recent_trades",
                      AsyncMock(return_value=[{"chain": "SOL", "pnl_pct": 5.0}])):
        r = await loop.run_cycle(trigger="daily")
    assert r.ok is False
    assert r.error == "reflection_returned_none"


@pytest.mark.asyncio
async def test_run_cycle_llm_exception_marks_failed():
    loop = ReflectLoop()
    fake_mem = MagicMock()
    fake_mem.semantic.get_all_active.return_value = []
    fake_mem.reflection.run_reflection = AsyncMock(side_effect=Exception("API timeout"))
    with patch("agent.memory.get_memory_manager", return_value=fake_mem), \
         patch.object(loop, "_gather_recent_trades",
                      AsyncMock(return_value=[{"chain": "SOL", "pnl_pct": 5.0}])):
        r = await loop.run_cycle(trigger="daily")
    assert r.ok is False
    assert "llm_failed" in (r.error or "")


# ── run_cycle: full flow with promotion ────────────────────

@pytest.mark.asyncio
async def test_run_cycle_promotes_when_gates_pass():
    loop = ReflectLoop()
    fake_mem = MagicMock()
    fake_mem.semantic.get_all_active.return_value = []
    fake_mem.reflection.run_reflection = AsyncMock(return_value={
        "winning_pattern": "SOL 跟单胜",
        "losing_pattern": "BC<5 死",
        "new_rules": [
            {"condition": "chain=SOL", "action": "buy",
             "evidence": "10 笔 SOL 全胜"},
        ],
    })
    fake_mem.reflection.deduplicate_proposed_rules.return_value = [
        {"condition": "chain=SOL", "action": "buy",
         "evidence": "10 笔 SOL 全胜"},
    ]
    # 5 条门槛全过
    fake_mem.semantic.try_promote_strict.return_value = {
        "ok": True, "promoted_rule_id": "r-100",
        "shadow_mode_until": "2026-05-15",
    }
    fake_mem.episodic.add.return_value = "ref-x"

    # 25 笔 SOL trade(都 comply 因为 condition=chain=SOL)
    trades = [{"chain": "SOL", "pnl_pct": 5.0, "regime": "TRENDING_UP" if i < 12 else "BREAKOUT"}
              for i in range(25)]

    with patch("agent.memory.get_memory_manager", return_value=fake_mem), \
         patch.object(loop, "_gather_recent_trades",
                      AsyncMock(return_value=trades)):
        r = await loop.run_cycle(trigger="daily")

    assert r.ok is True
    assert r.new_rules_proposed == 1
    assert r.promoted == 1
    assert "r-100" in r.promoted_rule_ids
    fake_mem.semantic.try_promote_strict.assert_called_once()


@pytest.mark.asyncio
async def test_run_cycle_dedupe_skips_duplicates():
    loop = ReflectLoop()
    fake_mem = MagicMock()
    fake_mem.semantic.get_all_active.return_value = [
        {"id": "r-existing", "structured_data": {"condition": "X", "action": "skip"}},
    ]
    fake_mem.reflection.run_reflection = AsyncMock(return_value={
        "winning_pattern": "x", "losing_pattern": "y",
        "new_rules": [
            {"condition": "X", "action": "skip"},  # 与 existing 重复
            {"condition": "Y", "action": "buy"},
        ],
    })
    # 假设 dedupe 留下 1 条(Y),X 被吃掉
    fake_mem.reflection.deduplicate_proposed_rules.return_value = [
        {"condition": "Y", "action": "buy"},
    ]
    fake_mem.semantic.try_promote_strict.return_value = {"ok": False, "reason": "FAILED gates: x"}
    fake_mem.episodic.add.return_value = "e-1"

    with patch("agent.memory.get_memory_manager", return_value=fake_mem), \
         patch.object(loop, "_gather_recent_trades",
                      AsyncMock(return_value=[{"chain": "SOL", "pnl_pct": 1.0}])):
        r = await loop.run_cycle(trigger="daily")

    assert r.dedupe_skipped == 1   # 2 new - 1 kept
    assert r.gate_blocked == 1     # try_promote returns ok=False


@pytest.mark.asyncio
async def test_run_cycle_gate_blocked_writes_episodic():
    """try_promote_strict 失败时写 episodic 留底。"""
    loop = ReflectLoop()
    fake_mem = MagicMock()
    fake_mem.semantic.get_all_active.return_value = []
    fake_mem.reflection.run_reflection = AsyncMock(return_value={
        "new_rules": [{"condition": "z", "action": "buy", "evidence": "..."}],
    })
    fake_mem.reflection.deduplicate_proposed_rules.return_value = [
        {"condition": "z", "action": "buy", "evidence": "..."},
    ]
    fake_mem.semantic.try_promote_strict.return_value = {
        "ok": False, "reason": "FAILED gates: sample_size",
    }
    fake_mem.episodic.add.return_value = "e-1"
    with patch("agent.memory.get_memory_manager", return_value=fake_mem), \
         patch.object(loop, "_gather_recent_trades",
                      AsyncMock(return_value=[{"chain": "SOL", "pnl_pct": 5.0}])):
        r = await loop.run_cycle(trigger="daily")
    assert r.gate_blocked == 1
    # episodic.add 至少调过 2 次:一次 reflection_proposal + 一次 reflection_summary
    assert fake_mem.episodic.add.call_count >= 2


# ── count trigger resets counter ─────────────────────────────

@pytest.mark.asyncio
async def test_run_cycle_count_resets_counter():
    loop = ReflectLoop()
    fake_mem = MagicMock()
    fake_mem.semantic.get_all_active.return_value = []
    fake_mem.reflection.run_reflection = AsyncMock(return_value={"new_rules": []})
    fake_mem.reflection.deduplicate_proposed_rules.return_value = []
    fake_mem.episodic.add.return_value = "e-1"

    with patch("agent.memory.get_memory_manager", return_value=fake_mem), \
         patch.object(loop, "_gather_recent_trades",
                      AsyncMock(return_value=[{"chain": "SOL", "pnl_pct": 1.0}])):
        await loop.run_cycle(trigger="count")
    fake_mem.reflection.reset_trade_count.assert_called_once()


# ── singleton ───────────────────────────────────────────────

def test_get_reflect_loop_singleton():
    reset_loop_for_test()
    a = get_reflect_loop()
    b = get_reflect_loop()
    assert a is b
