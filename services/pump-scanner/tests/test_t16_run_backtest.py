"""
T16 run_backtest 单元测试 — W3 D5+ autonomous-loop 续 13

跑法:python3 -m pytest tests/test_t16_run_backtest.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tools import RunBacktestTool, get_tool_registry  # noqa: E402


VALID_SPEC = {
    "name": "Test Strategy",
    "conditions": {
        "rules": [
            {"data_source": "hot_coins", "field": "score",
             "op": ">=", "value": 70},
        ],
    },
    "filters": {"chains": ["SOL"]},
}


# ── Registry has 17 tools(R35 加完 T01/T02/T03/T08)─────────

def test_registry_includes_t16():
    reg = get_tool_registry()
    assert "run_backtest" in reg
    assert len(reg) == 18  # R47+ 新增 1 个 tool


# ── Input schema validation ─────────────────────────────────

@pytest.mark.asyncio
async def test_t16_missing_spec_invalid():
    tool = RunBacktestTool()
    r = await tool.run({"days": 7})
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t16_spec_missing_conditions_invalid():
    tool = RunBacktestTool()
    r = await tool.run({"spec": {"name": "x"}})
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t16_days_too_high_invalid():
    tool = RunBacktestTool()
    r = await tool.run({"spec": VALID_SPEC, "days": 200})
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


# ── Successful backtest ─────────────────────────────────────

@pytest.mark.asyncio
async def test_t16_basic_returns_results():
    tool = RunBacktestTool()
    fake = AsyncMock(return_value={
        "trigger_count": 25,
        "simulated_win_rate": 0.65,
        "avg_return_pct": 8.5,
        "max_drawdown_pct": -12.3,
        "sample_triggers": [{"token": "TRUMP", "score": 80}],
    })
    with patch("agent.backtester.backtest_strategy", fake):
        r = await tool.run({"spec": VALID_SPEC, "days": 7})
    assert r.ok is True
    assert r.output["trigger_count"] == 25
    assert r.output["win_rate"] == 0.65
    assert r.output["avg_return_pct"] == 8.5
    assert r.output["days"] == 7


# ── Warnings rules ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_t16_warns_on_low_sample_size():
    tool = RunBacktestTool()
    fake = AsyncMock(return_value={
        "trigger_count": 5,  # < 10
        "simulated_win_rate": 0.6,
        "avg_return_pct": 5.0,
        "max_drawdown_pct": -3.0,
        "sample_triggers": [],
    })
    with patch("agent.backtester.backtest_strategy", fake):
        r = await tool.run({"spec": VALID_SPEC, "days": 7})
    assert any("sample_size_low" in w for w in r.output["warnings"])


@pytest.mark.asyncio
async def test_t16_warns_on_short_window():
    tool = RunBacktestTool()
    fake = AsyncMock(return_value={
        "trigger_count": 50, "simulated_win_rate": 0.5,
        "avg_return_pct": 2.0, "max_drawdown_pct": -5.0,
        "sample_triggers": [],
    })
    with patch("agent.backtester.backtest_strategy", fake):
        r = await tool.run({"spec": VALID_SPEC, "days": 3})
    assert any("window_short" in w for w in r.output["warnings"])


@pytest.mark.asyncio
async def test_t16_warns_on_long_window():
    tool = RunBacktestTool()
    fake = AsyncMock(return_value={
        "trigger_count": 100, "simulated_win_rate": 0.55,
        "avg_return_pct": 3.0, "max_drawdown_pct": -8.0,
        "sample_triggers": [],
    })
    with patch("agent.backtester.backtest_strategy", fake):
        r = await tool.run({"spec": VALID_SPEC, "days": 60})
    assert any("window_long" in w for w in r.output["warnings"])


@pytest.mark.asyncio
async def test_t16_warns_on_high_drawdown():
    tool = RunBacktestTool()
    fake = AsyncMock(return_value={
        "trigger_count": 30, "simulated_win_rate": 0.5,
        "avg_return_pct": 1.0, "max_drawdown_pct": -25.0,  # < -20
        "sample_triggers": [],
    })
    with patch("agent.backtester.backtest_strategy", fake):
        r = await tool.run({"spec": VALID_SPEC, "days": 14})
    assert any("high_drawdown" in w for w in r.output["warnings"])


@pytest.mark.asyncio
async def test_t16_disclaimer_always_present():
    tool = RunBacktestTool()
    fake = AsyncMock(return_value={
        "trigger_count": 50, "simulated_win_rate": 0.6,
        "avg_return_pct": 5.0, "max_drawdown_pct": -5.0,
        "sample_triggers": [],
    })
    with patch("agent.backtester.backtest_strategy", fake):
        r = await tool.run({"spec": VALID_SPEC, "days": 14})
    assert any("disclaimer" in w for w in r.output["warnings"])


# ── backtester failure → EXECUTE_ERROR ──────────────────────

@pytest.mark.asyncio
async def test_t16_backtester_exception_returns_execute_error():
    tool = RunBacktestTool()
    fake = AsyncMock(side_effect=Exception("DB connection lost"))
    with patch("agent.backtester.backtest_strategy", fake):
        r = await tool.run({"spec": VALID_SPEC, "days": 7})
    assert r.ok is False
    assert r.failure_mode == "EXECUTE_ERROR"
    assert "backtester_failed" in (r.error or "")


# ── metadata ───────────────────────────────────────────────

def test_t16_metadata():
    tool = RunBacktestTool()
    assert tool.metadata.name == "run_backtest"
    assert tool.metadata.idempotent is True
    assert tool.metadata.cost_usd == 0.0
    assert tool.metadata.permission.value == "device_only"
    assert tool.metadata.side_effects.value == "none"


def test_t16_anthropic_spec():
    tool = RunBacktestTool()
    spec = tool.to_anthropic_tool_spec()
    assert spec["name"] == "run_backtest"
    assert "回测" in spec["description"] or "backtest" in spec["description"].lower()
    assert "spec" in spec["input_schema"]["required"]
