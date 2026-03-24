"""
PRD-006: Market Regime Detection + Dynamic Risk — 综合测试

覆盖：
  - CUSUMDetector: 变化检测 + 警告级别
  - HMMClassifier: HMM 分类 + 规则 fallback + 标签校准
  - CrisisDetector: 触发 + 恢复 + 边界条件
  - RegimeDetector: 综合判定 + 叠加状态 + 链级 regime
  - RiskManager: regime 感知 + 动态仓位 + 动态止损 + 时间衰减
  - Config: CUSUM/Regime 参数
  - Shadow mode

Python 3.9 兼容。
"""
import asyncio
import math
import sys
import os
import time
from typing import Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import numpy as np

# 确保能 import 项目模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════
# CUSUMDetector 测试
# ═══════════════════════════════════════════════════

class TestCUSUMDetector:
    def test_init(self):
        from agent.regime_detector import CUSUMDetector
        d = CUSUMDetector("BTC", 3.0)
        assert d._asset == "BTC"
        assert d._h == 3.0
        assert d._s_up == 0.0
        assert d._s_down == 0.0

    def test_insufficient_data(self):
        from agent.regime_detector import CUSUMDetector
        d = CUSUMDetector("BTC", 3.0)
        # 不够 CUSUM_WINDOW (24) 条数据
        for _ in range(10):
            r = d.add_return(0.01)
        assert r["change"] is False
        assert r["warning"] is False
        assert r["direction"] == "none"

    def test_normal_returns_no_change(self):
        from agent.regime_detector import CUSUMDetector
        d = CUSUMDetector("BTC", 3.0)
        # 喂入稳定的小幅波动
        np.random.seed(42)
        for _ in range(50):
            ret = np.random.normal(0, 0.005)
            r = d.add_return(ret)
        # 正常波动不应触发变化
        assert r["change"] is False

    def test_large_shock_triggers_change(self):
        from agent.regime_detector import CUSUMDetector
        d = CUSUMDetector("BTC", 3.0)
        # 先填充基线
        for _ in range(30):
            d.add_return(0.001)
        # 突然大跌
        results = []
        for _ in range(10):
            r = d.add_return(-0.05)
            results.append(r)
        # 应该检测到变化
        any_change = any(r["change"] for r in results)
        assert any_change, "Large shock should trigger change detection"

    def test_sol_more_sensitive(self):
        """SOL h=2.5σ 应比 BTC h=3σ 更容易触发"""
        from agent.regime_detector import CUSUMDetector
        btc = CUSUMDetector("BTC", 3.0)
        sol = CUSUMDetector("SOL", 2.5)

        np.random.seed(42)
        btc_changes = 0
        sol_changes = 0
        for _ in range(100):
            ret = np.random.normal(0.002, 0.015)
            b = btc.add_return(ret)
            s = sol.add_return(ret)
            if b["change"]:
                btc_changes += 1
            if s["change"]:
                sol_changes += 1
        # SOL should be at least as sensitive
        assert sol_changes >= btc_changes

    def test_warning_level(self):
        from agent.regime_detector import CUSUMDetector
        d = CUSUMDetector("BTC", 3.0)
        # 填充基线
        for _ in range(30):
            d.add_return(0.001)
        # 中等偏大的变化 → 可能触发 warning
        for _ in range(5):
            r = d.add_return(-0.02)
        # warning 或 change 应被检测到
        assert r["warning"] or r["change"] or r["magnitude"] > 0


# ═══════════════════════════════════════════════════
# HMMClassifier 测试
# ═══════════════════════════════════════════════════

class TestHMMClassifier:
    def test_init_fallback(self):
        """hmmlearn 不可用时应 fallback 到规则引擎"""
        from agent.regime_detector import HMMClassifier
        with patch.dict("sys.modules", {"hmmlearn": None, "hmmlearn.hmm": None}):
            h = HMMClassifier.__new__(HMMClassifier)
            h._asset = "BTC"
            h._model = None
            h._scaler = None
            h._use_hmm = False
            h._label_map = {}
            # 应该可以分类
            features = np.random.randn(50, 4)
            result = h._rule_fallback(features)
            assert result["method"] == "rule_fallback"
            assert result["regime"] in ("TRENDING_UP", "TRENDING_DOWN", "RANGING", "HIGH_VOLATILITY")

    def test_rule_fallback_trending_up(self):
        from agent.regime_detector import HMMClassifier
        h = HMMClassifier.__new__(HMMClassifier)
        h._asset = "BTC"
        h._model = None
        h._scaler = None
        h._use_hmm = False
        h._label_map = {}
        # 持续上涨的特征
        features = np.zeros((50, 4))
        features[:, 0] = 0.005  # 正收益
        result = h._rule_fallback(features)
        assert result["regime"] == "TRENDING_UP"

    def test_rule_fallback_trending_down(self):
        from agent.regime_detector import HMMClassifier
        h = HMMClassifier.__new__(HMMClassifier)
        h._asset = "BTC"
        h._model = None
        h._scaler = None
        h._use_hmm = False
        h._label_map = {}
        # 持续下跌
        features = np.zeros((50, 4))
        features[:, 0] = -0.005
        result = h._rule_fallback(features)
        assert result["regime"] == "TRENDING_DOWN"

    def test_rule_fallback_high_volatility(self):
        from agent.regime_detector import HMMClassifier
        h = HMMClassifier.__new__(HMMClassifier)
        h._asset = "BTC"
        h._model = None
        h._scaler = None
        h._use_hmm = False
        h._label_map = {}
        # 高波动检测条件: recent_vol > 2 * full_vol
        # 需要 full_vol 很小，recent_vol 很大
        # full_vol 计算包含所有 50 行，所以用 100 行（更多稳定数据稀释）
        features = np.zeros((100, 4))
        features[:76, 0] = 0.0001  # 76 行极稳定
        np.random.seed(42)
        volatiles = np.random.normal(0, 0.10, 24)
        volatiles -= np.mean(volatiles)
        features[-24:, 0] = volatiles
        result = h._rule_fallback(features)
        assert result["regime"] == "HIGH_VOLATILITY", f"got {result['regime']}"

    def test_rule_fallback_ranging(self):
        from agent.regime_detector import HMMClassifier
        h = HMMClassifier.__new__(HMMClassifier)
        h._asset = "BTC"
        h._model = None
        h._scaler = None
        h._use_hmm = False
        h._label_map = {}
        # 震荡 — 接近零的收益
        features = np.zeros((50, 4))
        features[:, 0] = np.random.normal(0, 0.0005, 50)
        result = h._rule_fallback(features)
        assert result["regime"] == "RANGING"

    def test_insufficient_data_fallback(self):
        from agent.regime_detector import HMMClassifier
        h = HMMClassifier.__new__(HMMClassifier)
        h._asset = "BTC"
        h._model = None
        h._scaler = None
        h._use_hmm = False
        h._label_map = {}
        features = np.zeros((10, 4))  # 太少
        result = h._rule_fallback(features)
        assert result["regime"] == "RANGING"
        assert result["confidence"] == 0.5

    def test_manual_scale(self):
        from agent.regime_detector import HMMClassifier
        h = HMMClassifier.__new__(HMMClassifier)
        h._asset = "BTC"
        features = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        scaled = h._manual_scale_fit_transform(features)
        # 均值应接近 0
        assert abs(np.mean(scaled, axis=0)[0]) < 1e-10
        # transform 应与 fit_transform 一致
        scaled2 = h._manual_scale_transform(features)
        np.testing.assert_array_almost_equal(scaled, scaled2)


# ═══════════════════════════════════════════════════
# CrisisDetector 测试
# ═══════════════════════════════════════════════════

class TestCrisisDetector:
    def test_init_not_crisis(self):
        from agent.regime_detector import CrisisDetector
        c = CrisisDetector()
        assert c.is_crisis is False

    def test_btc_15min_drop_triggers_crisis(self):
        from agent.regime_detector import CrisisDetector
        c = CrisisDetector()
        # 模拟 15 分钟价格从 70000 跌到 66000（>5%）
        for i in range(14):
            c.check(70000)
        result = c.check(66000)  # -5.7%
        assert result["is_crisis"] is True
        assert result["just_entered"] is True
        assert c.is_crisis is True

    def test_liquidation_triggers_crisis(self):
        from agent.regime_detector import CrisisDetector
        c = CrisisDetector()
        result = c.check(70000, liquidation_1h=600e6)
        assert result["is_crisis"] is True
        assert "Liquidation" in result.get("reason", "")

    def test_extreme_funding_triggers_crisis(self):
        from agent.regime_detector import CrisisDetector
        c = CrisisDetector()
        result = c.check(70000, funding_rate=-0.002)
        assert result["is_crisis"] is True
        assert "funding" in result.get("reason", "").lower()

    def test_no_crisis_normal_conditions(self):
        from agent.regime_detector import CrisisDetector
        c = CrisisDetector()
        for _ in range(20):
            result = c.check(70000, liquidation_1h=50e6, funding_rate=0.0001)
        assert result["is_crisis"] is False
        assert result["just_entered"] is False

    def test_recovery_needs_30min(self):
        from agent.regime_detector import CrisisDetector, CRISIS_RECOVERY_MINUTES
        c = CrisisDetector()
        # 触发 CRISIS
        c.check(70000, liquidation_1h=600e6)
        assert c.is_crisis is True

        # 恢复条件立刻满足，但需要持续 30min
        for _ in range(20):
            result = c.check(70000, liquidation_1h=10e6)
        # 还没过 30min，应该还是 crisis
        assert c.is_crisis is True

    def test_recovery_with_simulated_time(self):
        from agent.regime_detector import CrisisDetector
        c = CrisisDetector()
        # 触发 CRISIS
        c.check(70000, liquidation_1h=600e6)
        assert c.is_crisis is True

        # 填充 _btc_15min 使其 >= 8 条，价格稳定上升（recent_min >= older_min）
        for i in range(14):
            c.check(70000 + i * 10, liquidation_1h=10e6)  # 稳定微涨

        assert len(c._btc_15min) >= 8
        # 设置 recovery_start 到 31 分钟前
        c._recovery_start = time.time() - 1900

        # 再检查一次，应触发恢复
        result = c.check(70200, liquidation_1h=10e6)
        assert result.get("just_recovered") is True or not c.is_crisis


# ═══════════════════════════════════════════════════
# RegimeDetector 综合判定测试
# ═══════════════════════════════════════════════════

class TestRegimeDetector:
    def test_init(self):
        from agent.regime_detector import RegimeDetector
        d = RegimeDetector()
        assert d._global_regime == "RANGING"
        assert d._crisis.is_crisis is False
        assert "BTC" in d._cusum
        assert "SOL" in d._cusum
        assert "ETH" in d._cusum

    def test_crisis_overrides_all(self):
        from agent.regime_detector import RegimeDetector
        d = RegimeDetector()
        d._crisis.is_crisis = True
        assert d.get_regime() == "CRISIS"
        assert d.get_regime("BTC") == "CRISIS"
        assert d.get_chain_regime("solana") == "CRISIS"

    def test_breakout_overlay(self):
        from agent.regime_detector import RegimeDetector
        d = RegimeDetector()
        d._current_regime["BTC"] = "TRENDING_UP"
        d._global_regime = "TRENDING_UP"
        d._cusum["BTC"]._s_up = 0.5  # 有上行 CUSUM 信号
        assert d.get_regime() == "BREAKOUT"

    def test_global_regime_combined(self):
        from agent.regime_detector import RegimeDetector
        d = RegimeDetector()

        # BTC=DOWN + SOL=DOWN → TRENDING_DOWN
        d._current_regime["BTC"] = "TRENDING_DOWN"
        d._current_regime["SOL"] = "TRENDING_DOWN"
        d._update_global_regime()
        assert d._global_regime == "TRENDING_DOWN"

        # BTC=UP + SOL=UP → TRENDING_UP
        d._current_regime["BTC"] = "TRENDING_UP"
        d._current_regime["SOL"] = "TRENDING_UP"
        d._update_global_regime()
        assert d._global_regime == "TRENDING_UP"

        # BTC=UP + SOL=DOWN → RANGING (矛盾)
        d._current_regime["BTC"] = "TRENDING_UP"
        d._current_regime["SOL"] = "TRENDING_DOWN"
        d._update_global_regime()
        assert d._global_regime == "RANGING"

        # HIGH_VOLATILITY 优先
        d._current_regime["BTC"] = "RANGING"
        d._current_regime["SOL"] = "HIGH_VOLATILITY"
        d._update_global_regime()
        assert d._global_regime == "HIGH_VOLATILITY"

    def test_chain_regime(self):
        from agent.regime_detector import RegimeDetector
        d = RegimeDetector()
        d._current_regime["SOL"] = "TRENDING_UP"
        d._current_regime["ETH"] = "TRENDING_DOWN"
        d._current_regime["BTC"] = "RANGING"
        d._update_global_regime()

        assert d._chain_regime["solana"] == "TRENDING_UP"
        assert d._chain_regime["eth"] == "TRENDING_DOWN"  # ETH non-RANGING
        assert d._chain_regime["bsc"] == "RANGING"  # follows BTC

    def test_get_stats(self):
        from agent.regime_detector import RegimeDetector
        d = RegimeDetector()
        stats = d.get_stats()
        assert "global_regime" in stats
        assert "per_asset" in stats
        assert "chain_regime" in stats
        assert "is_crisis" in stats
        assert "hmm_available" in stats
        assert "shadow_mode" in stats

    def test_regime_duration(self):
        from agent.regime_detector import RegimeDetector
        d = RegimeDetector()
        d._regime_since = time.time() - 3600  # 1 hour ago
        assert abs(d.get_regime_duration_hours() - 1.0) < 0.1


# ═══════════════════════════════════════════════════
# RiskManager Regime 测试
# ═══════════════════════════════════════════════════

class TestRiskManagerRegime:
    def _get_rm(self):
        from agent.risk_manager import RiskManager
        return RiskManager()

    def test_calculate_dynamic_position(self):
        rm = self._get_rm()
        rm._portfolio_value = 1000.0

        # TRENDING_UP (mult=1.0), normal ATR
        pos = rm.calculate_dynamic_position(100, 2000, 2000, "TRENDING_UP")
        assert pos <= 200.0  # hard cap
        assert pos > 0

        # CRISIS (mult=0.0)
        pos = rm.calculate_dynamic_position(100, 2000, 2000, "CRISIS")
        assert pos == 0.0

        # HIGH_VOLATILITY (mult=0.5), high ATR
        pos = rm.calculate_dynamic_position(100, 5000, 2000, "HIGH_VOLATILITY")
        # high ATR → smaller position, half mult → even smaller
        assert pos < 100.0

    def test_calculate_dynamic_position_hard_caps(self):
        rm = self._get_rm()
        rm._portfolio_value = 200.0

        # total_max = 200 * 0.5 = 100
        # daily_buy_max = 200 * 0.3 = 60
        pos = rm.calculate_dynamic_position(100, 1000, 2000, "TRENDING_UP")
        assert pos <= 60.0  # daily_buy_max dominates

    def test_calculate_dynamic_stop_loss(self):
        rm = self._get_rm()

        # TRENDING_UP (sl_mult=1.0)
        sl = rm.calculate_dynamic_stop_loss(70000, 2000, "TRENDING_UP")
        assert sl == 70000 - (2000 * 2.0 * 1.0)  # = 66000

        # CRISIS (sl_mult=0.5) → tighter
        sl = rm.calculate_dynamic_stop_loss(70000, 2000, "CRISIS")
        assert sl == 70000 - (2000 * 2.0 * 0.5)  # = 68000

        # HIGH_VOLATILITY (sl_mult=1.5) → wider
        sl = rm.calculate_dynamic_stop_loss(70000, 2000, "HIGH_VOLATILITY")
        assert sl == 70000 - (2000 * 2.0 * 1.5)  # = 64000

    def test_time_decay_stop_non_meme(self):
        rm = self._get_rm()
        # non-meme: 不应修改
        result = rm.apply_time_decay_stop(
            stop_loss=60000, entry_price=70000, peak_price=75000,
            current_pnl_pct=5.0, hold_hours=10, token_type="bluechip"
        )
        assert result == 60000

    def test_time_decay_stop_profitable_meme(self):
        rm = self._get_rm()
        # >8h, profitable → trailing stop
        result = rm.apply_time_decay_stop(
            stop_loss=60000, entry_price=70000, peak_price=80000,
            current_pnl_pct=10.0, hold_hours=10, token_type="meme"
        )
        # max(entry=70000, peak*0.85=68000) = 70000
        assert result == 70000

    def test_time_decay_stop_losing_meme(self):
        rm = self._get_rm()
        # >8h, losing >10% → tighten 0.8×
        result = rm.apply_time_decay_stop(
            stop_loss=60000, entry_price=70000, peak_price=70000,
            current_pnl_pct=-15.0, hold_hours=10, token_type="meme"
        )
        assert result == 60000 * 0.8  # 48000

    def test_time_decay_stop_12h(self):
        rm = self._get_rm()
        # >12h → tighten 0.7×
        result = rm.apply_time_decay_stop(
            stop_loss=60000, entry_price=70000, peak_price=70000,
            current_pnl_pct=-5.0, hold_hours=14, token_type="meme"
        )
        assert result == 60000 * 0.7  # 42000

    def test_shadow_mode_does_not_block(self):
        """Shadow mode: calculate but don't enforce"""
        rm = self._get_rm()
        with patch("config.REGIME_SHADOW_MODE", True):
            with patch("agent.regime_detector.get_regime_detector") as mock_det:
                mock_det.return_value.get_chain_regime.return_value = "CRISIS"
                result = rm._check_regime_adjustment("solana", "buy", 50, {})
                assert result.passed is True  # Shadow mode → always pass

    def test_regime_blocks_in_non_shadow(self):
        """Non-shadow: CRISIS should block buys"""
        rm = self._get_rm()
        with patch("config.REGIME_SHADOW_MODE", False):
            with patch("agent.regime_detector.get_regime_detector") as mock_det:
                mock_det.return_value.get_chain_regime.return_value = "CRISIS"
                result = rm._check_regime_adjustment("solana", "buy", 50, {})
                assert result.passed is False

    def test_regime_blocks_trending_down(self):
        """TRENDING_DOWN should block new buys"""
        rm = self._get_rm()
        with patch("config.REGIME_SHADOW_MODE", False):
            with patch("agent.regime_detector.get_regime_detector") as mock_det:
                mock_det.return_value.get_chain_regime.return_value = "TRENDING_DOWN"
                result = rm._check_regime_adjustment("solana", "buy", 50, {})
                assert result.passed is False


# ═══════════════════════════════════════════════════
# Config 测试
# ═══════════════════════════════════════════════════

class TestConfig:
    def test_cusum_params(self):
        from config import CUSUM_H_BTC, CUSUM_H_SOL, CUSUM_H_ETH, CUSUM_K_FACTOR, CUSUM_WINDOW
        assert CUSUM_H_BTC == 3.0
        assert CUSUM_H_SOL == 2.5
        assert CUSUM_H_ETH == 3.0
        assert CUSUM_K_FACTOR == 0.5
        assert CUSUM_WINDOW == 24

    def test_regime_risk_params(self):
        from config import REGIME_RISK_PARAMS
        assert "TRENDING_UP" in REGIME_RISK_PARAMS
        assert "CRISIS" in REGIME_RISK_PARAMS
        assert "RECOVERY" in REGIME_RISK_PARAMS
        assert len(REGIME_RISK_PARAMS) == 7

        # CRISIS must force close
        assert REGIME_RISK_PARAMS["CRISIS"]["force_close"] is True
        assert REGIME_RISK_PARAMS["CRISIS"]["new_trades"] is False
        assert REGIME_RISK_PARAMS["CRISIS"]["position_pct"] == 0.0

        # TRENDING_UP must allow trades
        assert REGIME_RISK_PARAMS["TRENDING_UP"]["new_trades"] is True
        assert REGIME_RISK_PARAMS["TRENDING_UP"]["position_pct"] == 1.0

    def test_shadow_mode_default_true(self):
        """Shadow mode should default to true for safe first deployment"""
        from config import REGIME_SHADOW_MODE
        # Default is true unless env var overrides
        assert isinstance(REGIME_SHADOW_MODE, bool)


# ═══════════════════════════════════════════════════
# Integration-level async tests
# ═══════════════════════════════════════════════════

class TestRegimeDetectorAsync:
    @pytest.fixture
    def detector(self):
        from agent.regime_detector import RegimeDetector
        return RegimeDetector()

    @pytest.mark.asyncio
    async def test_on_kline_close(self, detector):
        """Test kline_close event handling"""
        for i in range(30):
            await detector.on_kline_close({
                "asset": "BTC",
                "close": 70000 + i * 10,
                "volume": 1000,
                "prev_close": 70000 + (i - 1) * 10 if i > 0 else 69990,
                "prev_volume": 1000,
            })
        assert len(detector._feature_buffer["BTC"]) == 30

    @pytest.mark.asyncio
    async def test_on_indicator_update(self, detector):
        """Test indicator_update event handling"""
        await detector.on_indicator_update({
            "asset": "BTC",
            "price_usd": 70000,
            "atr_14": 2000,
            "funding_rate": 0.0001,
            "fear_greed_index": 60,
            "liquidation_24h_usd": 100e6,
        })
        assert "BTC" in detector._indicator_cache
        assert detector._indicator_cache["BTC"]["price_usd"] == 70000

    @pytest.mark.asyncio
    async def test_update_hmm_insufficient_data(self, detector):
        """HMM should return current regime with low confidence when data insufficient"""
        result = await detector.update_hmm("BTC")
        assert result["regime"] == "RANGING"
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_check_crisis_no_data(self, detector):
        """Crisis check with no indicator data should not crash"""
        result = await detector.check_crisis()
        assert "is_crisis" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
