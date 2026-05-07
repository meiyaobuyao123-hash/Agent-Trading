"""
R47 P2 — credit_recharge_loop 单测

mock 所有外部 HTTP(Helius + EVM RPC)+ credit_service.confirm/list_pending,
覆盖关键路径 + 边界:
  - Solana 命中(amount + mint + to 都对 → 调 confirm)
  - Solana amount 不匹配 → 不调 confirm
  - Solana mint 错(不是 USDC SPL)→ 跳过
  - EVM eth_getLogs 解析(USDC 6 decimals)
  - BSC 18 decimals 解析正确(关键 — 防多发 10^12 倍 credit)
  - pending 列表为空 → no-op
  - 单链 RPC 失败不影响其他链
  - amount 精度边界 10.003400 vs 10.003401 不匹配
  - _pad_evm_addr / _quantize_6 helpers

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_credit_recharge_loop.py -v
"""
from __future__ import annotations
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loops import credit_recharge_loop as crl


# ═════════════════════════════════════════════════════════
# helper functions
# ═════════════════════════════════════════════════════════

class TestHelpers:
    def test_pad_evm_addr(self):
        addr = "0xC862ff9Fd79D180950E546DBB8b108d5c9c38582"
        padded = crl._pad_evm_addr(addr)
        assert padded.startswith("0x")
        assert len(padded) == 66  # 0x + 64 hex
        assert padded.endswith("c862ff9fd79d180950e546dbb8b108d5c9c38582")
        assert "C862" not in padded  # 全小写

    def test_pad_lowercase_already(self):
        padded = crl._pad_evm_addr("0xabc123")
        assert padded.startswith("0x")
        # 总长 0x + 64 hex = 66 chars,以 abc123 结尾
        assert len(padded) == 66
        assert padded.endswith("abc123")
        # 中间应全为 0
        assert padded[2:-6] == "0" * 58

    def test_quantize_6(self):
        assert crl._quantize_6(Decimal("10.0034001234")) == Decimal("10.003400")
        assert crl._quantize_6(Decimal("10")) == Decimal("10.000000")
        assert crl._quantize_6(Decimal("10.0034")) == Decimal("10.003400")

    def test_match_pending_hit(self):
        pending = [
            {"id": 1, "amount_usd": Decimal("10.0034")},
            {"id": 2, "amount_usd": Decimal("20.5678")},
        ]
        m = crl._match_pending(pending, Decimal("20.567800"))
        assert m and m["id"] == 2

    def test_match_pending_miss(self):
        pending = [{"id": 1, "amount_usd": Decimal("10.0034")}]
        assert crl._match_pending(pending, Decimal("10.0035")) is None

    def test_match_pending_precision_boundary(self):
        """10.003400 vs 10.003401 — 精度边界"""
        pending = [{"id": 1, "amount_usd": Decimal("10.003400")}]
        # 完全相等
        assert crl._match_pending(pending, Decimal("10.003400")) is not None
        # 多 1 个 6 位精度单位 → miss
        assert crl._match_pending(pending, Decimal("10.003401")) is None


# ═════════════════════════════════════════════════════════
# Solana
# ═════════════════════════════════════════════════════════

class TestSolana:
    @pytest.mark.asyncio
    async def test_no_pending_orders_no_op(self):
        with patch.object(crl.credit_service, "list_pending_orders_by_chain", return_value=[]):
            session = MagicMock()
            assert await crl.scan_solana(session) == 0

    @pytest.mark.asyncio
    async def test_happy_path_confirms_order(self):
        """getSignaturesForAddress → getTransaction → 解析 tokenBalances 差值,匹配 → confirm"""
        addr = "66p5tnV6Fd7x5QmRE6X772PMVmVUVgozRzATJ4Ns9iQn"
        pending = [{
            "id": 42, "user_id": "u1", "chain": "solana",
            "receive_address": addr, "amount_usd": Decimal("10.0034"),
        }]
        # 1. getSignaturesForAddress 返 1 个 sig
        # 2. getTransaction 返 meta 含 pre/postTokenBalances,USDC delta = 10.0034 → 我们 addr
        rpc_responses = [
            {"jsonrpc": "2.0", "id": 1, "result": [{"signature": "sig_abc123"}]},
            {"jsonrpc": "2.0", "id": 1, "result": {
                "meta": {
                    "preTokenBalances": [{
                        "mint": crl.USDC_SOL_MINT,
                        "owner": addr,
                        "uiTokenAmount": {"uiAmount": 5.0},
                    }],
                    "postTokenBalances": [{
                        "mint": crl.USDC_SOL_MINT,
                        "owner": addr,
                        "uiTokenAmount": {"uiAmount": 15.0034},  # +10.0034
                    }],
                },
            }},
        ]
        with patch.object(crl.credit_service, "list_pending_orders_by_chain", return_value=pending), \
             patch.object(crl.credit_service, "confirm_recharge_order", return_value={"ok": True}) as mock_conf:
            session = _mock_session_post(rpc_responses)
            count = await crl.scan_solana(session)
            assert count == 1
            mock_conf.assert_called_once_with(42, "sig_abc123")

    @pytest.mark.asyncio
    async def test_amount_mismatch_skipped(self):
        addr = "addr_test"
        pending = [{
            "id": 42, "user_id": "u1", "chain": "solana",
            "receive_address": addr, "amount_usd": Decimal("10.0034"),
        }]
        rpc_responses = [
            {"jsonrpc": "2.0", "id": 1, "result": [{"signature": "sig"}]},
            {"jsonrpc": "2.0", "id": 1, "result": {
                "meta": {
                    "preTokenBalances": [{
                        "mint": crl.USDC_SOL_MINT, "owner": addr,
                        "uiTokenAmount": {"uiAmount": 5.0},
                    }],
                    "postTokenBalances": [{
                        "mint": crl.USDC_SOL_MINT, "owner": addr,
                        "uiTokenAmount": {"uiAmount": 15.0099},  # +10.0099 不匹配
                    }],
                },
            }},
        ]
        with patch.object(crl.credit_service, "list_pending_orders_by_chain", return_value=pending), \
             patch.object(crl.credit_service, "confirm_recharge_order") as mock_conf:
            session = _mock_session_post(rpc_responses)
            assert await crl.scan_solana(session) == 0
            mock_conf.assert_not_called()

    @pytest.mark.asyncio
    async def test_wrong_mint_skipped(self):
        """tokenBalance 是其他 SPL token,不是 USDC → 不调 confirm"""
        addr = "addr_test"
        pending = [{
            "id": 42, "user_id": "u1", "chain": "solana",
            "receive_address": addr, "amount_usd": Decimal("10.0034"),
        }]
        rpc_responses = [
            {"jsonrpc": "2.0", "id": 1, "result": [{"signature": "sig"}]},
            {"jsonrpc": "2.0", "id": 1, "result": {
                "meta": {
                    "preTokenBalances": [{
                        "mint": "OTHER_TOKEN_MINT", "owner": addr,
                        "uiTokenAmount": {"uiAmount": 5.0},
                    }],
                    "postTokenBalances": [{
                        "mint": "OTHER_TOKEN_MINT", "owner": addr,
                        "uiTokenAmount": {"uiAmount": 15.0034},
                    }],
                },
            }},
        ]
        with patch.object(crl.credit_service, "list_pending_orders_by_chain", return_value=pending), \
             patch.object(crl.credit_service, "confirm_recharge_order") as mock_conf:
            session = _mock_session_post(rpc_responses)
            assert await crl.scan_solana(session) == 0
            mock_conf.assert_not_called()


# ═════════════════════════════════════════════════════════
# EVM(关键覆盖 BSC 18 decimals)
# ═════════════════════════════════════════════════════════

class TestEvm:
    @pytest.mark.asyncio
    async def test_bsc_18_decimals_correct(self):
        """BSC USDC 18 decimals — 算错给用户多发 10^12 倍 credit"""
        pending = [{
            "id": 99,
            "user_id": "u_bsc",
            "chain": "bsc",
            "receive_address": "0xC862ff9Fd79D180950E546DBB8b108d5c9c38582",
            "amount_usd": Decimal("10.0034"),
        }]
        # 10.0034 USDC 在 BSC = 10003400 * 10^12 = 10003400000000000000
        # hex = 0x8AC7230489D89E0000 但要精确 — Python int.from_bytes 算
        amount_raw = int(Decimal("10.0034") * Decimal(10) ** 18)  # = 10003400000000000000
        log_data = "0x" + format(amount_raw, "064x")
        rpc_responses = [
            {"jsonrpc": "2.0", "id": 1, "result": "0x12345"},  # eth_blockNumber
            {"jsonrpc": "2.0", "id": 1, "result": [          # eth_getLogs
                {
                    "data": log_data,
                    "transactionHash": "0xtxhash_bsc",
                    "topics": [crl.TRANSFER_TOPIC, "0xfrom", "0xto"],
                }
            ]},
        ]
        with patch.object(crl.credit_service, "list_pending_orders_by_chain", return_value=pending), \
             patch.object(crl.credit_service, "confirm_recharge_order", return_value={"ok": True}) as mock_conf:
            session = _mock_session_post(rpc_responses)
            count = await crl.scan_evm(session, "bsc")
            assert count == 1
            mock_conf.assert_called_once_with(99, "0xtxhash_bsc")

    @pytest.mark.asyncio
    async def test_eth_6_decimals_correct(self):
        pending = [{
            "id": 7,
            "user_id": "u_eth",
            "chain": "ethereum",
            "receive_address": "0xC862ff9Fd79D180950E546DBB8b108d5c9c38582",
            "amount_usd": Decimal("5.123456"),
        }]
        # 5.123456 USDC ETH = 5123456 * 10^0 = 5123456 (decimals=6)
        amount_raw = int(Decimal("5.123456") * Decimal(10) ** 6)
        log_data = "0x" + format(amount_raw, "064x")
        rpc_responses = [
            {"jsonrpc": "2.0", "id": 1, "result": "0xabc"},
            {"jsonrpc": "2.0", "id": 1, "result": [
                {"data": log_data, "transactionHash": "0xeth_tx"}
            ]},
        ]
        with patch.object(crl.credit_service, "list_pending_orders_by_chain", return_value=pending), \
             patch.object(crl.credit_service, "confirm_recharge_order", return_value={"ok": True}) as mock_conf:
            session = _mock_session_post(rpc_responses)
            assert await crl.scan_evm(session, "ethereum") == 1
            mock_conf.assert_called_once_with(7, "0xeth_tx")

    @pytest.mark.asyncio
    async def test_no_pending_orders_no_op(self):
        with patch.object(crl.credit_service, "list_pending_orders_by_chain", return_value=[]):
            session = MagicMock()
            assert await crl.scan_evm(session, "ethereum") == 0

    @pytest.mark.asyncio
    async def test_rpc_error_returns_zero(self):
        pending = [{
            "id": 1, "user_id": "u", "chain": "ethereum",
            "receive_address": "0xabc", "amount_usd": Decimal("1.0"),
        }]
        with patch.object(crl.credit_service, "list_pending_orders_by_chain", return_value=pending):
            # session.post raises
            session = MagicMock()
            session.post = MagicMock(side_effect=Exception("RPC down"))
            assert await crl.scan_evm(session, "ethereum") == 0


# ═════════════════════════════════════════════════════════
# run_once(顶层)
# ═════════════════════════════════════════════════════════

class TestRunOnce:
    @pytest.mark.asyncio
    async def test_one_chain_failing_doesnt_break_others(self):
        """Solana 失败,其他 EVM 链照常跑"""
        async def _solana_fail(_s):
            raise Exception("solana broke")
        async def _evm_ok(_s, chain):
            return 0
        with patch.object(crl, "scan_solana", side_effect=_solana_fail), \
             patch.object(crl, "scan_evm", side_effect=_evm_ok):
            res = await crl.run_once()
            assert res == {"solana": 0, "ethereum": 0, "base": 0, "bsc": 0}


# ═════════════════════════════════════════════════════════
# mock helpers
# ═════════════════════════════════════════════════════════

def _mock_session_get(json_response):
    """Mock aiohttp session for GET (Helius)"""
    session = MagicMock()
    resp_mock = MagicMock()
    resp_mock.status = 200
    resp_mock.json = AsyncMock(return_value=json_response)
    resp_mock.text = AsyncMock(return_value="")

    # async context manager
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp_mock)
    cm.__aexit__ = AsyncMock(return_value=None)
    session.get = MagicMock(return_value=cm)
    return session


def _mock_session_post(rpc_responses_in_order):
    """Mock aiohttp session for POST (EVM JSON-RPC) with list of responses"""
    session = MagicMock()
    call_idx = {"i": 0}

    def post_factory(*args, **kwargs):
        idx = call_idx["i"]
        call_idx["i"] += 1
        resp_mock = MagicMock()
        resp_mock.status = 200
        resp_mock.json = AsyncMock(return_value=rpc_responses_in_order[idx])
        resp_mock.text = AsyncMock(return_value="")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=resp_mock)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    session.post = MagicMock(side_effect=post_factory)
    return session
