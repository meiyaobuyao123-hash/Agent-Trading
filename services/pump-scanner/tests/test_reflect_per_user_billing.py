"""
R47 P9 — Reflect Loop per-user 计费 单测

覆盖:
  - reflection.run_reflection 调 credit_service.deduct(user_id)
  - DEV bypass user(00000000-...0001)不扣费
  - run_per_user_cycle 余额不足跳过

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_reflect_per_user_billing.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.memory.reflection import ReflectionEngine, REFLECTION_MODEL  # noqa: E402
from agent.loops.reflect_loop import ReflectLoop, ReflectResult  # noqa: E402


# ═════════════════════════════════════════════════════════
# 1. reflection.run_reflection 调 credit_service.deduct
# ═════════════════════════════════════════════════════════


def _make_anthropic_response(
    text: str = '{"winning_pattern":"a","losing_pattern":"b","new_rules":[],"summary":"ok"}',
    in_tokens: int = 1234,
    out_tokens: int = 56,
):
    """构造一个伪 anthropic.messages.create 返回对象。"""
    fake = MagicMock()
    block = MagicMock()
    block.text = text
    fake.content = [block]
    usage = MagicMock()
    usage.input_tokens = in_tokens
    usage.output_tokens = out_tokens
    fake.usage = usage
    return fake


@pytest.mark.asyncio
async def test_run_reflection_calls_credit_deduct():
    """R47 P9 — 真用户调反思 → credit_service.deduct 被调一次。"""
    eng = ReflectionEngine()
    eng._api_key = "test-key"

    fake_response = _make_anthropic_response(in_tokens=1000, out_tokens=200)
    fake_client = MagicMock()
    fake_client.messages.create = MagicMock(return_value=fake_response)
    fake_anthropic_module = MagicMock()
    fake_anthropic_module.Anthropic = MagicMock(return_value=fake_client)

    fake_credit_module = MagicMock()
    fake_credit_module.deduct = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "anthropic": fake_anthropic_module,
            "agent.credit_service": fake_credit_module,
        },
    ):
        result = await eng.run_reflection(
            trades=[{"token_address": "X", "pnl_pct": 1.0}],
            active_rules=[],
            user_id="user-real-uuid",
            trigger="daily",
        )

    assert result is not None
    fake_credit_module.deduct.assert_called_once()
    kwargs = fake_credit_module.deduct.call_args.kwargs
    assert kwargs["user_id"] == "user-real-uuid"
    assert kwargs["model"] == REFLECTION_MODEL
    assert kwargs["tokens_in"] == 1000
    assert kwargs["tokens_out"] == 200
    assert kwargs["request_id"] == "reflect:daily"


@pytest.mark.asyncio
async def test_dev_user_bypass_no_deduct():
    """R47 P9 — DEV bypass user(00000000-...0001)不扣费。"""
    eng = ReflectionEngine()
    eng._api_key = "test-key"

    fake_response = _make_anthropic_response()
    fake_client = MagicMock()
    fake_client.messages.create = MagicMock(return_value=fake_response)
    fake_anthropic_module = MagicMock()
    fake_anthropic_module.Anthropic = MagicMock(return_value=fake_client)

    fake_credit_module = MagicMock()
    fake_credit_module.deduct = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "anthropic": fake_anthropic_module,
            "agent.credit_service": fake_credit_module,
        },
    ):
        await eng.run_reflection(
            trades=[{"token_address": "X", "pnl_pct": 1.0}],
            active_rules=[],
            user_id="00000000-0000-0000-0000-000000000001",
            trigger="daily",
        )

    fake_credit_module.deduct.assert_not_called()


@pytest.mark.asyncio
async def test_no_user_id_no_deduct():
    """user_id=None(跨用户聚合 / admin)→ 不扣费。"""
    eng = ReflectionEngine()
    eng._api_key = "test-key"

    fake_response = _make_anthropic_response()
    fake_client = MagicMock()
    fake_client.messages.create = MagicMock(return_value=fake_response)
    fake_anthropic_module = MagicMock()
    fake_anthropic_module.Anthropic = MagicMock(return_value=fake_client)

    fake_credit_module = MagicMock()
    fake_credit_module.deduct = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "anthropic": fake_anthropic_module,
            "agent.credit_service": fake_credit_module,
        },
    ):
        await eng.run_reflection(
            trades=[{"token_address": "X", "pnl_pct": 1.0}],
            active_rules=[],
            user_id=None,
        )

    fake_credit_module.deduct.assert_not_called()


# ═════════════════════════════════════════════════════════
# 2. run_per_user_cycle 余额 gate
# ═════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_run_per_user_cycle_skips_insufficient_balance():
    """R47 P9 — 一半 user 余额不足 → 实际只反思另一半。"""
    loop = ReflectLoop()

    # mock db 返 4 个 distinct user
    fake_query = MagicMock()
    fake_query.select.return_value = fake_query
    fake_query.gte.return_value = fake_query
    fake_query.limit.return_value = fake_query
    fake_query.execute.return_value = MagicMock(
        data=[
            {"user_id": "user-a"},
            {"user_id": "user-b"},
            {"user_id": "user-c"},
            {"user_id": "user-d"},
            {"user_id": "user-a"},  # 重复(测 dedup)
        ]
    )
    fake_db = MagicMock()
    fake_db.table.return_value = fake_query
    fake_db_module = MagicMock()
    fake_db_module.get_db = MagicMock(return_value=fake_db)

    # mock credit_service: 一半通过、一半拒
    def fake_can_proceed(uid, *args, **kwargs):
        if uid in ("user-a", "user-b"):
            return True, None
        return False, "余额不足"

    fake_credit_module = MagicMock()
    fake_credit_module.can_proceed = MagicMock(side_effect=fake_can_proceed)

    # mock self.run_cycle 返 ReflectResult
    async def fake_run_cycle(device_id=None, trigger="daily", lookback_days=7):
        return ReflectResult(
            ok=True, trigger=trigger, trades_analyzed=5, promoted=1,
        )

    with patch.dict(
        sys.modules,
        {
            "database": fake_db_module,
            "agent.credit_service": fake_credit_module,
        },
    ), patch.object(loop, "run_cycle", side_effect=fake_run_cycle) as mock_rc:
        results = await loop.run_per_user_cycle(trigger="daily", lookback_days=7)

    # 只 a, b 跑(c, d 被余额 gate 拒)
    assert len(results) == 2
    assert mock_rc.call_count == 2
    called_uids = {c.kwargs.get("device_id") for c in mock_rc.call_args_list}
    assert called_uids == {"user-a", "user-b"}


@pytest.mark.asyncio
async def test_run_per_user_cycle_empty_when_no_trades():
    """没 trade → 没 user_id → 返空 list。"""
    loop = ReflectLoop()

    fake_query = MagicMock()
    fake_query.select.return_value = fake_query
    fake_query.gte.return_value = fake_query
    fake_query.limit.return_value = fake_query
    fake_query.execute.return_value = MagicMock(data=[])
    fake_db = MagicMock()
    fake_db.table.return_value = fake_query
    fake_db_module = MagicMock()
    fake_db_module.get_db = MagicMock(return_value=fake_db)

    fake_credit_module = MagicMock()
    fake_credit_module.can_proceed = MagicMock(return_value=(True, None))

    with patch.dict(
        sys.modules,
        {
            "database": fake_db_module,
            "agent.credit_service": fake_credit_module,
        },
    ):
        results = await loop.run_per_user_cycle(trigger="daily")

    assert results == []
    fake_credit_module.can_proceed.assert_not_called()


# ═════════════════════════════════════════════════════════
# 3. 向后兼容:run_reflection 不传 user_id 仍工作
# ═════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_backward_compat_no_user_id_kwarg():
    """老调用方式不传 user_id/trigger 仍能跑(默认参数)。"""
    eng = ReflectionEngine()
    eng._api_key = "test-key"

    fake_response = _make_anthropic_response()
    fake_client = MagicMock()
    fake_client.messages.create = MagicMock(return_value=fake_response)
    fake_anthropic_module = MagicMock()
    fake_anthropic_module.Anthropic = MagicMock(return_value=fake_client)

    with patch.dict(sys.modules, {"anthropic": fake_anthropic_module}):
        result = await eng.run_reflection(
            trades=[{"token_address": "X", "pnl_pct": 1.0}],
            active_rules=[],
        )

    assert result is not None
    assert result.get("summary") == "ok"
