"""
review_engine v2(LLM 路径)测试 — W3 D5+ autonomous-loop 续 7

跑法:python3 -m pytest tests/test_review_engine_v2.py -v
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import review_engine  # noqa: E402


# ── 共用 fixtures / helpers ─────────────────────────────────

def _trade(addr, chain, pnl_ratio, is_closed=True, d3=0.0):
    return {
        "token_address": addr, "chain": chain,
        "buy_count": 1, "sell_count": 1 if is_closed else 0,
        "buy_usd": 100.0, "sell_usd": 100.0 * (pnl_ratio or 1) if is_closed else 0.0,
        "avg_buy_price": 1.0, "avg_sell_price": pnl_ratio if is_closed else None,
        "pnl_ratio": pnl_ratio if is_closed else None,
        "realized_pnl_usd": 100.0 * ((pnl_ratio or 1) - 1) if is_closed else 0.0,
        "d3_pct": d3, "first_executed_at": "2026-04-30T10:00:00Z",
        "is_closed": is_closed, "strategy_id": "s-1",
    }


# ── _parse_llm_json ─────────────────────────────────────────

def test_parse_llm_json_clean():
    r = review_engine._parse_llm_json('{"a":1,"b":"x"}')
    assert r == {"a": 1, "b": "x"}


def test_parse_llm_json_with_markdown_fence():
    raw = "```json\n{\"a\":1}\n```"
    r = review_engine._parse_llm_json(raw)
    assert r == {"a": 1}


def test_parse_llm_json_with_leading_text():
    raw = '解释:这是结果\n{"headline":"hi","body":"x"}\nover.'
    r = review_engine._parse_llm_json(raw)
    assert r == {"headline": "hi", "body": "x"}


def test_parse_llm_json_invalid_returns_none():
    assert review_engine._parse_llm_json("not a json") is None
    assert review_engine._parse_llm_json("") is None


# ── generate_review v2 LLM 路径 ─────────────────────────────

@pytest.mark.asyncio
async def test_v2_llm_success_uses_llm_summary():
    """LLM 成功时,review 标 source=llm 且用 LLM 文案。"""
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text='{"headline":"📈 LLM headline","body":"LLM body 三段","tone":"celebratory"}')]
    fake_resp.usage.input_tokens = 1000
    fake_resp.usage.output_tokens = 200

    fake_client = MagicMock()
    fake_client.messages.create = MagicMock(return_value=fake_resp)
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = fake_client

    trades = [_trade(f"w{i}", "SOL", 1.3) for i in range(8)] + [_trade(f"l{i}", "SOL", 0.8) for i in range(2)]

    with patch.object(review_engine, "_load_trades", AsyncMock(return_value=trades)), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        r = await review_engine.generate_review(period="weekly", use_llm=True)

    assert r["source"] == "llm"
    assert r["summary"]["headline"] == "📈 LLM headline"
    assert r["summary"]["body"] == "LLM body 三段"
    assert r["summary"]["tone"] == "celebratory"
    assert r["review_id"].startswith("v2-")


@pytest.mark.asyncio
async def test_v2_llm_failure_falls_back_to_rule_engine():
    """LLM 抛错 → 降级到 rule_engine summary。"""
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.side_effect = Exception("API timeout")

    trades = [_trade(f"a{i}", "SOL", 1.2) for i in range(8)]
    with patch.object(review_engine, "_load_trades", AsyncMock(return_value=trades)), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        r = await review_engine.generate_review(period="daily", use_llm=True)

    assert r["source"] == "rule_engine"
    # rule_engine summary 含周期前缀
    assert "今日" in r["summary"]["headline"]
    assert r["review_id"].startswith("v1-")


@pytest.mark.asyncio
async def test_v2_no_api_key_falls_back():
    """无 ANTHROPIC_API_KEY → 降级。"""
    trades = [_trade(f"a{i}", "SOL", 1.1) for i in range(8)]
    # 显式清除 env
    with patch.object(review_engine, "_load_trades", AsyncMock(return_value=trades)), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
        r = await review_engine.generate_review(period="daily", use_llm=True)
    assert r["source"] == "rule_engine"


@pytest.mark.asyncio
async def test_v2_use_llm_false_skips_llm():
    """use_llm=False 直接走 rule_engine 不调 Claude。"""
    fake_anthropic = MagicMock()  # 真调到会抛 / 但应该不会调到
    fake_anthropic.Anthropic.side_effect = AssertionError("LLM should not be called")

    trades = [_trade(f"a{i}", "SOL", 1.1) for i in range(8)]
    with patch.object(review_engine, "_load_trades", AsyncMock(return_value=trades)), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        r = await review_engine.generate_review(period="daily", use_llm=False)
    assert r["source"] == "rule_engine"


@pytest.mark.asyncio
async def test_v2_no_trades_skips_llm_directly():
    """trade_count=0 → cold_start=no_trades → 不调 LLM(节省 token)。"""
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.side_effect = AssertionError("LLM should not be called")

    with patch.object(review_engine, "_load_trades", AsyncMock(return_value=[])), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        r = await review_engine.generate_review(period="daily", use_llm=True)
    assert r["source"] == "rule_engine"
    assert r["cold_start_state"] == "no_trades"


@pytest.mark.asyncio
async def test_v2_llm_returns_invalid_json_falls_back():
    """LLM 返不是 JSON → 降级,不报错。"""
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="抱歉我不能输出 JSON")]
    fake_resp.usage.input_tokens = 100
    fake_resp.usage.output_tokens = 50
    fake_client = MagicMock()
    fake_client.messages.create = MagicMock(return_value=fake_resp)
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = fake_client

    trades = [_trade(f"a{i}", "SOL", 1.2) for i in range(8)]
    with patch.object(review_engine, "_load_trades", AsyncMock(return_value=trades)), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        r = await review_engine.generate_review(period="daily", use_llm=True)
    assert r["source"] == "rule_engine"


@pytest.mark.asyncio
async def test_v2_llm_returns_partial_json_falls_back():
    """LLM 返 JSON 但缺 headline → 降级。"""
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text='{"tone":"neutral"}')]  # 缺 headline+body
    fake_resp.usage.input_tokens = 100
    fake_resp.usage.output_tokens = 20
    fake_client = MagicMock()
    fake_client.messages.create = MagicMock(return_value=fake_resp)
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = fake_client

    trades = [_trade(f"a{i}", "SOL", 1.2) for i in range(8)]
    with patch.object(review_engine, "_load_trades", AsyncMock(return_value=trades)), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        r = await review_engine.generate_review(period="daily", use_llm=True)
    assert r["source"] == "rule_engine"


@pytest.mark.asyncio
async def test_v2_llm_truncates_overlong_output():
    """LLM 返超长 body → 裁剪到 600 字。"""
    long_body = "A" * 2000
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text=f'{{"headline":"hi","body":"{long_body}"}}')]
    fake_resp.usage.input_tokens = 100
    fake_resp.usage.output_tokens = 500
    fake_client = MagicMock()
    fake_client.messages.create = MagicMock(return_value=fake_resp)
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = fake_client

    trades = [_trade(f"a{i}", "SOL", 1.2) for i in range(8)]
    with patch.object(review_engine, "_load_trades", AsyncMock(return_value=trades)), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        r = await review_engine.generate_review(period="daily", use_llm=True)
    assert r["source"] == "llm"
    assert len(r["summary"]["body"]) <= 600
