"""
Scout Loop 单元测试 — W3 D5+ autonomous-loop 续 12

跑法:python3 -m pytest tests/test_scout_loop.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loops import scout_loop  # noqa: E402
from agent.loops.scout_loop import (  # noqa: E402
    ScoutLoop,
    ScoutResult,
    get_scout_loop,
    reset_loop_for_test,
)


def _signal(score=80, chain="SOL"):
    return {
        "address": "0xabc",
        "symbol": "TRUMP",
        "chain": chain,
        "score": score,
        "price_usd": 1.0,
        "liquidity_usd": 100000,
    }


def _trigger_event(strategy_id="s-1", strategy_name="S1"):
    """构造 StrategyTriggeredEvent 兼容 dict-like mock。"""
    ev = MagicMock()
    ev.strategy_id = strategy_id
    ev.user_id = "00000000-0000-0000-0000-000000000001"
    ev.strategy_name = strategy_name
    ev.matched_token = "0xabc"
    ev.matched_chain = "SOL"
    ev.token_name = "TRUMP"
    ev.trigger_context = {}
    ev.model_dump = lambda: {
        "strategy_id": strategy_id,
        "user_id": "00000000-0000-0000-0000-000000000001",
        "strategy_name": strategy_name,
        "matched_token": "0xabc",
        "matched_chain": "SOL",
        "token_name": "TRUMP",
        "trigger_context": {},
    }
    return ev


def _notify_result(verdict="executed_paper", position_usd=50.0):
    """构造 NotifyResult mock。"""
    nr = MagicMock()
    nr.ok = True
    nr.verdict = verdict
    nr.position_usd = position_usd
    nr.approval_id = None
    nr.push_sent_count = 1
    nr.reason = None
    return nr


# ── DataEvent build failure ─────────────────────────────────

@pytest.mark.asyncio
async def test_process_invalid_payload_returns_error():
    loop = ScoutLoop()
    # 让 DataEvent import 失败(模拟 schema 异常)
    with patch("agent.schemas.DataEvent", side_effect=Exception("schema corrupt")):
        r = await loop.process(signal_payload={"x": 1}, source="hot_coin")
    assert r.ok is False
    assert "data_event_build_failed" in (r.error or "")


# ── No active strategies ────────────────────────────────────

@pytest.mark.asyncio
async def test_process_no_active_strategies_returns_zero():
    loop = ScoutLoop()
    fake_mgr = MagicMock()
    fake_mgr.get_active_strategies.return_value = []
    fake_evaluator = MagicMock()
    fake_evaluator.evaluate.return_value = []
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr), \
         patch("agent.evaluator.StrategyEvaluator", return_value=fake_evaluator):
        r = await loop.process(_signal(), source="hot_coin")
    assert r.ok is True
    assert r.strategies_evaluated == 0
    assert r.triggered == 0
    assert r.dispatched == 0


# ── Strategies but no triggers ──────────────────────────────

@pytest.mark.asyncio
async def test_process_no_triggers_returns_evaluated_count():
    loop = ScoutLoop()
    fake_mgr = MagicMock()
    fake_mgr.get_active_strategies.return_value = [
        {"id": "s-1", "name": "x", "mode": "paper"},
        {"id": "s-2", "name": "y", "mode": "notify"},
    ]
    fake_evaluator = MagicMock()
    fake_evaluator.evaluate.return_value = []
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr), \
         patch("agent.evaluator.StrategyEvaluator", return_value=fake_evaluator):
        r = await loop.process(_signal(), source="hot_coin")
    assert r.strategies_evaluated == 2
    assert r.triggered == 0
    assert r.dispatched == 0


# ── Triggered → dispatched to NotifyLoop ────────────────────

@pytest.mark.asyncio
async def test_process_dispatches_to_notify_loop():
    reset_loop_for_test()
    loop = ScoutLoop()
    fake_mgr = MagicMock()
    fake_mgr.get_active_strategies.return_value = [
        {"id": "s-1", "name": "S1", "mode": "paper"},
    ]
    fake_mgr.check_daily_limit.return_value = True
    fake_mgr.get_strategy.return_value = {"id": "s-1", "mode": "paper"}
    fake_evaluator = MagicMock()
    fake_evaluator.evaluate.return_value = [_trigger_event("s-1")]

    fake_notify = MagicMock()
    fake_notify.process = AsyncMock(return_value=_notify_result("executed_paper", 50))

    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr), \
         patch("agent.evaluator.StrategyEvaluator", return_value=fake_evaluator), \
         patch("agent.loops.notify_loop.get_notify_loop", return_value=fake_notify):
        r = await loop.process(_signal(), source="hot_coin")
    assert r.triggered == 1
    assert r.dispatched == 1
    assert r.notify_results[0]["verdict"] == "executed_paper"
    assert r.notify_results[0]["position_usd"] == 50
    fake_mgr.record_trigger.assert_called_with("s-1")


# ── Daily limit skip ────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_skips_when_daily_limit_reached():
    loop = ScoutLoop()
    fake_mgr = MagicMock()
    fake_mgr.get_active_strategies.return_value = [
        {"id": "s-1", "mode": "paper"}, {"id": "s-2", "mode": "paper"},
    ]
    fake_mgr.check_daily_limit.side_effect = lambda sid: sid != "s-1"  # s-1 限额
    fake_mgr.get_strategy.return_value = {"id": "s-2", "mode": "paper"}
    fake_evaluator = MagicMock()
    fake_evaluator.evaluate.return_value = [
        _trigger_event("s-1"), _trigger_event("s-2"),
    ]
    fake_notify = MagicMock()
    fake_notify.process = AsyncMock(return_value=_notify_result())
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr), \
         patch("agent.evaluator.StrategyEvaluator", return_value=fake_evaluator), \
         patch("agent.loops.notify_loop.get_notify_loop", return_value=fake_notify):
        r = await loop.process(_signal(), source="hot_coin")
    assert r.triggered == 2
    assert r.dispatched == 1
    assert r.skipped_daily_limit == 1


# ── max_dispatch cap ────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_respects_max_dispatch():
    loop = ScoutLoop()
    fake_mgr = MagicMock()
    fake_mgr.get_active_strategies.return_value = [
        {"id": f"s-{i}", "mode": "paper"} for i in range(10)
    ]
    fake_mgr.check_daily_limit.return_value = True
    fake_mgr.get_strategy.side_effect = lambda sid: {"id": sid, "mode": "paper"}
    fake_evaluator = MagicMock()
    fake_evaluator.evaluate.return_value = [_trigger_event(f"s-{i}") for i in range(10)]
    fake_notify = MagicMock()
    fake_notify.process = AsyncMock(return_value=_notify_result())
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr), \
         patch("agent.evaluator.StrategyEvaluator", return_value=fake_evaluator), \
         patch("agent.loops.notify_loop.get_notify_loop", return_value=fake_notify):
        r = await loop.process(_signal(), source="hot_coin", max_dispatch=3)
    assert r.triggered == 10  # evaluator 找到 10 条
    assert r.dispatched == 3   # 但只 dispatch 3 条
    assert len(r.notify_results) == 3


# ── mode_override ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_mode_override_applied():
    loop = ScoutLoop()
    fake_mgr = MagicMock()
    fake_mgr.get_active_strategies.return_value = [
        {"id": "s-1", "mode": "paper"},
    ]
    fake_mgr.check_daily_limit.return_value = True
    fake_evaluator = MagicMock()
    fake_evaluator.evaluate.return_value = [_trigger_event("s-1")]
    fake_notify = MagicMock()
    fake_notify.process = AsyncMock(return_value=_notify_result("notify_only"))
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr), \
         patch("agent.evaluator.StrategyEvaluator", return_value=fake_evaluator), \
         patch("agent.loops.notify_loop.get_notify_loop", return_value=fake_notify):
        r = await loop.process(_signal(), source="hot_coin", mode_override="notify")
    # 验证 notify.process 被传 mode='notify'
    call_kwargs = fake_notify.process.call_args.kwargs
    assert call_kwargs.get("mode") == "notify"


# ── dry_run propagates ──────────────────────────────────────

@pytest.mark.asyncio
async def test_process_dry_run_propagates_to_notify():
    loop = ScoutLoop()
    fake_mgr = MagicMock()
    fake_mgr.get_active_strategies.return_value = [{"id": "s-1", "mode": "paper"}]
    fake_mgr.check_daily_limit.return_value = True
    fake_mgr.get_strategy.return_value = {"id": "s-1", "mode": "paper"}
    fake_evaluator = MagicMock()
    fake_evaluator.evaluate.return_value = [_trigger_event("s-1")]
    fake_notify = MagicMock()
    fake_notify.process = AsyncMock(return_value=_notify_result("dry_run"))
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr), \
         patch("agent.evaluator.StrategyEvaluator", return_value=fake_evaluator), \
         patch("agent.loops.notify_loop.get_notify_loop", return_value=fake_notify):
        r = await loop.process(_signal(), source="hot_coin", dry_run=True)
    call_kwargs = fake_notify.process.call_args.kwargs
    assert call_kwargs.get("dry_run") is True
    # dry_run 时 record_trigger 不应被调
    fake_mgr.record_trigger.assert_not_called()


# ── Notify dispatch failure recorded but not aborts ─────────

@pytest.mark.asyncio
async def test_process_notify_failure_recorded_continue():
    loop = ScoutLoop()
    fake_mgr = MagicMock()
    fake_mgr.get_active_strategies.return_value = [
        {"id": "s-1", "mode": "paper"}, {"id": "s-2", "mode": "paper"},
    ]
    fake_mgr.check_daily_limit.return_value = True
    fake_mgr.get_strategy.side_effect = lambda sid: {"id": sid, "mode": "paper"}
    fake_evaluator = MagicMock()
    fake_evaluator.evaluate.return_value = [
        _trigger_event("s-1"), _trigger_event("s-2"),
    ]

    fake_notify = MagicMock()
    fake_notify.process = AsyncMock(side_effect=[
        Exception("notify s-1 crashed"),
        _notify_result("executed_paper"),
    ])
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr), \
         patch("agent.evaluator.StrategyEvaluator", return_value=fake_evaluator), \
         patch("agent.loops.notify_loop.get_notify_loop", return_value=fake_notify):
        r = await loop.process(_signal(), source="hot_coin")
    # 第 1 条出错 → 记录 error;第 2 条成功 → executed_paper
    assert len(r.notify_results) == 2
    assert r.notify_results[0]["verdict"] == "error"
    assert r.notify_results[1]["verdict"] == "executed_paper"
    # dispatched 只算成功的
    assert r.dispatched == 1


# ── Evaluator failure marks failed ──────────────────────────

@pytest.mark.asyncio
async def test_process_evaluator_failure():
    loop = ScoutLoop()
    fake_mgr = MagicMock()
    fake_mgr.get_active_strategies.return_value = [{"id": "s-1", "mode": "paper"}]
    fake_evaluator = MagicMock()
    fake_evaluator.evaluate.side_effect = Exception("rule_engine crash")
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr), \
         patch("agent.evaluator.StrategyEvaluator", return_value=fake_evaluator):
        r = await loop.process(_signal(), source="hot_coin")
    assert r.ok is False
    assert "evaluator_failed" in (r.error or "")
    assert r.strategies_evaluated == 1


# ── trigger_context contains signal payload ─────────────────

@pytest.mark.asyncio
async def test_process_attaches_signal_payload_to_trigger_context():
    """ScoutLoop 应该把 signal_payload 注入 trigger_context.token_data,
    让下游 NotifyLoop / Thesis 拿到上下文。"""
    loop = ScoutLoop()
    fake_mgr = MagicMock()
    fake_mgr.get_active_strategies.return_value = [{"id": "s-1", "mode": "paper"}]
    fake_mgr.check_daily_limit.return_value = True
    fake_mgr.get_strategy.return_value = {"id": "s-1", "mode": "paper"}
    fake_evaluator = MagicMock()
    fake_evaluator.evaluate.return_value = [_trigger_event("s-1")]
    fake_notify = MagicMock()
    fake_notify.process = AsyncMock(return_value=_notify_result())
    payload = _signal(score=85)
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr), \
         patch("agent.evaluator.StrategyEvaluator", return_value=fake_evaluator), \
         patch("agent.loops.notify_loop.get_notify_loop", return_value=fake_notify):
        await loop.process(payload, source="hot_coin")
    call_kwargs = fake_notify.process.call_args.kwargs
    event_passed = call_kwargs.get("event")
    assert event_passed is not None
    ctx = event_passed.get("trigger_context") or {}
    assert ctx.get("token_data") == payload


# ── singleton ──────────────────────────────────────────────

def test_get_scout_loop_singleton():
    reset_loop_for_test()
    a = get_scout_loop()
    b = get_scout_loop()
    assert a is b
