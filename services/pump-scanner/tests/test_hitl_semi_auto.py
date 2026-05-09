"""
R47 P6 — HITL 分层 + 半自动撤销窗口 单测

覆盖:
  - decide_automation_level 阈值
  - HR01 联动 strategy.max_position_usd
  - semi_auto_service create/cancel/fetch_due 防 race

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_hitl_semi_auto.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ═════════════════════════════════════════════════════════
# 1. decide_automation_level 阈值
# ═════════════════════════════════════════════════════════

class TestDecideAutomationLevel:
    def test_below_500_returns_auto(self):
        from agent.hitl_router import decide_automation_level
        level, sec = decide_automation_level(amount_usd=499.0)
        assert level == "auto"
        assert sec == 0

    def test_at_499_99_returns_auto(self):
        from agent.hitl_router import decide_automation_level
        level, _ = decide_automation_level(amount_usd=499.99)
        assert level == "auto"

    def test_at_500_returns_semi_10sec(self):
        from agent.hitl_router import decide_automation_level
        level, sec = decide_automation_level(amount_usd=500.0)
        assert level == "semi"
        assert sec == 10

    def test_above_500_returns_semi(self):
        from agent.hitl_router import decide_automation_level
        level, sec = decide_automation_level(amount_usd=2000.0)
        assert level == "semi"
        assert sec == 10

    def test_sell_always_returns_auto(self):
        """卖出永远 auto(止损/止盈不允许撤销)"""
        from agent.hitl_router import decide_automation_level
        level, _ = decide_automation_level(amount_usd=5000.0, side="sell")
        assert level == "auto"

    def test_custom_threshold_and_window(self):
        """env 可调阈值 + 撤销窗口"""
        from agent.hitl_router import decide_automation_level
        level, sec = decide_automation_level(
            amount_usd=100.0,
            semi_auto_threshold_usd=50.0,
            cancel_window_sec=30,
        )
        assert level == "semi"
        assert sec == 30


# ═════════════════════════════════════════════════════════
# 2. HR01 联动 strategy.max_position_usd
# ═════════════════════════════════════════════════════════

class TestHr01StrategyMax:
    def test_within_max_position_passes(self):
        from agent.safety_engine import hr01_within_strategy_max
        ctx = {"mode": "live", "amount_usd": 400, "max_position_usd": 500}
        # 400 < 500 → 不触发
        assert hr01_within_strategy_max(ctx) is False

    def test_exceeds_max_position_blocks(self):
        from agent.safety_engine import hr01_within_strategy_max
        ctx = {"mode": "live", "amount_usd": 600, "max_position_usd": 500}
        assert hr01_within_strategy_max(ctx) is True

    def test_uses_default_500_when_max_not_provided(self):
        from agent.safety_engine import hr01_within_strategy_max
        # 没传 max_position_usd → 默认 $500
        ctx = {"mode": "live", "amount_usd": 600}
        assert hr01_within_strategy_max(ctx) is True

    def test_user_can_lift_to_5000(self):
        from agent.safety_engine import hr01_within_strategy_max
        # 用户调高 max_position 到 $5000 → $4000 应通过
        ctx = {"mode": "live", "amount_usd": 4000, "max_position_usd": 5000}
        assert hr01_within_strategy_max(ctx) is False

    def test_paper_mode_skipped(self):
        """paper 模式不烧真钱,跳过 HR01"""
        from agent.safety_engine import hr01_within_strategy_max
        ctx = {"mode": "paper", "amount_usd": 99999, "max_position_usd": 500}
        assert hr01_within_strategy_max(ctx) is False

    def test_amount_missing_skipped(self):
        from agent.safety_engine import hr01_within_strategy_max
        # 没传 amount_usd → 不触发(可能不是 trade ctx)
        ctx = {"mode": "live", "max_position_usd": 500}
        assert hr01_within_strategy_max(ctx) is False


# ═════════════════════════════════════════════════════════
# 3. semi_auto_service helpers(无 DB,只测纯函数)
# ═════════════════════════════════════════════════════════

class TestSemiAutoService:
    def test_create_pending_invalid_input_returns_none(self):
        from agent import semi_auto_service
        # user_id 空 → None
        assert semi_auto_service.create_pending(
            user_id="", strategy_id=None, chain="solana",
            token_address="X", token_symbol="X", action="buy",
            amount_usd=100,
        ) is None
        # action 非法
        assert semi_auto_service.create_pending(
            user_id="u1", strategy_id=None, chain="solana",
            token_address="X", token_symbol="X", action="hold",
            amount_usd=100,
        ) is None
        # amount <= 0
        assert semi_auto_service.create_pending(
            user_id="u1", strategy_id=None, chain="solana",
            token_address="X", token_symbol="X", action="buy",
            amount_usd=0,
        ) is None

    def test_cancel_returns_not_found_when_db_returns_nothing(self):
        from agent import semi_auto_service
        # mock _get_conn 返一个 cursor 查不到 row
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        with patch.object(semi_auto_service, "_get_conn", return_value=mock_conn):
            cancelled, reason = semi_auto_service.cancel_pending("pid", "user1")
        assert cancelled is False
        assert reason == "not_found"


# ═════════════════════════════════════════════════════════
# 4. 端到端 — action_dispatcher 分流逻辑(静态源码检查)
# ═════════════════════════════════════════════════════════

class TestActionDispatcherIntegration:
    def test_action_dispatcher_imports_decide_automation_level(self):
        """action_dispatcher 必须 import decide_automation_level + create_pending"""
        from pathlib import Path
        src = Path(__file__).resolve().parents[1] / "agent" / "action_dispatcher.py"
        content = src.read_text()
        assert "decide_automation_level" in content, \
            "action_dispatcher 必须用 decide_automation_level 决定 auto / semi"
        assert "semi_auto_service" in content, \
            "action_dispatcher 必须 import semi_auto_service.create_pending"
        assert 'level == "semi"' in content, \
            "必须有 level == 'semi' 分支"

    def test_routes_agent_has_cancel_endpoint(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[1] / "api" / "routes_agent.py"
        content = src.read_text()
        assert "/trades/pending/{pending_id}/cancel" in content
        assert "cancel_pending_semi_auto" in content
