"""
Thesis Loop 单元测试 — W3 D5+ autonomous-loop 续 9

跑法:python3 -m pytest tests/test_thesis_loop.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loops import thesis_loop  # noqa: E402
from agent.loops.thesis_loop import (  # noqa: E402
    ThesisLoop,
    ThesisResult,
    _estimate_cost_usd,
    _is_uuid,
    _parse_json_block,
    _summarize_analyst,
    _summarize_similar_cases,
    reset_loop_for_test,
)


# ── helpers ─────────────────────────────────────────────────

def test_is_uuid_valid():
    assert _is_uuid("550e8400-e29b-41d4-a716-446655440000") is True


def test_is_uuid_invalid():
    assert _is_uuid("system") is False
    assert _is_uuid("") is False
    assert _is_uuid(None) is False


def test_summarize_analyst():
    r = {"direction": "bullish", "confidence": 0.75,
         "points": ["RSI oversold", "MACD divergence", "extra"]}
    s = _summarize_analyst("技术", r)
    assert "技术" in s
    assert "bullish" in s
    assert "RSI" in s


def test_summarize_analyst_empty():
    assert "数据不可用" in _summarize_analyst("链上", {})


def test_summarize_similar_cases_empty():
    assert "无相似" in _summarize_similar_cases([])


def test_summarize_similar_cases_with_score():
    cases = [{"summary": "case 1", "score": 4.5}, {"summary": "case 2"}]
    s = _summarize_similar_cases(cases)
    assert "case 1" in s
    assert "4.5" in s


def test_parse_json_block():
    assert _parse_json_block('{"a":1}') == {"a": 1}
    assert _parse_json_block("```json\n{\"x\":2}\n```") == {"x": 2}
    assert _parse_json_block("noisy text {\"y\":3} more") == {"y": 3}
    assert _parse_json_block("not json") is None


def test_estimate_cost_haiku():
    cost = _estimate_cost_usd("claude-haiku-4-5-20251001", 100_000, 5_000)
    assert cost > 0
    # haiku: 100K * $1 + 5K * $5 / 1M = $0.1 + $0.025 = $0.125
    assert abs(cost - 0.125) < 0.001


def test_estimate_cost_sonnet():
    cost = _estimate_cost_usd("claude-sonnet-4-6", 50_000, 1_000)
    # sonnet: 50K * $3 + 1K * $15 / 1M = $0.15 + $0.015 = $0.165
    assert abs(cost - 0.165) < 0.001


def test_estimate_cost_unknown_model_uses_sonnet():
    """未知 model 默认按 sonnet 估算。"""
    cost = _estimate_cost_usd("custom-model", 1000, 100)
    assert cost > 0


# ── _select_level ───────────────────────────────────────────

def test_select_level_explicit_passes_through():
    loop = ThesisLoop()
    assert loop._select_level("L1", 100, 80) == "L1"
    assert loop._select_level("L3", 5, 30) == "L3"


def test_select_level_auto_low_position_low_score_l1():
    loop = ThesisLoop()
    assert loop._select_level("auto", 10, 30) == "L1"


def test_select_level_auto_high_score_l3():
    loop = ThesisLoop()
    assert loop._select_level("auto", 100, 80) == "L3"


def test_select_level_auto_mid_l2():
    loop = ThesisLoop()
    assert loop._select_level("auto", 100, 60) == "L2"


def test_select_level_auto_high_pos_low_score_l2():
    """高仓位 + 低 score → 不能 L1,但 score < 70 走 L2。"""
    loop = ThesisLoop()
    assert loop._select_level("auto", 100, 50) == "L2"


# ── _make_l1_thesis ─────────────────────────────────────────

def test_l1_thesis_high_score_bullish():
    loop = ThesisLoop()
    t = loop._make_l1_thesis(
        chain="SOL", token_address="0x", token_symbol="X",
        score=80, regime="BREAKOUT", tech={}, sent={}, onc={},
    )
    assert t["direction"] == "bullish"
    assert t["conviction"] < 0.5  # L1 不能超 0.5(避免冲突 hold/avoid 硬约束)
    assert len(t["risks"]) >= 2
    assert t["level"] == "L1"


def test_l1_thesis_low_score_bearish_normalized_to_hold():
    """L1 bearish 但 conviction<0.5 → normalize 时变 hold(走 _normalize 才生效)。
    _make_l1_thesis 自身不 normalize,所以这里返 bearish + 低 conviction。"""
    loop = ThesisLoop()
    t = loop._make_l1_thesis(
        chain="SOL", token_address="0x", token_symbol="X",
        score=20, regime=None, tech={}, sent={}, onc={},
    )
    assert t["direction"] == "bearish"


def test_l1_thesis_neutral_when_mid_score():
    loop = ThesisLoop()
    t = loop._make_l1_thesis(
        chain="SOL", token_address="0x", token_symbol="X",
        score=50, regime=None, tech={}, sent={}, onc={},
    )
    # neutral 在 _make_l1 里映射到 hold(避免硬约束)
    assert t["direction"] == "hold"


# ── _normalize_and_validate ─────────────────────────────────

def test_normalize_low_conviction_forces_neutral():
    loop = ThesisLoop()
    raw = {"direction": "bullish", "conviction": 0.3, "risks": ["a", "b"],
           "summary_30w": "看涨"}
    out = loop._normalize_and_validate(raw, "SOL", "0x", "X", "L2")
    assert out["direction"] == "neutral"
    assert "低置信度" in out["summary_30w"]


def test_normalize_pads_risks_to_2():
    loop = ThesisLoop()
    raw = {"direction": "neutral", "conviction": 0.3, "risks": [],
           "summary_30w": "x"}
    out = loop._normalize_and_validate(raw, "SOL", "0x", "X", "L2")
    assert len(out["risks"]) >= 2


def test_normalize_long_to_bullish():
    loop = ThesisLoop()
    raw = {"direction": "long", "conviction": 0.7, "risks": ["a", "b"],
           "summary_30w": "y"}
    out = loop._normalize_and_validate(raw, "SOL", "0x", "X", "L2")
    assert out["direction"] == "bullish"


def test_normalize_short_to_bearish():
    loop = ThesisLoop()
    raw = {"direction": "short", "conviction": 0.7, "risks": ["a", "b"],
           "summary_30w": "y"}
    out = loop._normalize_and_validate(raw, "SOL", "0x", "X", "L2")
    assert out["direction"] == "bearish"


def test_normalize_clamps_conviction():
    loop = ThesisLoop()
    raw = {"direction": "bullish", "conviction": 1.5, "risks": ["a", "b"],
           "summary_30w": "y"}
    out = loop._normalize_and_validate(raw, "SOL", "0x", "X", "L2")
    assert out["conviction"] == 1.0


def test_normalize_summary_30w_truncated():
    loop = ThesisLoop()
    raw = {"direction": "bullish", "conviction": 0.7, "risks": ["a", "b"],
           "summary_30w": "x" * 200}
    out = loop._normalize_and_validate(raw, "SOL", "0x", "X", "L2")
    assert len(out["summary_30w"]) <= 60


# ── generate (端到端,mock) ─────────────────────────────────

@pytest.mark.asyncio
async def test_generate_l1_path_no_llm():
    """level=L1 → 不调 LLM,返规则化 thesis。"""
    reset_loop_for_test()
    loop = ThesisLoop()
    with patch.object(loop, "_gather_evidence",
                      AsyncMock(return_value=({}, {}, {}))), \
         patch.object(loop, "_gather_similar_cases",
                      AsyncMock(return_value=[])), \
         patch.object(loop, "_persist_thesis",
                      AsyncMock(return_value="t-1")), \
         patch.object(loop, "_invoke_p02",
                      AsyncMock(return_value=(None, "should not be called", 0, 0))) as mock_llm:
        r = await loop.generate(
            device_id="00000000-0000-0000-0000-000000000001",
            chain="SOL", token_address="0xabc",
            level="L1", score=75,
        )
    assert r.ok is True
    assert r.level == "L1"
    assert r.source == "rule_engine"
    assert r.cost_usd == 0
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_generate_l2_llm_success():
    loop = ThesisLoop()
    fake_thesis_json = {
        "direction": "bullish", "conviction": 0.78,
        "summary_30w": "BREAKOUT 强势,聪明钱跟入",
        "entry_zone": {"low": 1.0, "high": 1.1},
        "stop_loss": 0.9, "target": [1.4, 1.8],
        "risks": ["流动性 < $50K", "BREAKOUT 失败回 RANGING"],
        "evidence": [{"layer": "technical", "text": "RSI 35", "weight": 0.8}],
        "level": "L2",
    }
    with patch.object(loop, "_gather_evidence",
                      AsyncMock(return_value=({"direction": "bullish"}, {}, {}))), \
         patch.object(loop, "_gather_similar_cases",
                      AsyncMock(return_value=[])), \
         patch.object(loop, "_invoke_p02",
                      AsyncMock(return_value=(fake_thesis_json, None, 0.025, 1500))), \
         patch.object(loop, "_persist_thesis",
                      AsyncMock(return_value="t-200")):
        r = await loop.generate(
            device_id="00000000-0000-0000-0000-000000000001",
            chain="SOL", token_address="0xabc", level="L2",
        )
    assert r.ok is True
    assert r.level == "L2"
    assert r.source == "llm"
    assert r.cost_usd == 0.025
    assert r.thesis["direction"] == "bullish"
    assert r.thesis_id == "t-200"


@pytest.mark.asyncio
async def test_generate_l2_llm_failure_degrades_to_l1():
    """L2 LLM 失败 → 降级 L1 + 不抛错。"""
    loop = ThesisLoop()
    with patch.object(loop, "_gather_evidence",
                      AsyncMock(return_value=({}, {}, {}))), \
         patch.object(loop, "_gather_similar_cases",
                      AsyncMock(return_value=[])), \
         patch.object(loop, "_invoke_p02",
                      AsyncMock(return_value=(None, "API timeout", 0, 0))), \
         patch.object(loop, "_persist_thesis",
                      AsyncMock(return_value="t-fallback")):
        r = await loop.generate(
            device_id="00000000-0000-0000-0000-000000000001",
            chain="SOL", token_address="0xabc",
            level="L2", score=60,
        )
    assert r.ok is True
    assert r.level == "L1"  # degraded
    assert r.source == "rule_engine"
    assert "l2_failed_degraded" in (r.error or "")


@pytest.mark.asyncio
async def test_generate_l3_falls_back_to_l2():
    """L3 暂未实施 → fallback to L2(显示日志,但 chosen_level 切 L2)。"""
    loop = ThesisLoop()
    fake = {"direction": "bullish", "conviction": 0.72,
            "summary_30w": "L3 fallback to L2",
            "risks": ["a", "b"],
            "evidence": [{"layer": "x", "text": "y", "weight": 0.5}]}
    with patch.object(loop, "_gather_evidence",
                      AsyncMock(return_value=({}, {}, {}))), \
         patch.object(loop, "_gather_similar_cases",
                      AsyncMock(return_value=[])), \
         patch.object(loop, "_invoke_p02",
                      AsyncMock(return_value=(fake, None, 0.05, 2000))), \
         patch.object(loop, "_persist_thesis",
                      AsyncMock(return_value="t-300")):
        r = await loop.generate(
            device_id="00000000-0000-0000-0000-000000000001",
            chain="SOL", token_address="0xabc", level="L3",
        )
    # L3 当前 fallback 到 L2(W7-W12 实施真 debate)
    assert r.level == "L2"
    assert r.source == "llm"


@pytest.mark.asyncio
async def test_generate_persist_failure_does_not_break():
    """_persist_thesis 返 None → 仍然返成功 thesis(只是没 thesis_id)。"""
    loop = ThesisLoop()
    with patch.object(loop, "_gather_evidence",
                      AsyncMock(return_value=({}, {}, {}))), \
         patch.object(loop, "_gather_similar_cases",
                      AsyncMock(return_value=[])), \
         patch.object(loop, "_persist_thesis",
                      AsyncMock(return_value=None)):
        r = await loop.generate(
            device_id="00000000-0000-0000-0000-000000000001",
            chain="SOL", token_address="0xabc",
            level="L1", score=80,
        )
    assert r.ok is True
    assert r.thesis_id is None  # 持久化失败但 result 仍 ok


# ── _persist_thesis: skip non-UUID device_id ────────────────

@pytest.mark.asyncio
async def test_persist_skips_non_uuid_device():
    loop = ThesisLoop()
    fake_conn = MagicMock()
    with patch("local_db._get_conn", return_value=fake_conn):
        tid = await loop._persist_thesis(
            "system",  # 非 UUID
            {"direction": "neutral", "conviction": 0.3,
             "risks": ["a", "b"], "summary_30w": "x"},
            "L1", {}, {}, {}, [],
        )
    assert tid is None
    fake_conn.cursor.assert_not_called()


# ── _gather_similar_cases ───────────────────────────────────

@pytest.mark.asyncio
async def test_gather_similar_cases_returns_top3():
    loop = ThesisLoop()
    fake_tool = MagicMock()
    fake_result = MagicMock()
    fake_result.ok = True
    fake_result.output = {"episodic": [
        {"id": "e1", "summary": "case 1"},
        {"id": "e2", "summary": "case 2"},
        {"id": "e3", "summary": "case 3"},
        {"id": "e4", "summary": "case 4"},
    ]}
    fake_tool.run = AsyncMock(return_value=fake_result)
    with patch("agent.tools.RecallMemoryTool", return_value=fake_tool):
        out = await loop._gather_similar_cases("dev-1", "SOL")
    assert len(out) == 3


@pytest.mark.asyncio
async def test_gather_similar_cases_failure_returns_empty():
    loop = ThesisLoop()
    with patch("agent.tools.RecallMemoryTool", side_effect=Exception("import fail")):
        out = await loop._gather_similar_cases("dev-1", "SOL")
    assert out == []


# ── singleton ───────────────────────────────────────────────

def test_get_thesis_loop_singleton():
    reset_loop_for_test()
    from agent.loops.thesis_loop import get_thesis_loop
    a = get_thesis_loop()
    b = get_thesis_loop()
    assert a is b
