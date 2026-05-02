"""
Notify Loop 单元测试 — W3 D5+ autonomous-loop 续 11

跑法:python3 -m pytest tests/test_notify_loop.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loops import notify_loop  # noqa: E402
from agent.loops.notify_loop import (  # noqa: E402
    HITL_24H_TRADES,
    HITL_AMOUNT_USD,
    HITL_LOW_CONVICTION,
    HITL_PORTFOLIO_PCT,
    NotifyLoop,
    NotifyResult,
    get_notify_loop,
    reset_loop_for_test,
)


def _event(strategy_id="s-1", mode_hint=None, amount_hint=None):
    return {
        "strategy_id": strategy_id,
        "user_id": "00000000-0000-0000-0000-000000000001",
        "strategy_name": "Test Strat",
        "matched_token": "0xabc",
        "matched_chain": "SOL",
        "token_name": "TRUMP",
        "trigger_context": {
            "token_data": {"address": "0xabc", "symbol": "TRUMP",
                           "price_usd": 1.0, "chain": "SOL"},
            "sl_pct": -10, "tp_pct": 30,
        },
    }


# ── _needs_hitl ─────────────────────────────────────────────

def test_needs_hitl_no_triggers_returns_false():
    loop = NotifyLoop()
    needed, reasons = loop._needs_hitl(
        position_usd=50, portfolio_pct_in_chain=0.10,
        recent_trades_24h=2, thesis={"conviction": 0.8},
    )
    assert needed is False
    assert reasons == []


def test_needs_hitl_high_amount():
    loop = NotifyLoop()
    needed, reasons = loop._needs_hitl(
        position_usd=HITL_AMOUNT_USD + 10, portfolio_pct_in_chain=0,
        recent_trades_24h=0, thesis=None,
    )
    assert needed is True
    assert any("amount" in r for r in reasons)


def test_needs_hitl_high_concentration():
    loop = NotifyLoop()
    needed, reasons = loop._needs_hitl(
        position_usd=10, portfolio_pct_in_chain=HITL_PORTFOLIO_PCT + 0.05,
        recent_trades_24h=0, thesis=None,
    )
    assert needed is True
    assert any("portfolio" in r for r in reasons)


def test_needs_hitl_overtrade():
    loop = NotifyLoop()
    needed, reasons = loop._needs_hitl(
        position_usd=10, portfolio_pct_in_chain=0,
        recent_trades_24h=HITL_24H_TRADES + 1, thesis=None,
    )
    assert needed is True
    assert any("24h_trades" in r for r in reasons)


def test_needs_hitl_low_conviction():
    loop = NotifyLoop()
    needed, reasons = loop._needs_hitl(
        position_usd=10, portfolio_pct_in_chain=0,
        recent_trades_24h=0,
        thesis={"conviction": HITL_LOW_CONVICTION - 0.1},
    )
    assert needed is True
    assert any("conviction" in r for r in reasons)


def test_needs_hitl_multiple_triggers():
    loop = NotifyLoop()
    needed, reasons = loop._needs_hitl(
        position_usd=HITL_AMOUNT_USD + 10,
        portfolio_pct_in_chain=HITL_PORTFOLIO_PCT + 0.05,
        recent_trades_24h=HITL_24H_TRADES + 1,
        thesis={"conviction": 0.3},
    )
    assert needed is True
    assert len(reasons) == 4  # 全部 4 条命中


# ── _safety_pre_check ───────────────────────────────────────

def test_safety_pre_check_globally_blocked():
    loop = NotifyLoop()
    fake_engine = MagicMock()
    fake_engine.is_globally_blocked.return_value = True
    fake_engine.active_breakers = {"CB07": object()}
    with patch("agent.safety_engine.get_safety_engine", return_value=fake_engine):
        ok, reason, meta = loop._safety_pre_check(_event(), "paper")
    assert ok is False
    assert reason == "safety_globally_blocked"


def test_safety_pre_check_normal_passes():
    loop = NotifyLoop()
    fake_engine = MagicMock()
    fake_engine.is_globally_blocked.return_value = False
    with patch("agent.safety_engine.get_safety_engine", return_value=fake_engine):
        ok, reason, meta = loop._safety_pre_check(_event(), "paper")
    assert ok is True
    assert reason is None


def test_safety_pre_check_engine_unavailable_passes():
    loop = NotifyLoop()
    with patch("agent.safety_engine.get_safety_engine", side_effect=Exception("import")):
        ok, _, _ = loop._safety_pre_check(_event(), "paper")
    assert ok is True  # fail-open


# ── process: invalid mode ───────────────────────────────────

@pytest.mark.asyncio
async def test_process_invalid_mode():
    loop = NotifyLoop()
    r = await loop.process(_event(), mode="ghost")
    assert r.ok is False
    assert "invalid_mode" in (r.reason or "")


# ── process: paper happy path ───────────────────────────────

@pytest.mark.asyncio
async def test_process_paper_executes_t07():
    reset_loop_for_test()
    loop = NotifyLoop()

    fake_engine = MagicMock()
    fake_engine.is_globally_blocked.return_value = False

    fake_risk = MagicMock()
    risk_result = MagicMock()
    risk_result.passed = True
    fake_risk.check_trade.return_value = risk_result

    fake_t17 = MagicMock()
    t17_result = MagicMock()
    t17_result.ok = True
    t17_result.output = {"position_usd": 50.0, "capped_by": [], "reasoning": "ok"}
    fake_t17.run = AsyncMock(return_value=t17_result)

    fake_t07 = MagicMock()
    t07_result = MagicMock()
    t07_result.ok = True
    t07_result.output = {"trade": {"id": "trade-1", "amount_usd": 50}}
    fake_t07.run = AsyncMock(return_value=t07_result)

    fake_t13 = MagicMock()
    t13_result = MagicMock()
    t13_result.ok = True
    t13_result.output = {"sent_count": 1, "deep_link": "aitrading://strategy/s-1"}
    fake_t13.run = AsyncMock(return_value=t13_result)

    with patch("agent.safety_engine.get_safety_engine", return_value=fake_engine), \
         patch("agent.risk_manager.RiskManager", return_value=fake_risk), \
         patch("agent.tools.CalcPositionSizeTool", return_value=fake_t17), \
         patch("agent.tools.RunPaperTradeTool", return_value=fake_t07), \
         patch("agent.tools.SendPushNotificationTool", return_value=fake_t13):
        r = await loop.process(_event(), mode="paper")

    assert r.ok is True
    assert r.verdict == "executed_paper"
    assert r.position_usd == 50.0
    assert r.paper_trade is not None
    assert r.push_sent_count == 1
    fake_t07.run.assert_called_once()
    fake_t13.run.assert_called_once()


# ── safety blocked ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_safety_blocked_pushes_blocked_notice():
    loop = NotifyLoop()
    fake_engine = MagicMock()
    fake_engine.is_globally_blocked.return_value = True
    fake_engine.active_breakers = {}

    fake_t13 = MagicMock()
    t13_result = MagicMock()
    t13_result.ok = True
    t13_result.output = {"sent_count": 1, "deep_link": "aitrading://home"}
    fake_t13.run = AsyncMock(return_value=t13_result)

    with patch("agent.safety_engine.get_safety_engine", return_value=fake_engine), \
         patch("agent.tools.SendPushNotificationTool", return_value=fake_t13):
        r = await loop.process(_event(), mode="paper")
    assert r.verdict == "blocked_safety"
    assert r.push_sent_count == 1


# ── risk blocked ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_risk_blocked():
    loop = NotifyLoop()
    fake_engine = MagicMock()
    fake_engine.is_globally_blocked.return_value = False

    fake_risk = MagicMock()
    risk_blocked = MagicMock()
    risk_blocked.passed = False
    risk_blocked.reason = "[liquidity] liquidity 8000 < 10000"
    fake_risk.check_trade.return_value = risk_blocked

    fake_t13 = MagicMock()
    t13_result = MagicMock()
    t13_result.ok = True
    t13_result.output = {"sent_count": 0, "deep_link": "aitrading://home"}
    fake_t13.run = AsyncMock(return_value=t13_result)

    with patch("agent.safety_engine.get_safety_engine", return_value=fake_engine), \
         patch("agent.risk_manager.RiskManager", return_value=fake_risk), \
         patch("agent.tools.SendPushNotificationTool", return_value=fake_t13):
        r = await loop.process(_event(), mode="paper")
    assert r.verdict == "blocked_risk"
    assert "liquidity" in (r.reason or "")


# ── notify mode: no trade just push ─────────────────────────

@pytest.mark.asyncio
async def test_process_notify_only_no_t07_called():
    loop = NotifyLoop()
    fake_engine = MagicMock()
    fake_engine.is_globally_blocked.return_value = False
    fake_risk = MagicMock()
    risk_result = MagicMock(); risk_result.passed = True
    fake_risk.check_trade.return_value = risk_result

    fake_t17 = MagicMock()
    t17_result = MagicMock()
    t17_result.ok = True
    t17_result.output = {"position_usd": 80.0, "capped_by": [], "reasoning": "ok"}
    fake_t17.run = AsyncMock(return_value=t17_result)

    fake_t07_class = MagicMock(side_effect=AssertionError("T07 should NOT be called for notify-only"))

    fake_t13 = MagicMock()
    t13_result = MagicMock()
    t13_result.ok = True
    t13_result.output = {"sent_count": 1, "deep_link": "aitrading://strategy/s-1"}
    fake_t13.run = AsyncMock(return_value=t13_result)

    with patch("agent.safety_engine.get_safety_engine", return_value=fake_engine), \
         patch("agent.risk_manager.RiskManager", return_value=fake_risk), \
         patch("agent.tools.CalcPositionSizeTool", return_value=fake_t17), \
         patch("agent.tools.RunPaperTradeTool", fake_t07_class), \
         patch("agent.tools.SendPushNotificationTool", return_value=fake_t13):
        r = await loop.process(_event(), mode="notify")
    assert r.verdict == "notify_only"
    assert r.position_usd == 80.0
    assert r.push_sent_count == 1


# ── auto + HITL needed → T09 approval ───────────────────────

@pytest.mark.asyncio
async def test_process_auto_with_hitl_creates_approval():
    loop = NotifyLoop()
    fake_engine = MagicMock()
    fake_engine.is_globally_blocked.return_value = False
    fake_risk = MagicMock()
    risk_result = MagicMock(); risk_result.passed = True
    fake_risk.check_trade.return_value = risk_result

    fake_t17 = MagicMock()
    t17_result = MagicMock()
    t17_result.ok = True
    # 高金额 → 触发 HITL
    t17_result.output = {"position_usd": 300.0, "capped_by": [], "reasoning": "ok"}
    fake_t17.run = AsyncMock(return_value=t17_result)

    fake_t09 = MagicMock()
    t09_result = MagicMock()
    t09_result.ok = True
    t09_result.output = {"approval_id": "appr-uuid", "idempotent_hit": False,
                          "expires_at": "2026-05-02T12:00:00Z"}
    fake_t09.run = AsyncMock(return_value=t09_result)

    fake_t13 = MagicMock()
    t13_result = MagicMock()
    t13_result.ok = True
    t13_result.output = {"sent_count": 1, "deep_link": "aitrading://hitl/appr-uuid"}
    fake_t13.run = AsyncMock(return_value=t13_result)

    with patch("agent.safety_engine.get_safety_engine", return_value=fake_engine), \
         patch("agent.risk_manager.RiskManager", return_value=fake_risk), \
         patch("agent.tools.CalcPositionSizeTool", return_value=fake_t17), \
         patch("agent.tools.CreateApprovalRequestTool", return_value=fake_t09), \
         patch("agent.tools.SendPushNotificationTool", return_value=fake_t13), \
         patch("agent.rollout_gate.is_in_rollout", return_value=True):  # Round 34: gate-open
        r = await loop.process(
            _event(), mode="auto",
            account_balance_usd=10000,  # 让 fixed_pct 高
        )
    assert r.verdict == "hitl_pending"
    assert r.approval_id == "appr-uuid"
    fake_t09.run.assert_called_once()
    # idempotency_key 应被传入
    call_payload = fake_t09.run.call_args.args[0]
    assert call_payload.get("idempotency_key")


# ── auto direct fallback ────────────────────────────────────

@pytest.mark.asyncio
async def test_process_auto_no_hitl_fallback_to_notify():
    """v0:auto + 不需要 HITL → 降级 notify_only(KMS pending)。"""
    loop = NotifyLoop()
    fake_engine = MagicMock()
    fake_engine.is_globally_blocked.return_value = False
    fake_risk = MagicMock()
    risk_result = MagicMock(); risk_result.passed = True
    fake_risk.check_trade.return_value = risk_result

    fake_t17 = MagicMock()
    t17_result = MagicMock()
    t17_result.ok = True
    # 低金额 + 高置信度 → 不触发 HITL
    t17_result.output = {"position_usd": 50.0, "capped_by": [], "reasoning": "ok"}
    fake_t17.run = AsyncMock(return_value=t17_result)

    fake_t13 = MagicMock()
    t13_result = MagicMock()
    t13_result.ok = True
    t13_result.output = {"sent_count": 1, "deep_link": "aitrading://strategy/s-1"}
    fake_t13.run = AsyncMock(return_value=t13_result)

    with patch("agent.safety_engine.get_safety_engine", return_value=fake_engine), \
         patch("agent.risk_manager.RiskManager", return_value=fake_risk), \
         patch("agent.tools.CalcPositionSizeTool", return_value=fake_t17), \
         patch("agent.tools.SendPushNotificationTool", return_value=fake_t13), \
         patch("agent.rollout_gate.is_in_rollout", return_value=True):  # Round 34: gate-open
        r = await loop.process(
            _event(), mode="auto",
            thesis={"conviction": 0.85},
        )
    assert r.verdict == "notify_only"
    assert "auto_direct_fallback" in (r.extra or {})


# ── dry_run ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_dry_run_paper_no_t07_no_push():
    loop = NotifyLoop()
    fake_engine = MagicMock(); fake_engine.is_globally_blocked.return_value = False
    fake_risk = MagicMock(); risk = MagicMock(); risk.passed = True
    fake_risk.check_trade.return_value = risk
    fake_t17 = MagicMock()
    t17_result = MagicMock()
    t17_result.ok = True
    t17_result.output = {"position_usd": 50.0, "capped_by": [], "reasoning": "ok"}
    fake_t17.run = AsyncMock(return_value=t17_result)
    # 不让 T07 / T13 被实例化(用 side_effect 抛错)— dry_run 不应该调它们
    fake_t07_class = MagicMock(side_effect=AssertionError("T07 not allowed in dry_run"))
    fake_t13_class = MagicMock(side_effect=AssertionError("T13 not allowed in dry_run"))

    with patch("agent.safety_engine.get_safety_engine", return_value=fake_engine), \
         patch("agent.risk_manager.RiskManager", return_value=fake_risk), \
         patch("agent.tools.CalcPositionSizeTool", return_value=fake_t17), \
         patch("agent.tools.RunPaperTradeTool", fake_t07_class), \
         patch("agent.tools.SendPushNotificationTool", fake_t13_class):
        r = await loop.process(_event(), mode="paper", dry_run=True)
    assert r.verdict == "dry_run"


# ── singleton ──────────────────────────────────────────────

def test_get_notify_loop_singleton():
    reset_loop_for_test()
    a = get_notify_loop()
    b = get_notify_loop()
    assert a is b
