"""
R42 P0.2 — trade_executor 接 risk_params 测试

覆盖 TradeExecutor.execute_trade(risk_params=...):
  - max_position_usd 强制限仓(超出截断)
  - max_slippage_pct 真用(覆盖入参 slippage)
  - priority_fee_sol / mev_bribe_sol 透传给 dex_router
  - risk_params=None → 用默认值
  - risk_params 缺字段 → 各自用默认值
  - safety BLOCK 优先于 risk_params

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_trade_executor_risk_params.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def fake_router():
    """模拟 dex_router.execute 返成功 RouteResult"""
    from agent.dex_router import RouteResult
    router = MagicMock()
    router.execute = AsyncMock(return_value=RouteResult(
        success=True,
        tx_hash="fake_tx_hash",
        from_amount=50.0,
        to_amount=50000.0,
        price=0.001,
        gas_fee=0.0005,
        chain="solana",
        token_address="SoMeT0kEn",
        action="buy",
        dex_used="jupiter",
    ))
    return router


@pytest.fixture
def executor():
    from agent.trade_executor import TradeExecutor
    return TradeExecutor()


# ═════════════════════════════════════════════════════════
# risk_params 真用
# ═════════════════════════════════════════════════════════

class TestRiskParamsWiring:

    @pytest.mark.asyncio
    async def test_max_position_caps_amount(self, executor, fake_router):
        """amount_usd > max_position_usd → 截断"""
        with patch("agent.dex_router.get_dex_router", return_value=fake_router):
            await executor.execute_trade(
                chain="solana", token_address="SoMeT0kEn", action="buy",
                amount_usd=500.0,
                risk_params={"max_position_usd": 50.0},
            )
        # 验证 dex_router 收到的 amount 被截断为 50
        call_kwargs = fake_router.execute.call_args.kwargs
        assert call_kwargs["amount_usd"] == 50.0

    @pytest.mark.asyncio
    async def test_max_position_does_not_increase(self, executor, fake_router):
        """amount_usd < max_position_usd → 不变"""
        with patch("agent.dex_router.get_dex_router", return_value=fake_router):
            await executor.execute_trade(
                chain="solana", token_address="SoMeT0kEn", action="buy",
                amount_usd=20.0,
                risk_params={"max_position_usd": 100.0},
            )
        assert fake_router.execute.call_args.kwargs["amount_usd"] == 20.0

    @pytest.mark.asyncio
    async def test_max_slippage_overrides_param(self, executor, fake_router):
        """risk_params.max_slippage_pct=0.025 → dex_router 收 slippage_pct=2.5"""
        with patch("agent.dex_router.get_dex_router", return_value=fake_router):
            await executor.execute_trade(
                chain="solana", token_address="x", action="buy", amount_usd=10,
                slippage_pct=1.0,  # 入参 1%
                risk_params={"max_slippage_pct": 0.025},  # risk_params 覆盖到 2.5%
            )
        assert fake_router.execute.call_args.kwargs["slippage_pct"] == 2.5

    @pytest.mark.asyncio
    async def test_priority_fee_passed_to_router(self, executor, fake_router):
        with patch("agent.dex_router.get_dex_router", return_value=fake_router):
            await executor.execute_trade(
                chain="solana", token_address="x", action="buy", amount_usd=10,
                risk_params={"priority_fee_sol": 0.005},
            )
        assert fake_router.execute.call_args.kwargs["priority_fee_sol"] == 0.005

    @pytest.mark.asyncio
    async def test_mev_bribe_passed_to_router(self, executor, fake_router):
        with patch("agent.dex_router.get_dex_router", return_value=fake_router):
            await executor.execute_trade(
                chain="solana", token_address="x", action="buy", amount_usd=10,
                risk_params={"mev_bribe_sol": 0.003},
            )
        assert fake_router.execute.call_args.kwargs["mev_bribe_sol"] == 0.003

    @pytest.mark.asyncio
    async def test_risk_params_none_uses_defaults(self, executor, fake_router):
        """risk_params=None → 默认值(priority=0.0005, mev=0, max_pos=1000)"""
        with patch("agent.dex_router.get_dex_router", return_value=fake_router):
            await executor.execute_trade(
                chain="solana", token_address="x", action="buy", amount_usd=10,
            )
        kw = fake_router.execute.call_args.kwargs
        assert kw["priority_fee_sol"] == 0.0005
        assert kw["mev_bribe_sol"] == 0.0
        assert kw["amount_usd"] == 10  # 没截断

    @pytest.mark.asyncio
    async def test_risk_params_partial_fills_with_defaults(self, executor, fake_router):
        """只传 max_position,其他用默认"""
        with patch("agent.dex_router.get_dex_router", return_value=fake_router):
            await executor.execute_trade(
                chain="solana", token_address="x", action="buy", amount_usd=10,
                risk_params={"max_position_usd": 200},
            )
        kw = fake_router.execute.call_args.kwargs
        assert kw["priority_fee_sol"] == 0.0005
        assert kw["mev_bribe_sol"] == 0.0


# ═════════════════════════════════════════════════════════
# Safety 优先级
# ═════════════════════════════════════════════════════════

class TestSafetyOverrides:

    @pytest.mark.asyncio
    async def test_safety_block_overrides_risk_params(self, executor, fake_router):
        """safety BLOCK 即使 risk_params 合法也被拦,且不调 dex_router"""
        # check_safety_for_trade 返一个有 rule_id + reason 的对象 → BLOCK
        fake_block = MagicMock()
        fake_block.rule_id = "HR01"
        fake_block.reason = "amount over $500"
        with patch("agent.dex_router.get_dex_router", return_value=fake_router), \
             patch("agent.trade_executor.check_safety_for_trade", return_value=fake_block):
            result = await executor.execute_trade(
                chain="solana", token_address="x", action="buy", amount_usd=10,
                safety_ctx={"daily_total_usd": 0},
                risk_params={"max_position_usd": 50},
            )
        assert not result.success
        assert "HR01" in result.error
        fake_router.execute.assert_not_called()
