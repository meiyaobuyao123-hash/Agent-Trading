"""
R47 — credit_service 单测

只测纯函数 + DB-mocked 路径(不连真 PG):
  - calc_cost 各 model
  - DEV bypass(deduct 跳)
  - estimate_remaining_messages
  - can_proceed 余额不够
  - LLMParser._last_usage 累加器(reset + accumulate)

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_credit_service.py -v
"""
from __future__ import annotations
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import credit_service


# ═════════════════════════════════════════════════════════
# calc_cost
# ═════════════════════════════════════════════════════════

class TestCalcCost:
    def test_sonnet_cost(self):
        # Sonnet $3/$15 per MTok × 1.0005
        # 1000 in + 500 out = 0.003 + 0.0075 = 0.0105 × 1.0005 = 0.01050525
        c = credit_service.calc_cost("claude-sonnet-4-6", 1000, 500)
        assert c == Decimal("0.01050525")

    def test_haiku_cheaper_than_sonnet(self):
        c_h = credit_service.calc_cost("claude-haiku-4-5", 1000, 500)
        c_s = credit_service.calc_cost("claude-sonnet-4-6", 1000, 500)
        assert c_h < c_s

    def test_opus_most_expensive(self):
        c_o = credit_service.calc_cost("claude-opus-4-6", 1000, 500)
        c_s = credit_service.calc_cost("claude-sonnet-4-6", 1000, 500)
        assert c_o > c_s

    def test_unknown_model_fallback_to_sonnet(self):
        c_unknown = credit_service.calc_cost("claude-unknown-model", 1000, 500)
        c_sonnet = credit_service.calc_cost("claude-sonnet-4-6", 1000, 500)
        assert c_unknown == c_sonnet

    def test_zero_tokens(self):
        c = credit_service.calc_cost("claude-sonnet-4-6", 0, 0)
        assert c == Decimal("0")

    def test_markup_applied(self):
        # 不带 markup: 1000*$3 + 500*$15 = 3000 + 7500 = 10500 / 1M = $0.0105
        # 带 markup × 1.0005 = $0.01050525
        c = credit_service.calc_cost("claude-sonnet-4-6", 1000, 500)
        without_markup = Decimal("0.0105")
        assert c > without_markup
        diff = c - without_markup
        assert diff > Decimal("0") and diff < Decimal("0.001")  # 微量


# ═════════════════════════════════════════════════════════
# DEV bypass
# ═════════════════════════════════════════════════════════

class TestDevBypass:
    def test_dev_user_deduct_returns_zero(self):
        """dev-user uuid 在 deduct 时不扣费,直接返 Decimal(0)"""
        result = credit_service.deduct(
            "00000000-0000-0000-0000-000000000001",
            "claude-sonnet-4-6",
            1000, 500,
        )
        assert result == Decimal(0)

    def test_empty_user_id_no_action(self):
        """空 user_id 不操作"""
        # get_balance 直接返 0
        bal = credit_service.get_balance("")
        assert bal == Decimal(0)


# ═════════════════════════════════════════════════════════
# estimate_remaining_messages
# ═════════════════════════════════════════════════════════

class TestEstimateMessages:
    def test_balance_zero(self):
        assert credit_service.estimate_remaining_messages(Decimal("0")) == 0

    def test_balance_one_dollar_sonnet(self):
        # $1 / 单 chat 大概几千 token
        n = credit_service.estimate_remaining_messages(Decimal("1.0"), "claude-sonnet-4-6")
        assert n > 0
        assert n < 100000  # sanity

    def test_haiku_more_messages_than_sonnet_for_same_balance(self):
        n_h = credit_service.estimate_remaining_messages(Decimal("1.0"), "claude-haiku-4-5")
        n_s = credit_service.estimate_remaining_messages(Decimal("1.0"), "claude-sonnet-4-6")
        assert n_h > n_s


# ═════════════════════════════════════════════════════════
# can_proceed (DB mocked)
# ═════════════════════════════════════════════════════════

class TestCanProceed:
    def test_dev_user_always_proceeds(self):
        ok, reason = credit_service.can_proceed("00000000-0000-0000-0000-000000000001")
        assert ok is True
        assert reason is None

    @patch("agent.credit_service.get_balance")
    def test_low_balance_blocked(self, mock_bal):
        mock_bal.return_value = Decimal("0.00005")
        ok, reason = credit_service.can_proceed("real-user-id")
        assert ok is False
        assert reason and "余额" in reason

    @patch("agent.credit_service.get_balance")
    def test_sufficient_balance_passes(self, mock_bal):
        mock_bal.return_value = Decimal("10.0")
        ok, reason = credit_service.can_proceed("real-user-id")
        assert ok is True
        assert reason is None


# ═════════════════════════════════════════════════════════
# LLMParser._last_usage(R47 token 累加器)
# ═════════════════════════════════════════════════════════

class TestLLMParserUsage:
    def test_init_has_last_usage(self):
        from agent.llm_parser import LLMParser
        p = LLMParser(api_key="dummy")
        assert hasattr(p, "_last_usage")
        assert p._last_usage["in"] == 0
        assert p._last_usage["out"] == 0
        assert "model" in p._last_usage

    def test_last_usage_can_be_mutated(self):
        """模拟 parse_strategy 累加 usage"""
        from agent.llm_parser import LLMParser
        p = LLMParser(api_key="dummy")
        # 重置(模拟 parse_strategy 顶部行为)
        p._last_usage = {"in": 0, "out": 0, "model": "claude-sonnet-4-6"}
        # 累加(模拟 messages.create 后)
        p._last_usage["in"] += 100
        p._last_usage["out"] += 50
        p._last_usage["in"] += 200
        p._last_usage["out"] += 80
        assert p._last_usage["in"] == 300
        assert p._last_usage["out"] == 130
