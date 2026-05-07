"""
R47 P4 — sl_pct/tp_pct 单位 bug 修复单测

背景:
  audit 发现 ALL 3150 paper trades sl_pct=0.1 / tp_pct=0.1 — 整个系统 mixed unit:
  - schemas.py / llm_parser SYSTEM_PROMPT 描述了 ratio (0.05-0.50)
  - paper_engine / position_monitor / templates 实现 assume percent (5-50)
  - LLM 写 ratio,被 clamp 到 0.05-0.50,paper_engine 当 percent 解读 → 0.3% 一动就 SL

修复:
  1. schemas.py RiskParams ge=1 le=90 + ratio (0<x<1) 拒收 validator
  2. llm_parser SYSTEM_PROMPT + _normalize_spec auto migrate ratio→percent
  3. paper_engine sanity check < 1 跳过 + log error
  4. fix_paper_trades_unit.sql 修历史数据

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_paper_engine_units.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import pydantic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ═════════════════════════════════════════════════════════
# 1. Pydantic schema 单元测试
# ═════════════════════════════════════════════════════════

class TestSchemaRejectRatio:
    def test_pydantic_accepts_30_percent(self):
        """percent 整数 30 应通过(30%)"""
        from agent.schemas import ActionSpec
        a = ActionSpec(type="buy", stop_loss_pct=30, take_profit_pct=100)
        assert a.stop_loss_pct == 30
        assert a.take_profit_pct == 100

    def test_pydantic_accepts_boundary_values(self):
        """边界值 1 / 90 / 10000 都接受"""
        from agent.schemas import ActionSpec
        ActionSpec(type="buy", stop_loss_pct=1)
        ActionSpec(type="buy", stop_loss_pct=90)
        ActionSpec(type="buy", take_profit_pct=10000)

    def test_pydantic_rejects_ratio_below_1(self):
        """0 < x < 1 应被 validator 拒收(ratio 单位 — Pydantic ge=1 或 custom validator 都拦)"""
        from agent.schemas import ActionSpec
        with pytest.raises(pydantic.ValidationError):
            ActionSpec(type="buy", stop_loss_pct=0.3)
        with pytest.raises(pydantic.ValidationError):
            ActionSpec(type="buy", take_profit_pct=0.5)

    def test_pydantic_rejects_zero(self):
        """0 也是非法(ge=1)"""
        from agent.schemas import ActionSpec
        with pytest.raises(pydantic.ValidationError):
            ActionSpec(type="buy", stop_loss_pct=0)

    def test_pydantic_rejects_above_max(self):
        """sl_pct > 90 拒(止损不可能 100% 以上)"""
        from agent.schemas import ActionSpec
        with pytest.raises(pydantic.ValidationError):
            ActionSpec(type="buy", stop_loss_pct=95)


# ═════════════════════════════════════════════════════════
# 2. _normalize_spec ratio→percent 自动迁移
# ═════════════════════════════════════════════════════════

class TestNormalizeAutoMigrate:
    def test_normalize_keeps_percent_value(self):
        """LLM 写 percent (30) → 保留 30"""
        from agent.llm_parser import LLMParser
        p = LLMParser(api_key="dummy")
        out = p._normalize_spec({
            "name": "x",
            "conditions": {"operator": "AND", "rules": []},
            "risk_params": {"stop_loss_pct": 30, "take_profit_pct": 100},
        })
        assert out["risk_params"]["stop_loss_pct"] == 30
        assert out["risk_params"]["take_profit_pct"] == 100

    def test_normalize_migrates_ratio_to_percent(self):
        """LLM 误传 ratio (0.3 / 0.5) → 自动 ×100 转 30 / 50"""
        from agent.llm_parser import LLMParser
        p = LLMParser(api_key="dummy")
        out = p._normalize_spec({
            "name": "x",
            "conditions": {"operator": "AND", "rules": []},
            "risk_params": {"stop_loss_pct": 0.3, "take_profit_pct": 0.5},
        })
        assert out["risk_params"]["stop_loss_pct"] == 30
        assert out["risk_params"]["take_profit_pct"] == 50

    def test_normalize_clamps_to_max(self):
        """sl_pct > 90 → clamp 到 90"""
        from agent.llm_parser import LLMParser
        p = LLMParser(api_key="dummy")
        out = p._normalize_spec({
            "name": "x",
            "conditions": {"operator": "AND", "rules": []},
            "risk_params": {"stop_loss_pct": 200, "take_profit_pct": 100},
        })
        assert out["risk_params"]["stop_loss_pct"] == 90


# ═════════════════════════════════════════════════════════
# 3. paper_engine sanity check
# ═════════════════════════════════════════════════════════

class TestPaperEngineSanity:
    @pytest.mark.asyncio
    async def test_paper_engine_skips_ratio_with_log(self, caplog):
        """sl_pct < 1 应跳过本仓 + log error"""
        import logging
        from agent.paper_engine import PaperEngine

        engine = PaperEngine.__new__(PaperEngine)  # bypass __init__

        # mock get_db().table().select().eq().execute() 返一条 ratio 单位的 trade
        bad_trade = {
            "id": "bad-trade-1",
            "token_address": "0xtest",
            "entry_price": 1.0,
            "sl_pct": 0.3,           # ratio 误存
            "tp_pct": 1.0,           # ratio 误存
            "status": "open",
        }

        # mock get_db chain
        mock_query = MagicMock()
        mock_query.execute.return_value = MagicMock(data=[bad_trade])
        mock_eq = MagicMock(return_value=mock_query)
        mock_select = MagicMock()
        mock_select.eq = mock_eq
        mock_table = MagicMock(return_value=mock_select)
        mock_db = MagicMock()
        mock_db.table = MagicMock(return_value=MagicMock(select=MagicMock(return_value=mock_select)))

        # mock close_position 应该 NOT 被调到(因为 sanity check 跳过)
        engine.close_position = AsyncMock()

        with patch("agent.paper_engine.get_db", return_value=mock_db), \
             patch("price_feed.price_feed.get_token_price", return_value=2.0), \
             caplog.at_level(logging.ERROR, logger="agent.paper_engine"):
            count = await engine.check_exits()

        assert count == 0
        engine.close_position.assert_not_called()
        # 应有 ERROR log 报警 ratio 误存
        assert any("ratio_unit_skip" in rec.getMessage()
                   for rec in caplog.records if rec.levelname == "ERROR")

    @pytest.mark.asyncio
    async def test_paper_engine_triggers_sl_at_correct_threshold(self, caplog):
        """sl_pct=30 时,价跌 31% 触发 SL"""
        from agent.paper_engine import PaperEngine

        engine = PaperEngine.__new__(PaperEngine)
        good_trade = {
            "id": "good-trade-1",
            "token_address": "0xtest",
            "entry_price": 1.0,
            "sl_pct": 30,         # 正确 percent
            "tp_pct": 100,
            "status": "open",
        }

        mock_select = MagicMock()
        mock_select.eq = MagicMock(return_value=MagicMock(execute=MagicMock(
            return_value=MagicMock(data=[good_trade]))))
        mock_db = MagicMock()
        mock_db.table = MagicMock(return_value=MagicMock(select=MagicMock(return_value=mock_select)))

        engine.close_position = AsyncMock()

        # 价 1.0 → 0.69 = -31% > sl_pct=30,触发 SL
        with patch("agent.paper_engine.get_db", return_value=mock_db), \
             patch("price_feed.price_feed.get_token_price", return_value=0.69):
            count = await engine.check_exits()

        assert count == 1
        engine.close_position.assert_called_once()
        # 验证 reason="sl"
        kwargs = engine.close_position.call_args.kwargs
        assert kwargs.get("reason") == "sl"

    @pytest.mark.asyncio
    async def test_paper_engine_no_trigger_below_sl(self):
        """sl_pct=30 时,价跌 5% 不触发"""
        from agent.paper_engine import PaperEngine

        engine = PaperEngine.__new__(PaperEngine)
        good_trade = {
            "id": "good-trade-2",
            "token_address": "0xtest",
            "entry_price": 1.0,
            "sl_pct": 30,
            "tp_pct": 100,
            "status": "open",
        }

        mock_select = MagicMock()
        mock_select.eq = MagicMock(return_value=MagicMock(execute=MagicMock(
            return_value=MagicMock(data=[good_trade]))))
        mock_db = MagicMock()
        mock_db.table = MagicMock(return_value=MagicMock(select=MagicMock(return_value=mock_select)))

        engine.close_position = AsyncMock()

        # 价 0.95 = -5% < sl_pct=30,不触发
        with patch("agent.paper_engine.get_db", return_value=mock_db), \
             patch("price_feed.price_feed.get_token_price", return_value=0.95):
            count = await engine.check_exits()

        assert count == 0
        engine.close_position.assert_not_called()
