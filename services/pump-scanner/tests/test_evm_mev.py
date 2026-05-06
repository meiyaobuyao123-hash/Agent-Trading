"""
R45 — EVM MEV broadcast 测试

覆盖:
- chain=eth + mev_protected=True → 走 Flashbots Protect URL
- chain=eth + mev_protected=False → 走公共 RPC
- chain=bsc + mev_protected=True → fallback 公共 + log warning
- chain=base + mev_protected=True → fallback 公共
- 无 chain RPC → 返 None

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_evm_mev.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.trade_executor import (
    EVM_RPC, EVM_RPC_MEV_PROTECTED, TradeExecutor,
)


@pytest.fixture
def executor():
    return TradeExecutor()


def _mock_session(response_json: dict):
    """构造一个 mock aiohttp session,post 返预设 json"""
    mock_resp = MagicMock()
    mock_resp.json = AsyncMock(return_value=response_json)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.closed = False
    return mock_session


# ═════════════════════════════════════════════════════════
# Flashbots Protect 选 URL
# ═════════════════════════════════════════════════════════

class TestEvmMevRpcSelection:

    def test_eth_protected_url_configured(self):
        """eth 链应有 Flashbots Protect URL"""
        url = EVM_RPC_MEV_PROTECTED.get("eth", "")
        assert "flashbots.net" in url

    def test_bsc_protected_empty_for_now(self):
        """R45 第一版 bsc 还没接 bloXroute,fallback 公共"""
        assert EVM_RPC_MEV_PROTECTED.get("bsc", "") == ""

    def test_base_protected_empty_for_now(self):
        assert EVM_RPC_MEV_PROTECTED.get("base", "") == ""

    def test_public_rpc_still_present(self):
        """公共 RPC 必须保留(无 mev_protected 时用)"""
        for chain in ("eth", "bsc", "base"):
            assert EVM_RPC.get(chain, "") != ""


# ═════════════════════════════════════════════════════════
# _broadcast_evm 行为
# ═════════════════════════════════════════════════════════

class TestBroadcastEvm:

    @pytest.mark.asyncio
    async def test_eth_mev_protected_uses_flashbots(self, executor):
        """eth + mev_protected=True → POST Flashbots URL"""
        ms = _mock_session({"result": "0xabc"})
        with patch.object(executor, "_get_session", new=AsyncMock(return_value=ms)):
            tx_hash = await executor._broadcast_evm(
                "eth", "0xdeadbeef", mev_protected=True,
            )
        assert tx_hash == "0xabc"
        # 验证 POST 走 flashbots.net
        ms.post.assert_called_once()
        called_url = ms.post.call_args[0][0]
        assert "flashbots.net" in called_url

    @pytest.mark.asyncio
    async def test_eth_no_mev_uses_public_rpc(self, executor):
        """eth + mev_protected=False → POST 公共 RPC"""
        ms = _mock_session({"result": "0xabc"})
        with patch.object(executor, "_get_session", new=AsyncMock(return_value=ms)):
            tx_hash = await executor._broadcast_evm("eth", "0xdeadbeef", mev_protected=False)
        assert tx_hash == "0xabc"
        called_url = ms.post.call_args[0][0]
        assert "flashbots.net" not in called_url
        # 应该走 EVM_RPC['eth']
        assert called_url == EVM_RPC["eth"]

    @pytest.mark.asyncio
    async def test_bsc_mev_protected_falls_back_public(self, executor, caplog):
        """bsc + mev_protected=True → 无 Protect URL 降级公共 + log warning"""
        import logging
        caplog.set_level(logging.WARNING)
        ms = _mock_session({"result": "0xbsc_tx"})
        with patch.object(executor, "_get_session", new=AsyncMock(return_value=ms)):
            tx_hash = await executor._broadcast_evm("bsc", "0xdead", mev_protected=True)
        assert tx_hash == "0xbsc_tx"
        called_url = ms.post.call_args[0][0]
        assert called_url == EVM_RPC["bsc"]
        # 应有 warning log "降级公共 RPC"
        assert any("降级公共 RPC" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_unknown_chain_returns_none(self, executor):
        """未知链 → 返 None,不抛"""
        with patch.object(executor, "_get_session", new=AsyncMock()):
            tx_hash = await executor._broadcast_evm("dogechain", "0xdead", mev_protected=True)
        assert tx_hash is None

    @pytest.mark.asyncio
    async def test_eth_mev_default_param_is_false(self, executor):
        """不传 mev_protected 默认 False(不破坏旧 caller)"""
        ms = _mock_session({"result": "0xabc"})
        with patch.object(executor, "_get_session", new=AsyncMock(return_value=ms)):
            await executor._broadcast_evm("eth", "0xdead")
        called_url = ms.post.call_args[0][0]
        # 默认走公共
        assert called_url == EVM_RPC["eth"]
        assert "flashbots.net" not in called_url
