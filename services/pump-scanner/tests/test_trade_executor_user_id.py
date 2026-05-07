"""
R47 P5 — trade_executor user_id 透传 + DRY_RUN_LIVE_TRADES 单测

audit 发现:
  ActionDispatcher → executor.execute_trade(无 user_id)
    → _resolve_wallet(user_id=None)
    → 跳过 user_wallets DB → 走 env → env 没配 → live 必断

R47 P5 修:user_id 从 event 透传到 _resolve_wallet,优先 user_wallets AES 解密路径。
+ DRY_RUN_LIVE_TRADES env 拦截真发链上,只 mock 成功(给运维 trace 验证用)。

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_trade_executor_user_id.py -v
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ═════════════════════════════════════════════════════════
# 1. _resolve_wallet user_id 路径
# ═════════════════════════════════════════════════════════

class TestResolveWallet:
    def test_resolve_uses_user_id_to_decrypt_first(self):
        """user_id 提供 → 优先调 get_decrypted_wallet,不走 env"""
        from agent.trade_executor import TradeExecutor
        executor = TradeExecutor()

        # mock get_decrypted_wallet 返成功
        mock_wallet = {"public_key": "PUB_TEST", "private_key": "PRIV_TEST"}
        with patch("api.routes_wallet.get_decrypted_wallet", return_value=mock_wallet) as mock_dec, \
             patch.dict(os.environ, {"TRADE_WALLET_ADDRESS": "ENV_PUB", "TRADE_WALLET_PRIVATE_KEY": "ENV_PRIV"}):
            addr, key = executor._resolve_wallet(
                "solana", None, None, user_id="user-uuid-123",
            )
        # 应返 user_wallets 解密的(不是 env)
        assert addr == "PUB_TEST"
        assert key == "PRIV_TEST"
        mock_dec.assert_called_once_with("user-uuid-123", "solana")

    def test_resolve_falls_back_to_env_when_no_user_id(self):
        """user_id=None → 跳过 DB → 走 env"""
        from agent.trade_executor import TradeExecutor
        executor = TradeExecutor()
        with patch.dict(os.environ, {"TRADE_WALLET_ADDRESS": "ENV_PUB", "TRADE_WALLET_PRIVATE_KEY": "ENV_PRIV"}):
            addr, key = executor._resolve_wallet("solana", None, None, user_id=None)
        assert addr == "ENV_PUB"
        assert key == "ENV_PRIV"

    def test_resolve_falls_back_when_db_decrypt_fails(self):
        """user_id 提供但 get_decrypted_wallet raise → fallback env"""
        from agent.trade_executor import TradeExecutor
        executor = TradeExecutor()
        with patch("api.routes_wallet.get_decrypted_wallet", side_effect=Exception("db down")), \
             patch.dict(os.environ, {"TRADE_WALLET_ADDRESS": "ENV_PUB", "TRADE_WALLET_PRIVATE_KEY": "ENV_PRIV"}):
            addr, key = executor._resolve_wallet(
                "solana", None, None, user_id="user-uuid-123",
            )
        # fallback 到 env
        assert addr == "ENV_PUB"
        assert key == "ENV_PRIV"

    def test_resolve_input_param_takes_precedence(self):
        """入参 wallet+key 优先,不查任何来源"""
        from agent.trade_executor import TradeExecutor
        executor = TradeExecutor()
        addr, key = executor._resolve_wallet(
            "solana", "INPUT_PUB", "INPUT_PRIV", user_id="user-uuid-123",
        )
        assert addr == "INPUT_PUB"
        assert key == "INPUT_PRIV"


# ═════════════════════════════════════════════════════════
# 2. DRY_RUN_LIVE_TRADES env 安全闸
# ═════════════════════════════════════════════════════════

class TestDryRunGate:
    @pytest.mark.asyncio
    async def test_dry_run_env_returns_mock_without_dex_call(self):
        """DRY_RUN_LIVE_TRADES=true → 返 mock 成功 + tx_hash 以 DRY_RUN_ 开头 + 不调 dex_router"""
        from agent.trade_executor import TradeExecutor
        executor = TradeExecutor()

        with patch.dict(os.environ, {"DRY_RUN_LIVE_TRADES": "true"}), \
             patch("agent.dex_router.get_dex_router") as mock_get_router:
            result = await executor.execute_trade(
                chain="solana",
                token_address="TOKEN_TEST",
                action="buy",
                amount_usd=1.0,
                user_id="user-uuid-123",
            )

        assert result.success is True
        assert result.tx_hash.startswith("DRY_RUN_")
        # dex_router 应该完全没被调
        mock_get_router.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_disabled_proceeds_to_dex_router(self):
        """env 不设 → 正常走 dex_router(用 mock 拦,不真发链)"""
        from agent.trade_executor import TradeExecutor, TradeResult
        executor = TradeExecutor()

        # 准备 dex_router mock 返失败(因为没钱包)
        mock_route = MagicMock(success=False, tx_hash=None, error="No wallet")
        mock_route.from_amount = 0
        mock_route.to_amount = 0
        mock_route.price = 0
        mock_route.gas_fee = 0
        mock_route.dex_used = "jupiter"
        mock_route.fallback_used = False
        mock_route.split_count = 1

        mock_router = MagicMock()
        mock_router.execute = AsyncMock(return_value=mock_route)

        with patch.dict(os.environ, {"DRY_RUN_LIVE_TRADES": ""}, clear=False), \
             patch("agent.dex_router.get_dex_router", return_value=mock_router):
            # clear DRY_RUN to be safe
            os.environ.pop("DRY_RUN_LIVE_TRADES", None)
            result = await executor.execute_trade(
                chain="solana",
                token_address="TOKEN_TEST",
                action="buy",
                amount_usd=1.0,
                user_id="user-uuid-123",
            )

        # 真调了 dex_router
        mock_router.execute.assert_called_once()
        # 验证 user_id 透传给了 dex_router.execute
        kwargs = mock_router.execute.call_args.kwargs
        assert kwargs.get("user_id") == "user-uuid-123"


# ═════════════════════════════════════════════════════════
# 3. action_dispatcher 透传 event.user_id
# ═════════════════════════════════════════════════════════

class TestActionDispatcherUserId:
    """静态检查 — 直接读 action_dispatcher.py 源码确认 user_id 透传到 execute_trade。

    动态 dispatch 测试有太多 db/memory/risk 依赖,改静态检查更稳。
    R47 P5 修改的关键代码块必须含 user_id=event.user_id。
    """

    def test_action_dispatcher_source_passes_user_id(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[1] / "agent" / "action_dispatcher.py"
        content = src.read_text()
        # 必须含 R47 P5 透传代码
        assert "user_id=event.user_id" in content, \
            "action_dispatcher 必须 user_id=event.user_id 透传到 execute_trade"
        # safety_ctx 也必须补 user_id + mode
        assert "\"user_id\": event.user_id" in content
        assert "\"mode\": strategy_mode" in content


# ═════════════════════════════════════════════════════════
# 4. position_monitor 透传 pos.user_id
# ═════════════════════════════════════════════════════════

class TestPositionMonitorUserId:
    def test_position_info_loads_user_id(self):
        """PositionInfo 从 row 里拉 user_id"""
        from agent.position_monitor import PositionInfo
        row = {
            "id": "exec-1",
            "strategy_id": "strat-1",
            "user_id": "USER_Y",
            "chain": "solana",
            "token_address": "TOKEN_X",
            "executed_price": 1.0,
            "amount_usd": 50,
        }
        pos = PositionInfo(row)
        assert pos.user_id == "USER_Y"
