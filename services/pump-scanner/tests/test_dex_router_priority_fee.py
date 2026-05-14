"""
R64 — dex_router 真传 priority_fee_sol + mev_bribe_sol(jito_tip)给 Jupiter 单测

跑法:python3 -m pytest tests/test_dex_router_priority_fee.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _mk_quote(out_amount: str = "100000"):
    """构造 fake QuoteResult(dex + out_amount + raw 就够,success 是 @property)"""
    from agent.dex_router import QuoteResult
    return QuoteResult(
        dex="jupiter",
        out_amount=out_amount,
        price_impact=0.001,
        raw={"inAmount": "50000000", "outAmount": out_amount},
    )


@pytest.fixture
def jup_mock():
    """patch agent.dex.jupiter.get_jupiter_dex 让 jup.get_swap 是 AsyncMock"""
    fake_jup = MagicMock()
    fake_jup.get_swap = AsyncMock(return_value={
        "swapTransaction": "fakebase64==",
        "lastValidBlockHeight": 99999,
    })
    with patch("agent.dex.jupiter.get_jupiter_dex", return_value=fake_jup):
        yield fake_jup


@pytest.fixture
def executor_mock():
    """patch _get_okx_executor 避免触发 OKX 客户端构造"""
    fake_exec = MagicMock()
    # _broadcast_solana → 假装 tx 上链成功
    fake_exec._broadcast_solana = AsyncMock(return_value=("tx_hash_abc", True, ""))
    fake_exec._sign_solana_tx = MagicMock(return_value="signed_tx_base64")
    return fake_exec


@pytest.mark.asyncio
async def test_jupiter_priority_fee_passed_to_get_swap(jup_mock, executor_mock):
    """priority_fee_sol=0.005 → jup.get_swap 收到 priority_fee_sol=0.005"""
    from agent.dex_router import DexRouter
    router = DexRouter()
    router._get_okx_executor = MagicMock(return_value=executor_mock)

    # 直接调 _execute_jupiter,绕开 quote 阶段的 OKX/Jupiter quote 网络
    quote = _mk_quote()
    await router._execute_jupiter(
        quote=quote,
        chain="solana",
        token_address="So1111...",
        action="buy",
        amount_usd=50.0,
        slippage_pct=1.0,
        wallet_address="OwnerWallet111",
        private_key="priv_base64",
        priority_fee_sol=0.005,
        mev_bribe_sol=0.001,
    )

    # 验证 jup.get_swap 被调用,且 priority_fee_sol/jito_tip_sol 真传过去
    jup_mock.get_swap.assert_called_once()
    _, kwargs = jup_mock.get_swap.call_args
    assert kwargs.get("priority_fee_sol") == 0.005, f"priority_fee_sol not passed: {kwargs}"
    assert kwargs.get("jito_tip_sol") == 0.001, f"jito_tip_sol not passed: {kwargs}"


@pytest.mark.asyncio
async def test_jupiter_no_priority_fee_defaults_zero(jup_mock, executor_mock):
    """不传 priority_fee → jup.get_swap 收到 priority_fee_sol=0(默认值,Jupiter 内部 if>0 跳过)"""
    from agent.dex_router import DexRouter
    router = DexRouter()
    router._get_okx_executor = MagicMock(return_value=executor_mock)

    quote = _mk_quote()
    await router._execute_jupiter(
        quote=quote,
        chain="solana",
        token_address="So1111...",
        action="buy",
        amount_usd=50.0,
        slippage_pct=1.0,
        wallet_address="OwnerWallet111",
        private_key="priv_base64",
    )

    jup_mock.get_swap.assert_called_once()
    _, kwargs = jup_mock.get_swap.call_args
    assert kwargs.get("priority_fee_sol", 0) == 0.0
    assert kwargs.get("jito_tip_sol", 0) == 0.0


def test_jupiter_payload_includes_priority_fee_lamports():
    """jupiter.py get_swap 内部:priority_fee_sol=0.005 → payload['prioritizationFeeLamports']=5_000_000"""
    import asyncio
    from agent.dex.jupiter import JupiterDex

    captured: dict = {}

    class FakeResp:
        status = 200
        async def json(self): return {"swapTransaction": "fake"}
        async def text(self): return ""
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None

    class FakeSession:
        closed = False
        def post(self, url, json=None, timeout=None):  # noqa — async with 要求返回 ctx mgr,不是 coroutine
            captured["payload"] = json
            return FakeResp()

    async def run():
        jup = JupiterDex(session=FakeSession())  # type: ignore[arg-type]
        await jup.get_swap(
            quote_response={"inAmount": "1", "outAmount": "2"},
            user_public_key="Owner111",
            priority_fee_sol=0.005,
            jito_tip_sol=0.001,
        )

    asyncio.run(run())
    payload = captured["payload"]
    assert payload.get("prioritizationFeeLamports") == 5_000_000
    assert payload.get("jitoTipLamports") == 1_000_000
    assert payload.get("dynamicComputeUnitLimit") is True


def test_jupiter_payload_skips_field_when_zero():
    """priority_fee_sol=0 + jito_tip_sol=0 → payload 不含两个字段(避免 Jupiter API 收到 0 报错)"""
    import asyncio
    from agent.dex.jupiter import JupiterDex

    captured: dict = {}

    class FakeResp:
        status = 200
        async def json(self): return {"swapTransaction": "fake"}
        async def text(self): return ""
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None

    class FakeSession:
        closed = False
        def post(self, url, json=None, timeout=None):  # noqa — async with 要求返回 ctx mgr,不是 coroutine
            captured["payload"] = json
            return FakeResp()

    async def run():
        jup = JupiterDex(session=FakeSession())  # type: ignore[arg-type]
        await jup.get_swap(
            quote_response={"inAmount": "1", "outAmount": "2"},
            user_public_key="Owner111",
        )

    asyncio.run(run())
    payload = captured["payload"]
    assert "prioritizationFeeLamports" not in payload
    assert "jitoTipLamports" not in payload
    # 但 dynamicComputeUnitLimit 总是 True
    assert payload.get("dynamicComputeUnitLimit") is True


def test_format_top_movers_outputs_markdown_table():
    """A3 — _format_top_movers 输出 GFM markdown table(表头 + 分隔行 + 数据行)"""
    from agent.loops.chat_loop import _format_top_movers

    items = [
        {"rank": 1, "symbol": "Swinu", "chain": "solana",
         "pct_change": 20767, "volume_usd": 20700, "mcap_usd": 314000, "score": 67.8},
        {"rank": 2, "symbol": "PUMP IT", "chain": "solana",
         "pct_change": 16814, "volume_usd": 23400, "mcap_usd": 256000, "score": 66.6},
    ]
    out = _format_top_movers(items, "24h", "all")
    # 表头存在
    assert "| # | 代币 | 链 | 涨幅 | 24h量 | 市值 | 评分 |" in out
    # 分隔行(GFM 必须)
    assert "|---|------|" in out
    # 数据行包含 symbol
    assert "Swinu" in out
    assert "PUMP IT" in out
    # 链大写
    assert "SOLANA" in out
    # 涨幅格式
    assert "+20767%" in out
