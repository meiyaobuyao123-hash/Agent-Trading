# TECH-006: 市场 Regime 检测 + 动态风控 — 技术方案

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.1（12 项缺陷修复） |
| 对应 PRD | PRD-006 v1.1 |
| 创建日期 | 2026-03-23 |
| 修订日期 | 2026-03-23 |

---

## 一、架构总览（v1.1 新增）

```
┌─────────────────── 数据管道（事件驱动）──────────────────┐
│                                                          │
│  Binance WS kline_close ──→ EventBus "kline.close"       │
│  IndicatorEngine 5min   ──→ EventBus "indicator.update"  │
│                                                          │
│  regime_detector 订阅：                                   │
│    "kline.close"       → update_cusum + add_features     │
│    "indicator.update"  → 缓存爆仓/资金费率/恐慌指数       │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌─────────────────── RegimeDetector ───────────────────────┐
│                                                          │
│  ┌─ CUSUM (事件触发，每根K线) ───────────────────────┐   │
│  │  BTC(h=3σ) / SOL(h=2.5σ) / ETH(h=3σ) 各自独立   │   │
│  │  变化检测 → 触发 HMM 立即分类（不等 30min）         │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─ HMM (每30min + CUSUM触发) ──────────────────────┐   │
│  │  StandardScaler 归一化（v1.1 修复#2）              │   │
│  │  asyncio.to_thread 防阻塞（v1.1 修复#4）          │   │
│  │  score_samples 状态概率（v1.1 修复#3）             │   │
│  │  训练后 return 均值校准标签                         │   │
│  │  切换 → LLM Haiku 解释                            │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─ CRISIS (每1min，独立) ───────────────────────────┐   │
│  │  从 indicator_engine 缓存读数据（v1.1 修复#5）     │   │
│  │  BTC 15min跌>5% / 爆仓>$500M / 资金费率极端       │   │
│  │  触发 → EventBus → position_monitor 清仓           │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─ 规则引擎 (叠加状态) ────────────────────────────┐   │
│  │  BREAKOUT = HMM=UP + 突破20日高 + 量>3x均值       │   │
│  │  RECOVERY = 从CRISIS恢复，4条件持续30min           │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─ 全局+链级综合判定（v1.1 修复#7）────────────────┐   │
│  │  global_regime = 综合 BTC+SOL+ETH                  │   │
│  │  chain_regime = {solana: SOL, eth: ETH, ...}      │   │
│  └───────────────────────────────────────────────────┘   │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌─────────────────── 输出 ─────────────────────────────────┐
│  EventBus "market.regime_change" →                       │
│    risk_manager     → 动态参数调整                        │
│    position_monitor → CRISIS清仓（v1.1 修复#10）          │
│    working_memory   → 记录短期记忆                        │
│    event_listener   → 注入 DataEvent._regime（修复#8）    │
│                                                          │
│  DB agent_regime_history → 每30min快照（v1.1 修复#11）    │
│  API /api/agent/regime → Flutter App                     │
└──────────────────────────────────────────────────────────┘
```

---

## 二、文件结构

```
services/pump-scanner/
├── agent/
│   ├── regime_detector.py          # 新建：CUSUM+HMM+CRISIS+规则引擎+综合判定
│   ├── risk_manager.py             # 修改：Regime感知+ATR仓位+ATR止损+时间衰减+CRISIS+Shadow
│   ├── position_monitor.py         # 修改：CRISIS清仓+时间衰减止损接入
│   ├── event_listener.py           # 修改：订阅regime_change+注入DataEvent._regime
│   └── memory/working_memory.py    # 修改：Regime变化写入
├── optimizer_tools.py              # 修改：+tool_read_regime_history
├── optimizer_agent.py              # 修改：+1工具
├── main.py                         # 修改：注册regime任务+EventBus订阅
├── config.py                       # 修改：+Regime/ATR/CUSUM/Shadow配置
├── api/routes_agent.py             # 修改：+/api/agent/regime
└── supabase/migrations/029_regime_history.sql
```

---

## 三、核心模块：regime_detector.py（v1.1 重写）

```python
"""
市场 Regime 检测器 v1.1
- 事件驱动（非轮询）：kline_close → CUSUM → HMM
- 多资产：BTC/SOL/ETH 独立检测 + 综合判定
- 三阶段：CUSUM(变化) + HMM(分类) + LLM(解释)
- CRISIS 独立 1min 检测
- 启动时加载历史数据（避免冷启动 12h 空白）
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

# ─── 从 config.py 读取（支持 .env 覆盖 + 优化Agent提案修改）─────
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
    """累积和变化检测 — 检测价格结构性变化"""

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
    """HMM 状态分类 — 输出 4 个基础状态"""

    def __init__(self, asset: str):
        self._asset = asset
        self._model = None
        self._scaler = None  # v1.1 修复#2：归一化
        self._use_hmm = False
        self._label_map: Dict[int, str] = {}
        self._try_init()

    def _try_init(self):
        try:
            from hmmlearn.hmm import GaussianHMM
            from sklearn.preprocessing import StandardScaler
            self._model = GaussianHMM(
                n_components=HMM_STATES, covariance_type="full",
                n_iter=100, random_state=42,
            )
            self._scaler = StandardScaler()
            self._use_hmm = True
            log.info("[Regime] HMM + Scaler initialized for %s", self._asset)
        except ImportError:
            log.warning("[Regime] hmmlearn/sklearn unavailable, rule-based fallback for %s", self._asset)

    def train(self, features: np.ndarray) -> bool:
        """训练 HMM（v1.1：归一化 + 标签校准）"""
        if not self._use_hmm or len(features) < HMM_MIN_SAMPLES:
            return False
        try:
            # v1.1 修复#2：归一化
            scaled = self._scaler.fit_transform(features)
            self._model.fit(scaled)

            # 标签校准：按 return 均值排序
            states = self._model.predict(scaled)
            state_returns = {}
            state_vol = {}
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
        """分类当前状态（v1.1：修复 predict_proba + to_thread 安全）"""
        if self._use_hmm and self._model and self._label_map and self._scaler:
            try:
                scaled = self._scaler.transform(features)
                # v1.1 修复#3：用 score_samples 获取状态概率
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
        """纯规则引擎 fallback"""
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

CRISIS_BTC_15MIN_DROP = -0.05
CRISIS_LIQUIDATION_1H = 500e6
CRISIS_FUNDING_EXTREME = -0.001
CRISIS_RECOVERY_MINUTES = 30


class CrisisDetector:

    def __init__(self):
        self.is_crisis: bool = False
        self._crisis_start: float = 0
        self._recovery_start: float = 0
        self._btc_15min: deque = deque(maxlen=15)

    def check(self, btc_price: float, liquidation_1h: float = 0,
              funding_rate: float = 0) -> Dict[str, Any]:
        self._btc_15min.append(btc_price)

        if not self.is_crisis:
            triggered, reason = False, ""
            if len(self._btc_15min) >= 15:
                pct = (btc_price - self._btc_15min[0]) / self._btc_15min[0]
                if pct <= CRISIS_BTC_15MIN_DROP:
                    triggered, reason = True, f"BTC 15min {pct*100:.1f}%"
            if liquidation_1h >= CRISIS_LIQUIDATION_1H:
                triggered, reason = True, f"Liquidation ${liquidation_1h/1e6:.0f}M"
            if funding_rate <= CRISIS_FUNDING_EXTREME:
                triggered, reason = True, f"Extreme funding {funding_rate*100:.4f}%"

            if triggered:
                self.is_crisis = True
                self._crisis_start = time.time()
                self._recovery_start = 0
                return {"is_crisis": True, "just_entered": True, "reason": reason}
        else:
            # 恢复检测：4 条件持续 30min
            if len(self._btc_15min) >= 8:
                recent_min = min(list(self._btc_15min)[-4:])
                older_min = min(list(self._btc_15min)[:8])
                no_new_low = recent_min >= older_min
                stable = len(self._btc_15min) >= 2 and \
                    abs(btc_price - self._btc_15min[-2]) / max(self._btc_15min[-2], 1) < 0.01

                if no_new_low and stable:
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

    def __init__(self):
        self._cusum = {
            "BTC": CUSUMDetector("BTC", CUSUM_H_BTC),
            "SOL": CUSUMDetector("SOL", CUSUM_H_SOL),
            "ETH": CUSUMDetector("ETH", CUSUM_H_ETH),
        }
        self._hmm = {
            "BTC": HMMClassifier("BTC"),
            "SOL": HMMClassifier("SOL"),
            "ETH": HMMClassifier("ETH"),
        }
        self._crisis = CrisisDetector()
        self._feature_buffer: Dict[str, List] = {"BTC": [], "SOL": [], "ETH": []}
        self._current_regime: Dict[str, str] = {"BTC": "RANGING", "SOL": "RANGING", "ETH": "RANGING"}
        self._global_regime: str = "RANGING"
        # v1.1 修复#7：链级 regime
        self._chain_regime: Dict[str, str] = {
            "solana": "RANGING", "eth": "RANGING", "bsc": "RANGING", "base": "RANGING",
        }
        self._regime_since: float = time.time()
        self._indicator_cache: Dict[str, Dict] = {}  # v1.1 修复#5

    # ── 数据管道接口（v1.1 修复#1）──────────────────────

    async def on_kline_close(self, asset: str, close: float, volume: float,
                              prev_close: float, prev_volume: float):
        """EventBus "kline.close" 回调 — 驱动 CUSUM + 特征收集"""
        if prev_close <= 0:
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

    async def on_indicator_update(self, asset: str, indicators: Dict):
        """EventBus "indicator.update" 回调 — 缓存衍生品数据（v1.1 修复#5）"""
        self._indicator_cache[asset] = {
            "atr_ratio": indicators.get("atr_14", 0) / max(indicators.get("price_usd", 1), 1),
            "funding_rate": indicators.get("funding_rate", 0),
            "liquidation_1h": indicators.get("liquidation_24h_usd", 0) / 24,
            "fear_greed": indicators.get("fear_greed_index", 50),
        }

    # ── HMM 分类（v1.1：to_thread + score_samples）────

    async def update_hmm(self, asset: str) -> Dict:
        """HMM 状态分类 — CPU 密集操作在线程池执行"""
        features = np.array(self._feature_buffer.get(asset, []))
        if len(features) < 24:
            return {"regime": self._current_regime[asset], "confidence": 0.5}

        # v1.1 修复#4：防阻塞
        result = await asyncio.to_thread(self._hmm[asset].classify, features)
        old = self._current_regime[asset]
        new = result["regime"]

        if old != new and result["confidence"] > 0.7:
            self._current_regime[asset] = new
            self._update_global_regime()
            log.info("[Regime] %s: %s → %s (conf=%.2f, %s)",
                     asset, old, new, result["confidence"], result["method"])

            explanation = await self._get_llm_explanation(asset, old, new)
            from agent.event_bus import get_event_bus
            get_event_bus().publish("market.regime_change", {
                "asset": asset, "old_regime": old, "new_regime": new,
                "confidence": result["confidence"], "explanation": explanation,
            })
            self._save_snapshot(asset, new, result["confidence"],
                                result.get("state_probs"), explanation, old, is_transition=True)
        return result

    # ── CRISIS 检测 ─────────────────────────────────

    async def check_crisis(self) -> Dict:
        """每 1min 调用 — 从 indicator_cache 读数据（v1.1 修复#5）"""
        btc_ind = self._indicator_cache.get("BTC", {})
        btc_price = btc_ind.get("price_usd", 0)
        if btc_price <= 0:
            # fallback: 从 indicator_engine 直接读
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
            log.warning("[Regime] ⚠️ CRISIS: %s", result["reason"])
            from agent.event_bus import get_event_bus
            get_event_bus().publish("market.regime_change", {
                "asset": "GLOBAL", "old_regime": old, "new_regime": "CRISIS",
                "confidence": 1.0, "explanation": result["reason"],
            })
        elif result.get("just_recovered"):
            self._global_regime = self._current_regime.get("BTC", "RANGING")
            self._regime_since = time.time()
            log.info("[Regime] CRISIS recovered → %s", self._global_regime)

        return result

    # ── 综合判定（v1.1 修复#7）─────────────────────

    def _update_global_regime(self):
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

    def get_regime(self, asset: str = None) -> str:
        """获取当前 regime（含叠加状态判定）"""
        if self._crisis.is_crisis:
            return "CRISIS"

        if asset:
            base = self._current_regime.get(asset, "RANGING")
        else:
            base = self._global_regime

        # BREAKOUT 叠加
        btc_ind = self._indicator_cache.get("BTC", {})
        # 简化判定：如果 HMM=UP 且当前有 CUSUM 上行信号
        if base == "TRENDING_UP":
            cusum = self._cusum.get("BTC")
            if cusum and cusum._s_up > 0:
                base = "BREAKOUT"  # 可在后续细化

        return base

    def get_chain_regime(self, chain: str) -> str:
        if self._crisis.is_crisis:
            return "CRISIS"
        return self._chain_regime.get(chain, self._global_regime)

    def get_regime_duration_hours(self) -> float:
        return (time.time() - self._regime_since) / 3600

    # ── 30min 快照写入（v1.1 修复#11）───────────────

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

    # ── 启动时加载历史（v1.1 修复#12）───────────────

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
        for asset in ("BTC", "SOL", "ETH"):
            features = np.array(self._feature_buffer.get(asset, []))
            if len(features) >= HMM_MIN_SAMPLES:
                success = await asyncio.to_thread(self._hmm[asset].train, features)
                log.info("[Regime] HMM retrain %s: %s (%d samples)",
                         asset, "OK" if success else "SKIP", len(features))

    # ── LLM 解释 ────────────────────────────────

    async def _get_llm_explanation(self, asset: str, old: str, new: str) -> str:
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

    def _save_snapshot(self, asset, regime, confidence, state_probs,
                       explanation, prev_regime, is_transition):
        try:
            ind = self._indicator_cache.get(asset, {})
            get_db().table("agent_regime_history").insert({
                "asset": asset, "regime": regime, "confidence": confidence,
                "btc_price": ind.get("price_usd"),
                "atr_14": ind.get("atr_ratio"),
                "funding_rate": ind.get("funding_rate"),
                "fear_greed": ind.get("fear_greed"),
                "hmm_state_probs": state_probs,
                "cusum_up": round(self._cusum.get(asset, CUSUMDetector(asset, 3))._s_up, 4),
                "cusum_down": round(self._cusum.get(asset, CUSUMDetector(asset, 3))._s_down, 4),
                "explanation": explanation,
                "is_transition": is_transition,
                "previous_regime": prev_regime,
            }).execute()
        except Exception as e:
            log.debug("[Regime] Snapshot save failed: %s", e)

    def get_stats(self) -> Dict:
        return {
            "global_regime": self.get_regime(),
            "per_asset": dict(self._current_regime),
            "chain_regime": dict(self._chain_regime),
            "is_crisis": self._crisis.is_crisis,
            "regime_duration_hours": round(self.get_regime_duration_hours(), 1),
            "hmm_available": {a: h._use_hmm for a, h in self._hmm.items()},
            "feature_counts": {a: len(b) for a, b in self._feature_buffer.items()},
        }


# ── 全局单例 ─────────────────────────────────────
_detector: Optional[RegimeDetector] = None

def get_regime_detector() -> RegimeDetector:
    global _detector
    if _detector is None:
        _detector = RegimeDetector()
    return _detector
```

---

## 四、risk_manager.py 修改

### 4.1 Shadow Mode（v1.1 修复#6）

```python
def _check_regime_adjustment(self, chain, action, amount_usd, token_data):
    from agent.regime_detector import get_regime_detector
    from config import REGIME_RISK_PARAMS, REGIME_SHADOW_MODE

    detector = get_regime_detector()
    regime = detector.get_chain_regime(chain)  # v1.1：链级 regime
    params = REGIME_RISK_PARAMS.get(regime, REGIME_RISK_PARAMS["RANGING"])

    if REGIME_SHADOW_MODE:
        log.info("[SHADOW] chain=%s regime=%s: position_pct=%.0f%% new_trades=%s",
                 chain, regime, params["position_pct"]*100, params["new_trades"])
        return RiskCheckResult.ok()

    if action == "buy" and not params.get("new_trades", True):
        return RiskCheckResult.block(f"Regime={regime}: no new buys on {chain}")
    if params.get("force_close", False):
        return RiskCheckResult.block(f"CRISIS: force close all")

    position_mult = params.get("position_pct", 1.0)
    if position_mult < 1.0:
        adjusted = amount_usd * position_mult
        return RiskCheckResult(passed=True,
            reason=f"Regime={regime}: position {position_mult*100:.0f}% (${amount_usd:.0f}→${adjusted:.0f})",
            risk_level="medium")
    return RiskCheckResult.ok()
```

### 4.2 ATR 动态仓位（v1.1 修复#9：硬上限）

```python
def calculate_dynamic_position(self, base_usd, atr_14, avg_atr_30d, regime):
    from config import REGIME_RISK_PARAMS
    mult = REGIME_RISK_PARAMS.get(regime, {}).get("position_pct", 1.0)
    atr_ratio = atr_14 / avg_atr_30d if avg_atr_30d > 0 else 1.0
    dynamic = base_usd / max(atr_ratio, 0.3) * mult
    return min(dynamic, 200.0)  # 单笔硬上限
```

### 4.3 时间衰减止损（v1.1 修复#10：盈利保护）

```python
def apply_time_decay_stop(self, stop_loss, entry_price, peak_price,
                           current_pnl_pct, hold_hours, token_type):
    if token_type != "meme":
        return stop_loss
    if hold_hours > 8 and current_pnl_pct > 0:
        return max(entry_price, peak_price * 0.85)
    elif hold_hours > 8 and current_pnl_pct < -10:
        return stop_loss * 0.8
    elif hold_hours > 12:
        return stop_loss * 0.7
    return stop_loss
```

---

## 五、position_monitor.py 修改

### 5.1 CRISIS 清仓连接 EventBus（v1.1 修复#10）

```python
# main.py 启动时注册：
async def _on_regime_for_positions(event):
    if event.data.get("new_regime") == "CRISIS":
        pm = get_position_monitor()
        closed = await pm.execute_crisis_close_all()
        log.warning("[CRISIS] Auto-closed %d positions", closed)

get_event_bus().subscribe("market.regime_change", _on_regime_for_positions)
```

### 5.2 时间衰减止损接入（v1.1 修复#9）

```python
# check_all() 中，在 pnl 计算后、止损检查前：
from agent.risk_manager import get_risk_manager
rm = get_risk_manager()
entry_ts = pos.created_at or time.time()
hold_hours = (time.time() - entry_ts) / 3600
adjusted_sl_price = rm.apply_time_decay_stop(
    stop_loss=pos.entry_price * (1 - pos.stop_loss_pct / 100),
    entry_price=pos.entry_price, peak_price=peak,
    current_pnl_pct=pnl_pct, hold_hours=hold_hours,
    token_type="meme",
)
# 用 adjusted_sl_price 替代原来的固定止损价
```

---

## 六、event_listener.py 修改（v1.1 修复#8）

```python
# 构建 DataEvent 时注入 regime 信息
from agent.regime_detector import get_regime_detector

def _inject_regime(event):
    detector = get_regime_detector()
    event.data["_market_regime"] = detector.get_regime()
    event.data["_chain_regime"] = detector.get_chain_regime(event.chain or "solana")

# 在 _on_hot_coin_event / _on_pump_event / _on_kol_event 中：
_inject_regime(event)
```

---

## 七、main.py 任务注册

```python
from agent.regime_detector import get_regime_detector
from agent.event_bus import get_event_bus

# 启动时加载历史
detector = get_regime_detector()
asyncio.create_task(detector.load_historical_features())

# EventBus 订阅（数据管道）
bus = get_event_bus()
bus.subscribe("btc_eth.kline_close", detector.on_kline_close)
bus.subscribe("btc_eth.indicator_update", detector.on_indicator_update)

# CRISIS 清仓订阅
async def _on_crisis(event):
    if event.data.get("new_regime") == "CRISIS":
        from agent.position_monitor import get_position_monitor
        closed = await get_position_monitor().execute_crisis_close_all()
        log.warning("[CRISIS] Closed %d positions", closed)

bus.subscribe("market.regime_change", _on_crisis)

# 定时任务
scheduler.add_job(detector.check_crisis, IntervalTrigger(minutes=1),
                  name="Crisis Check", max_instances=1)
scheduler.add_job(lambda: asyncio.ensure_future(detector.update_hmm("BTC")),
                  IntervalTrigger(minutes=30), name="HMM BTC", max_instances=1)
scheduler.add_job(lambda: asyncio.ensure_future(detector.save_periodic_snapshot()),
                  IntervalTrigger(minutes=30), name="Regime Snapshot", max_instances=1)
scheduler.add_job(detector.retrain_hmm, CronTrigger(hour=4, minute=0, timezone="UTC"),
                  name="HMM Retrain", max_instances=1)
```

---

## 八、config.py 新增

```python
# ── Regime 检测配置 ────────────────────────────────
CUSUM_WINDOW = int(os.getenv("CUSUM_WINDOW", "24"))
CUSUM_K_FACTOR = float(os.getenv("CUSUM_K_FACTOR", "0.5"))
CUSUM_H_BTC = float(os.getenv("CUSUM_H_BTC", "3.0"))
CUSUM_H_SOL = float(os.getenv("CUSUM_H_SOL", "2.5"))
CUSUM_H_ETH = float(os.getenv("CUSUM_H_ETH", "3.0"))
REGIME_SHADOW_MODE = os.getenv("REGIME_SHADOW_MODE", "true").lower() == "true"

# ── Regime 风控参数（可被优化 Agent 提案修改）────────
REGIME_RISK_PARAMS = {
    "TRENDING_UP":     {"position_pct": 1.0, "sl_mult": 1.0, "tp_mult": 1.5, "new_trades": True,  "force_close": False},
    "TRENDING_DOWN":   {"position_pct": 0.3, "sl_mult": 0.7, "tp_mult": 0.8, "new_trades": False, "force_close": False},
    "RANGING":         {"position_pct": 0.5, "sl_mult": 0.8, "tp_mult": 0.8, "new_trades": True,  "force_close": False},
    "HIGH_VOLATILITY": {"position_pct": 0.5, "sl_mult": 1.5, "tp_mult": 1.0, "new_trades": True,  "force_close": False},
    "BREAKOUT":        {"position_pct": 0.8, "sl_mult": 1.2, "tp_mult": 2.0, "new_trades": True,  "force_close": False},
    "CRISIS":          {"position_pct": 0.0, "sl_mult": 0.5, "tp_mult": 0.0, "new_trades": False, "force_close": True},
    "RECOVERY":        {"position_pct": 0.3, "sl_mult": 0.8, "tp_mult": 1.0, "new_trades": True,  "force_close": False},
}
```

---

## 九、v1.1 修订记录

| # | 缺陷 | 修复 |
|---|------|------|
| 1 | 特征数据管道缺失 | EventBus 订阅 kline_close + indicator_update |
| 2 | HMM 特征未归一化 | StandardScaler fit_transform / transform |
| 3 | predict_proba 不存在 | 改用 score_samples 获取 posteriors |
| 4 | HMM predict 阻塞事件循环 | asyncio.to_thread 包装 |
| 5 | CRISIS 爆仓数据来源不明 | 从 indicator_cache 读（indicator_update 事件填充） |
| 6 | Shadow Mode 无实现 | config.REGIME_SHADOW_MODE + 风控中判断 |
| 7 | 全局 regime 组合太简单 | BTC+SOL+ETH 综合 + chain_regime 字典 |
| 8 | Regime 信息未传递到策略评估 | _inject_regime 注入 DataEvent._market_regime |
| 9 | 时间衰减止损未接入 position_monitor | check_all 中调用 apply_time_decay_stop |
| 10 | CRISIS 清仓未连接 EventBus | main.py 订阅 regime_change → execute_crisis_close_all |
| 11 | 只在 transition 时写 DB | save_periodic_snapshot 每 30min 写快照 |
| 12 | 启动时无历史数据 | load_historical_features 从 btc_eth_indicators 加载 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本 |
| v1.1 | 2026-03-23 | 12 项实现缺陷修复（数据管道/归一化/阻塞/Shadow/冷启动等） |
