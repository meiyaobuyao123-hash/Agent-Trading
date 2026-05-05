"""
R42 P0.3 — hitl_router 全自动化兜底测试

覆盖 7 条防线 + record_executed daily 累计 + paper 不消耗 cap:
  - paper mode → 直接通过
  - status=archived/paused → 拒
  - 单笔 > max_position → 拒
  - sell 不受 daily cap / 连亏 / 回撤限制
  - daily cap 累计 + 超出拒
  - 连续亏损 ≥ 3 → 拒
  - 30 天回撤 > 30 → 拒
  - record_executed buy 累计;sell 不累计
  - get_daily_remaining 计算正确

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_hitl_router_full_auto.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def fresh_daily():
    """每个测试前清空 daily 累计"""
    from agent.hitl_router import reset_daily_for_test
    reset_daily_for_test()
    yield
    reset_daily_for_test()


# ═════════════════════════════════════════════════════════
# 7 条兜底防线
# ═════════════════════════════════════════════════════════

class TestGuardrails:

    def test_paper_mode_always_allowed(self):
        from agent.hitl_router import is_allowed_to_auto_execute
        ok, reason = is_allowed_to_auto_execute(
            "user1", {"mode": "paper"}, amount_usd=999999, side="buy",
        )
        assert ok is True
        assert reason is None

    def test_archived_strategy_rejected(self):
        from agent.hitl_router import is_allowed_to_auto_execute
        ok, reason = is_allowed_to_auto_execute(
            "user1", {"mode": "live", "status": "archived"}, amount_usd=10, side="buy",
        )
        assert ok is False
        assert "archived" in reason

    def test_paused_strategy_rejected(self):
        from agent.hitl_router import is_allowed_to_auto_execute
        ok, reason = is_allowed_to_auto_execute(
            "user1", {"mode": "live", "status": "paused"}, amount_usd=10, side="buy",
        )
        assert ok is False
        assert "paused" in reason

    def test_amount_over_max_position_rejected(self):
        from agent.hitl_router import is_allowed_to_auto_execute
        ok, reason = is_allowed_to_auto_execute(
            "user1", {"mode": "live", "max_position_usd": 100}, amount_usd=200, side="buy",
        )
        assert ok is False
        assert "上限" in reason

    def test_amount_at_max_position_allowed(self):
        from agent.hitl_router import is_allowed_to_auto_execute
        ok, _ = is_allowed_to_auto_execute(
            "user1", {"mode": "live", "max_position_usd": 100}, amount_usd=100, side="buy",
        )
        assert ok is True

    def test_default_max_position_5000(self):
        """无 max_position_usd → 默认 $5000"""
        from agent.hitl_router import is_allowed_to_auto_execute
        ok1, _ = is_allowed_to_auto_execute(
            "user1", {"mode": "live"}, amount_usd=4999, side="buy",
        )
        assert ok1 is True
        ok2, reason = is_allowed_to_auto_execute(
            "user1", {"mode": "live"}, amount_usd=5001, side="buy",
        )
        assert ok2 is False
        assert "5000" in reason

    def test_sell_skips_daily_cap(self):
        """sell 不受 daily cap / 连亏 / 回撤限制(让止损能正常出货)"""
        from agent.hitl_router import is_allowed_to_auto_execute, record_executed
        # 灌满 daily cap
        for _ in range(10):
            record_executed("user1", 5000, "buy")
        # buy 应该被拒(累计 50000)
        ok_buy, _ = is_allowed_to_auto_execute(
            "user1", {"mode": "live", "max_position_usd": 100}, amount_usd=10, side="buy",
        )
        assert ok_buy is False  # 累计 50000 + 10 > 50000 cap
        # sell 应该过(止损要能出)
        ok_sell, _ = is_allowed_to_auto_execute(
            "user1", {"mode": "live", "max_position_usd": 100}, amount_usd=10, side="sell",
        )
        assert ok_sell is True

    def test_consecutive_losses_rejected(self):
        from agent.hitl_router import is_allowed_to_auto_execute
        ok, reason = is_allowed_to_auto_execute(
            "user1",
            {"mode": "live", "max_position_usd": 100, "consecutive_losses": 3},
            amount_usd=10, side="buy",
        )
        assert ok is False
        assert "连续亏损" in reason

    def test_drawdown_over_30pct_rejected(self):
        from agent.hitl_router import is_allowed_to_auto_execute
        ok, reason = is_allowed_to_auto_execute(
            "user1",
            {"mode": "live", "max_position_usd": 100, "max_drawdown_pct_30d": 35},
            amount_usd=10, side="buy",
        )
        assert ok is False
        assert "回撤" in reason

    def test_drawdown_exactly_30_allowed(self):
        """30% 是边界,刚好 30 应允许"""
        from agent.hitl_router import is_allowed_to_auto_execute
        ok, _ = is_allowed_to_auto_execute(
            "user1",
            {"mode": "live", "max_position_usd": 100, "max_drawdown_pct_30d": 30.0},
            amount_usd=10, side="buy",
        )
        assert ok is True


# ═════════════════════════════════════════════════════════
# Daily cap 累计 + record
# ═════════════════════════════════════════════════════════

class TestDailyCapAccumulation:

    def test_record_executed_accumulates_buy(self):
        from agent.hitl_router import record_executed, _get_daily_total
        record_executed("user1", 100, "buy")
        record_executed("user1", 200, "buy")
        assert _get_daily_total("user1") == 300

    def test_record_executed_skips_sell(self):
        from agent.hitl_router import record_executed, _get_daily_total
        record_executed("user1", 100, "buy")
        record_executed("user1", 50, "sell")
        assert _get_daily_total("user1") == 100

    def test_daily_cap_50000_default(self):
        """默认 cap $50,000 全 App 合计"""
        from agent.hitl_router import is_allowed_to_auto_execute, record_executed
        # 灌到 49,000
        record_executed("user1", 49000, "buy")
        # 1500 应允许(49000 + 1500 = 50500 > 50000 拒;改成 999 通过)
        ok_over, _ = is_allowed_to_auto_execute(
            "user1", {"mode": "live", "max_position_usd": 5000}, amount_usd=1500, side="buy",
        )
        assert ok_over is False
        ok_under, _ = is_allowed_to_auto_execute(
            "user1", {"mode": "live", "max_position_usd": 5000}, amount_usd=999, side="buy",
        )
        assert ok_under is True

    def test_strategy_can_override_daily_cap(self):
        """策略 daily_auto_cap_usd 字段覆盖默认"""
        from agent.hitl_router import is_allowed_to_auto_execute, record_executed
        record_executed("user1", 99, "buy")
        ok, reason = is_allowed_to_auto_execute(
            "user1",
            {"mode": "live", "max_position_usd": 100, "daily_auto_cap_usd": 100},
            amount_usd=50, side="buy",
        )
        # 99 + 50 = 149 > 100 cap → 拒
        assert ok is False
        assert "100" in reason

    def test_get_daily_remaining(self):
        from agent.hitl_router import record_executed, get_daily_remaining
        record_executed("user1", 30000, "buy")
        assert get_daily_remaining("user1") == 20000  # 50000 - 30000

    def test_user_isolation(self):
        """不同用户 cap 独立"""
        from agent.hitl_router import record_executed, _get_daily_total
        record_executed("userA", 1000, "buy")
        record_executed("userB", 500, "buy")
        assert _get_daily_total("userA") == 1000
        assert _get_daily_total("userB") == 500


# ═════════════════════════════════════════════════════════
# Stats
# ═════════════════════════════════════════════════════════

class TestStats:

    def test_stats_reflects_state(self):
        from agent.hitl_router import record_executed, get_stats
        record_executed("user1", 1234.56, "buy")
        s = get_stats("user1")
        assert s["user_id"] == "user1"
        assert s["today_used_usd"] == 1234.56
        assert s["daily_cap_usd"] == 50000.0
        assert s["remaining_usd"] == round(50000 - 1234.56, 2)
