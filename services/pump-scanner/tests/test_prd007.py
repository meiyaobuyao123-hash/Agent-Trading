"""
PRD-007: Multi-Role Agent Architecture — 综合测试

覆盖：
  - TechnicalAnalyst: 分析 + 降级
  - SentimentAnalyst: 分析 + 降级
  - OnchainAnalyst: 分析 + 降级
  - DebateEngine: 辩论流程 + 默认结果
  - DecisionAgent: 决策逻辑（置信度门槛/Regime/已持仓）
  - RiskReviewer: 审查触发条件 + 审查流程
  - MultiRoleOrchestrator: 分级触发 + L1/L2/L3 执行
  - event_listener: 编排器集成

Python 3.9 兼容。
"""

import asyncio
import json
import sys
import os
from typing import Any, Dict
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# 确保能 import 项目模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════

def _run(coro):
    """运行 async 函数"""
    return asyncio.get_event_loop().run_until_complete(coro)


SAMPLE_TOKEN_DATA = {
    "address": "So11111111111111111111111111111111111111112",
    "symbol": "TEST",
    "name": "TestCoin",
    "chain": "solana",
    "price_usd": 0.001,
    "score": 75,
    "market_cap_usd": 500000,
    "liquidity_usd": 100000,
    "volume_1h_usd": 50000,
    "volume_24h_usd": 200000,
    "holder_count": 500,
    "buys_1h": 100,
    "sells_1h": 40,
    "price_change_1h": 15.5,
    "price_change_24h": 45.0,
}

SAMPLE_MARKET_DATA = {
    "fear_greed_index": 35,
    "funding_rate": -0.002,
    "rsi_14": 42,
    "macd": 0.0005,
}


# ═══════════════════════════════════════════════════
# TechnicalAnalyst 测试
# ═══════════════════════════════════════════════════

class TestTechnicalAnalyst:
    def test_no_api_key_returns_neutral(self):
        from agent.analysts.technical import TechnicalAnalyst
        analyst = TechnicalAnalyst(api_key="")
        result = _run(analyst.analyze(SAMPLE_TOKEN_DATA, SAMPLE_MARKET_DATA))
        assert result["direction"] == "neutral"
        assert result["confidence"] == 0.3

    def test_build_input_includes_fields(self):
        from agent.analysts.technical import TechnicalAnalyst
        analyst = TechnicalAnalyst(api_key="fake")
        text = analyst._build_input(SAMPLE_TOKEN_DATA, SAMPLE_MARKET_DATA)
        assert "当前价格" in text
        assert "1h 涨跌幅" in text
        assert "综合评分" in text

    @patch("agent.analysts.technical.anthropic")
    def test_api_call_success(self, mock_anthropic):
        from agent.analysts.technical import TechnicalAnalyst

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "direction": "bullish",
            "confidence": 0.72,
            "points": ["RSI=42 偏低", "金叉确认"],
            "key_level": {"support": 0.0008, "resistance": 0.0015},
        }))]
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 100

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        analyst = TechnicalAnalyst(api_key="test-key")
        result = _run(analyst.analyze(SAMPLE_TOKEN_DATA, SAMPLE_MARKET_DATA))

        assert result["direction"] == "bullish"
        assert result["confidence"] == 0.72
        assert len(result["points"]) == 2
        assert result["_tokens_used"] == 300

    @patch("agent.analysts.technical.anthropic")
    def test_api_json_error_returns_neutral(self, mock_anthropic):
        from agent.analysts.technical import TechnicalAnalyst

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not valid json")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        analyst = TechnicalAnalyst(api_key="test-key")
        result = _run(analyst.analyze(SAMPLE_TOKEN_DATA, SAMPLE_MARKET_DATA))
        assert result["direction"] == "neutral"


# ═══════════════════════════════════════════════════
# SentimentAnalyst 测试
# ═══════════════════════════════════════════════════

class TestSentimentAnalyst:
    def test_no_api_key_returns_neutral(self):
        from agent.analysts.sentiment import SentimentAnalyst
        analyst = SentimentAnalyst(api_key="")
        result = _run(analyst.analyze(SAMPLE_TOKEN_DATA, SAMPLE_MARKET_DATA))
        assert result["direction"] == "neutral"
        assert result["smart_money_signal"] == "neutral"

    def test_build_input_includes_fields(self):
        from agent.analysts.sentiment import SentimentAnalyst
        analyst = SentimentAnalyst(api_key="fake")
        text = analyst._build_input(SAMPLE_TOKEN_DATA, SAMPLE_MARKET_DATA)
        assert "恐慌贪婪指数" in text
        assert "资金费率" in text


# ═══════════════════════════════════════════════════
# OnchainAnalyst 测试
# ═══════════════════════════════════════════════════

class TestOnchainAnalyst:
    def test_no_api_key_returns_neutral(self):
        from agent.analysts.onchain import OnchainAnalyst
        analyst = OnchainAnalyst(api_key="")
        result = _run(analyst.analyze(SAMPLE_TOKEN_DATA))
        assert result["direction"] == "neutral"
        assert result["risk_flag"] == "medium"

    def test_build_input_includes_fields(self):
        from agent.analysts.onchain import OnchainAnalyst
        analyst = OnchainAnalyst(api_key="fake")
        text = analyst._build_input(SAMPLE_TOKEN_DATA, {})
        assert "持有人数" in text
        assert "流动性" in text


# ═══════════════════════════════════════════════════
# DebateEngine 测试
# ═══════════════════════════════════════════════════

class TestDebateEngine:
    def test_no_api_key_returns_default(self):
        from agent.debate import DebateEngine
        engine = DebateEngine(api_key="")
        result = _run(engine.run_debate({"technical": {}, "sentiment": {}, "onchain": {}}))
        assert result["conclusion"]["action"] == "hold"
        assert result["rounds"] == 0

    @patch("agent.debate.anthropic")
    def test_full_debate_flow(self, mock_anthropic):
        from agent.debate import DebateEngine

        call_count = [0]

        def fake_create(**kwargs):
            call_count[0] += 1
            mock_resp = MagicMock()
            if call_count[0] == 5:
                # Facilitator 返回 JSON
                mock_resp.content = [MagicMock(text=json.dumps({
                    "winner": "bull",
                    "confidence": 0.72,
                    "action": "buy",
                    "risk": "流动性偏低",
                    "reasoning": "看多论据更充分",
                }))]
            else:
                mock_resp.content = [MagicMock(text=f"Round {call_count[0]} arguments")]
            mock_resp.usage.input_tokens = 300
            mock_resp.usage.output_tokens = 200
            return mock_resp

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = fake_create
        mock_anthropic.Anthropic.return_value = mock_client

        engine = DebateEngine(api_key="test-key")
        reports = {
            "technical": {"direction": "bullish", "confidence": 0.7},
            "sentiment": {"direction": "neutral", "confidence": 0.5},
            "onchain": {"direction": "bullish", "confidence": 0.6},
        }
        result = _run(engine.run_debate(reports, "记忆上下文"))

        assert result["rounds"] == 3
        assert result["conclusion"]["winner"] == "bull"
        assert result["conclusion"]["action"] == "buy"
        assert result["tokens_used"] == 2500  # 5 calls * 500 tokens
        assert "Bull Round 1" in result["debate_log"]
        assert "Bear Round 2" in result["debate_log"]


# ═══════════════════════════════════════════════════
# DecisionAgent 测试
# ═══════════════════════════════════════════════════

class TestDecisionAgent:
    def test_buy_low_confidence_hold(self):
        from agent.decision_agent import DecisionAgent
        agent = DecisionAgent()
        result = agent.decide(
            conclusion={"action": "buy", "confidence": 0.4, "reasoning": "weak signal"},
            memory_context={"short_term": [], "episodic": [], "semantic": []},
            regime="RANGING",
        )
        assert result["action"] == "hold"
        assert result["skipped_reason"] == "low_confidence_buy"

    def test_buy_adequate_confidence(self):
        from agent.decision_agent import DecisionAgent
        agent = DecisionAgent()
        result = agent.decide(
            conclusion={"action": "buy", "confidence": 0.75, "reasoning": "strong"},
            memory_context={"short_term": [], "episodic": [], "semantic": []},
            regime="TRENDING_UP",
        )
        assert result["action"] == "buy"
        assert result["position_multiplier"] == 1.0
        assert result["skipped_reason"] is None

    def test_crisis_blocks_buy(self):
        from agent.decision_agent import DecisionAgent
        agent = DecisionAgent()
        result = agent.decide(
            conclusion={"action": "buy", "confidence": 0.9, "reasoning": "great opportunity"},
            memory_context={"short_term": [], "episodic": [], "semantic": []},
            regime="CRISIS",
        )
        assert result["action"] == "hold"
        assert result["skipped_reason"] == "crisis_regime"

    def test_trending_down_blocks_buy(self):
        from agent.decision_agent import DecisionAgent
        agent = DecisionAgent()
        result = agent.decide(
            conclusion={"action": "buy", "confidence": 0.8, "reasoning": "ok"},
            memory_context={"short_term": [], "episodic": [], "semantic": []},
            regime="TRENDING_DOWN",
        )
        assert result["action"] == "hold"
        assert result["skipped_reason"] == "trending_down_regime"

    def test_sell_low_confidence_hold(self):
        from agent.decision_agent import DecisionAgent
        agent = DecisionAgent()
        result = agent.decide(
            conclusion={"action": "sell", "confidence": 0.3, "reasoning": "uncertain"},
            memory_context={"short_term": [], "episodic": [], "semantic": []},
            regime="RANGING",
        )
        assert result["action"] == "hold"
        assert result["skipped_reason"] == "low_confidence_sell"

    def test_already_holding_blocks_buy(self):
        from agent.decision_agent import DecisionAgent
        agent = DecisionAgent()
        result = agent.decide(
            conclusion={"action": "buy", "confidence": 0.8, "reasoning": "good"},
            memory_context={"short_term": [], "episodic": [], "semantic": []},
            regime="RANGING",
            existing_position=True,
        )
        assert result["action"] == "hold"
        assert result["skipped_reason"] == "already_holding"

    def test_high_volatility_position_multiplier(self):
        from agent.decision_agent import DecisionAgent
        agent = DecisionAgent()
        result = agent.decide(
            conclusion={"action": "buy", "confidence": 0.8, "reasoning": "go"},
            memory_context={"short_term": [], "episodic": [], "semantic": []},
            regime="HIGH_VOLATILITY",
        )
        assert result["action"] == "buy"
        assert result["position_multiplier"] == 0.5

    def test_recovery_position_multiplier(self):
        from agent.decision_agent import DecisionAgent
        agent = DecisionAgent()
        result = agent.decide(
            conclusion={"action": "buy", "confidence": 0.7, "reasoning": "recovering"},
            memory_context={"short_term": [], "episodic": [], "semantic": []},
            regime="RECOVERY",
        )
        assert result["action"] == "buy"
        assert result["position_multiplier"] == 0.3


# ═══════════════════════════════════════════════════
# RiskReviewer 测试
# ═══════════════════════════════════════════════════

class TestRiskReviewer:
    def test_should_review_high_amount(self):
        from agent.risk_reviewer import RiskReviewer
        reviewer = RiskReviewer()
        assert reviewer.should_review(amount_usd=60, regime="RANGING", debate_confidence=0.8)

    def test_should_review_high_volatility(self):
        from agent.risk_reviewer import RiskReviewer
        reviewer = RiskReviewer()
        assert reviewer.should_review(amount_usd=20, regime="HIGH_VOLATILITY", debate_confidence=0.9)

    def test_should_review_recovery(self):
        from agent.risk_reviewer import RiskReviewer
        reviewer = RiskReviewer()
        assert reviewer.should_review(amount_usd=20, regime="RECOVERY", debate_confidence=0.9)

    def test_should_review_low_confidence(self):
        from agent.risk_reviewer import RiskReviewer
        reviewer = RiskReviewer()
        assert reviewer.should_review(amount_usd=20, regime="RANGING", debate_confidence=0.6)

    def test_no_review_normal(self):
        from agent.risk_reviewer import RiskReviewer
        reviewer = RiskReviewer()
        assert not reviewer.should_review(amount_usd=20, regime="RANGING", debate_confidence=0.8)

    def test_no_api_key_auto_approve(self):
        from agent.risk_reviewer import RiskReviewer
        reviewer = RiskReviewer(api_key="")
        result = _run(reviewer.review(
            trade_details={"action": "buy", "token": "TEST", "chain": "solana", "amount_usd": 100},
            portfolio={"portfolio_value": 1000, "open_positions": 3, "daily_pnl": -5, "drawdown_pct": 0.02},
            regime="RANGING",
            debate_conclusion={"winner": "bull", "confidence": 0.7, "action": "buy", "risk": "low"},
        ))
        assert result["decision"] == "APPROVE"

    @patch("agent.risk_reviewer.anthropic")
    def test_reject_decision(self, mock_anthropic):
        from agent.risk_reviewer import RiskReviewer

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "decision": "REJECT",
            "reason": "仓位已满，风险过高",
            "risk_score": 0.85,
        }))]
        mock_response.usage.input_tokens = 300
        mock_response.usage.output_tokens = 100

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        reviewer = RiskReviewer(api_key="test-key")
        result = _run(reviewer.review(
            trade_details={"action": "buy", "token": "TEST", "chain": "solana", "amount_usd": 100},
            portfolio={"portfolio_value": 1000, "open_positions": 15, "daily_pnl": -30, "drawdown_pct": 0.15},
            regime="HIGH_VOLATILITY",
            debate_conclusion={"winner": "bull", "confidence": 0.55, "action": "buy", "risk": "high vol"},
        ))
        assert result["decision"] == "REJECT"
        assert result["tokens_used"] == 400


# ═══════════════════════════════════════════════════
# MultiRoleOrchestrator 测试
# ═══════════════════════════════════════════════════

class TestMultiRoleOrchestrator:
    def test_determine_level_no_trade_returns_l1(self):
        from agent.multi_role_orchestrator import MultiRoleOrchestrator
        orch = MultiRoleOrchestrator(api_key="fake")
        level = orch.determine_level(
            amount_usd=100, score=90,
            token_address="test", has_trade_action=False,
        )
        assert level == 1

    def test_determine_level_high_amount_returns_l3(self):
        from agent.multi_role_orchestrator import MultiRoleOrchestrator
        orch = MultiRoleOrchestrator(api_key="fake")
        level = orch.determine_level(
            amount_usd=50, score=60,
            token_address="test", has_trade_action=True,
        )
        assert level == 3

    def test_determine_level_high_score_returns_l3(self):
        from agent.multi_role_orchestrator import MultiRoleOrchestrator
        orch = MultiRoleOrchestrator(api_key="fake")
        level = orch.determine_level(
            amount_usd=20, score=75,
            token_address="test", has_trade_action=True,
        )
        assert level == 3

    def test_determine_level_normal_returns_l2(self):
        from agent.multi_role_orchestrator import MultiRoleOrchestrator
        orch = MultiRoleOrchestrator(api_key="fake")
        # Mock memory to return known token
        with patch("agent.multi_role_orchestrator.get_memory_manager") as mock_mem:
            mock_mgr = MagicMock()
            mock_mgr.working.get_recent.return_value = [
                {"token": "test1234", "type": "signal"}
            ]
            mock_mem.return_value = mock_mgr
            level = orch.determine_level(
                amount_usd=20, score=60,
                token_address="test12345678abc", has_trade_action=True,
            )
            assert level == 2

    def test_execute_l1(self):
        from agent.multi_role_orchestrator import MultiRoleOrchestrator
        orch = MultiRoleOrchestrator(api_key="fake")
        result = _run(orch.execute(
            level=1,
            token_data=SAMPLE_TOKEN_DATA,
            market_data=SAMPLE_MARKET_DATA,
            strategy={},
            trade_action={"type": "alert"},
        ))
        assert result["level"] == 1
        assert result["cost_usd"] == 0
        assert result["tokens_used"] == 0

    def test_execute_l2_no_api_key(self):
        from agent.multi_role_orchestrator import MultiRoleOrchestrator
        orch = MultiRoleOrchestrator(api_key="")
        result = _run(orch.execute(
            level=2,
            token_data=SAMPLE_TOKEN_DATA,
            market_data=SAMPLE_MARKET_DATA,
            strategy={},
            trade_action={"type": "buy", "amount_usd": 20},
        ))
        assert result["level"] == 2
        assert result["action"] == "hold"  # no API key → hold

    @patch("agent.multi_role_orchestrator.get_memory_manager")
    @patch("agent.multi_role_orchestrator.get_risk_manager")
    def test_execute_l3_hold_on_low_confidence(self, mock_risk, mock_mem):
        """L3: 辩论结论 confidence < 0.6 → hold"""
        from agent.multi_role_orchestrator import MultiRoleOrchestrator

        mock_mgr = MagicMock()
        mock_mgr.get_context_for_decision.return_value = {
            "short_term": [], "episodic": [], "semantic": []
        }
        mock_mgr.format_for_prompt.return_value = "no memory"
        mock_mem.return_value = mock_mgr

        mock_risk_inst = MagicMock()
        mock_risk_inst._open_positions = {}
        mock_risk_inst.get_risk_summary.return_value = {
            "portfolio_value": 1000, "open_positions": 0,
            "daily_pnl": 0, "drawdown_pct": 0,
        }
        mock_risk.return_value = mock_risk_inst

        orch = MultiRoleOrchestrator(api_key="test-key")

        # Mock all analysts to return bullish
        with patch.object(orch._technical, "analyze", new_callable=AsyncMock) as m_tech, \
             patch.object(orch._sentiment, "analyze", new_callable=AsyncMock) as m_sent, \
             patch.object(orch._onchain, "analyze", new_callable=AsyncMock) as m_onch, \
             patch.object(orch._debate, "run_debate", new_callable=AsyncMock) as m_debate:

            m_tech.return_value = {"direction": "bullish", "confidence": 0.7, "points": []}
            m_sent.return_value = {"direction": "neutral", "confidence": 0.5, "points": []}
            m_onch.return_value = {"direction": "bullish", "confidence": 0.6, "points": []}

            m_debate.return_value = {
                "debate_log": "test log",
                "conclusion": {
                    "winner": "draw",
                    "confidence": 0.45,  # Below 0.6 threshold
                    "action": "buy",
                    "risk": "uncertain",
                    "reasoning": "mixed signals",
                },
                "rounds": 3,
                "tokens_used": 2000,
                "duration_ms": 5000,
            }

            result = _run(orch.execute(
                level=3,
                token_data=SAMPLE_TOKEN_DATA,
                market_data=SAMPLE_MARKET_DATA,
                strategy={},
                trade_action={"type": "buy", "amount_usd": 50},
            ))

            assert result["action"] == "hold"
            assert "置信度不足" in result["reason"]

    def test_stats_tracking(self):
        from agent.multi_role_orchestrator import MultiRoleOrchestrator
        orch = MultiRoleOrchestrator(api_key="fake")
        _run(orch.execute(
            level=1,
            token_data=SAMPLE_TOKEN_DATA,
            market_data=SAMPLE_MARKET_DATA,
            strategy={},
            trade_action={"type": "alert"},
        ))
        stats = orch.get_stats()
        assert stats["l1_count"] == 1
        assert stats["total_cost_usd"] == 0


# ═══════════════════════════════════════════════════
# 集成测试：event_listener + orchestrator
# ═══════════════════════════════════════════════════

class TestEventListenerIntegration:
    """测试 event_listener 正确路由到 orchestrator"""

    @patch("agent.event_listener.get_orchestrator")
    @patch("agent.event_listener._dispatcher")
    @patch("agent.event_listener._strategy_mgr")
    @patch("agent.event_listener._evaluator")
    @patch("agent.event_listener.get_event_bus")
    def test_trade_actions_go_through_orchestrator(
        self, mock_bus, mock_eval, mock_strat_mgr, mock_dispatcher, mock_orch_fn,
    ):
        """交易动作（buy/sell）应该走编排器"""
        from agent.event_listener import _process_event_driven
        from agent.schemas import DataEvent

        # Setup mocks
        mock_bus_inst = AsyncMock()
        mock_bus.return_value = mock_bus_inst

        trigger_event = MagicMock()
        trigger_event.strategy_id = "s1"
        trigger_event.user_id = "u1"
        trigger_event.strategy_name = "test"
        trigger_event.matched_token = "addr"
        trigger_event.matched_chain = "solana"

        mock_eval.evaluate.return_value = [trigger_event]
        mock_strat_mgr.check_daily_limit.return_value = True
        mock_strat_mgr.get_strategy.return_value = {
            "actions": [
                {"type": "alert", "severity": "info"},
                {"type": "buy", "amount_usd": 50},
            ]
        }

        mock_orch = MagicMock()
        mock_orch.determine_level.return_value = 3
        mock_orch.execute = AsyncMock(return_value={
            "action": "buy",
            "amount_usd": 50,
            "confidence": 0.8,
            "reason": "debate approved",
            "tokens_used": 2000,
            "debate_id": "debate-123",
        })
        mock_orch_fn.return_value = mock_orch

        de = DataEvent(
            source="hot_coins",
            data=SAMPLE_TOKEN_DATA,
            chain="solana",
            token_address="So11111111111111111111111111111111111111112",
            token_name="TestCoin",
        )

        strategies = [{"id": "s1"}]
        mock_strat_mgr.get_active_strategies.return_value = strategies

        # 用 patch 替换 _get_cached_strategies
        with patch("agent.event_listener._get_cached_strategies", return_value=strategies):
            count = _run(_process_event_driven([de], "hot_coins"))

        assert count == 1

        # alert 应该直接 dispatch
        mock_dispatcher.dispatch.assert_called()

        # buy 应该走 orchestrator
        mock_orch.execute.assert_called_once()


# ═══════════════════════════════════════════════════
# SQL Migration 测试（验证文件存在且语法正确）
# ═══════════════════════════════════════════════════

class TestMigration:
    def test_migration_file_exists(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "supabase",
            "migrations", "030_agent_debates.sql",
        )
        assert os.path.exists(path), f"Migration file not found: {path}"

    def test_migration_contains_required_columns(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "supabase",
            "migrations", "030_agent_debates.sql",
        )
        with open(path) as f:
            sql = f.read()
        # 验证关键列
        assert "agent_debates" in sql
        assert "technical_report" in sql
        assert "sentiment_report" in sql
        assert "onchain_report" in sql
        assert "debate_log" in sql
        assert "conclusion_action" in sql
        assert "conclusion_confidence" in sql
        assert "risk_review" in sql
        assert "final_action" in sql
        assert "debate_level" in sql
        assert "total_tokens_used" in sql
        assert "idx_debates_token" in sql
