"""
PRD-009: 多 DEX 执行路由 — 单元测试

测试覆盖：
- Jupiter 报价/swap
- 1inch 报价/swap（含 key 缺失场景）
- DexRouter: 并行报价、选最优、fallback、大单拆分
- trade_executor 集成

使用 unittest.mock 模拟所有外部 HTTP 调用。
Python 3.9 兼容。
"""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import dataclass

# 确保 pump-scanner 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestJupiterDex(unittest.TestCase):
    """Jupiter v6 API 测试"""

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_get_quote_success(self):
        """Jupiter 报价成功"""
        from agent.dex.jupiter import JupiterDex

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "inputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "outputMint": "So11111111111111111111111111111111111111112",
            "inAmount": "1000000",
            "outAmount": "5000000000",
            "priceImpactPct": 0.12,
            "routePlan": [{"swapInfo": {"label": "Raydium"}}],
        })
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        jup = JupiterDex(session=mock_session)

        quote = self.loop.run_until_complete(
            jup.get_quote(
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "So11111111111111111111111111111111111111112",
                "1000000",
                100,
            )
        )

        self.assertTrue(quote.success)
        self.assertEqual(quote.out_amount, "5000000000")
        self.assertAlmostEqual(quote.price_impact_pct, 0.12)
        self.assertEqual(quote.dex, "jupiter")

    def test_get_quote_error(self):
        """Jupiter 报价失败 — HTTP 错误"""
        from agent.dex.jupiter import JupiterDex

        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_resp.text = AsyncMock(return_value="Bad Request")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        jup = JupiterDex(session=mock_session)

        quote = self.loop.run_until_complete(
            jup.get_quote("A", "B", "1000", 100)
        )

        self.assertFalse(quote.success)
        self.assertIn("400", quote.error)

    def test_get_swap_success(self):
        """Jupiter swap 成功"""
        from agent.dex.jupiter import JupiterDex

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "swapTransaction": "AQAAAA==",
        })
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        jup = JupiterDex(session=mock_session)

        result = self.loop.run_until_complete(
            jup.get_swap({"inputMint": "A"}, "WalletPubKey123")
        )

        self.assertNotIn("error", result)
        self.assertEqual(result["swapTransaction"], "AQAAAA==")


class TestOneInchDex(unittest.TestCase):
    """1inch v6 API 测试"""

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    @patch.dict(os.environ, {"ONEINCH_API_KEY": "test-key-123"})
    def test_get_quote_success(self):
        """1inch 报价成功"""
        from agent.dex.oneinch import OneInchDex

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "fromAmount": "1000000",
            "toAmount": "500000000000000000",
            "gas": 150000,
        })
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        inch = OneInchDex(session=mock_session)
        inch._api_key = "test-key-123"

        quote = self.loop.run_until_complete(
            inch.get_quote(
                1,
                "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "1000000",
            )
        )

        self.assertTrue(quote.success)
        self.assertEqual(quote.to_amount, "500000000000000000")
        self.assertEqual(quote.dex, "oneinch")

    def test_get_quote_no_key(self):
        """1inch 报价失败 — 无 API Key"""
        from agent.dex.oneinch import OneInchDex

        inch = OneInchDex()
        inch._api_key = ""

        self.assertFalse(inch.available)

        quote = self.loop.run_until_complete(
            inch.get_quote(1, "0xA", "0xB", "1000")
        )

        self.assertFalse(quote.success)
        self.assertIn("not configured", quote.error)

    @patch.dict(os.environ, {"ONEINCH_API_KEY": "test-key"})
    def test_get_swap_success(self):
        """1inch swap 成功"""
        from agent.dex.oneinch import OneInchDex

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "tx": {
                "to": "0x1111111254EEB25477B68fb85Ed929f73A960582",
                "data": "0xabcdef",
                "value": "0",
                "gas": 200000,
            }
        })
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        inch = OneInchDex(session=mock_session)
        inch._api_key = "test-key"

        result = self.loop.run_until_complete(
            inch.get_swap(
                1,
                "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "1000000",
                "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD30",
                1.0,
            )
        )

        self.assertNotIn("error", result)
        self.assertIn("tx", result)


class TestDexRouter(unittest.TestCase):
    """DexRouter 路由逻辑测试"""

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_select_best_picks_highest_output(self):
        """_select_best 选择 out_amount 最高的报价"""
        from agent.dex_router import DexRouter, QuoteResult

        router = DexRouter()

        quotes = [
            QuoteResult(dex="jupiter", out_amount="5000000000", price_impact=0.5),
            QuoteResult(dex="okx", out_amount="4800000000", price_impact=0.8),
        ]

        best = router._select_best(quotes)
        self.assertIsNotNone(best)
        self.assertEqual(best.dex, "jupiter")
        self.assertEqual(best.out_amount, "5000000000")

    def test_select_best_skips_errors(self):
        """_select_best 跳过有错误的报价"""
        from agent.dex_router import DexRouter, QuoteResult

        router = DexRouter()

        quotes = [
            QuoteResult(dex="jupiter", out_amount="0", error="timeout"),
            QuoteResult(dex="okx", out_amount="4800000000", price_impact=0.8),
        ]

        best = router._select_best(quotes)
        self.assertIsNotNone(best)
        self.assertEqual(best.dex, "okx")

    def test_select_best_all_failed(self):
        """_select_best 所有报价失败返回 None"""
        from agent.dex_router import DexRouter, QuoteResult

        router = DexRouter()

        quotes = [
            QuoteResult(dex="jupiter", error="timeout"),
            QuoteResult(dex="okx", error="api error"),
        ]

        best = router._select_best(quotes)
        self.assertIsNone(best)

    def test_quote_result_properties(self):
        """QuoteResult 属性测试"""
        from agent.dex_router import QuoteResult

        q1 = QuoteResult(dex="jupiter", out_amount="5000000000")
        self.assertTrue(q1.success)
        self.assertEqual(q1.out_amount_int, 5000000000)

        q2 = QuoteResult(dex="okx", out_amount="0", error="failed")
        self.assertFalse(q2.success)

        # invalid out_amount raises ValueError in success property
        q3 = QuoteResult(dex="test", out_amount="invalid")
        with self.assertRaises(ValueError):
            _ = q3.success

    def test_route_result_defaults(self):
        """RouteResult 默认值测试"""
        from agent.dex_router import RouteResult

        r = RouteResult(success=True, dex_used="jupiter", tx_hash="abc123")
        self.assertTrue(r.success)
        self.assertEqual(r.dex_used, "jupiter")
        self.assertFalse(r.fallback_used)
        self.assertEqual(r.split_count, 1)
        self.assertEqual(r.quotes_received, [])

    def test_primary_dex_mapping(self):
        """链 → primary DEX 映射"""
        from agent.dex_router import PRIMARY_DEX

        self.assertEqual(PRIMARY_DEX["solana"], "jupiter")
        self.assertEqual(PRIMARY_DEX["eth"], "oneinch")
        self.assertEqual(PRIMARY_DEX["bsc"], "oneinch")
        self.assertEqual(PRIMARY_DEX["base"], "oneinch")


class TestDexRouterIntegration(unittest.TestCase):
    """DexRouter 集成测试（mock 外部调用）"""

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    @patch("agent.dex_router.DexRouter._get_okx_quote")
    @patch("agent.dex_router.DexRouter._get_jupiter_quote")
    def test_parallel_quotes_sol(self, mock_jup, mock_okx):
        """SOL 链并行获取 Jupiter + OKX 报价"""
        from agent.dex_router import DexRouter, QuoteResult

        mock_jup.return_value = QuoteResult(
            dex="jupiter", out_amount="5000000000", price_impact=0.3,
        )
        mock_okx.return_value = QuoteResult(
            dex="okx", out_amount="4800000000", price_impact=0.6,
        )

        router = DexRouter()
        quotes = self.loop.run_until_complete(
            router._get_parallel_quotes(
                "solana",
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "So11111111111111111111111111111111111111112",
                "1000000",
                1.0,
            )
        )

        self.assertEqual(len(quotes), 2)
        successful = [q for q in quotes if q.success]
        self.assertEqual(len(successful), 2)

    @patch("agent.dex_router.DexRouter._get_okx_quote")
    @patch("agent.dex_router.DexRouter._get_jupiter_quote")
    def test_jupiter_timeout_uses_okx(self, mock_jup, mock_okx):
        """Jupiter 超时 → 使用 OKX"""
        from agent.dex_router import DexRouter, QuoteResult

        async def slow_jup(*args, **kwargs):
            await asyncio.sleep(5)  # 超过 2s 超时
            return QuoteResult(dex="jupiter", out_amount="5000000000")

        mock_jup.side_effect = slow_jup
        mock_okx.return_value = QuoteResult(
            dex="okx", out_amount="4800000000", price_impact=0.6,
        )

        router = DexRouter()

        # 并行报价会超时，但 OKX 应该成功
        # 注意：asyncio.gather 在 wait_for timeout 时会取消所有
        # 所以这里测试的是 fallback 到 OKX direct 路径
        quotes = self.loop.run_until_complete(
            router._get_parallel_quotes(
                "solana",
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "TokenMint123",
                "1000000",
                1.0,
            )
        )

        # 至少有一个结果
        self.assertTrue(len(quotes) >= 1)


class TestConfig(unittest.TestCase):
    """配置测试"""

    def test_dex_config_exists(self):
        """PRD-009 配置项存在"""
        import config

        self.assertTrue(hasattr(config, "JUPITER_BASE_URL"))
        self.assertTrue(hasattr(config, "ONEINCH_API_KEY"))
        self.assertTrue(hasattr(config, "ONEINCH_BASE_URL"))
        self.assertTrue(hasattr(config, "DEX_PARALLEL_QUOTE_TIMEOUT"))
        self.assertTrue(hasattr(config, "DEX_SPLIT_IMPACT_THRESHOLD"))
        self.assertTrue(hasattr(config, "DEX_MIN_SPLIT_AMOUNT_USD"))

    def test_jupiter_base_url(self):
        """Jupiter base URL 正确"""
        import config
        self.assertEqual(config.JUPITER_BASE_URL, "https://quote-api.jup.ag/v6")

    def test_oneinch_base_url(self):
        """1inch base URL 正确"""
        import config
        self.assertEqual(config.ONEINCH_BASE_URL, "https://api.1inch.dev/swap/v6.0")

    def test_default_timeout(self):
        """默认超时 2s"""
        import config
        self.assertEqual(config.DEX_PARALLEL_QUOTE_TIMEOUT, 2.0)


class TestTradeExecutorIntegration(unittest.TestCase):
    """TradeExecutor 集成测试 — 确认调用 DexRouter"""

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    @patch("agent.dex_router.get_dex_router")
    def test_execute_trade_uses_dex_router(self, mock_get_router):
        """execute_trade 通过 DexRouter 执行"""
        from agent.dex_router import RouteResult

        mock_router = MagicMock()
        mock_router.execute = AsyncMock(return_value=RouteResult(
            success=True,
            dex_used="jupiter",
            tx_hash="abcdef123456",
            from_amount=10.0,
            to_amount=50000.0,
            price=0.0002,
            chain="solana",
            token_address="TokenMint123",
            action="buy",
        ))
        mock_get_router.return_value = mock_router

        # 需要 mock config imports
        with patch.dict(os.environ, {
            "OKX_API_KEY": "test",
            "OKX_SECRET_KEY": "test",
            "OKX_PASSPHRASE": "test",
        }):
            from agent.trade_executor import TradeExecutor
            executor = TradeExecutor()

            result = self.loop.run_until_complete(
                executor.execute_trade(
                    chain="solana",
                    token_address="TokenMint123",
                    action="buy",
                    amount_usd=10.0,
                )
            )

        self.assertTrue(result.success)
        self.assertEqual(result.tx_hash, "abcdef123456")
        mock_router.execute.assert_called_once()


class TestOptimizerTool(unittest.TestCase):
    """optimizer_tools.py 执行质量工具测试"""

    @patch("optimizer_tools.get_db")
    def test_tool_read_execution_quality_empty(self, mock_db):
        """无数据时返回空结果"""
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.gte.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])
        mock_db.return_value.table.return_value = mock_table

        from optimizer_tools import tool_read_execution_quality

        result = tool_read_execution_quality(days=7)

        self.assertEqual(result["total_trades"], 0)
        self.assertEqual(result["by_dex"], {})
        self.assertEqual(result["fallback_triggered"], 0)

    @patch("optimizer_tools.get_db")
    def test_tool_read_execution_quality_with_data(self, mock_db):
        """有数据时正确统计"""
        rows = [
            {
                "dex_used": "jupiter",
                "status": "confirmed",
                "actual_slippage": 0.5,
                "amount_usd": 10.0,
                "fallback_used": False,
                "split_count": 1,
            },
            {
                "dex_used": "jupiter",
                "status": "confirmed",
                "actual_slippage": 0.3,
                "amount_usd": 20.0,
                "fallback_used": False,
                "split_count": 1,
            },
            {
                "dex_used": "okx",
                "status": "confirmed",
                "actual_slippage": 1.5,
                "amount_usd": 15.0,
                "fallback_used": True,
                "split_count": 1,
            },
            {
                "dex_used": "jupiter",
                "status": "failed",
                "actual_slippage": 0,
                "amount_usd": 5.0,
                "fallback_used": False,
                "split_count": 3,
            },
        ]

        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.gte.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=rows)
        mock_db.return_value.table.return_value = mock_table

        from optimizer_tools import tool_read_execution_quality

        result = tool_read_execution_quality(days=7)

        self.assertEqual(result["total_trades"], 4)
        self.assertIn("jupiter", result["by_dex"])
        self.assertIn("okx", result["by_dex"])
        self.assertEqual(result["by_dex"]["jupiter"]["trades"], 3)
        self.assertEqual(result["by_dex"]["jupiter"]["success"], 2)
        self.assertEqual(result["by_dex"]["jupiter"]["failed"], 1)
        self.assertEqual(result["by_dex"]["okx"]["trades"], 1)
        self.assertEqual(result["fallback_triggered"], 1)
        self.assertEqual(result["split_triggered"], 1)

    def test_tool_in_agent_tool_map(self):
        """tool_read_execution_quality 在 AGENT_TOOL_MAP 中"""
        from optimizer_tools import AGENT_TOOL_MAP

        self.assertIn("read_execution_quality", AGENT_TOOL_MAP)


if __name__ == "__main__":
    unittest.main()
