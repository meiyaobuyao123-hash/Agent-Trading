"""
routes_agent chat/stream safety pre-check 测试 — W3 D4
覆盖 _check_safety_for_chat 函数:
  - safety_ctx=None + global normal → 通过
  - global BLOCKED CB active → 拦截
  - safety_ctx 命中 HR → 拦截
  - SafetyEngine 不可用 → 降级不阻断

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_routes_chat_safety.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.safety_engine import (  # noqa: E402
    SafetyEngine,
    get_safety_engine,
    reset_safety_engine_singleton,
)


@pytest.fixture(autouse=True)
def fresh_singleton():
    reset_safety_engine_singleton()
    yield
    reset_safety_engine_singleton()


@pytest.fixture
def clean_safety_ctx() -> dict:
    """合规 safety_ctx,跑全部 30 HR 不触发"""
    return {
        "amount_usd": 0, "daily_total_usd": 0, "monthly_total_usd": 0,
        "strategy_position_pct": 0, "chain_concentration_pct": 0,
        "open_position_count": 0, "liquidity_usd": 100000,
        "buy_tax_pct": 0, "sell_tax_pct": 0, "is_honeypot": False,
        "auth_single_trade_max": 500, "credentials_revoked_at": None,
        "kms_unavailable": False, "holders_count": 5000, "top10_pct": 0.30,
        "price_change_24h_pct": 0.0, "regime": "TRENDING_UP",
        "action": "chat", "daily_loss_usd": 0, "weekly_loss_usd": 0,
        "consecutive_losses": 0, "max_drawdown_pct": 0.05,
        "token_address": "Mock", "blacklist_tokens": [],
        "seconds_since_last_trade": 600, "trades_last_hour": 1,
        "slippage_pct": 0.01, "max_slippage_pct": 0.05,
        "hitl_required": False, "hitl_approved": True,
        "strategy_stage": "saved", "copy_target_wallet": None,
        "blacklist_wallets": [], "token_age_seconds": 86400 * 30,
        "mode": "paper", "user_quota_exhausted": False,
        "agent_global_state": "normal",
    }


# ============================================================
# _check_safety_for_chat 单元测试
# ============================================================

class TestCheckSafetyForChat:

    def test_no_ctx_normal_state_returns_none(self):
        """全局 normal + safety_ctx=None → 通过"""
        from api.routes_agent import _check_safety_for_chat
        # 单例预加载干净状态
        get_safety_engine()
        result = _check_safety_for_chat(None)
        assert result is None

    def test_global_blocked_cb_intercepts(self):
        """全局 CB01(blocked 级) trip → 所有 chat 拦截(即使 ctx=None)"""
        from api.routes_agent import _check_safety_for_chat
        engine = get_safety_engine()
        engine.trip_breaker("CB01", reason="日亏损测试")

        result = _check_safety_for_chat(None)
        assert result is not None
        assert "CB01" in result
        assert "停机维护" in result

    def test_global_degraded_passes(self):
        """global degraded(CB03 等)不拦 chat,只 blocked 级才拦"""
        from api.routes_agent import _check_safety_for_chat
        engine = get_safety_engine()
        engine.trip_breaker("CB03", reason="连亏 3 笔(degraded)")

        result = _check_safety_for_chat(None)
        # CB03 是 degraded,不应拦
        assert result is None

    def test_ctx_clean_passes(self, clean_safety_ctx):
        """safety_ctx 干净 → 通过"""
        from api.routes_agent import _check_safety_for_chat
        result = _check_safety_for_chat(clean_safety_ctx)
        assert result is None

    def test_ctx_amount_over_blocks(self, clean_safety_ctx):
        """ctx amount 超 $500 → 拦截(HR01)"""
        from api.routes_agent import _check_safety_for_chat
        clean_safety_ctx["amount_usd"] = 1000
        result = _check_safety_for_chat(clean_safety_ctx)
        assert result is not None
        assert "HR01" in result

    def test_ctx_honeypot_blocks(self, clean_safety_ctx):
        from api.routes_agent import _check_safety_for_chat
        clean_safety_ctx["is_honeypot"] = True
        result = _check_safety_for_chat(clean_safety_ctx)
        assert result is not None
        assert "HR09" in result

    def test_ctx_quota_exhausted_blocks(self, clean_safety_ctx):
        """user_quota_exhausted → HR30 拦截"""
        from api.routes_agent import _check_safety_for_chat
        clean_safety_ctx["user_quota_exhausted"] = True
        result = _check_safety_for_chat(clean_safety_ctx)
        assert result is not None
        assert "HR30" in result

    def test_ctx_global_blocked_state_blocks(self, clean_safety_ctx):
        """ctx 里 agent_global_state=blocked → HR28 拦截"""
        from api.routes_agent import _check_safety_for_chat
        clean_safety_ctx["agent_global_state"] = "blocked"
        result = _check_safety_for_chat(clean_safety_ctx)
        assert result is not None
        assert "HR28" in result

    def test_engine_failure_silent_pass(self):
        """SafetyEngine import 失败 → 静默返 None(降级)"""
        from api import routes_agent
        with patch("agent.safety_engine.get_safety_engine") as mock_get:
            mock_get.side_effect = RuntimeError("yaml gone")
            # 导入函数后再调
            result = routes_agent._check_safety_for_chat(None)
            # 降级:不阻断
            assert result is None

    def test_blocked_cb_priority_over_ctx(self, clean_safety_ctx):
        """全局 BLOCKED 优先于 ctx 检查(返全局原因不是 ctx 原因)"""
        from api.routes_agent import _check_safety_for_chat
        engine = get_safety_engine()
        engine.trip_breaker("CB13", reason="CRISIS")  # blocked 级
        clean_safety_ctx["amount_usd"] = 1000  # ctx 也违规

        result = _check_safety_for_chat(clean_safety_ctx)
        # 应优先返 CB13(全局检查在前)
        assert "CB13" in result
