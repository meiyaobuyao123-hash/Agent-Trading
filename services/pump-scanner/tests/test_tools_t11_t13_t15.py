"""
Tool 单元测试:T11 approve_rule / T13 send_push_notification / T15 calc_risk_metrics
W3 D5+

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_tools_t11_t13_t15.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tools import (  # noqa: E402
    ApproveRuleTool,
    CalcRiskMetricsTool,
    SendPushNotificationTool,
    get_tool_registry,
)


# ── Registry ────────────────────────────────────────────────

def test_registry_has_three_tools():
    reg = get_tool_registry()
    assert "approve_rule" in reg
    assert "send_push_notification" in reg
    assert "calc_risk_metrics" in reg


def test_registry_tools_have_anthropic_spec():
    """每个 Tool 应该能产出 Anthropic tool_use spec。"""
    reg = get_tool_registry()
    for name, tool in reg.items():
        spec = tool.to_anthropic_tool_spec()
        assert spec["name"] == name
        assert spec["description"]
        assert "input_schema" in spec


# ── T15 calc_risk_metrics ───────────────────────────────────

@pytest.mark.asyncio
async def test_t15_empty_trades():
    tool = CalcRiskMetricsTool()
    r = await tool.run({"trades": []})
    assert r.ok is True
    assert r.output["trade_count"] == 0
    assert r.output["win_rate"] == 0.0


@pytest.mark.asyncio
async def test_t15_all_wins():
    tool = CalcRiskMetricsTool()
    trades = [
        {"is_closed": True, "pnl_ratio": 1.5, "d3_pct": 50}
        for _ in range(5)
    ]
    r = await tool.run({"trades": trades})
    assert r.ok is True
    assert r.output["trade_count"] == 5
    assert r.output["win_rate"] == 1.0
    assert r.output["ev_pct"] == 50.0
    assert r.output["wilson_ci_lower"] is not None  # 5 笔有 CI


@pytest.mark.asyncio
async def test_t15_open_positions_use_d3():
    tool = CalcRiskMetricsTool()
    trades = [
        {"is_closed": False, "pnl_ratio": None, "d3_pct": 25},
        {"is_closed": False, "pnl_ratio": None, "d3_pct": 15},
        {"is_closed": False, "pnl_ratio": None, "d3_pct": 30},
    ]
    r = await tool.run({"trades": trades})
    assert r.ok is True
    assert r.output["trade_count"] == 3
    # 2/3 D3 ≥ 20 → win_rate = 0.667
    assert abs(r.output["win_rate"] - 0.667) < 0.001


@pytest.mark.asyncio
async def test_t15_input_schema_validation():
    tool = CalcRiskMetricsTool()
    r = await tool.run({"foo": "bar"})  # 没 trades 字段
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t15_metadata():
    tool = CalcRiskMetricsTool()
    m = tool.metadata
    assert m.name == "calc_risk_metrics"
    assert m.idempotent is True
    assert m.cost_usd == 0.0


# ── T13 send_push_notification ──────────────────────────────

@pytest.mark.asyncio
async def test_t13_invalid_category():
    tool = SendPushNotificationTool()
    r = await tool.run({
        "user_id": "u-1",
        "title": "Test",
        "body": "hi",
        "category": "wrong_category",
    })
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t13_strategy_triggered_with_id():
    tool = SendPushNotificationTool()
    with patch("agent.push_service.send_push", AsyncMock(return_value=2)):
        r = await tool.run({
            "user_id": "u-1",
            "title": "策略触发",
            "body": "TRUMP 触发跟单策略",
            "category": "strategy_triggered",
            "params": {"strategy_id": "s-1"},
        })
    assert r.ok is True
    assert r.output["sent_count"] == 2
    assert r.output["deep_link"] == "aitrading://strategy/s-1"
    assert r.output["category"] == "strategy_triggered"


@pytest.mark.asyncio
async def test_t13_review_ready_default_period():
    tool = SendPushNotificationTool()
    with patch("agent.push_service.send_push", AsyncMock(return_value=1)):
        r = await tool.run({
            "user_id": "u-1",
            "title": "今日复盘",
            "body": "请查看",
            "category": "review_ready",
        })
    assert r.ok is True
    assert "aitrading://review/" in r.output["deep_link"]


@pytest.mark.asyncio
async def test_t13_send_push_zero_when_no_devices():
    tool = SendPushNotificationTool()
    with patch("agent.push_service.send_push", AsyncMock(return_value=0)):
        r = await tool.run({
            "user_id": "u-noexist",
            "title": "x", "body": "x", "category": "system",
        })
    assert r.ok is True
    assert r.output["sent_count"] == 0


@pytest.mark.asyncio
async def test_t13_metadata_marked_non_idempotent():
    tool = SendPushNotificationTool()
    assert tool.metadata.idempotent is False
    assert tool.metadata.side_effects.value == "push"


# ── T11 approve_rule ────────────────────────────────────────

@pytest.mark.asyncio
async def test_t11_input_validation_missing_condition():
    tool = ApproveRuleTool()
    r = await tool.run({
        "user_id": "u-1",
        "proposal_id": "rp-1",
        "human_readable": "test rule",
        "formal_condition": {"condition": "x>1"},  # 缺 action
    })
    assert r.ok is False
    assert r.failure_mode == "INPUT_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_t11_inserts_new_rule_with_shadow_mode():
    tool = ApproveRuleTool()
    fake_db = MagicMock()
    # 幂等检查返空(不是 duplicate)
    fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    # insert 返成功
    fake_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "x"}])

    with patch("database.get_db", return_value=fake_db):
        r = await tool.run({
            "user_id": "u-1",
            "proposal_id": "rp-001",
            "human_readable": "RANGING regime BC<8 禁开仓",
            "formal_condition": {"condition": "regime=RANGING AND bc<8", "action": "block_entry"},
            "active_regimes": ["RANGING"],
            "evidence": {"sample_size": 22, "win_rate_diff": 12.4, "wilson_ci_lower": 0.58},
        })
    assert r.ok is True
    assert r.output["ok"] is True
    assert r.output["shadow_mode_days"] == 14
    assert r.output["duplicate"] is False
    # 验证 insert 被调用
    fake_db.table.return_value.insert.assert_called_once()
    inserted = fake_db.table.return_value.insert.call_args.args[0]
    assert inserted["type"] == "semantic"
    assert inserted["is_active"] is True
    assert "shadow_mode_until" in inserted
    assert inserted["structured_data"]["source_proposal_id"] == "rp-001"


@pytest.mark.asyncio
async def test_t11_idempotent_returns_existing():
    tool = ApproveRuleTool()
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "existing-uuid", "shadow_mode_until": "2026-05-15T00:00:00+00:00"}]
    )
    with patch("database.get_db", return_value=fake_db):
        r = await tool.run({
            "user_id": "u-1",
            "proposal_id": "rp-001",
            "human_readable": "同一规则再调一次",
            "formal_condition": {"condition": "x", "action": "y"},
        })
    assert r.ok is True
    assert r.output["duplicate"] is True
    assert r.output["promoted_rule_id"] == "existing-uuid"
    # insert 应当没被调用
    fake_db.table.return_value.insert.assert_not_called()


@pytest.mark.asyncio
async def test_t11_db_failure_returns_execute_error():
    tool = ApproveRuleTool()
    with patch("database.get_db", side_effect=Exception("DB down")):
        r = await tool.run({
            "user_id": "u-1",
            "proposal_id": "rp-1",
            "human_readable": "valid rule text",  # ≥ 5 chars
            "formal_condition": {"condition": "x", "action": "y"},
        })
    assert r.ok is False
    assert r.failure_mode == "EXECUTE_ERROR"


@pytest.mark.asyncio
async def test_t11_anthropic_spec():
    tool = ApproveRuleTool()
    spec = tool.to_anthropic_tool_spec()
    assert spec["name"] == "approve_rule"
    assert "Shadow Mode" in spec["description"]
    assert "user_id" in spec["input_schema"]["required"]
    assert "formal_condition" in spec["input_schema"]["required"]
