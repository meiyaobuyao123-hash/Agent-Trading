"""
Tool 单元测试:T07 run_paper_trade / T09 create_approval_request /
                T10 get_paper_performance / T12 save_strategy
W3 D5+(autonomous-loop 续 5)

跑法:python3 -m pytest tests/test_tools_t07_t09_t10_t12.py -v
"""
from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tools import (  # noqa: E402
    CreateApprovalRequestTool,
    GetPaperPerformanceTool,
    RunPaperTradeTool,
    SaveStrategyTool,
    get_tool_registry,
)


# ── Registry now has 12 ─────────────────────────────────────

def test_registry_has_twelve_tools():
    reg = get_tool_registry()
    assert len(reg) >= 12
    for name in ("run_paper_trade", "create_approval_request",
                 "get_paper_performance", "save_strategy"):
        assert name in reg


# ── T07 run_paper_trade ─────────────────────────────────────

@pytest.mark.asyncio
async def test_t07_buy_basic():
    tool = RunPaperTradeTool()
    fake_engine = MagicMock()
    fake_engine.open_position = AsyncMock(return_value={
        "id": "trade-1", "action": "buy", "entry_price": 101.5,
        "amount_usd": 100, "status": "open",
    })
    with patch("agent.paper_engine.get_paper_engine", return_value=fake_engine):
        r = await tool.run({
            "action": "buy",
            "strategy_id": "s-1", "user_id": "u-1",
            "token_address": "0xabc", "token_symbol": "TRUMP",
            "chain": "SOL", "price": 100.0, "amount_usd": 100.0,
            "sl_pct": -10.0, "tp_pct": 30.0,
        })
    assert r.ok is True
    assert r.output["ok"] is True
    assert r.output["trade"]["id"] == "trade-1"
    assert r.output["action"] == "buy"


@pytest.mark.asyncio
async def test_t07_buy_missing_params():
    tool = RunPaperTradeTool()
    fake_engine = MagicMock()
    with patch("agent.paper_engine.get_paper_engine", return_value=fake_engine):
        r = await tool.run({
            "action": "buy", "price": 100.0,
            # 缺 strategy_id / user_id / sl_pct 等
        })
    assert r.ok is True  # tool 不抛错,只是 ok=False 在 output
    assert r.output["ok"] is False
    assert "missing buy params" in r.output["reason"]


@pytest.mark.asyncio
async def test_t07_sell_with_trade_id():
    tool = RunPaperTradeTool()
    fake_engine = MagicMock()
    fake_engine.close_position = AsyncMock(return_value={
        "id": "trade-1", "action": "sell", "exit_price": 130.0,
        "pnl_pct": 28.5, "status": "closed",
    })
    with patch("agent.paper_engine.get_paper_engine", return_value=fake_engine):
        r = await tool.run({
            "action": "sell", "trade_id": "trade-1",
            "price": 132.0, "exit_reason": "target_reached",
        })
    assert r.ok is True
    assert r.output["ok"] is True
    assert r.output["action"] == "sell"


@pytest.mark.asyncio
async def test_t07_sell_missing_trade_id():
    tool = RunPaperTradeTool()
    fake_engine = MagicMock()
    with patch("agent.paper_engine.get_paper_engine", return_value=fake_engine):
        r = await tool.run({"action": "sell", "price": 100.0})
    assert r.output["ok"] is False
    assert "trade_id required" in r.output["reason"]


@pytest.mark.asyncio
async def test_t07_open_returns_none():
    tool = RunPaperTradeTool()
    fake_engine = MagicMock()
    fake_engine.open_position = AsyncMock(return_value=None)
    with patch("agent.paper_engine.get_paper_engine", return_value=fake_engine):
        r = await tool.run({
            "action": "buy",
            "strategy_id": "s-1", "user_id": "u-1",
            "token_address": "0x", "token_symbol": "X", "chain": "SOL",
            "price": 100, "amount_usd": 100, "sl_pct": -5, "tp_pct": 20,
        })
    assert r.output["ok"] is False
    assert r.output["reason"] == "open_position_failed"


@pytest.mark.asyncio
async def test_t07_invalid_action_rejected():
    tool = RunPaperTradeTool()
    r = await tool.run({"action": "hold", "price": 100.0})
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


# ── T10 get_paper_performance ───────────────────────────────

@pytest.mark.asyncio
async def test_t10_promotion_eligible_when_30_trades_high_ev():
    tool = GetPaperPerformanceTool()
    fake_engine = MagicMock()
    fake_engine.get_stats = AsyncMock(return_value={
        "strategy_id": "s-1",
        "trade_count": 35, "closed_count": 32, "open_count": 3,
        "win_rate": 65.0, "total_pnl_usd": 350.0,
        "total_pnl_pct": 64.0, "avg_pnl_pct": 2.0,
        "max_win_pct": 35.0, "max_loss_pct": -8.0,
    })
    with patch("agent.paper_engine.get_paper_engine", return_value=fake_engine):
        r = await tool.run({"strategy_id": "s-1"})
    assert r.ok is True
    assert r.output["ok"] is True
    assert r.output["promotion_eligible"] is True
    assert r.output["promotion_blockers"] == []
    assert r.output["stats"]["closed_count"] == 32


@pytest.mark.asyncio
async def test_t10_promotion_blocked_too_few_trades():
    tool = GetPaperPerformanceTool()
    fake_engine = MagicMock()
    fake_engine.get_stats = AsyncMock(return_value={
        "trade_count": 5, "closed_count": 5, "open_count": 0,
        "win_rate": 80, "total_pnl_pct": 15, "avg_pnl_pct": 3,
        "max_win_pct": 30, "max_loss_pct": -5,
    })
    with patch("agent.paper_engine.get_paper_engine", return_value=fake_engine):
        r = await tool.run({"strategy_id": "s-1"})
    assert r.output["promotion_eligible"] is False
    assert any("closed_trades_lt_30" in b for b in r.output["promotion_blockers"])


@pytest.mark.asyncio
async def test_t10_promotion_blocked_low_ev():
    tool = GetPaperPerformanceTool()
    fake_engine = MagicMock()
    fake_engine.get_stats = AsyncMock(return_value={
        "trade_count": 35, "closed_count": 32, "open_count": 3,
        "win_rate": 60, "total_pnl_pct": 10, "avg_pnl_pct": 0.3,
        "max_win_pct": 10, "max_loss_pct": -3,
    })
    with patch("agent.paper_engine.get_paper_engine", return_value=fake_engine):
        r = await tool.run({"strategy_id": "s-1"})
    assert r.output["promotion_eligible"] is False
    assert any("avg_pnl_pct_lt_1" in b for b in r.output["promotion_blockers"])


@pytest.mark.asyncio
async def test_t10_db_error_returns_blockers():
    tool = GetPaperPerformanceTool()
    fake_engine = MagicMock()
    fake_engine.get_stats = AsyncMock(side_effect=Exception("PG down"))
    with patch("agent.paper_engine.get_paper_engine", return_value=fake_engine):
        r = await tool.run({"strategy_id": "s-1"})
    assert r.output["ok"] is False
    assert any("db_query_failed" in b for b in r.output["promotion_blockers"])


@pytest.mark.asyncio
async def test_t10_include_comparison():
    tool = GetPaperPerformanceTool()
    fake_engine = MagicMock()
    fake_engine.get_stats = AsyncMock(return_value={
        "trade_count": 35, "closed_count": 32, "open_count": 3,
        "win_rate": 65, "avg_pnl_pct": 2.0, "max_win_pct": 30, "max_loss_pct": -5,
    })
    fake_engine.get_comparison = AsyncMock(return_value={"paper": {}, "live": {}})
    with patch("agent.paper_engine.get_paper_engine", return_value=fake_engine):
        r = await tool.run({"strategy_id": "s-1", "include_comparison": True})
    assert r.output["comparison"] is not None


# ── T12 save_strategy ───────────────────────────────────────

@pytest.mark.asyncio
async def test_t12_basic_creates():
    tool = SaveStrategyTool()
    fake_mgr = MagicMock()
    fake_mgr.list_strategies.return_value = []  # 配额够
    fake_mgr.create_strategy.return_value = {
        "id": "s-100", "name": "新策略", "mode": "paper", "status": "active",
    }
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr):
        r = await tool.run({
            "user_id": "u-1",
            "spec": {
                "name": "聪明钱跟单",
                "conditions": {"rules": [{"data_source": "smart_money", "field": "elite_score", "op": ">=", "value": 75}]},
                "actions": [{"type": "alert"}],
            },
        })
    assert r.output["ok"] is True
    assert r.output["strategy"]["id"] == "s-100"


@pytest.mark.asyncio
async def test_t12_quota_exceeded_blocks():
    tool = SaveStrategyTool()
    fake_mgr = MagicMock()
    fake_mgr.list_strategies.return_value = [{"id": str(i)} for i in range(20)]
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr):
        r = await tool.run({
            "user_id": "u-1",
            "spec": {
                "conditions": {"rules": [{"data_source": "x", "field": "y"}]},
                "actions": [{"type": "alert"}],
            },
        })
    assert r.output["ok"] is False
    assert "quota_exceeded" in r.output["reason"]
    fake_mgr.create_strategy.assert_not_called()


@pytest.mark.asyncio
async def test_t12_skip_quota_check():
    tool = SaveStrategyTool()
    fake_mgr = MagicMock()
    # 即使有 20 条也应该通过(skip_quota_check=true)
    fake_mgr.list_strategies.return_value = [{"id": str(i)} for i in range(50)]
    fake_mgr.create_strategy.return_value = {"id": "s-x"}
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr):
        r = await tool.run({
            "user_id": "u-1", "skip_quota_check": True,
            "spec": {
                "conditions": {"rules": [{"data_source": "x", "field": "y"}]},
                "actions": [{"type": "alert"}],
            },
        })
    assert r.output["ok"] is True


@pytest.mark.asyncio
async def test_t12_spec_value_error():
    tool = SaveStrategyTool()
    fake_mgr = MagicMock()
    fake_mgr.list_strategies.return_value = []
    fake_mgr.create_strategy.side_effect = ValueError("rules empty")
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr):
        r = await tool.run({
            "user_id": "u-1",
            "spec": {
                "conditions": {"rules": [{"data_source": "x", "field": "y"}]},
                "actions": [{"type": "alert"}],
            },
        })
    assert r.output["ok"] is False
    assert "spec_invalid" in r.output["reason"]


@pytest.mark.asyncio
async def test_t12_db_runtime_error():
    tool = SaveStrategyTool()
    fake_mgr = MagicMock()
    fake_mgr.list_strategies.return_value = []
    fake_mgr.create_strategy.side_effect = RuntimeError("supabase 503")
    with patch("agent.strategy_manager.StrategyManager", return_value=fake_mgr):
        r = await tool.run({
            "user_id": "u-1",
            "spec": {
                "conditions": {"rules": [{"data_source": "x", "field": "y"}]},
                "actions": [{"type": "alert"}],
            },
        })
    assert r.output["ok"] is False
    assert "db_write_failed" in r.output["reason"]


@pytest.mark.asyncio
async def test_t12_input_schema_no_actions():
    tool = SaveStrategyTool()
    r = await tool.run({
        "user_id": "u-1",
        "spec": {
            "conditions": {"rules": [{"data_source": "x", "field": "y"}]},
            # 缺 actions
        },
    })
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


# ── T09 create_approval_request ─────────────────────────────

def _make_fake_pg_conn():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = None
    return conn, cur


@pytest.mark.asyncio
async def test_t09_creates_new_approval():
    tool = CreateApprovalRequestTool()
    conn, cur = _make_fake_pg_conn()
    expires = datetime.now(timezone.utc)
    # 第一次查 idem_key 返空,第二次 INSERT RETURNING 返新 id
    cur.fetchone.side_effect = [None, ("appr-uuid", expires)]
    with patch("local_db._get_conn", return_value=conn):
        r = await tool.run({
            "device_id": "d-1", "strategy_id": "s-1",
            "trigger_conditions_matched": {"score": 80},
            "amount_usd": 50.0,
            "idempotency_key": "s-1::sig-100::50",
        })
    assert r.ok is True
    assert r.output["ok"] is True
    assert r.output["approval_id"] == "appr-uuid"
    assert r.output["idempotent_hit"] is False


@pytest.mark.asyncio
async def test_t09_idempotent_hit_returns_existing():
    tool = CreateApprovalRequestTool()
    conn, cur = _make_fake_pg_conn()
    expires = datetime.now(timezone.utc)
    cur.fetchone.return_value = ("existing-uuid", expires)
    with patch("local_db._get_conn", return_value=conn):
        r = await tool.run({
            "device_id": "d-1", "strategy_id": "s-1",
            "trigger_conditions_matched": {"x": 1},
            "idempotency_key": "duplicate-key",
        })
    assert r.output["idempotent_hit"] is True
    assert r.output["approval_id"] == "existing-uuid"
    # 没调 INSERT(只调一次 SELECT)
    assert cur.execute.call_count == 1


@pytest.mark.asyncio
async def test_t09_no_idempotency_key_creates_directly():
    tool = CreateApprovalRequestTool()
    conn, cur = _make_fake_pg_conn()
    expires = datetime.now(timezone.utc)
    cur.fetchone.return_value = ("new-uuid", expires)
    with patch("local_db._get_conn", return_value=conn):
        r = await tool.run({
            "device_id": "d-1", "strategy_id": "s-1",
            "trigger_conditions_matched": {"x": 1},
        })
    assert r.output["ok"] is True
    assert r.output["idempotent_hit"] is False
    # 没 idem_key 时只有 INSERT 一次
    assert cur.execute.call_count == 1


@pytest.mark.asyncio
async def test_t09_db_failure():
    tool = CreateApprovalRequestTool()
    with patch("local_db._get_conn", side_effect=Exception("PG down")):
        r = await tool.run({
            "device_id": "d-1", "strategy_id": "s-1",
            "trigger_conditions_matched": {"x": 1},
        })
    assert r.ok is False
    assert r.failure_mode == "EXECUTE_ERROR"


@pytest.mark.asyncio
async def test_t09_timeout_validation():
    tool = CreateApprovalRequestTool()
    r = await tool.run({
        "device_id": "d-1", "strategy_id": "s-1",
        "trigger_conditions_matched": {"x": 1},
        "timeout_seconds": 30,  # < 60 min
    })
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t09_metadata_idempotent():
    tool = CreateApprovalRequestTool()
    assert tool.metadata.idempotent is True
    assert "idempotency_key" in tool.metadata.idempotency_key_fields
    assert tool.metadata.side_effects.value == "db_write"
