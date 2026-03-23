"""
市场 Regime 检测器 — PRD-006 v1.1

三阶段混合检测 + 多资产：
  Stage 1: CUSUM（事件驱动，每根K线）→ "市场发生了变化"
  Stage 2: HMM（每 30min + CUSUM 触发）→ "当前是什么状态"（fallback：纯规则引擎）
  Stage 3: LLM（仅切换时）→ "为什么变了 + 策略建议"
  CRISIS: 独立 1min 规则引擎（不等 HMM）

7 种 Regime = HMM(4 基础) + 规则引擎(3 叠加):
  HMM: TRENDING_UP / TRENDING_DOWN / RANGING / HIGH_VOLATILITY
  规则: BREAKOUT / CRISIS / RECOVERY

多资产：BTC(大盘) + SOL(SOL 生态) + ETH(EVM 链)，独立检测 + 综合判定。

Python 3.9 兼容。
"""
import asyncio
import logging
import math
import time
import os
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

import numpy as np
from database import get_db

log = logging.getLogger(__name__)

# ─── 从 config.py 读取（支持 .env 覆盖 + 优化 Agent 提案修改）─────
from config import (
    CUSUM_H_BTC, CUSUM_H_SOL, CUSUM_H_ETH, CUSUM_K_FACTOR, CUSUM_WINDOW,
    REGIME_SHADOW_MODE,
)

HMM_STATES = 4
HMM_MIN_SAMPLES = 48   # 最少 2 天数据才训练
FEATURE_BUFFER_MAX = 720  # 30 天 × 24h


# ═══════════════════════════════════════════════════
# CUSUM 变化点检测
# ═══════════════════════════════════════════════════

class CUSUMDetector:
    """累积和变化检测 — 检测价格结构性变化

    BTC: h=3σ, SOL: h=2.5σ, ETH: h=3σ — 各自独立。
    """

    def __init__(self, asset: str, h_threshold: float):
        self._asset = asset
        self._h = h_threshold
        self._returns: deque = deque(maxlen=200)
        self._s_up: float = 0.0
        self._s_down: float = 0.0

    def add_return(self, log_return: float) -> Dict[str, Any]:
        """添加新的 log-return，返回检测结果"""
        self._returns.append(log_return)
        if len(self._returns) < CUSUM_WINDOW:
            return {"change": False, "warning": False, "direction": "none", "magnitude": 0}

        window = list(self._returns)[-CUSUM_WINDOW:]
        mu = float(np.mean(window))
        sigma = float(np.std(window)) or 1e-8
        k = CUSUM_K_FACTOR * sigma
        h = self._h * sigma
        h_warn = h * 0.67

        x = log_return
        self._s_up = max(0, self._s_up + (x - mu - k))
        self._s_down = min(0, self._s_down + (x - mu + k))

        change = self._s_up > h or abs(self._s_down) > h
        warning = (not change) and (self._s_up > h_warn or abs(self._s_down) > h_warn)
        direction = "up" if self._s_up > abs(self._s_down) else "down"
        magnitude = max(self._s_up, abs(self._s_down))

        if change:
            self._s_up = 0.0
            self._s_down = 0.0

        return {"change": change, "warning": warning, "direction": direction,
                "magnitude": round(magnitude, 4)}


# ═══════════════════════════════════════════════════
# HMM 状态分类（+ 规则引擎 fallback）
# ═══════════════════════════════════════════════════

class HMMClassifier:
    """HMM 状态分类 — 输出 4 个基础状态

    特征向量: [1h_returns, volume_change, ATR_14/MA_ATR_14, funding_rate]
    StandardScaler 归一化 → GaussianHMM 4 states → score_samples 概率 → 标签校准。
    hmmlearn 不可用时 fallback 到纯规则引擎。
    """

    def __init__(self, asset: str):
        self._asset = asset
        self._model = None  # type: Any
        self._scaler = None  # type: Any
        self._use_hmm = False
        self._label_map: Dict[int, str] = {}
        self._try_init()

    def _try_init(self):
        try:
            from hmmlearn.hmm import GaussianHMM
            self._model = GaussianHMM(
                n_components=HMM_STATES, covariance_type="full",
                n_iter=100, random_state=42,
            )
            self._use_hmm = True
            log.info("[Regime] HMM initialized for %s", self._asset)
        except ImportError:
            log.warning("[Regime] hmmlearn unavailable, rule-based fallback for %s", self._asset)

        # StandardScaler: try sklearn, fallback to manual
        try:
            from sklearn.preprocessing import StandardScaler
            self._scaler = StandardScaler()
        except ImportError:
            self._scaler = None
            log.warning("[Regime] sklearn unavailable, manual normalization for %s", self._asset)

    def _manual_scale_fit_transform(self, features: np.ndarray) -> np.ndarray:
        """Manual StandardScaler fallback"""
        self._manual_mean = np.mean(features, axis=0)
        self._manual_std = np.std(features, axis=0)
        self._manual_std[self._manual_std == 0] = 1e-8
        return (features - self._manual_mean) / self._manual_std

    def _manual_scale_transform(self, features: np.ndarray) -> np.ndarray:
        """Manual transform using stored mean/std"""
        if not hasattr(self, "_manual_mean"):
            return features
        return (features - self._manual_mean) / self._manual_std

    def train(self, features: np.ndarray) -> bool:
        """训练 HMM（归一化 + 标签校准）"""
        if not self._use_hmm or len(features) < HMM_MIN_SAMPLES:
            return False
        try:
            # 归一化
            if self._scaler is not None:
                scaled = self._scaler.fit_transform(features)
            else:
                scaled = self._manual_scale_fit_transform(features)

            self._model.fit(scaled)

            # 标签校准：按 return 均值排序
            states = self._model.predict(scaled)
            state_returns: Dict[int, float] = {}
            state_vol: Dict[int, float] = {}
            for s in range(HMM_STATES):
                mask = states == s
                if mask.any():
                    state_returns[s] = float(np.mean(features[mask, 0]))
                    state_vol[s] = float(np.std(features[mask, 0]))

            sorted_ret = sorted(state_returns.items(), key=lambda x: x[1])
            sorted_vol = sorted(state_vol.items(), key=lambda x: -x[1])

            self._label_map = {
                sorted_ret[-1][0]: "TRENDING_UP",
                sorted_ret[0][0]: "TRENDING_DOWN",
                sorted_vol[0][0]: "HIGH_VOLATILITY",
            }
            for s in range(HMM_STATES):
                if s not in self._label_map:
                    self._label_map[s] = "RANGING"

            log.info("[Regime] HMM trained %s: labels=%s, samples=%d",
                     self._asset, self._label_map, len(features))
            return True
        except Exception as e:
            log.warning("[Regime] HMM train failed %s: %s", self._asset, e)
            return False

    def classify(self, features: np.ndarray) -> Dict[str, Any]:
        """分类当前状态（score_samples 获取概率，to_thread 安全）"""
        if self._use_hmm and self._model and self._label_map:
            try:
                if self._scaler is not None:
                    scaled = self._scaler.transform(features)
                else:
                    scaled = self._manual_scale_transform(features)

                # score_samples 获取状态概率
                _, posteriors = self._model.score_samples(scaled)
                probs = posteriors[-1]  # 最后时间步的概率分布
                state = int(np.argmax(probs))
                regime = self._label_map.get(state, "RANGING")
                confidence = float(probs[state])
                return {
                    "regime": regime,
                    "confidence": round(confidence, 3),
                    "state_probs": {self._label_map.get(i, f"S{i}"): round(float(p), 3)
                                    for i, p in enumerate(probs)},
                    "method": "hmm",
                }
            except Exception as e:
                log.debug("[Regime] HMM classify failed %s: %s", self._asset, e)

        return self._rule_fallback(features)

    def _rule_fallback(self, features: np.ndarray) -> Dict[str, Any]:
        """纯规则引擎 fallback

        TRENDING_UP: MA7 > MA25 > MA99 + 24h 涨幅 > 3%
        TRENDING_DOWN: MA7 < MA25 < MA99 + 24h 跌幅 > 3%
        HIGH_VOLATILITY: ATR_14 > 2 × MA_ATR_30
        RANGING: 以上都不满足
        """
        if len(features) < 24:
            return {"regime": "RANGING", "confidence": 0.5, "state_probs": {}, "method": "rule_fallback"}

        recent = features[-24:]
        avg_ret = float(np.mean(recent[:, 0]))
        recent_vol = float(np.std(recent[:, 0]))
        full_vol = float(np.std(features[:, 0])) if len(features) > 48 else recent_vol

        if recent_vol > 2 * full_vol:
            regime = "HIGH_VOLATILITY"
        elif avg_ret > 0.001:
            regime = "TRENDING_UP"
        elif avg_ret < -0.001:
            regime = "TRENDING_DOWN"
        else:
            regime = "RANGING"

        return {"regime": regime, "confidence": 0.6, "state_probs": {}, "method": "rule_fallback"}


# ═══════════════════════════════════════════════════
# CRISIS 独立检测（每 1min）
# ═══════════════════════════════════════════════════

CRISIS_BTC_15MIN_DROP = -0.05      # BTC 15min 跌 > 5%
CRISIS_LIQUIDATION_1H = 500e6      # 全网 1h 爆仓 > $500M
CRISIS_FUNDING_EXTREME = -0.001    # 资金费率 < -0.1%
CRISIS_RECOVERY_MINUTES = 30


class CrisisDetector:
    """CRISIS 独立检测 — 每 1min，不等 HMM 30min

    触发条件（任一）：
      1. BTC 15min 跌 > 5%
      2. 全网 1h 爆仓 > $500M
      3. 资金费率 < -0.1%

    恢复条件（全部满足 + 持续 30min）：
      1. BTC 过去 1h 最低价 > 过去 2h 最低价
      2. BTC 15min 涨跌幅 > -1%
      3. 全网 1h 爆仓 < $100M
      4. 以上持续满足 30 分钟
    """

    def __init__(self):
        self.is_crisis: bool = False
        self._crisis_start: float = 0
        self._recovery_start: float = 0
        self._btc_15min: deque = deque(maxlen=15)  # 1min 采样，15 条 = 15min 窗口

    def check(self, btc_price: float, liquidation_1h: float = 0,
              funding_rate: float = 0) -> Dict[str, Any]:
        """检查 CRISIS 状态"""
        self._btc_15min.append(btc_price)

        if not self.is_crisis:
            triggered, reason = False, ""

            # 条件 1: BTC 15min 跌 > 5%
            if len(self._btc_15min) >= 15:
                pct = (btc_price - self._btc_15min[0]) / self._btc_15min[0]
                if pct <= CRISIS_BTC_15MIN_DROP:
                    triggered, reason = True, f"BTC 15min {pct*100:.1f}%"

            # 条件 2: 爆仓
            if liquidation_1h >= CRISIS_LIQUIDATION_1H:
                triggered, reason = True, f"Liquidation ${liquidation_1h/1e6:.0f}M"

            # 条件 3: 极端资金费率
            if funding_rate <= CRISIS_FUNDING_EXTREME:
                triggered, reason = True, f"Extreme funding {funding_rate*100:.4f}%"

            if triggered:
                self.is_crisis = True
                self._crisis_start = time.time()
                self._recovery_start = 0
                return {"is_crisis": True, "just_entered": True, "reason": reason}
        else:
            # 恢复检测：4 条件持续 30min
            recovery_ok = True

            # 条件 1: 过去 1h 最低 > 过去 2h 最低（无新低）
            if len(self._btc_15min) >= 8:
                recent_min = min(list(self._btc_15min)[-4:])
                older_min = min(list(self._btc_15min)[:8])
                if recent_min < older_min:
                    recovery_ok = False
            else:
                recovery_ok = False

            # 条件 2: BTC 15min 涨跌幅 > -1%
            if len(self._btc_15min) >= 2:
                short_pct = abs(btc_price - self._btc_15min[-2]) / max(self._btc_15min[-2], 1)
                if short_pct > 0.01 and btc_price < self._btc_15min[-2]:
                    recovery_ok = False
            else:
                recovery_ok = False

            # 条件 3: 爆仓 < $100M
            if liquidation_1h >= 100e6:
                recovery_ok = False

            if recovery_ok:
                if self._recovery_start == 0:
                    self._recovery_start = time.time()
                elif time.time() - self._recovery_start >= CRISIS_RECOVERY_MINUTES * 60:
                    self.is_crisis = False
                    self._recovery_start = 0
                    return {"is_crisis": False, "just_recovered": True, "reason": "Recovery confirmed"}
            else:
                self._recovery_start = 0

        return {"is_crisis": self.is_crisis, "just_entered": False, "just_recovered": False}


# ═══════════════════════════════════════════════════
# 主检测器
# ═══════════════════════════════════════════════════

class RegimeDetector:
    """市场 Regime 主检测器

    综合 CUSUM + HMM + CRISIS + 规则叠加（BREAKOUT/RECOVERY），
    多资产独立检测 + 全局/链级综合判定。
    """

    def __init__(self):
        self._cusum: Dict[str, CUSUMDetector] = {
            "BTC": CUSUMDetector("BTC", CUSUM_H_BTC),
            "SOL": CUSUMDetector("SOL", CUSUM_H_SOL),
            "ETH": CUSUMDetector("ETH", CUSUM_H_ETH),
        }
        self._hmm: Dict[str, HMMClassifier] = {
            "BTC": HMMClassifier("BTC"),
            "SOL": HMMClassifier("SOL"),
            "ETH": HMMClassifier("ETH"),
        }
        self._crisis = CrisisDetector()
        self._feature_buffer: Dict[str, List] = {"BTC": [], "SOL": [], "ETH": []}
        self._current_regime: Dict[str, str] = {"BTC": "RANGING", "SOL": "RANGING", "ETH": "RANGING"}
        self._global_regime: str = "RANGING"
        # 链级 regime
        self._chain_regime: Dict[str, str] = {
            "solana": "RANGING", "eth": "RANGING", "bsc": "RANGING", "base": "RANGING",
        }
        self._regime_since: float = time.time()
        self._indicator_cache: Dict[str, Dict] = {}  # 从 indicator_update 事件缓存

    # ── 数据管道接口（事件驱动）──────────────────────

    async def on_kline_close(self, event_data: Any):
        """EventBus "btc_eth.kline_close" 回调 — 驱动 CUSUM + 特征收集

        event_data 可能是 dict 或带 .data 属性的事件对象。
        """
        if isinstance(event_data, dict):
            data = event_data
        elif hasattr(event_data, "data"):
            data = event_data.data
        else:
            data = event_data

        asset = data.get("asset", "")
        close = float(data.get("close", 0))
        volume = float(data.get("volume", 0))
        prev_close = float(data.get("prev_close", 0))
        prev_volume = float(data.get("prev_volume", 0))

        if not asset or asset not in self._cusum or prev_close <= 0:
            return

        log_return = math.log(close / prev_close)
        vol_change = (volume - prev_volume) / max(prev_volume, 1) if prev_volume > 0 else 0

        # CUSUM 检测
        cusum_result = self._cusum[asset].add_return(log_return)

        # 收集 HMM 特征
        ind = self._indicator_cache.get(asset, {})
        atr_ratio = ind.get("atr_ratio", 1.0)
        funding = ind.get("funding_rate", 0)
        self._feature_buffer[asset].append([log_return, vol_change, atr_ratio, funding])
        if len(self._feature_buffer[asset]) > FEATURE_BUFFER_MAX:
            self._feature_buffer[asset] = self._feature_buffer[asset][-FEATURE_BUFFER_MAX:]

        # CUSUM 变化 → 立即触发 HMM 分类（不等 30min）
        if cusum_result["change"]:
            log.info("[Regime] CUSUM %s change: %s mag=%.4f → trigger HMM",
                     asset, cusum_result["direction"], cusum_result["magnitude"])
            await self.update_hmm(asset)

    async def on_indicator_update(self, event_data: Any):
        """EventBus "btc_eth.indicator_update" 回调 — 缓存衍生品数据"""
        if isinstance(event_data, dict):
            data = event_data
        elif hasattr(event_data, "data"):
            data = event_data.data
        else:
            data = event_data

        asset = data.get("asset", "")
        if not asset:
            return

        self._indicator_cache[asset] = {
            "price_usd": data.get("price_usd", 0),
            "atr_ratio": data.get("atr_14", 0) / max(data.get("price_usd", 1), 1),
            "funding_rate": data.get("funding_rate", 0),
            "liquidation_1h": data.get("liquidation_24h_usd", 0) / 24,
            "fear_greed": data.get("fear_greed_index", 50),
        }

    # ── HMM 分类（to_thread + score_samples）────

    async def update_hmm(self, asset: str) -> Dict:
        """HMM 状态分类 — CPU 密集操作在线程池执行"""
        features = np.array(self._feature_buffer.get(asset, []))
        if len(features) < 24:
            return {"regime": self._current_regime[asset], "confidence": 0.5}

        # 防阻塞：asyncio.to_thread
        result = await asyncio.to_thread(self._hmm[asset].classify, features)
        old = self._current_regime[asset]
        new = result["regime"]

        if old != new and result["confidence"] > 0.7:
            self._current_regime[asset] = new
            self._update_global_regime()
            log.info("[Regime] %s: %s → %s (conf=%.2f, %s)",
                     asset, old, new, result["confidence"], result["method"])

            explanation = await self._get_llm_explanation(asset, old, new)

            try:
                from agent.event_bus import get_event_bus
                get_event_bus().publish("market.regime_change", {
                    "asset": asset, "old_regime": old, "new_regime": new,
                    "confidence": result["confidence"], "explanation": explanation,
                })
            except Exception as e:
                log.debug("[Regime] EventBus publish failed: %s", e)

            self._save_snapshot(asset, new, result["confidence"],
                                result.get("state_probs"), explanation, old, is_transition=True)
        return result

    # ── CRISIS 检测 ─────────────────────────────────

    async def check_crisis(self) -> Dict:
        """每 1min 调用 — 从 indicator_cache 读数据"""
        btc_ind = self._indicator_cache.get("BTC", {})
        btc_price = btc_ind.get("price_usd", 0)

        if btc_price <= 0:
            # fallback: 从 btc_eth manager 直接读
            try:
                from btc_eth.manager import get_btc_eth_manager
                mgr = get_btc_eth_manager()
                if mgr:
                    snap = mgr._indicator_engine.get_snapshot("BTC")
                    btc_price = snap.get("price_usd", 0)
            except Exception:
                pass

        if btc_price <= 0:
            return {"is_crisis": self._crisis.is_crisis}

        liq = btc_ind.get("liquidation_1h", 0)
        funding = btc_ind.get("funding_rate", 0)
        result = self._crisis.check(btc_price, liq, funding)

        if result.get("just_entered"):
            old = self._global_regime
            self._global_regime = "CRISIS"
            self._regime_since = time.time()
            log.warning("[Regime] CRISIS: %s", result["reason"])

            try:
                from agent.event_bus import get_event_bus
                get_event_bus().publish("market.regime_change", {
                    "asset": "GLOBAL", "old_regime": old, "new_regime": "CRISIS",
                    "confidence": 1.0, "explanation": result["reason"],
                })
            except Exception as e:
                log.debug("[Regime] EventBus publish failed: %s", e)

        elif result.get("just_recovered"):
            self._global_regime = self._current_regime.get("BTC", "RANGING")
            self._regime_since = time.time()
            log.info("[Regime] CRISIS recovered → %s", self._global_regime)

        return result

    # ── 综合判定 ─────────────────────────────────

    def _update_global_regime(self):
        """BTC + SOL + ETH 综合判定全局 + 链级 regime"""
        btc = self._current_regime.get("BTC", "RANGING")
        sol = self._current_regime.get("SOL", "RANGING")
        eth = self._current_regime.get("ETH", "RANGING")

        if btc == "TRENDING_DOWN" and sol == "TRENDING_DOWN":
            self._global_regime = "TRENDING_DOWN"
        elif btc == "TRENDING_UP" and sol == "TRENDING_UP":
            self._global_regime = "TRENDING_UP"
        elif btc == "HIGH_VOLATILITY" or sol == "HIGH_VOLATILITY":
            self._global_regime = "HIGH_VOLATILITY"
        elif btc == "TRENDING_UP" and sol == "TRENDING_DOWN":
            self._global_regime = "RANGING"  # 矛盾信号 → 谨慎
        else:
            self._global_regime = btc

        # 链级 regime
        self._chain_regime = {
            "solana": sol,
            "eth": eth if eth != "RANGING" else btc,
            "bsc": btc,
            "base": eth if eth != "RANGING" else btc,
        }
        self._regime_since = time.time()

    # ── 叠加状态（BREAKOUT / RECOVERY）─────────────

    def get_regime(self, asset: Optional[str] = None) -> str:
        """获取当前 regime（含叠加状态判定）"""
        if self._crisis.is_crisis:
            return "CRISIS"

        if asset:
            base = self._current_regime.get(asset, "RANGING")
        else:
            base = self._global_regime

        # BREAKOUT 叠加: HMM=UP + CUSUM 上行信号
        if base == "TRENDING_UP":
            cusum = self._cusum.get("BTC")
            if cusum and cusum._s_up > 0:
                base = "BREAKOUT"

        return base

    def get_chain_regime(self, chain: str) -> str:
        """获取链级 regime"""
        if self._crisis.is_crisis:
            return "CRISIS"
        return self._chain_regime.get(chain, self._global_regime)

    def get_regime_duration_hours(self) -> float:
        return (time.time() - self._regime_since) / 3600

    # ── 30min 快照写入 ───────────────────────────

    async def save_periodic_snapshot(self):
        """每 30min 调用：写快照到 DB（不管是否切换）"""
        for asset in ("BTC", "SOL", "ETH"):
            regime = self._current_regime.get(asset, "RANGING")
            features = np.array(self._feature_buffer.get(asset, []))
            confidence = 0.5
            if self._hmm[asset]._use_hmm and len(features) >= 24:
                try:
                    result = await asyncio.to_thread(self._hmm[asset].classify, features)
                    confidence = result.get("confidence", 0.5)
                except Exception:
                    pass
            self._save_snapshot(asset, regime, confidence, None, None, None, is_transition=False)

    # ── 启动时加载历史 ───────────────────────────

    async def load_historical_features(self):
        """启动时从 btc_eth_indicators 加载，避免冷启动 12h 空白"""
        for asset in ("BTC", "ETH"):
            try:
                res = get_db().table("btc_eth_indicators").select(
                    "price_usd, price_change_1h, atr_14, funding_rate"
                ).eq("asset", asset).order("ts", desc=True).limit(720).execute()

                prev_price = 0
                for row in reversed(res.data or []):
                    price = float(row.get("price_usd", 0))
                    if price <= 0:
                        continue
                    ret = math.log(price / prev_price) if prev_price > 0 else 0
                    atr_ratio = float(row.get("atr_14", 0)) / price if price > 0 else 0
                    funding = float(row.get("funding_rate", 0) or 0)
                    self._feature_buffer[asset].append([ret, 0, atr_ratio, funding])
                    prev_price = price

                loaded = len(self._feature_buffer[asset])
                log.info("[Regime] Loaded %d historical features for %s", loaded, asset)
            except Exception as e:
                log.warning("[Regime] History load failed %s: %s", asset, e)

        # SOL 暂无 indicator 表数据，用 BTC 特征做初始化
        if not self._feature_buffer["SOL"] and self._feature_buffer["BTC"]:
            self._feature_buffer["SOL"] = list(self._feature_buffer["BTC"])
            log.info("[Regime] SOL features initialized from BTC (%d)", len(self._feature_buffer["SOL"]))

        await self.retrain_hmm()

    # ── HMM 重训练 ───────────────────────────────

    async def retrain_hmm(self):
        """每日 04:00 UTC 重训练所有 HMM"""
        for asset in ("BTC", "SOL", "ETH"):
            features = np.array(self._feature_buffer.get(asset, []))
            if len(features) >= HMM_MIN_SAMPLES:
                success = await asyncio.to_thread(self._hmm[asset].train, features)
                log.info("[Regime] HMM retrain %s: %s (%d samples)",
                         asset, "OK" if success else "SKIP", len(features))

    # ── LLM 解释 ────────────────────────────────

    async def _get_llm_explanation(self, asset: str, old: str, new: str) -> str:
        """Stage 3: Claude Haiku 解释 regime 切换"""
        try:
            import anthropic
            key = os.getenv("ANTHROPIC_API_KEY", "")
            if not key:
                return ""
            client = anthropic.Anthropic(api_key=key)
            resp = await asyncio.to_thread(
                client.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{"role": "user",
                           "content": f"{asset} market regime: {old} → {new}. "
                                      f"Explain in 1 sentence and suggest adjustment."}],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            log.debug("[Regime] LLM explanation failed: %s", e)
            return ""

    # ── DB 操作 ──────────────────────────────────

    def _save_snapshot(self, asset: str, regime: str, confidence: float,
                       state_probs: Optional[Dict], explanation: Optional[str],
                       prev_regime: Optional[str], is_transition: bool):
        """写入 agent_regime_history 快照"""
        try:
            ind = self._indicator_cache.get(asset, {})
            cusum = self._cusum.get(asset)
            get_db().table("agent_regime_history").insert({
                "asset": asset,
                "regime": regime,
                "confidence": confidence,
                "btc_price": ind.get("price_usd"),
                "atr_14": ind.get("atr_ratio"),
                "funding_rate": ind.get("funding_rate"),
                "fear_greed": ind.get("fear_greed"),
                "hmm_state_probs": state_probs,
                "cusum_up": round(cusum._s_up, 4) if cusum else 0,
                "cusum_down": round(cusum._s_down, 4) if cusum else 0,
                "explanation": explanation,
                "is_transition": is_transition,
                "previous_regime": prev_regime,
            }).execute()
        except Exception as e:
            log.debug("[Regime] Snapshot save failed: %s", e)

    def get_stats(self) -> Dict:
        """返回检测器状态（API / 诊断用）"""
        return {
            "global_regime": self.get_regime(),
            "per_asset": dict(self._current_regime),
            "chain_regime": dict(self._chain_regime),
            "is_crisis": self._crisis.is_crisis,
            "regime_duration_hours": round(self.get_regime_duration_hours(), 1),
            "hmm_available": {a: h._use_hmm for a, h in self._hmm.items()},
            "feature_counts": {a: len(b) for a, b in self._feature_buffer.items()},
            "shadow_mode": REGIME_SHADOW_MODE,
        }


# ── 全局单例 ─────────────────────────────────────
_detector: Optional[RegimeDetector] = None


def get_regime_detector() -> RegimeDetector:
    global _detector
    if _detector is None:
        _detector = RegimeDetector()
    return _detector
