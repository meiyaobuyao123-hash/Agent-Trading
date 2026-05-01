"""
Tool 单元测试:T04 recall_memory / T14 calc_technical_indicators / T17 calc_position_size
W3 D5+

跑法:python3 -m pytest tests/test_tools_t04_t14_t17.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tools import (  # noqa: E402
    CalcPositionSizeTool,
    CalcTechnicalIndicatorsTool,
    RecallMemoryTool,
    get_tool_registry,
)


# ── Registry now has 6 tools ────────────────────────────────

def test_registry_has_six_tools_after_p5_p7():
    reg = get_tool_registry()
    assert len(reg) == 6
    assert {"recall_memory", "calc_technical_indicators", "calc_position_size"}.issubset(set(reg.keys()))


# ── T14 calc_technical_indicators ───────────────────────────

def _candles(closes, h=None, l=None):
    return [
        {
            "open": c, "close": c,
            "high": h if h is not None else c * 1.01,
            "low": l if l is not None else c * 0.99,
            "volume": 1000,
        }
        for c in closes
    ]


@pytest.mark.asyncio
async def test_t14_rsi_basic():
    tool = CalcTechnicalIndicatorsTool()
    closes = list(range(1, 31))  # 单调上涨
    r = await tool.run({
        "candles": _candles(closes),
        "indicators": ["rsi"],
    })
    assert r.ok is True
    assert r.output["rsi"] is not None
    # 单调上涨 → RSI 接近 100
    assert r.output["rsi"] > 60
    assert r.output["candle_count"] == 30
    assert "rsi" in r.output["indicators_computed"]


@pytest.mark.asyncio
async def test_t14_insufficient_candles_returns_null():
    tool = CalcTechnicalIndicatorsTool()
    r = await tool.run({
        "candles": _candles([100, 101]),
        "indicators": ["rsi", "macd"],
    })
    assert r.ok is True
    assert r.output["rsi"] is None
    assert r.output["macd"] is None
    assert r.output["indicators_computed"] == []


@pytest.mark.asyncio
async def test_t14_ma_multiple_periods():
    tool = CalcTechnicalIndicatorsTool()
    r = await tool.run({
        "candles": _candles(list(range(1, 51))),
        "indicators": ["ma"],
        "ma_periods": [10, 20, 30],
    })
    assert r.ok is True
    assert r.output["ma"] is not None
    assert "10" in r.output["ma"]
    assert "20" in r.output["ma"]
    assert "30" in r.output["ma"]


@pytest.mark.asyncio
async def test_t14_invalid_indicator_rejected():
    tool = CalcTechnicalIndicatorsTool()
    r = await tool.run({
        "candles": _candles([1, 2, 3]),
        "indicators": ["unknown_indicator"],
    })
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t14_atr_with_high_low():
    tool = CalcTechnicalIndicatorsTool()
    candles = [
        {"open": 100, "high": 102, "low": 98, "close": 100, "volume": 1000}
        for _ in range(20)
    ]
    r = await tool.run({
        "candles": candles,
        "indicators": ["atr"],
    })
    assert r.ok is True
    assert r.output["atr"] is not None
    assert r.output["atr"] > 0


# ── T17 calc_position_size ──────────────────────────────────

@pytest.mark.asyncio
async def test_t17_fixed_pct_basic():
    tool = CalcPositionSizeTool()
    r = await tool.run({
        "account_balance_usd": 1000,
        "mode": "fixed_pct",
        "fixed_pct": 0.05,
    })
    assert r.ok is True
    # 5% × $1000 = $50,under HR01 ($500) and HR04 (10% = $100) → $50
    assert r.output["position_usd"] == 50.0
    assert r.output["position_pct_of_balance"] == 0.05
    assert r.output["capped_by"] == []


@pytest.mark.asyncio
async def test_t17_fixed_pct_capped_by_hr01():
    tool = CalcPositionSizeTool()
    r = await tool.run({
        "account_balance_usd": 100000,
        "mode": "fixed_pct",
        "fixed_pct": 0.10,  # 10% × 100k = $10000,but HR01 caps to $500
    })
    assert r.ok is True
    assert r.output["position_usd"] == 500.0
    assert "HR01_max_per_trade_500usd" in r.output["capped_by"]


@pytest.mark.asyncio
async def test_t17_fixed_pct_capped_by_hr04():
    tool = CalcPositionSizeTool()
    r = await tool.run({
        "account_balance_usd": 1000,
        "mode": "fixed_pct",
        "fixed_pct": 0.50,  # 50% but HR04 caps to 10% = $100
    })
    assert r.ok is True
    assert r.output["position_usd"] == 100.0
    assert any("max_pct_of_balance" in c for c in r.output["capped_by"])


@pytest.mark.asyncio
async def test_t17_kelly_fraction():
    tool = CalcPositionSizeTool()
    # 60% win rate,W/L=2 → kelly_f = 0.6 - 0.4/2 = 0.4 × 0.5 = 20%
    r = await tool.run({
        "account_balance_usd": 1000,
        "mode": "kelly",
        "win_rate": 0.6,
        "win_loss_ratio": 2.0,
        "kelly_safety_factor": 0.5,
    })
    assert r.ok is True
    # raw = 20% × $1000 = $200,but HR04 (10%) caps to $100
    assert r.output["position_usd"] == 100.0
    assert any("max_pct_of_balance" in c for c in r.output["capped_by"])


@pytest.mark.asyncio
async def test_t17_kelly_negative_clipped_to_zero():
    """胜率太低 → kelly_f 负数,应该 clip 到 0。"""
    tool = CalcPositionSizeTool()
    r = await tool.run({
        "account_balance_usd": 1000,
        "mode": "kelly",
        "win_rate": 0.3,
        "win_loss_ratio": 1.0,  # kelly = 0.3 - 0.7/1 = -0.4 → clip 0
    })
    assert r.ok is True
    assert r.output["position_usd"] == 0.0


@pytest.mark.asyncio
async def test_t17_atr_risk_basic():
    tool = CalcPositionSizeTool()
    # entry $100,stop $98 → risk per unit = $2
    # risk_usd = $20 → 10 units × $100 = $1000
    # Capped to HR04 10% = $100
    r = await tool.run({
        "account_balance_usd": 1000,
        "mode": "atr_risk",
        "entry_price": 100.0,
        "stop_loss_price": 98.0,
        "risk_per_trade_usd": 20.0,
    })
    assert r.ok is True
    assert r.output["raw_position_usd"] == 1000.0
    assert r.output["position_usd"] == 100.0


@pytest.mark.asyncio
async def test_t17_kelly_missing_params():
    tool = CalcPositionSizeTool()
    r = await tool.run({
        "account_balance_usd": 1000,
        "mode": "kelly",
    })
    assert r.ok is False
    assert r.failure_mode == "EXECUTE_ERROR"


@pytest.mark.asyncio
async def test_t17_user_max_position_overrides():
    tool = CalcPositionSizeTool()
    r = await tool.run({
        "account_balance_usd": 1000,
        "mode": "fixed_pct",
        "fixed_pct": 0.05,
        "max_position_usd": 30,
    })
    assert r.ok is True
    assert r.output["position_usd"] == 30.0
    assert "user_max_position_usd" in r.output["capped_by"]


# ── T04 recall_memory ───────────────────────────────────────

@pytest.mark.asyncio
async def test_t04_memory_init_failure_returns_empty():
    """memory_manager init 失败 → 全空 layer 返回。"""
    tool = RecallMemoryTool()
    with patch("agent.memory.get_memory_manager", side_effect=Exception("init failed")):
        r = await tool.run({"device_id": "u-1"})
    assert r.ok is True
    assert r.output["working"] == []
    assert r.output["episodic"] == []
    assert r.output["semantic"] == []
    assert r.output["layers_returned"] == []


@pytest.mark.asyncio
async def test_t04_returns_three_layers():
    tool = RecallMemoryTool()
    fake_mm = MagicMock()
    fake_mm.working.get_recent.return_value = [
        {"type": "trade", "summary": "BTC bought", "_ts": 100}
    ]
    fake_mm.episodic.get_relevant.return_value = [
        {"id": "ep-1", "content": "trade in TRENDING_UP",
         "structured_data": {"regime": "TRENDING_UP"}, "_score": 4.5}
    ]
    fake_mm.semantic.get_relevant.return_value = [
        {"id": "sm-1", "content": "RANGING BC<8 禁开",
         "structured_data": {"condition": "regime=RANGING", "action": "block"},
         "importance": 7, "match_count": 12},
    ]
    with patch("agent.memory.get_memory_manager", return_value=fake_mm):
        r = await tool.run({"device_id": "u-1"})
    assert r.ok is True
    assert len(r.output["working"]) == 1
    assert len(r.output["episodic"]) == 1
    assert len(r.output["semantic"]) == 1
    assert "working" in r.output["layers_returned"]
    assert "episodic" in r.output["layers_returned"]
    assert "semantic" in r.output["layers_returned"]


@pytest.mark.asyncio
async def test_t04_partial_failure_returns_other_layers():
    """working 失败但 semantic 成功 → 返 semantic + 错误标记 working。"""
    tool = RecallMemoryTool()
    fake_mm = MagicMock()
    fake_mm.working.get_recent.side_effect = Exception("working DB down")
    fake_mm.episodic.get_relevant.return_value = []
    fake_mm.semantic.get_relevant.return_value = [
        {"id": "sm-1", "content": "rule",
         "structured_data": {"condition": "x", "action": "y"},
         "importance": 5}
    ]
    with patch("agent.memory.get_memory_manager", return_value=fake_mm):
        r = await tool.run({"device_id": "u-1"})
    assert r.ok is True
    assert "semantic" in r.output["layers_returned"]
    assert "working" in r.output["errors"]
    assert r.output["working"] == []


@pytest.mark.asyncio
async def test_t04_layers_filter():
    """只查 semantic,不调 working/episodic。"""
    tool = RecallMemoryTool()
    fake_mm = MagicMock()
    fake_mm.semantic.get_relevant.return_value = []
    with patch("agent.memory.get_memory_manager", return_value=fake_mm):
        r = await tool.run({"device_id": "u-1", "layers": ["semantic"]})
    assert r.ok is True
    assert r.output["layers_returned"] == ["semantic"]
    fake_mm.working.get_recent.assert_not_called()


@pytest.mark.asyncio
async def test_t04_metadata_is_readonly():
    tool = RecallMemoryTool()
    assert tool.metadata.side_effects.value == "none"
    assert tool.metadata.idempotent is True
    assert tool.metadata.permission.value == "device_only"
