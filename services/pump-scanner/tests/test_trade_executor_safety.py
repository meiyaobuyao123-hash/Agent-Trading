"""
TradeExecutor Safety 集成测试 — W3 D3
覆盖:
  check_safety_for_trade 纯函数 helper
  execute_trade(safety_ctx=...) 接入
    - None: 不影响原流程(本测不真调 DEX,只 verify safety 不阻断)
    - 命中 HR: 不调 dex_router,返回 success=False
    - 命中 active CB: 不调 dex_router,返回 success=False
    - 干净 ctx: 跑完 safety 后继续走 DEX(mocked)
  SafetyEngine 故障 → fail-safe BLOCK

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_trade_executor_safety.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.safety_engine import (  # noqa: E402
    CheckOutcome,
    SafetyEngine,
    get_safety_engine,
    reset_safety_engine_singleton,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def fresh_singleton():
    """每个测试一个全新 SafetyEngine 单例"""
    reset_safety_engine_singleton()
    yield
    reset_safety_engine_singleton()


@pytest.fixture
def base_safety_ctx() -> dict:
    """合规 ctx(应通过所有 HR)"""
    return {
        "amount_usd": 100.0, "daily_total_usd": 200.0, "monthly_total_usd": 1000.0,
        "strategy_position_pct": 0.05, "chain_concentration_pct": 0.20,
        "open_position_count": 5, "liquidity_usd": 50000.0,
        "buy_tax_pct": 0.02, "sell_tax_pct": 0.02, "is_honeypot": False,
        "auth_single_trade_max": 500.0, "credentials_revoked_at": None,
        "kms_unavailable": False, "holders_count": 2000, "top10_pct": 0.40,
        "price_change_24h_pct": 0.05, "regime": "TRENDING_UP", "action": "buy",
        "daily_loss_usd": 0, "weekly_loss_usd": 0, "consecutive_losses": 0,
        "max_drawdown_pct": 0.05, "token_address": "Mock", "blacklist_tokens": [],
        "seconds_since_last_trade": 600, "trades_last_hour": 1,
        "slippage_pct": 0.005, "max_slippage_pct": 0.05,
        "hitl_required": False, "hitl_approved": True,
        "strategy_stage": "saved", "copy_target_wallet": None,
        "blacklist_wallets": [], "token_age_seconds": 86400 * 7,
        "mode": "paper", "user_quota_exhausted": False,
        "agent_global_state": "normal",
    }


# ============================================================
# 1. check_safety_for_trade 纯函数 helper
# ============================================================

class TestCheckHelper:

    def test_clean_ctx_returns_none(self, base_safety_ctx):
        from agent.trade_executor import check_safety_for_trade
        block = check_safety_for_trade(base_safety_ctx)
        assert block is None

    def test_amount_over_returns_block(self, base_safety_ctx):
        from agent.trade_executor import check_safety_for_trade
        base_safety_ctx["amount_usd"] = 1000  # > $500
        block = check_safety_for_trade(base_safety_ctx)
        assert block is not None
        assert block.rule_id == "HR01"
        assert block.outcome == CheckOutcome.BLOCK

    def test_blacklist_returns_block(self, base_safety_ctx):
        from agent.trade_executor import check_safety_for_trade
        base_safety_ctx["token_address"] = "Bad"
        base_safety_ctx["blacklist_tokens"] = ["Bad"]
        block = check_safety_for_trade(base_safety_ctx)
        assert block is not None
        assert block.rule_id == "HR21"

    def test_honeypot_returns_block(self, base_safety_ctx):
        from agent.trade_executor import check_safety_for_trade
        base_safety_ctx["is_honeypot"] = True
        block = check_safety_for_trade(base_safety_ctx)
        assert block is not None
        assert block.rule_id == "HR09"

    def test_engine_failure_failsafe(self, base_safety_ctx):
        """SafetyEngine 自身故障 → fail-safe CB12 BLOCK"""
        from agent import trade_executor as te

        with patch("agent.safety_engine.get_safety_engine") as mock_get:
            mock_get.side_effect = RuntimeError("yaml gone")
            block = te.check_safety_for_trade(base_safety_ctx)
            assert block is not None
            assert block.rule_id == "CB12"


# ============================================================
# 2. execute_trade(safety_ctx=...) 接入
# ============================================================

class TestExecuteTradeSafety:

    @pytest.mark.asyncio
    async def test_no_ctx_falls_through(self, monkeypatch):
        """safety_ctx=None 时不跑 safety,直接走 DEX(被 mock)"""
        from agent.trade_executor import TradeExecutor, TradeResult
        from agent import dex_router as dr

        executor = TradeExecutor()
        mock_router = MagicMock()
        mock_router.execute = AsyncMock(return_value=MagicMock(
            success=True, tx_hash="0xMOCK", from_amount=100.0, to_amount=99.0,
            price=1.0, gas_fee=0.001, error=None, dex_used="jupiter",
            fallback_used=False, split_count=1,
        ))
        monkeypatch.setattr(dr, "get_dex_router", lambda: mock_router)
        monkeypatch.setattr("config.USE_AVE", False, raising=False)

        result = await executor.execute_trade(
            chain="solana", token_address="Mock", action="buy",
            amount_usd=100.0,
            # safety_ctx not passed
        )
        # 应该正常走 DEX(mock 返回 success)
        assert result.success is True
        assert result.tx_hash == "0xMOCK"
        # router 应被调
        mock_router.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_amount_block_skips_dex(self, monkeypatch, base_safety_ctx):
        """safety_ctx 命中 HR01 → 不调 DEX 直接返回失败"""
        from agent.trade_executor import TradeExecutor
        from agent import dex_router as dr

        executor = TradeExecutor()
        mock_router = MagicMock()
        mock_router.execute = AsyncMock()  # 不应被调
        monkeypatch.setattr(dr, "get_dex_router", lambda: mock_router)
        monkeypatch.setattr("config.USE_AVE", False, raising=False)

        base_safety_ctx["amount_usd"] = 100  # ctx 内的 amount(< 500)
        result = await executor.execute_trade(
            chain="solana", token_address="Mock", action="buy",
            amount_usd=1000.0,  # 实际交易超 $500 → safety_ctx 重写后命中 HR01
            safety_ctx=base_safety_ctx,
        )
        assert result.success is False
        assert "HR01" in (result.error or "")
        assert "safety BLOCKED" in (result.error or "")
        # router 不应被调
        mock_router.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_active_cb_skips_dex(self, monkeypatch, base_safety_ctx):
        """先 trip CB → execute_trade 直接 BLOCK"""
        from agent.trade_executor import TradeExecutor
        from agent import dex_router as dr

        # 先 trip CB
        engine = get_safety_engine()
        engine.trip_breaker("CB01", reason="test setup")
        assert engine.is_breaker_active("CB01")

        executor = TradeExecutor()
        mock_router = MagicMock()
        mock_router.execute = AsyncMock()
        monkeypatch.setattr(dr, "get_dex_router", lambda: mock_router)
        monkeypatch.setattr("config.USE_AVE", False, raising=False)

        result = await executor.execute_trade(
            chain="solana", token_address="Mock", action="buy",
            amount_usd=50.0, safety_ctx=base_safety_ctx,
        )
        assert result.success is False
        assert "CB01" in (result.error or "")
        mock_router.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_clean_ctx_passes_to_dex(self, monkeypatch, base_safety_ctx):
        """safety_ctx 干净 → 跑完 safety 后继续走 DEX"""
        from agent.trade_executor import TradeExecutor
        from agent import dex_router as dr

        executor = TradeExecutor()
        mock_router = MagicMock()
        mock_router.execute = AsyncMock(return_value=MagicMock(
            success=True, tx_hash="0xCLEAN", from_amount=50.0, to_amount=49.0,
            price=1.0, gas_fee=0.001, error=None, dex_used="jupiter",
            fallback_used=False, split_count=1,
        ))
        monkeypatch.setattr(dr, "get_dex_router", lambda: mock_router)
        monkeypatch.setattr("config.USE_AVE", False, raising=False)

        result = await executor.execute_trade(
            chain="solana", token_address="Mock", action="buy",
            amount_usd=50.0, safety_ctx=base_safety_ctx,
        )
        assert result.success is True
        assert result.tx_hash == "0xCLEAN"
        mock_router.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_hitl_required_unapproved_block(self, monkeypatch, base_safety_ctx):
        from agent.trade_executor import TradeExecutor
        from agent import dex_router as dr

        executor = TradeExecutor()
        mock_router = MagicMock()
        mock_router.execute = AsyncMock()
        monkeypatch.setattr(dr, "get_dex_router", lambda: mock_router)
        monkeypatch.setattr("config.USE_AVE", False, raising=False)

        base_safety_ctx["hitl_required"] = True
        base_safety_ctx["hitl_approved"] = False

        result = await executor.execute_trade(
            chain="solana", token_address="Mock", action="buy",
            amount_usd=50.0, safety_ctx=base_safety_ctx,
        )
        assert result.success is False
        assert "HR25" in (result.error or "")
        mock_router.execute.assert_not_called()
