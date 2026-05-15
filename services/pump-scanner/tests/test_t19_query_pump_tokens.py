"""
R68 — T19 query_pump_tokens 单测

跑法:python3 -m pytest tests/test_t19_query_pump_tokens.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _mk_signal(symbol="TEST", score=70, bc_pct=15, vol=5000, mcap=300000,
               age_min: float = 30):
    """构造一条 pump signal mock。"""
    detected_at = (datetime.now(timezone.utc) - timedelta(minutes=age_min)).isoformat()
    return {
        "symbol": symbol,
        "name": f"{symbol} Token",
        "address": f"Mint{symbol}",
        "score": score,
        "bonding_curve_pct": bc_pct,
        "price_usd": 0.00001,
        "market_cap_usd": mcap,
        "volume_24h_usd": vol,
        "price_change_24h": 50,
        "detected_at": detected_at,
    }


@pytest.mark.asyncio
async def test_t19_metadata():
    from agent.tools.t19_query_pump_tokens import QueryPumpTokensTool
    tool = QueryPumpTokensTool()
    meta = tool.metadata
    assert meta.name == "query_pump_tokens"
    assert meta.cost_usd == 0.0
    assert meta.idempotent is True
    assert "pump.fun" in meta.description


@pytest.mark.asyncio
async def test_t19_input_schema_validation_ok():
    """合法 payload 通过 input schema 校验。"""
    from agent.tools.t19_query_pump_tokens import QueryPumpTokensTool
    tool = QueryPumpTokensTool()
    # 全空 payload(走默认) — fetch 内部会 return empty 不报错
    with patch.object(tool, "_fetch_signal_pool", return_value=([], "empty", False)):
        res = await tool.run({})
        assert res.ok is True
        assert res.output["items"] == []
        assert res.output["source_used"] == "empty"


@pytest.mark.asyncio
async def test_t19_filter_by_score_bc_volume():
    """score < 55 / BC 超范围 / vol < min 都被过滤。"""
    from agent.tools.t19_query_pump_tokens import QueryPumpTokensTool
    tool = QueryPumpTokensTool()
    signals = [
        _mk_signal("PASS", score=80, bc_pct=20, vol=5000),  # 通过
        _mk_signal("LOWSCORE", score=40, bc_pct=20, vol=5000),  # score 低
        _mk_signal("BCLOW", score=80, bc_pct=1, vol=5000),  # BC 低
        _mk_signal("BCHIGH", score=80, bc_pct=60, vol=5000),  # BC 高
        _mk_signal("LOWVOL", score=80, bc_pct=20, vol=100),  # vol 低
    ]
    with patch.object(tool, "_fetch_signal_pool", return_value=(signals, "scanner", False)):
        res = await tool.run({
            "min_score": 55, "bc_min": 3, "bc_max": 35, "min_volume_usd": 1000,
        })
    assert res.ok
    items = res.output["items"]
    assert len(items) == 1
    assert items[0]["symbol"] == "PASS"


@pytest.mark.asyncio
async def test_t19_sort_by_score():
    """sort_by=score → 高分排前。"""
    from agent.tools.t19_query_pump_tokens import QueryPumpTokensTool
    tool = QueryPumpTokensTool()
    signals = [
        _mk_signal("A", score=60, bc_pct=10),
        _mk_signal("B", score=90, bc_pct=10),
        _mk_signal("C", score=75, bc_pct=10),
    ]
    with patch.object(tool, "_fetch_signal_pool", return_value=(signals, "scanner", False)):
        res = await tool.run({"sort_by": "score"})
    items = res.output["items"]
    assert [it["symbol"] for it in items] == ["B", "C", "A"]
    # rank 是 1, 2, 3
    assert items[0]["rank"] == 1
    assert items[1]["rank"] == 2


@pytest.mark.asyncio
async def test_t19_sort_by_detected_age():
    """sort_by=detected_age → 最新检测(age 最小)排前。"""
    from agent.tools.t19_query_pump_tokens import QueryPumpTokensTool
    tool = QueryPumpTokensTool()
    signals = [
        _mk_signal("OLD", score=70, age_min=120),
        _mk_signal("NEW", score=70, age_min=5),
        _mk_signal("MID", score=70, age_min=30),
    ]
    with patch.object(tool, "_fetch_signal_pool", return_value=(signals, "redis", False)):
        res = await tool.run({"sort_by": "detected_age"})
    items = res.output["items"]
    assert items[0]["symbol"] == "NEW"
    assert items[2]["symbol"] == "OLD"


@pytest.mark.asyncio
async def test_t19_age_minutes_computed():
    """age_minutes 从 detected_at 算出来。"""
    from agent.tools.t19_query_pump_tokens import QueryPumpTokensTool
    tool = QueryPumpTokensTool()
    signals = [_mk_signal("X", age_min=15)]
    with patch.object(tool, "_fetch_signal_pool", return_value=(signals, "scanner", False)):
        res = await tool.run({})
    age = res.output["items"][0]["age_minutes"]
    # 给点容差(测试运行时间会比构造时间晚一点)
    assert 14.5 <= age <= 16.0


@pytest.mark.asyncio
async def test_t19_limit_clamped():
    """limit 上限 50,超出 reject(input schema)。"""
    from agent.tools.t19_query_pump_tokens import QueryPumpTokensTool
    tool = QueryPumpTokensTool()
    res = await tool.run({"limit": 100})
    assert res.ok is False
    assert "schema" in (res.error or "").lower() or "100" in (res.error or "")


@pytest.mark.asyncio
async def test_t19_empty_pool_reason():
    """空池返 friendly reason。"""
    from agent.tools.t19_query_pump_tokens import QueryPumpTokensTool
    tool = QueryPumpTokensTool()
    with patch.object(tool, "_fetch_signal_pool", return_value=([], "empty", False)):
        res = await tool.run({})
    assert res.ok
    assert res.output["total"] == 0
    assert "无实时信号" in (res.output.get("reason") or "")


def test_chat_loop_pump_intent_keywords():
    """_matches_pump_tokens_intent 命中 pump.fun / 毕业 / BC / 新币 等。"""
    from agent.loops.chat_loop import _matches_pump_tokens_intent
    assert _matches_pump_tokens_intent("看下 pump.fun 最新有什么") is True
    assert _matches_pump_tokens_intent("毕业进度 10-20% 的代币") is True
    assert _matches_pump_tokens_intent("pump 新币 score>70") is True
    assert _matches_pump_tokens_intent("bonding curve 还在 30% 以下") is True
    # 不应命中(纯策略意图):
    assert _matches_pump_tokens_intent("建一个 pump.fun 监控策略") is False
    # 不应命中(完全无 pump 相关):
    assert _matches_pump_tokens_intent("BTC 现在价格") is False


def test_chat_loop_bc_range_detection():
    """_detect_bc_range 从文本抽 BC 范围。"""
    from agent.loops.chat_loop import _detect_bc_range
    assert _detect_bc_range("毕业进度 10-20%") == (10.0, 20.0)
    assert _detect_bc_range("BC 5%-25% 范围") == (5.0, 25.0)
    assert _detect_bc_range("一般查询") == (3.0, 35.0)  # 默认
