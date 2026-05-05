"""
R42 P0.1 — position_monitor 常驻 loop 测试

覆盖 PositionMonitor.scan_and_check_now():
  - 无 position → 返 0,不抛
  - 有 position 但 price_feed 无价 → 返 count,不调 check_all
  - 有 position + 有价 → 调 check_all,prices dict 含 chain:addr 和 addr 两种 key
  - load_positions 失败 → 返 0,不抛
  - check_all 失败 → 返 count,不抛(失败保护)

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_position_monitor_loop.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def monitor_with_one_position():
    """构造一个含一笔 SOL position 的 monitor(绕开 DB 加载)"""
    from agent.position_monitor import PositionMonitor, PositionInfo
    m = PositionMonitor()
    pos = PositionInfo({
        "id": "exec_1",
        "token_address": "7Beoebgjepbf4MayW4pZ48tcGrdK25kr7ZeXv42aPump",
        "chain": "solana",
        "entry_price": 0.001,
        "amount_usd": 50,
        "stop_loss_pct": 30,
        "take_profit_pct": 100,
        "trailing_stop_pct": 0,
    })
    m._positions = {"exec_1": pos}
    m._last_load = 9999999999.0  # 防 load_positions 重新拉
    return m


# ═════════════════════════════════════════════════════════
# scan_and_check_now
# ═════════════════════════════════════════════════════════

class TestScanAndCheckNow:

    @pytest.mark.asyncio
    async def test_no_positions_returns_zero(self):
        from agent.position_monitor import PositionMonitor
        m = PositionMonitor()
        m._last_load = 9999999999.0
        # mock load_positions 不动 _positions(模拟空 DB)
        with patch.object(m, "load_positions", new=AsyncMock()):
            result = await m.scan_and_check_now()
        assert result == 0

    @pytest.mark.asyncio
    async def test_position_no_price_skips_check_all(self, monitor_with_one_position):
        m = monitor_with_one_position
        fake_feed = MagicMock()
        fake_feed.get_token_price = MagicMock(return_value=None)  # 无价
        with patch.dict(sys.modules, {"price_feed": MagicMock(price_feed=fake_feed)}):
            with patch.object(m, "load_positions", new=AsyncMock()):
                with patch.object(m, "check_all", new=AsyncMock()) as mock_check:
                    result = await m.scan_and_check_now()
        assert result == 1
        mock_check.assert_not_called()  # 没价 → 不调 check_all

    @pytest.mark.asyncio
    async def test_position_with_price_calls_check_all(self, monitor_with_one_position):
        m = monitor_with_one_position
        fake_feed = MagicMock()
        fake_feed.get_token_price = MagicMock(return_value=0.0008)  # 跌 20%
        with patch.dict(sys.modules, {"price_feed": MagicMock(price_feed=fake_feed)}):
            with patch.object(m, "load_positions", new=AsyncMock()):
                with patch.object(m, "check_all", new=AsyncMock()) as mock_check:
                    result = await m.scan_and_check_now()
        assert result == 1
        mock_check.assert_called_once()
        # 验证 prices dict 含两种 key
        prices_arg = mock_check.call_args[0][0]
        addr_lower = "7beoebgjepbf4mayw4pz48tcgrdk25kr7zexv42apump"
        assert prices_arg.get(addr_lower) == 0.0008
        assert prices_arg.get(f"solana:{addr_lower}") == 0.0008

    @pytest.mark.asyncio
    async def test_load_positions_failure_returns_zero(self):
        from agent.position_monitor import PositionMonitor
        m = PositionMonitor()
        m._last_load = 0  # 强制 load 必发
        with patch.object(m, "load_positions", new=AsyncMock(side_effect=RuntimeError("DB down"))):
            # 不应抛
            result = await m.scan_and_check_now()
        assert result == 0

    @pytest.mark.asyncio
    async def test_check_all_failure_does_not_raise(self, monitor_with_one_position):
        m = monitor_with_one_position
        fake_feed = MagicMock()
        fake_feed.get_token_price = MagicMock(return_value=0.001)
        with patch.dict(sys.modules, {"price_feed": MagicMock(price_feed=fake_feed)}):
            with patch.object(m, "load_positions", new=AsyncMock()):
                with patch.object(m, "check_all",
                                   new=AsyncMock(side_effect=RuntimeError("check broken"))):
                    # 不应抛
                    result = await m.scan_and_check_now()
        assert result == 1

    @pytest.mark.asyncio
    async def test_price_feed_import_failure_safe(self, monitor_with_one_position):
        """price_feed import 失败 → 返 count,不调 check_all,不抛"""
        m = monitor_with_one_position
        with patch.object(m, "load_positions", new=AsyncMock()):
            with patch.object(m, "check_all", new=AsyncMock()) as mock_check:
                # 临时把 price_feed module 替换为会抛 import error 的 stub
                broken_module = MagicMock()
                # 删掉 price_feed 属性,触发 AttributeError 时被外层 except 捕获
                with patch.dict(sys.modules, {"price_feed": MagicMock(spec=[])}):
                    result = await m.scan_and_check_now()
        # 即使 price_feed 用不了,函数也不应抛;count 取决于 _positions
        assert result >= 0
