"""
R51 — pricing.yaml 加载 + calc_cost 行为 + 1% 充值手续费 单测

跑法:cd services/pump-scanner && python3 -m pytest tests/test_pricing.py -v
"""
from __future__ import annotations
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import credit_service  # noqa: E402


# ── 1. pricing.yaml 加载完整性 ──────────────────────────────

class TestPricingYaml:

    def test_yaml_loads(self):
        p = Path(__file__).parent.parent / "agent" / "pricing.yaml"
        assert p.exists(), "pricing.yaml 文件缺失"
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert "models" in data
        assert "markup" in data
        assert "recharge_fee_rate" in data
        assert "estimate_assumptions" in data

    def test_each_model_has_in_out(self):
        for model_id, prices in credit_service.LLM_PRICES.items():
            assert "in" in prices, f"{model_id} 缺 in 价"
            assert "out" in prices, f"{model_id} 缺 out 价"
            assert prices["in"] >= 0, f"{model_id} in 价为负"
            assert prices["out"] >= 0, f"{model_id} out 价为负"
            # output 价应当 >= input 价(LLM 业界惯例)
            assert prices["out"] >= prices["in"], f"{model_id} out < in,价格反了?"

    def test_must_have_currently_used_models(self):
        """生产线上跑 chat 用的 model 必须在价目表里(防误删)"""
        REQUIRED = [
            "claude-sonnet-4-6",
            "claude-sonnet-4-20250514",
            "claude-haiku-4-5",
            "claude-opus-4-6",
        ]
        for m in REQUIRED:
            assert m in credit_service.LLM_PRICES, f"必备 model {m} 不在 pricing.yaml"

    def test_markup_in_safe_range(self):
        """markup 在 [1.0, 1.05] 之间(防误改成 100x)"""
        assert Decimal("1.0") <= credit_service.MARKUP <= Decimal("1.05")

    def test_recharge_fee_rate_in_safe_range(self):
        """充值手续费在 (0, 0.05] 之间(防误改)"""
        assert Decimal("0") < credit_service.RECHARGE_FEE_RATE <= Decimal("0.05")


# ── 2. calc_cost 行为(确保跟 R47 P9 hardcoded 行为兼容)──

class TestCalcCost:

    def test_sonnet_3000_in_500_out(self):
        """3000 in + 500 out × Sonnet ($3/$15 per MTok) × markup 1.0
        = (3000 * 3 + 500 * 15) / 1M = 0.0165
        """
        cost = credit_service.calc_cost("claude-sonnet-4-6", 3000, 500)
        # markup=1.0 (R51) → 0.0165
        # markup=1.0005 (pre-R51) → 0.0165 * 1.0005 ≈ 0.01650825
        assert Decimal("0.016") <= cost <= Decimal("0.017")

    def test_haiku_cheaper_than_sonnet(self):
        """同样 token 数,Haiku 必须比 Sonnet 便宜"""
        h = credit_service.calc_cost("claude-haiku-4-5", 1000, 1000)
        s = credit_service.calc_cost("claude-sonnet-4-6", 1000, 1000)
        assert h < s

    def test_opus_5x_sonnet(self):
        """Opus ($15/$75) ≈ Sonnet ($3/$15) × 5"""
        s = credit_service.calc_cost("claude-sonnet-4-6", 1000, 1000)
        o = credit_service.calc_cost("claude-opus-4-6", 1000, 1000)
        ratio = o / s
        assert Decimal("4.5") < ratio < Decimal("5.5")

    def test_unknown_model_falls_back_to_sonnet(self):
        """未知 model 用 Sonnet 价(保守 + 不崩)"""
        cost = credit_service.calc_cost("unknown-model-xyz", 1000, 1000)
        s = credit_service.calc_cost("claude-sonnet-4-6", 1000, 1000)
        assert cost == s

    def test_zero_tokens_zero_cost(self):
        assert credit_service.calc_cost("claude-sonnet-4-6", 0, 0) == Decimal("0")


# ── 3. 1% 充值手续费(R51 新加)─────────────────────────────

class TestRechargeFee:
    """confirm_recharge_order 计算 fee + amount_credited 的 Decimal 计算正确性
    (不真调 DB,只测算法部分)
    """

    def test_100_dollar_fee_1_dollar(self):
        amount = Decimal("100")
        fee = (amount * credit_service.RECHARGE_FEE_RATE).quantize(Decimal("0.01"))
        credited = amount - fee
        assert fee == Decimal("1.00")
        assert credited == Decimal("99.00")

    def test_1_dollar_fee_1_cent(self):
        amount = Decimal("1")
        fee = (amount * credit_service.RECHARGE_FEE_RATE).quantize(Decimal("0.01"))
        credited = amount - fee
        assert fee == Decimal("0.01")
        assert credited == Decimal("0.99")

    def test_500_dollar_fee_5_dollar(self):
        amount = Decimal("500")
        fee = (amount * credit_service.RECHARGE_FEE_RATE).quantize(Decimal("0.01"))
        credited = amount - fee
        assert fee == Decimal("5.00")
        assert credited == Decimal("495.00")

    def test_estimate_for_recharge_100_sonnet(self):
        """充 $100 → 扣 1% → 余 $99 → 按 3000 in / 500 out @ Sonnet → ~6000 次"""
        n = credit_service.estimate_messages_for_recharge(Decimal("100"), "claude-sonnet-4-6")
        # 99 / 0.0165 ≈ 6000
        assert 5500 < n < 6500

    def test_estimate_for_recharge_100_haiku_much_more(self):
        """同样 $100 充值,Haiku 应该能问明显更多(因为价格 1/12)"""
        sonnet = credit_service.estimate_messages_for_recharge(Decimal("100"), "claude-sonnet-4-6")
        haiku = credit_service.estimate_messages_for_recharge(Decimal("100"), "claude-haiku-4-5")
        assert haiku > sonnet * 5  # Haiku 应能问至少 5x


# ── 4. estimate_remaining_messages 行为 ────────────────────

class TestEstimateMessages:

    def test_zero_balance_zero_messages(self):
        n = credit_service.estimate_remaining_messages(Decimal("0"), "claude-sonnet-4-6")
        assert n == 0

    def test_99_dollar_balance_messages_count(self):
        """$99 余额 / Sonnet $0.0165 per call = ~6000 次"""
        n = credit_service.estimate_remaining_messages(Decimal("99"), "claude-sonnet-4-6")
        assert 5500 < n < 6500

    def test_uses_pricing_yaml_assumptions(self):
        """estimate 必须用 yaml 里的 ESTIMATE_AVG_IN/OUT,而非历史 800/300 硬编码"""
        assert credit_service.ESTIMATE_AVG_IN == 3000
        assert credit_service.ESTIMATE_AVG_OUT == 500
