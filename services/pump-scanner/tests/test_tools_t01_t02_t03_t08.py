"""
T01/T02/T03/T08 4 个新包装 Tool 单元测试 — R35

跑法:python3 -m pytest tests/test_tools_t01_t02_t03_t08.py -v

设计:
  - 不真调外部 API(OKX / Helius / DEX)
  - mock 现有底层函数(okx_market_client.batch_price_info / fetch_top_holders /
    smart_money_signals DB / TradeExecutor.execute_trade)
  - 验 input_schema / output_schema 校验生效
  - 验 fail_modes 各种路径
  - T08 必含 wallet_address / private_key 缺失保护测试
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tools.t01_query_market import QueryMarketTool  # noqa: E402
from agent.tools.t02_query_holders import QueryHoldersTool  # noqa: E402
from agent.tools.t03_query_onchain_activity import QueryOnchainActivityTool  # noqa: E402
from agent.tools.t08_execute_swap import ExecuteSwapTool  # noqa: E402


# ── T01 query_market ────────────────────────────────────────


class TestQueryMarket:

    def setup_method(self):
        self.tool = QueryMarketTool()

    def test_metadata_basic(self):
        m = self.tool.metadata
        assert m.name == "query_market"
        assert m.idempotent is True
        assert "OKX_API_ERROR" in m.failure_modes
        assert m.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_missing_required_action_input_invalid(self):
        result = await self.tool.run({"chain": "solana"})
        assert result.failure_mode == "INPUT_SCHEMA_INVALID"

    @pytest.mark.asyncio
    async def test_unknown_action_input_invalid(self):
        result = await self.tool.run({"action": "weird", "chain": "solana"})
        assert result.failure_mode == "INPUT_SCHEMA_INVALID"

    @pytest.mark.asyncio
    async def test_unknown_chain_input_invalid(self):
        result = await self.tool.run({"action": "price", "chain": "polygon"})
        assert result.failure_mode == "INPUT_SCHEMA_INVALID"

    @pytest.mark.asyncio
    async def test_price_action_no_token_returns_ok_false(self):
        result = await self.tool.run({"action": "price", "chain": "solana"})
        # token_address 缺 → ok=true(schema 通过)+ output.ok=False
        assert result.ok is True
        assert result.output["ok"] is False
        assert "token_address required" in result.output["reason"]

    @pytest.mark.asyncio
    async def test_price_action_with_mock_okx(self):
        with patch("okx_market_client.batch_price_info",
                   new=AsyncMock(return_value={
                       "0xabc": {"lastPriceUsd": 1.23, "marketCap": 1000000}
                   })):
            result = await self.tool.run({
                "action": "price", "chain": "solana", "token_address": "0xABC",
            })
        assert result.ok is True
        assert result.output["ok"] is True
        assert result.output["data"]["lastPriceUsd"] == 1.23

    @pytest.mark.asyncio
    async def test_candles_action_with_mock(self):
        fake_candles = [{"ts": 1000, "open": 1.0, "close": 1.1,
                          "high": 1.2, "low": 0.9, "vol": 100, "volUsd": 110}]
        with patch("okx_market_client.get_candles",
                   new=AsyncMock(return_value=fake_candles)):
            result = await self.tool.run({
                "action": "candles", "chain": "solana",
                "token_address": "0xabc", "bar": "1H", "limit": 50,
            })
        assert result.ok is True
        assert result.output["ok"] is True
        assert len(result.output["data"]) == 1


# ── T02 query_holders ───────────────────────────────────────


class TestQueryHolders:

    def setup_method(self):
        self.tool = QueryHoldersTool()

    def test_metadata(self):
        m = self.tool.metadata
        assert m.name == "query_holders"
        assert m.idempotent is True

    @pytest.mark.asyncio
    async def test_missing_token_address_invalid(self):
        result = await self.tool.run({"chain": "solana"})
        assert result.failure_mode == "INPUT_SCHEMA_INVALID"

    @pytest.mark.asyncio
    async def test_concentration_warning_when_top10_high(self):
        fake_holders = [{"rank": i+1, "wallet": f"w{i}", "pct": 8.0}
                         for i in range(10)]
        # top10_pct = 80 > 60% red line
        with patch("hot_coin_fetcher.fetch_top_holders",
                   new=AsyncMock(return_value=fake_holders)):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
            })
        assert result.ok is True
        assert result.output["ok"] is True
        assert result.output["concentration_warning"] is True
        assert result.output["top10_pct"] == 80.0

    @pytest.mark.asyncio
    async def test_no_warning_when_concentration_low(self):
        fake_holders = [{"rank": i+1, "wallet": f"w{i}", "pct": 3.0}
                         for i in range(10)]
        # top10 = 30 < 60
        with patch("hot_coin_fetcher.fetch_top_holders",
                   new=AsyncMock(return_value=fake_holders)):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
            })
        assert result.output["concentration_warning"] is False

    @pytest.mark.asyncio
    async def test_empty_holders_returns_ok_false(self):
        with patch("hot_coin_fetcher.fetch_top_holders",
                   new=AsyncMock(return_value=[])):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
            })
        assert result.output["ok"] is False
        assert result.output["reason"] == "empty_result"

    @pytest.mark.asyncio
    async def test_fetch_exception_returns_ok_false(self):
        with patch("hot_coin_fetcher.fetch_top_holders",
                   new=AsyncMock(side_effect=RuntimeError("api down"))):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
            })
        assert result.output["ok"] is False
        assert "fetch_failed" in result.output["reason"]


# ── T03 query_onchain_activity ───────────────────────────────


class TestQueryOnchainActivity:

    def setup_method(self):
        self.tool = QueryOnchainActivityTool()

    def test_metadata(self):
        m = self.tool.metadata
        assert m.name == "query_onchain_activity"
        assert m.idempotent is True

    @pytest.mark.asyncio
    async def test_missing_chain_invalid(self):
        result = await self.tool.run({"token_address": "0xabc"})
        assert result.failure_mode == "INPUT_SCHEMA_INVALID"

    @pytest.mark.asyncio
    async def test_db_query_with_strong_signal(self):
        fake_db = MagicMock()
        fake_resp = MagicMock()
        fake_resp.data = [{
            "net_flow": 80000, "elite_buy_count": 5, "elite_sell_count": 0,
            "buy_count": 20, "sell_count": 5, "unique_buyers": 15,
            "signal_strength": "strong", "heat_score": 90,
        }]
        fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = fake_resp

        with patch("database.get_db", return_value=fake_db):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
            })
        assert result.output["ok"] is True
        assert result.output["smart_money_net_usd"] == 80000
        assert result.output["big_buy_warning"] is True  # elite=5 + net+
        assert result.output["signal_strength"] == "strong"

    @pytest.mark.asyncio
    async def test_no_big_buy_when_elite_low(self):
        fake_db = MagicMock()
        fake_resp = MagicMock()
        fake_resp.data = [{
            "net_flow": 50000, "elite_buy_count": 1,
            "signal_strength": "weak", "heat_score": 20,
        }]
        fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = fake_resp

        with patch("database.get_db", return_value=fake_db):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
            })
        assert result.output["big_buy_warning"] is False

    @pytest.mark.asyncio
    async def test_empty_db_returns_ok_false(self):
        fake_db = MagicMock()
        fake_resp = MagicMock()
        fake_resp.data = []
        fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = fake_resp

        with patch("database.get_db", return_value=fake_db):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
            })
        assert result.output["ok"] is False
        assert result.output["reason"] == "empty_result"


# ── T08 execute_swap (高风险路径,严测)────────────────────────


class TestExecuteSwap:

    def setup_method(self):
        self.tool = ExecuteSwapTool()

    def test_metadata_non_idempotent(self):
        m = self.tool.metadata
        assert m.name == "execute_swap"
        assert m.idempotent is False  # 真金交易非幂等
        assert "MISSING_PRIVATE_KEY" in m.failure_modes
        assert "SAFETY_BLOCKED" in m.failure_modes

    @pytest.mark.asyncio
    async def test_missing_wallet_address_input_invalid(self):
        result = await self.tool.run({
            "chain": "solana", "token_address": "0xabc",
            "action": "buy", "amount_usd": 50,
            "private_key": "secret",
        })
        # schema 校验 → wallet_address required
        assert result.failure_mode == "INPUT_SCHEMA_INVALID"

    @pytest.mark.asyncio
    async def test_missing_private_key_input_invalid(self):
        result = await self.tool.run({
            "chain": "solana", "token_address": "0xabc",
            "action": "buy", "amount_usd": 50,
            "wallet_address": "wallet1",
        })
        assert result.failure_mode == "INPUT_SCHEMA_INVALID"

    @pytest.mark.asyncio
    async def test_amount_too_small_input_invalid(self):
        result = await self.tool.run({
            "chain": "solana", "token_address": "0xabc",
            "action": "buy", "amount_usd": 0.5,  # < $1 框架硬下限
            "wallet_address": "w", "private_key": "k",
        })
        assert result.failure_mode == "INPUT_SCHEMA_INVALID"

    @pytest.mark.asyncio
    async def test_amount_too_large_input_invalid(self):
        result = await self.tool.run({
            "chain": "solana", "token_address": "0xabc",
            "action": "buy", "amount_usd": 50000,  # > $10000 框架硬上限
            "wallet_address": "w", "private_key": "k",
        })
        assert result.failure_mode == "INPUT_SCHEMA_INVALID"

    @pytest.mark.asyncio
    async def test_invalid_action_invalid(self):
        result = await self.tool.run({
            "chain": "solana", "token_address": "0xabc",
            "action": "swap",  # 不在 buy/sell
            "amount_usd": 50, "wallet_address": "w", "private_key": "k",
        })
        assert result.failure_mode == "INPUT_SCHEMA_INVALID"

    @pytest.mark.asyncio
    async def test_successful_swap_returns_tx_hash(self):
        from agent.trade_executor import TradeResult
        fake_result = TradeResult(
            success=True, tx_hash="0xtx123",
            from_amount=50, to_amount=42, price=1.19, gas_fee=0.5,
            chain="solana", token_address="0xabc", action="buy",
        )
        fake_executor = MagicMock()
        fake_executor.execute_trade = AsyncMock(return_value=fake_result)
        fake_executor.close = AsyncMock()

        with patch("agent.trade_executor.TradeExecutor",
                   return_value=fake_executor):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
                "action": "buy", "amount_usd": 50,
                "wallet_address": "wallet-x", "private_key": "secret-key",
            })
        assert result.ok is True
        assert result.output["success"] is True
        assert result.output["tx_hash"] == "0xtx123"
        assert result.output["exec_price"] == 1.19

    @pytest.mark.asyncio
    async def test_safety_blocked_returns_safety_blocked_reason(self):
        from agent.trade_executor import TradeResult
        fake_result = TradeResult(
            success=False,
            error="safety BLOCKED: HR01 - amount > $500",
            chain="solana", token_address="0xabc", action="buy",
        )
        fake_executor = MagicMock()
        fake_executor.execute_trade = AsyncMock(return_value=fake_result)
        fake_executor.close = AsyncMock()

        with patch("agent.trade_executor.TradeExecutor",
                   return_value=fake_executor):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
                "action": "buy", "amount_usd": 600,
                "wallet_address": "w", "private_key": "k",
                "safety_ctx": {"agent_global_state": "normal"},
            })
        assert result.output["success"] is False
        assert result.output["reason"] == "safety_blocked"

    @pytest.mark.asyncio
    async def test_dex_route_failure_returns_dex_route_failed(self):
        from agent.trade_executor import TradeResult
        fake_result = TradeResult(
            success=False, error="no liquidity",
            chain="solana", token_address="0xabc", action="buy",
        )
        fake_executor = MagicMock()
        fake_executor.execute_trade = AsyncMock(return_value=fake_result)
        fake_executor.close = AsyncMock()

        with patch("agent.trade_executor.TradeExecutor",
                   return_value=fake_executor):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
                "action": "buy", "amount_usd": 50,
                "wallet_address": "w", "private_key": "k",
            })
        assert result.output["success"] is False
        assert result.output["reason"] == "dex_route_failed"

    @pytest.mark.asyncio
    async def test_executor_exception_returns_executor_exception(self):
        with patch("agent.trade_executor.TradeExecutor",
                   side_effect=RuntimeError("import boom")):
            result = await self.tool.run({
                "chain": "solana", "token_address": "0xabc",
                "action": "buy", "amount_usd": 50,
                "wallet_address": "w", "private_key": "k",
            })
        assert result.output["success"] is False
        assert "executor_exception" in result.output["reason"]


# ── 联合验证:registry 17/17 ────────────────────────────────


def test_registry_has_17_tools():
    """R35 完成判定:17/17 Tool 全实施。"""
    from agent.tools import get_tool_registry
    registry = get_tool_registry()
    assert len(registry) == 17
    expected = {
        "query_market", "query_holders", "query_onchain_activity",
        "execute_swap",
        "recall_memory", "list_strategies", "update_strategy_status",
        "run_paper_trade", "create_approval_request", "get_paper_performance",
        "approve_rule", "save_strategy", "send_push_notification",
        "calc_technical_indicators", "calc_risk_metrics", "run_backtest",
        "calc_position_size",
    }
    assert set(registry.keys()) == expected
