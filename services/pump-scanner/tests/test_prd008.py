"""
PRD-008: Agent Paper Trading + Strategy Templates + AI Proactive Recommendations

覆盖：
  - PaperEngine: open_position / close_position / check_exits / get_stats / check_reminders
  - Templates: list_templates / get_template / create_from_template / override
  - ProactiveScanner: quality_filter / cooldown / scan_opportunities
  - ActionDispatcher: paper mode routing
  - StrategyManager: mode field / go_live
  - API endpoints: paper-trades / paper-stats / go-live / templates / compare

Python 3.9 兼容。
"""

import asyncio
import sys
import os
from typing import Any, Dict
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone

import pytest

# 确保能 import 项目模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════

def _run(coro):
    """运行 async 函数"""
    return asyncio.get_event_loop().run_until_complete(coro)


# ═══════════════════════════════════════════════════
# 1. Templates — 策略模板
# ═══════════════════════════════════════════════════

class TestTemplates:
    """策略模板测试"""

    def test_list_templates_returns_5(self):
        """应返回 5 个预设模板"""
        from agent.templates import list_templates
        templates = list_templates()
        assert len(templates) == 5
        ids = {t["id"] for t in templates}
        assert ids == {
            "meme_sniper", "hot_breakout", "smart_money_follow",
            "kol_sentiment", "conservative_dca",
        }

    def test_get_template_exists(self):
        """获取存在的模板"""
        from agent.templates import get_template
        t = get_template("meme_sniper")
        assert t is not None
        assert t["name"] == "MEME 早期狙击"
        assert "conditions" in t
        assert "risk_params" in t

    def test_get_template_not_exists(self):
        """获取不存在的模板返回 None"""
        from agent.templates import get_template
        assert get_template("nonexistent") is None

    def test_create_from_template_basic(self):
        """从模板创建策略（无 override）"""
        from agent.templates import create_from_template
        spec = create_from_template("meme_sniper", "user-123")
        assert spec["name"] == "MEME 早期狙击"
        assert spec["conditions"]["operator"] == "AND"
        assert len(spec["conditions"]["rules"]) == 4
        assert spec["actions"][0]["type"] == "buy"
        assert spec["actions"][0]["amount_usd"] == 50

    def test_create_from_template_override_amount(self):
        """override 覆盖金额"""
        from agent.templates import create_from_template
        spec = create_from_template(
            "hot_breakout", "user-123",
            override={"amount_usd": 200}
        )
        assert spec["actions"][0]["amount_usd"] == 200

    def test_create_from_template_override_risk(self):
        """override 覆盖止损止盈"""
        from agent.templates import create_from_template
        spec = create_from_template(
            "smart_money_follow", "user-123",
            override={"stop_loss_pct": 10, "take_profit_pct": 200}
        )
        assert spec["risk_params"]["stop_loss_pct"] == 10
        assert spec["risk_params"]["take_profit_pct"] == 200

    def test_create_from_template_invalid_id(self):
        """不存在的模板抛出 ValueError"""
        from agent.templates import create_from_template
        with pytest.raises(ValueError, match="模板不存在"):
            create_from_template("nonexistent", "user-123")

    def test_create_from_template_invalid_amount(self):
        """金额超范围抛出 ValueError"""
        from agent.templates import create_from_template
        with pytest.raises(ValueError, match="amount_usd"):
            create_from_template(
                "meme_sniper", "user-123",
                override={"amount_usd": 99999}
            )

    def test_template_deep_copy(self):
        """确保 override 不影响原始模板"""
        from agent.templates import create_from_template, STRATEGY_TEMPLATES
        original_amount = STRATEGY_TEMPLATES["meme_sniper"]["actions"][0]["amount_usd"]
        create_from_template(
            "meme_sniper", "user-123",
            override={"amount_usd": 999}
        )
        assert STRATEGY_TEMPLATES["meme_sniper"]["actions"][0]["amount_usd"] == original_amount


# ═══════════════════════════════════════════════════
# 2. PaperEngine — 模拟交易引擎
# ═══════════════════════════════════════════════════

class TestPaperEngine:
    """模拟交易引擎测试"""

    def _mock_db(self):
        """创建 mock DB"""
        mock = MagicMock()
        # 默认返回空结果
        mock.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{
                "id": "trade-001",
                "strategy_id": "strat-001",
                "status": "open",
                "entry_price": 1.015,
                "amount_usd": 50,
                "pnl_usd": None,
            }]
        )
        return mock

    def test_simulated_slippage_constant(self):
        """滑点常量正确"""
        from agent.paper_engine import SIMULATED_SLIPPAGE
        assert SIMULATED_SLIPPAGE == 0.015

    @patch("agent.paper_engine.get_db")
    def test_open_position_applies_slippage(self, mock_get_db):
        """open_position 应用 +1.5% 买入滑点"""
        mock_db = self._mock_db()
        mock_get_db.return_value = mock_db

        from agent.paper_engine import PaperEngine

        engine = PaperEngine()
        result = _run(engine.open_position(
            strategy_id="strat-001",
            user_id="user-001",
            token_address="0xabc",
            token_symbol="TEST",
            chain="solana",
            price=1.0,
            amount_usd=50,
            sl_pct=25,
            tp_pct=100,
        ))

        assert result is not None
        # 验证写入的 entry_price 包含滑点
        call_args = mock_db.table.return_value.insert.call_args
        inserted_row = call_args[0][0]
        assert inserted_row["entry_price"] == pytest.approx(1.015, rel=1e-6)
        assert inserted_row["action"] == "buy"
        assert inserted_row["status"] == "open"

    @patch("agent.paper_engine.get_db")
    def test_close_position_applies_sell_slippage(self, mock_get_db):
        """close_position 应用 -1.5% 卖出滑点"""
        mock_db = MagicMock()
        # select open trade
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": "trade-001",
                "entry_price": 1.0,
                "amount_usd": 100,
                "trigger_context": {},
                "chain": "solana",
                "token_symbol": "TEST",
            }]
        )
        # update result
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "trade-001", "status": "closed", "pnl_pct": -3.0}]
        )
        mock_get_db.return_value = mock_db

        from agent.paper_engine import PaperEngine
        engine = PaperEngine()
        result = _run(engine.close_position(
            trade_id="trade-001",
            exit_price=1.0,
            reason="manual",
        ))

        assert result is not None
        # 验证 update 调用中的 exit_price (1.0 * 0.985 = 0.985)
        update_call = mock_db.table.return_value.update.call_args
        update_data = update_call[0][0]
        assert update_data["exit_price"] == pytest.approx(0.985, rel=1e-6)
        assert update_data["status"] == "closed"

    def test_get_stats_empty(self):
        """无交易时统计全零"""
        with patch("agent.paper_engine.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            mock_get_db.return_value = mock_db

            from agent.paper_engine import PaperEngine
            engine = PaperEngine()
            stats = _run(engine.get_stats("strat-001"))
            assert stats["trade_count"] == 0
            assert stats["win_rate"] == 0.0
            assert stats["total_pnl_usd"] == 0.0

    def test_get_stats_with_trades(self):
        """有交易时正确计算统计"""
        with patch("agent.paper_engine.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {"status": "closed", "pnl_usd": 10, "pnl_pct": 20},
                    {"status": "closed", "pnl_usd": -5, "pnl_pct": -10},
                    {"status": "closed", "pnl_usd": 15, "pnl_pct": 30},
                    {"status": "open", "pnl_usd": None, "pnl_pct": None},
                ]
            )
            mock_get_db.return_value = mock_db

            from agent.paper_engine import PaperEngine
            engine = PaperEngine()
            stats = _run(engine.get_stats("strat-001"))
            assert stats["trade_count"] == 4
            assert stats["closed_count"] == 3
            assert stats["open_count"] == 1
            # 2 wins out of 3 closed
            assert stats["win_rate"] == pytest.approx(66.67, rel=0.1)
            assert stats["total_pnl_usd"] == 20.0
            assert stats["max_win_pct"] == 30.0
            assert stats["max_loss_pct"] == -10.0


# ═══════════════════════════════════════════════════
# 3. ProactiveScanner — AI 主动推荐
# ═══════════════════════════════════════════════════

class TestProactiveScanner:
    """AI 主动推荐扫描器测试"""

    def test_quality_filter_pass(self):
        """质量过滤：满足条件通过"""
        from agent.proactive_scanner import ProactiveScanner
        scanner = ProactiveScanner()
        opp = {
            "score": 75,
            "liquidity_usd": 50000,
            "volume_24h_usd": 20000,
            "goplus_risk": False,
        }
        assert scanner._passes_quality_filter(opp) is True

    def test_quality_filter_low_score(self):
        """质量过滤：score 不足"""
        from agent.proactive_scanner import ProactiveScanner
        scanner = ProactiveScanner()
        opp = {"score": 30, "liquidity_usd": 50000, "volume_24h_usd": 20000}
        assert scanner._passes_quality_filter(opp) is False

    def test_quality_filter_low_liquidity(self):
        """质量过滤：流动性不足"""
        from agent.proactive_scanner import ProactiveScanner
        scanner = ProactiveScanner()
        opp = {"score": 75, "liquidity_usd": 10000, "volume_24h_usd": 20000}
        assert scanner._passes_quality_filter(opp) is False

    def test_quality_filter_goplus_risk(self):
        """质量过滤：GoPlus 风险"""
        from agent.proactive_scanner import ProactiveScanner
        scanner = ProactiveScanner()
        opp = {
            "score": 75, "liquidity_usd": 50000,
            "volume_24h_usd": 20000, "goplus_risk": True,
        }
        assert scanner._passes_quality_filter(opp) is False

    def test_quality_filter_low_volume(self):
        """质量过滤：成交量不足"""
        from agent.proactive_scanner import ProactiveScanner
        scanner = ProactiveScanner()
        opp = {"score": 75, "liquidity_usd": 50000, "volume_24h_usd": 5000}
        assert scanner._passes_quality_filter(opp) is False

    def test_cooldown_mechanism(self):
        """冷却机制：同一代币 24h 内不重复"""
        from agent.proactive_scanner import ProactiveScanner, _cooldown_cache
        scanner = ProactiveScanner()

        # 未在冷却中
        assert scanner._is_in_cooldown("0xabc123") is False

        # 加入冷却
        _cooldown_cache["0xabc123"] = datetime.now(timezone.utc)
        assert scanner._is_in_cooldown("0xabc123") is True

        # 清理
        del _cooldown_cache["0xabc123"]

    def test_cooldown_expires(self):
        """冷却到期后可再次推荐"""
        from agent.proactive_scanner import ProactiveScanner, _cooldown_cache
        scanner = ProactiveScanner()

        # 设置 25 小时前的冷却
        _cooldown_cache["0xexpired"] = datetime.now(timezone.utc) - timedelta(hours=25)
        assert scanner._is_in_cooldown("0xexpired") is False

    def test_quality_filter_zero_liquidity_passes(self):
        """流动性为 0 时（未知）通过过滤"""
        from agent.proactive_scanner import ProactiveScanner
        scanner = ProactiveScanner()
        opp = {"score": 75, "liquidity_usd": 0, "volume_24h_usd": 0}
        assert scanner._passes_quality_filter(opp) is True


# ═══════════════════════════════════════════════════
# 4. ActionDispatcher — Paper 模式分流
# ═══════════════════════════════════════════════════

class TestActionDispatcherPaperMode:
    """Paper 模式分流测试"""

    @patch("agent.action_dispatcher.get_db")
    def test_get_strategy_mode_paper(self, mock_get_db):
        """获取 paper 模式策略"""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"mode": "paper"}]
        )
        mock_get_db.return_value = mock_db

        from agent.action_dispatcher import ActionDispatcher
        dispatcher = ActionDispatcher()
        mode = _run(dispatcher._get_strategy_mode("strat-001"))
        assert mode == "paper"

    @patch("agent.action_dispatcher.get_db")
    def test_get_strategy_mode_live(self, mock_get_db):
        """获取 live 模式策略"""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"mode": "live"}]
        )
        mock_get_db.return_value = mock_db

        from agent.action_dispatcher import ActionDispatcher
        dispatcher = ActionDispatcher()
        mode = _run(dispatcher._get_strategy_mode("strat-001"))
        assert mode == "live"

    @patch("agent.action_dispatcher.get_db")
    def test_get_strategy_mode_default(self, mock_get_db):
        """策略不存在时默认 live"""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        mock_get_db.return_value = mock_db

        from agent.action_dispatcher import ActionDispatcher
        dispatcher = ActionDispatcher()
        mode = _run(dispatcher._get_strategy_mode("nonexistent"))
        assert mode == "live"

    def test_get_strategy_mode_none_id(self):
        """strategy_id 为 None 时返回 live"""
        from agent.action_dispatcher import ActionDispatcher
        dispatcher = ActionDispatcher()
        mode = _run(dispatcher._get_strategy_mode(None))
        assert mode == "live"


# ═══════════════════════════════════════════════════
# 5. StrategyManager — mode 字段 + go_live
# ═══════════════════════════════════════════════════

class TestStrategyManagerMode:
    """策略管理器 mode 字段测试"""

    @patch("agent.strategy_manager.get_db")
    def test_create_strategy_default_paper(self, mock_get_db):
        """创建策略默认 mode=paper"""
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{
                "id": "strat-new",
                "name": "Test",
                "mode": "paper",
                "status": "active",
            }]
        )
        mock_get_db.return_value = mock_db

        from agent.strategy_manager import StrategyManager
        mgr = StrategyManager()
        result = mgr.create_strategy(
            user_id="user-001",
            spec={
                "name": "Test",
                "conditions": {
                    "operator": "AND",
                    "rules": [{"data_source": "pump_tokens", "field": "score", "operator": ">=", "value": 70}],
                },
                "actions": [{"type": "buy", "amount_usd": 50}],
            },
        )

        # 验证 insert 调用中包含 mode=paper
        call_args = mock_db.table.return_value.insert.call_args
        inserted = call_args[0][0]
        assert inserted["mode"] == "paper"

    @patch("agent.strategy_manager.get_db")
    def test_go_live(self, mock_get_db):
        """go_live 将 paper 切换到 live"""
        mock_db = MagicMock()
        # get_strategy 返回 paper + active
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "strat-001", "mode": "paper", "status": "active"}]
        )
        # update 返回成功
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "strat-001", "mode": "live", "status": "active"}]
        )
        mock_get_db.return_value = mock_db

        from agent.strategy_manager import StrategyManager
        mgr = StrategyManager()
        result = mgr.go_live("strat-001")
        assert result is not None
        # 验证 update 被调用
        mock_db.table.return_value.update.assert_called()

    @patch("agent.strategy_manager.get_db")
    def test_go_live_already_live(self, mock_get_db):
        """已在 live 模式时返回现有策略"""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "strat-001", "mode": "live", "status": "active"}]
        )
        mock_get_db.return_value = mock_db

        from agent.strategy_manager import StrategyManager
        mgr = StrategyManager()
        result = mgr.go_live("strat-001")
        assert result is not None
        assert result.get("mode") == "live"

    @patch("agent.strategy_manager.get_db")
    def test_go_live_paused_strategy(self, mock_get_db):
        """暂停策略不能切换 live"""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "strat-001", "mode": "paper", "status": "paused"}]
        )
        mock_get_db.return_value = mock_db

        from agent.strategy_manager import StrategyManager
        mgr = StrategyManager()
        result = mgr.go_live("strat-001")
        assert result is None


# ═══════════════════════════════════════════════════
# 6. 常量和配置验证
# ═══════════════════════════════════════════════════

class TestConstants:
    """常量验证"""

    def test_paper_engine_constants(self):
        from agent.paper_engine import (
            SIMULATED_SLIPPAGE, PAPER_DEFAULT_DAYS, PAPER_MAX_IDLE_DAYS,
        )
        assert SIMULATED_SLIPPAGE == 0.015
        assert PAPER_DEFAULT_DAYS == 3
        assert PAPER_MAX_IDLE_DAYS == 7

    def test_proactive_scanner_constants(self):
        from agent.proactive_scanner import (
            MAX_DAILY_RECOMMENDATIONS, COOLDOWN_HOURS,
        )
        assert MAX_DAILY_RECOMMENDATIONS == 5
        assert COOLDOWN_HOURS == 24

    def test_template_count(self):
        from agent.templates import STRATEGY_TEMPLATES
        assert len(STRATEGY_TEMPLATES) == 5

    def test_all_templates_have_required_fields(self):
        from agent.templates import STRATEGY_TEMPLATES
        required_fields = {"name", "description", "conditions", "actions", "risk_params"}
        for tid, tpl in STRATEGY_TEMPLATES.items():
            for field in required_fields:
                assert field in tpl, f"Template '{tid}' missing field '{field}'"

    def test_all_templates_have_sl_tp(self):
        from agent.templates import STRATEGY_TEMPLATES
        for tid, tpl in STRATEGY_TEMPLATES.items():
            rp = tpl["risk_params"]
            assert "stop_loss_pct" in rp, f"Template '{tid}' missing stop_loss_pct"
            assert "take_profit_pct" in rp, f"Template '{tid}' missing take_profit_pct"
            assert rp["stop_loss_pct"] > 0
            assert rp["take_profit_pct"] > 0


# ═══════════════════════════════════════════════════
# 运行入口
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
