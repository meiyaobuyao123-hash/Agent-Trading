"""
T18 query_top_movers 单元测试 — R39
跑法:python3 -m pytest tests/test_t18_query_top_movers.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tools import get_tool_registry
from agent.tools.t18_query_top_movers import QueryTopMoversTool


# ── metadata + schema ────────────────────────────────────────


def test_t18_metadata_ok():
    tool = QueryTopMoversTool()
    m = tool.metadata
    assert m.name == "query_top_movers"
    assert m.idempotent is True
    assert m.cost_usd == 0.0
    assert "INPUT_SCHEMA_INVALID" in m.failure_modes


def test_t18_input_schema_defaults():
    tool = QueryTopMoversTool()
    s = tool.input_schema
    assert s["properties"]["source"]["default"] == "all"
    assert s["properties"]["window"]["default"] == "24h"
    assert s["properties"]["limit"]["default"] == 10
    assert s["properties"]["sort_by"]["default"] == "pct_change"


def test_t18_in_registry_18_total():
    """R39:registry 应有 18 tools(原 17 + T18)。"""
    reg = get_tool_registry()
    assert "query_top_movers" in reg
    assert len(reg) == 18


# ── input validation ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_t18_invalid_source():
    tool = QueryTopMoversTool()
    res = await tool.run({"source": "invalid_source"})
    assert res.ok is False
    assert res.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t18_invalid_window():
    tool = QueryTopMoversTool()
    res = await tool.run({"window": "100y"})
    assert res.ok is False
    assert res.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t18_limit_over_max():
    tool = QueryTopMoversTool()
    res = await tool.run({"limit": 1000})
    assert res.ok is False
    assert res.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t18_additional_property_rejected():
    tool = QueryTopMoversTool()
    res = await tool.run({"unknown_field": 1})
    assert res.ok is False
    assert res.failure_mode == "INPUT_SCHEMA_INVALID"


# ── happy paths(mocked DB)────────────────────────────────


def _mock_hot_coins(items: list[dict]):
    """构造 Supabase chain mock for hot_coins query。"""
    db = MagicMock()
    chain_mock = MagicMock()
    chain_mock.execute.return_value.data = items
    table = MagicMock()
    # .table().select().eq().eq().eq().gte().not_.is_().order().limit().execute()
    table.select.return_value.eq.return_value.eq.return_value.eq.return_value \
        .gte.return_value.not_.is_.return_value.order.return_value.limit.return_value = chain_mock
    db.table.return_value = table
    return db


@pytest.mark.asyncio
async def test_t18_hot_only_returns_items():
    tool = QueryTopMoversTool()
    items = [
        {"chain": "solana", "address": "AAA", "symbol": "ALPHA", "name": "Alpha",
         "score": 80, "price_usd": 0.001, "market_cap_usd": 500000, "liquidity_usd": 50000,
         "price_change_24h": 0.45, "volume_24h_usd": 100000,
         "price_change_5m": 0.05, "price_change_1h": 0.15, "price_change_6h": 0.30,
         "volume_5m_usd": 1000, "volume_1h_usd": 5000,
         "goplus_risk": False, "is_honeypot": False},
    ]
    db = _mock_hot_coins(items)
    with patch("database.get_db", return_value=db):
        res = await tool.run({"source": "hot", "chain": "solana", "limit": 5})
    assert res.ok is True
    out = res.output
    assert out["ok"] is True
    assert out["total"] == 1
    assert out["items"][0]["symbol"] == "ALPHA"
    assert out["items"][0]["pct_change"] == 0.45
    assert out["items"][0]["rank"] == 1
    assert out["items"][0]["source"] == "hot"


@pytest.mark.asyncio
async def test_t18_empty_db_returns_empty_ok():
    tool = QueryTopMoversTool()
    db = _mock_hot_coins([])
    # pump_signals 也 mock 成 empty
    with patch("database.get_db", return_value=db):
        res = await tool.run({"source": "all"})
    assert res.ok is True
    assert res.output["ok"] is True
    assert res.output["total"] == 0
    assert res.output["items"] == []
    assert "no data" in res.output.get("reason", "")


@pytest.mark.asyncio
async def test_t18_db_error_swallowed():
    """DB 抛 → 不抛,返 empty + ok=true(failure mode 不是 schema)。"""
    tool = QueryTopMoversTool()
    db = MagicMock()
    db.table.side_effect = RuntimeError("PG down")
    with patch("database.get_db", return_value=db):
        res = await tool.run({"source": "hot"})
    # 当前实施:DB 异常 swallow,返 empty(因为 chat 用例下不应阻塞)
    assert res.ok is True
    assert res.output["total"] == 0


@pytest.mark.asyncio
async def test_t18_sort_by_volume():
    tool = QueryTopMoversTool()
    items = [
        {"chain": "solana", "address": "A1", "symbol": "ONE",
         "price_change_24h": 0.10, "volume_24h_usd": 1000000, "score": 50,
         "market_cap_usd": 0, "liquidity_usd": 0, "goplus_risk": False, "is_honeypot": False,
         "price_change_5m": 0, "price_change_1h": 0, "price_change_6h": 0, "name": "One",
         "price_usd": 1, "volume_5m_usd": 0, "volume_1h_usd": 0},
        {"chain": "solana", "address": "A2", "symbol": "TWO",
         "price_change_24h": 0.50, "volume_24h_usd": 5000, "score": 60,
         "market_cap_usd": 0, "liquidity_usd": 0, "goplus_risk": False, "is_honeypot": False,
         "price_change_5m": 0, "price_change_1h": 0, "price_change_6h": 0, "name": "Two",
         "price_usd": 1, "volume_5m_usd": 0, "volume_1h_usd": 0},
    ]
    db = _mock_hot_coins(items)
    with patch("database.get_db", return_value=db):
        res = await tool.run({"source": "hot", "chain": "solana",
                              "sort_by": "volume", "limit": 5})
    # ONE 体量大 → rank 1
    assert res.ok is True
    assert res.output["items"][0]["symbol"] == "ONE"


# ── pump source semantics ───────────────────────────────────


@pytest.mark.asyncio
async def test_t18_pump_only_non_solana_returns_empty():
    """pump.fun 是 solana only,chain=eth/bsc/base 时 pump 部分必空。"""
    tool = QueryTopMoversTool()
    db = _mock_hot_coins([])
    with patch("database.get_db", return_value=db):
        res = await tool.run({"source": "pump", "chain": "eth"})
    assert res.ok is True
    assert res.output["total"] == 0


# ── description quality ─────────────────────────────────────


def test_t18_description_mentions_keywords():
    """description 必须含 chat 触发关键词,LLM 选 tool 才准。"""
    desc = QueryTopMoversTool().metadata.description
    for kw in ["pump", "涨", "top movers", "近期"]:
        assert kw in desc, f"description 缺关键词:{kw}"
