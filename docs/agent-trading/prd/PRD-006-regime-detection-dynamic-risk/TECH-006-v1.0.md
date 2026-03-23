# TECH-006: 市场 Regime 检测 + 动态风控 — 技术方案

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 对应 PRD | PRD-006 v1.1 |
| 创建日期 | 2026-03-23 |

---

## 一、文件结构

```
services/pump-scanner/
├── agent/
│   ├── regime_detector.py          # 新建：CUSUM + HMM + CRISIS + LLM
│   ├── risk_manager.py             # 修改：Regime 感知 + ATR + 时间衰减 + CRISIS
│   ├── position_monitor.py         # 修改：CRISIS 清仓序列
│   ├── event_listener.py           # 修改：订阅 regime_change
│   └── memory/working_memory.py    # 修改：Regime 变化写入
├── optimizer_tools.py              # 修改：+tool_read_regime_history
├── optimizer_agent.py              # 修改：+1 工具
├── main.py                         # 修改：注册 regime 任务
├── config.py                       # 修改：+Regime/ATR/CUSUM 配置
├── api/routes_agent.py             # 修改：+/api/agent/regime
└── supabase/migrations/
    └── 029_regime_history.sql
```

---

## 二、核心模块：regime_detector.py

```python
"""
市场 Regime 检测器 — 三阶段混合检测 + 多资产

Stage 1: CUSUM 统计变化检测（每 5min）
Stage 2: HMM 状态分类（每 30min）+ 规则引擎 fallback
Stage 3: LLM 解释（仅 regime 切换时）
CRISIS: 独立 1min 规则引擎（不等 HMM）

Python 3.9+ 兼容。
"""
import asyncio
import logging
import math
import time
import os
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import numpy as np
from database import get_db

log = logging.getLogger(__name__)

# ─── 配置 ────────────────────────────────────────────────
CUSUM_WINDOW = 24          # 24 根 1h K线作为基线
CUSUM_K_FACTOR = 0.5       # 灵敏度 = 0.5σ
CUSUM_H_BTC = 3.0          # BTC 报警阈值 = 3σ
CUSUM_H_SOL = 2.5          # SOL 更敏感
CUSUM_H_ETH = 3.0
CUSUM_WARNING_MULT = 0.67  # warning = h × 0.67

HMM_STATES = 4
HMM_RETRAIN_HOUR = 4      # UTC 04:00 重训练
HMM_FEATURES = ["returns", "volume_change", "atr_ratio", "funding_rate"]

CRISIS_BTC_15MIN_DROP = -0.05   # BTC 15min 跌 5%
CRISIS_LIQUIDATION_1H = 500e6   # 全网 1h 爆仓 $500M
CRISIS_FUNDING_EXTREME = -0.001 # 资金费率 < -0.1%
CRISIS_RECOVERY_MINUTES = 30    # 恢复需持续 30min


class CUSUMDetector:
    """CUSUM 变化点检测"""

    def __init__(self, asset: str, h_threshold: float):
        self._asset = asset
        self._h = h_threshold
        self._returns: deque = deque(maxlen=200)
        self._s_up: float = 0.0
        self._s_down: float = 0.0

    def add_return(self, log_return: float) -> Dict[str, Any]:
        self._returns.append(log_return)
        if len(self._returns) < CUSUM_WINDOW:
            return {"change": False, "warning": False, "direction": "none", "magnitude": 0}

        window = list(self._returns)[-CUSUM_WINDOW:]
        mu = np.mean(window)
        sigma = np.std(window) or 1e-8
        k = CUSUM_K_FACTOR * sigma
        h = self._h * sigma
        h_warn = h * CUSUM_WARNING_MULT

        # 累积偏差
        x = log_return
        self._s_up = max(0, self._s_up + (x - mu - k))
        self._s_down = min(0, self._s_down + (x - mu + k))

        change = self._s_up > h or abs(self._s_down) > h
        warning = (not change) and (self._s_up > h_warn or abs(self._s_down) > h_warn)
        direction = "up" if self._s_up > abs(self._s_down) else "down"
        magnitude = max(self._s_up, abs(self._s_down))

        if change:
            self._s_up = 0
            self._s_down = 0

        return {"change": change, "warning": warning, "direction": direction,
                "magnitude": round(magnitude, 4)}


class HMMClassifier:
    """HMM 状态分类器（fallback: 规则引擎）"""

    def __init__(self, asset: str):
        self._asset = asset
        self._model = None
        self._use_hmm = False
        self._label_map: Dict[int, str] = {}
        self._try_init_hmm()

    def _try_init_hmm(self):
        try:
            from hmmlearn.hmm import GaussianHMM
            self._model = GaussianHMM(
                n_components=HMM_STATES,
                covariance_type="full",
                n_iter=100,
                random_state=42,
            )
            self._use_hmm = True
            log.info("[Regime] HMM initialized for %s", self._asset)
        except ImportError:
            log.warning("[Regime] hmmlearn not available, using rule-based fallback for %s", self._asset)
            self._use_hmm = False

    def train(self, features: np.ndarray) -> bool:
        """用历史数据训练 HMM"""
        if not self._use_hmm or len(features) < 48:
            return False
        try:
            self._model.fit(features)
            # 状态标签校准（按 return 均值排序）
            states = self._model.predict(features)
            state_returns = {}
            state_volatility = {}
            for s in range(HMM_STATES):
                mask = states == s
                if mask.any():
                    state_returns[s] = float(np.mean(features[mask, 0]))  # returns 列
                    state_volatility[s] = float(np.std(features[mask, 0]))

            sorted_by_return = sorted(state_returns.items(), key=lambda x: x[1])
            sorted_by_vol = sorted(state_volatility.items(), key=lambda x: -x[1])

            self._label_map = {
                sorted_by_return[-1][0]: "TRENDING_UP",
                sorted_by_return[0][0]: "TRENDING_DOWN",
                sorted_by_vol[0][0]: "HIGH_VOLATILITY",
            }
            # 剩余的 = RANGING
            for s in range(HMM_STATES):
                if s not in self._label_map:
                    self._label_map[s] = "RANGING"

            log.info("[Regime] HMM trained for %s: %s", self._asset, self._label_map)
            return True
        except Exception as e:
            log.warning("[Regime] HMM train failed for %s: %s", self._asset, e)
            return False

    def classify(self, features: np.ndarray) -> Dict[str, Any]:
        """分类当前状态"""
        if self._use_hmm and self._model and self._label_map:
            try:
                state = int(self._model.predict(features[-1:].reshape(1, -1))[0])
                probs = self._model.predict_proba(features[-1:].reshape(1, -1))[0]
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
                log.debug("[Regime] HMM classify failed: %s, using rules", e)

        # Fallback: 规则引擎
        return self._rule_based_classify(features)

    def _rule_based_classify(self, features: np.ndarray) -> Dict[str, Any]:
        """纯规则引擎分类"""
        if len(features) < 24:
            return {"regime": "RANGING", "confidence": 0.5, "state_probs": {}, "method": "rule_fallback"}

        recent = features[-24:]
        avg_return = float(np.mean(recent[:, 0]))
        avg_vol = float(np.std(recent[:, 0]))
        vol_30d = float(np.std(features[:, 0])) if len(features) > 48 else avg_vol

        if avg_vol > 2 * vol_30d:
            regime = "HIGH_VOLATILITY"
        elif avg_return > 0.001:  # ~0.1% per hour = 2.4%/day
            regime = "TRENDING_UP"
        elif avg_return < -0.001:
            regime = "TRENDING_DOWN"
        else:
            regime = "RANGING"

        return {"regime": regime, "confidence": 0.6, "state_probs": {}, "method": "rule_fallback"}


class CrisisDetector:
    """CRISIS 独立 1min 检测器"""

    def __init__(self):
        self._is_crisis: bool = False
        self._crisis_start: float = 0
        self._recovery_start: float = 0
        self._btc_prices_15min: deque = deque(maxlen=15)  # 15 个 1min 采样 = 15min

    def check(self, btc_price: float, liquidation_1h: float = 0,
              funding_rate: float = 0) -> Dict[str, Any]:
        """每 1min 调用"""
        self._btc_prices_15min.append(btc_price)

        if not self._is_crisis:
            # 检测是否进入 CRISIS
            triggered = False
            reason = ""

            if len(self._btc_prices_15min) >= 15:
                pct_15min = (btc_price - self._btc_prices_15min[0]) / self._btc_prices_15min[0]
                if pct_15min <= CRISIS_BTC_15MIN_DROP:
                    triggered = True
                    reason = f"BTC 15min drop {pct_15min*100:.1f}%"

            if liquidation_1h >= CRISIS_LIQUIDATION_1H:
                triggered = True
                reason = f"Liquidation ${liquidation_1h/1e6:.0f}M"

            if funding_rate <= CRISIS_FUNDING_EXTREME:
                triggered = True
                reason = f"Extreme funding {funding_rate*100:.4f}%"

            if triggered:
                self._is_crisis = True
                self._crisis_start = time.time()
                self._recovery_start = 0
                return {"is_crisis": True, "just_entered": True, "reason": reason}

        else:
            # 检测是否恢复
            if len(self._btc_prices_15min) >= 2:
                recent_min = min(list(self._btc_prices_15min)[-4:]) if len(self._btc_prices_15min) >= 4 else btc_price
                older_min = min(list(self._btc_prices_15min)[:8]) if len(self._btc_prices_15min) >= 8 else btc_price
                no_new_low = recent_min >= older_min
                small_change = abs(btc_price - self._btc_prices_15min[-2]) / self._btc_prices_15min[-2] < 0.01

                if no_new_low and small_change:
                    if self._recovery_start == 0:
                        self._recovery_start = time.time()
                    elif time.time() - self._recovery_start >= CRISIS_RECOVERY_MINUTES * 60:
                        self._is_crisis = False
                        self._recovery_start = 0
                        return {"is_crisis": False, "just_recovered": True, "reason": "Recovery confirmed"}
                else:
                    self._recovery_start = 0

        return {"is_crisis": self._is_crisis, "just_entered": False, "just_recovered": False}


class RegimeDetector:
    """主检测器 — 整合 CUSUM + HMM + CRISIS + LLM"""

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
        self._regime_since: float = time.time()

    def get_regime(self, asset: str = None) -> str:
        if asset:
            return self._current_regime.get(asset, "RANGING")
        return self._global_regime

    def get_regime_duration_hours(self) -> float:
        return (time.time() - self._regime_since) / 3600

    async def update_cusum(self, asset: str, log_return: float) -> Dict:
        """每 5min 调用"""
        result = self._cusum[asset].add_return(log_return)
        if result["change"]:
            log.info("[Regime] CUSUM %s change detected: %s mag=%.4f",
                     asset, result["direction"], result["magnitude"])
        return result

    async def update_hmm(self, asset: str) -> Dict:
        """每 30min 调用"""
        features = np.array(self._feature_buffer.get(asset, []))
        if len(features) < 24:
            return {"regime": self._current_regime[asset], "confidence": 0.5}

        result = self._hmm[asset].classify(features)
        old_regime = self._current_regime[asset]
        new_regime = result["regime"]

        if old_regime != new_regime and result["confidence"] > 0.7:
            self._current_regime[asset] = new_regime
            self._update_global_regime()
            log.info("[Regime] %s: %s → %s (conf=%.2f, method=%s)",
                     asset, old_regime, new_regime, result["confidence"], result["method"])

            # LLM 解释 + EventBus 发布
            explanation = await self._get_llm_explanation(asset, old_regime, new_regime)
            from agent.event_bus import get_event_bus
            get_event_bus().publish("market.regime_change", {
                "asset": asset, "old_regime": old_regime, "new_regime": new_regime,
                "confidence": result["confidence"], "explanation": explanation,
            })

            # 写入 DB
            self._save_to_db(asset, new_regime, result["confidence"],
                             result.get("state_probs"), explanation, old_regime)

        return result

    async def check_crisis(self, btc_price: float, liquidation_1h: float = 0,
                            funding_rate: float = 0) -> Dict:
        """每 1min 调用"""
        result = self._crisis.check(btc_price, liquidation_1h, funding_rate)
        if result.get("just_entered"):
            old = self._global_regime
            self._global_regime = "CRISIS"
            self._regime_since = time.time()
            log.warning("[Regime] ⚠️ CRISIS entered: %s", result["reason"])
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

    def add_features(self, asset: str, features: List[float]):
        """追加特征数据（由 indicator_engine 或 price_feed 调用）"""
        self._feature_buffer[asset].append(features)
        # 保留最近 30 天 = 720 条
        if len(self._feature_buffer[asset]) > 720:
            self._feature_buffer[asset] = self._feature_buffer[asset][-720:]

    async def retrain_hmm(self):
        """每日重训练"""
        for asset in ("BTC", "SOL", "ETH"):
            features = np.array(self._feature_buffer.get(asset, []))
            if len(features) >= 168:  # 至少 7 天
                success = self._hmm[asset].train(features)
                log.info("[Regime] HMM retrain %s: %s (%d samples)",
                         asset, "OK" if success else "FAIL", len(features))

    def _update_global_regime(self):
        """综合多资产判定全局 regime"""
        btc = self._current_regime.get("BTC", "RANGING")
        # BTC CRISIS 已由 check_crisis 处理
        if btc == "TRENDING_DOWN":
            self._global_regime = "TRENDING_DOWN"
        elif btc == "HIGH_VOLATILITY":
            self._global_regime = "HIGH_VOLATILITY"
        else:
            self._global_regime = btc
        self._regime_since = time.time()

    async def _get_llm_explanation(self, asset: str, old: str, new: str) -> str:
        """Claude Haiku 简短解释"""
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
                           "content": f"{asset} market regime changed from {old} to {new}. "
                                      f"Explain in 1 sentence why and suggest strategy adjustment."}],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            log.debug("[Regime] LLM explanation failed: %s", e)
            return ""

    def _save_to_db(self, asset, regime, confidence, state_probs, explanation, prev):
        try:
            get_db().table("agent_regime_history").insert({
                "asset": asset, "regime": regime, "confidence": confidence,
                "hmm_state_probs": state_probs, "explanation": explanation,
                "is_transition": True, "previous_regime": prev,
            }).execute()
        except Exception as e:
            log.debug("[Regime] DB save failed: %s", e)

    def get_stats(self) -> Dict:
        return {
            "global_regime": self._global_regime,
            "per_asset": dict(self._current_regime),
            "is_crisis": self._crisis._is_crisis,
            "regime_duration_hours": round(self.get_regime_duration_hours(), 1),
            "hmm_available": {a: h._use_hmm for a, h in self._hmm.items()},
        }


# 全局单例
_detector: Optional[RegimeDetector] = None

def get_regime_detector() -> RegimeDetector:
    global _detector
    if _detector is None:
        _detector = RegimeDetector()
    return _detector
```

---

## 三、risk_manager.py 修改

### 3.1 新增 Regime 感知入口

```python
# check_trade() 中新增第 16 项检查：
def _check_regime_adjustment(self, chain, action, amount_usd, token_data):
    """Regime 感知动态调整"""
    from agent.regime_detector import get_regime_detector
    from config import REGIME_RISK_PARAMS

    detector = get_regime_detector()
    regime = detector.get_regime()
    params = REGIME_RISK_PARAMS.get(regime, REGIME_RISK_PARAMS["RANGING"])

    # 1. 不允许新交易
    if action == "buy" and not params.get("new_trades", True):
        return RiskCheckResult.block(f"Regime={regime}: 不允许新买入")

    # 2. 强制清仓
    if params.get("force_close", False):
        return RiskCheckResult.block(f"Regime=CRISIS: 触发清仓保护")

    # 3. 仓位调整
    position_mult = params.get("position_pct", 1.0)
    if position_mult < 1.0:
        adjusted = amount_usd * position_mult
        return RiskCheckResult(
            passed=True,
            reason=f"Regime={regime}: 仓位调整 {position_mult*100:.0f}% (${amount_usd:.0f}→${adjusted:.0f})",
            risk_level="medium",
        )
    return RiskCheckResult.ok()
```

### 3.2 ATR 动态仓位

```python
def calculate_dynamic_position(self, base_usd: float, atr_14: float,
                                avg_atr_30d: float, regime: str) -> float:
    from config import REGIME_RISK_PARAMS
    params = REGIME_RISK_PARAMS.get(regime, {})
    regime_mult = params.get("position_pct", 1.0)
    atr_ratio = atr_14 / avg_atr_30d if avg_atr_30d > 0 else 1.0

    dynamic = base_usd / max(atr_ratio, 0.3) * regime_mult  # 最小 0.3 防除零
    return min(dynamic, 200.0)  # 硬上限 $200
```

### 3.3 ATR 动态止损

```python
def calculate_dynamic_stop_loss(self, entry_price: float, atr_14: float,
                                 regime: str, side: str = "long") -> float:
    from config import REGIME_RISK_PARAMS
    params = REGIME_RISK_PARAMS.get(regime, {})
    sl_mult = params.get("sl_mult", 1.0)
    atr_distance = atr_14 * 2.0 * sl_mult

    if side == "long":
        return entry_price - atr_distance
    else:
        return entry_price + atr_distance
```

### 3.4 时间衰减止损（MEME）

```python
def apply_time_decay_stop(self, stop_loss: float, entry_price: float,
                           peak_price: float, current_pnl_pct: float,
                           hold_hours: float, token_type: str) -> float:
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

## 四、position_monitor.py — CRISIS 清仓

```python
async def execute_crisis_close_all(self):
    """CRISIS 模式：按金额排序 + 间隔卖出"""
    positions = sorted(self._positions.values(),
                       key=lambda p: p.amount_usd, reverse=True)
    closed = 0
    for pos in positions:
        if pos.execution_id in self._selling:
            continue
        try:
            await self._execute_exit(pos.execution_id, pos,
                                     exit_price=0,  # 市价卖出
                                     trigger="crisis_close", pnl_pct=0)
            closed += 1
        except Exception as e:
            log.error("[CRISIS] Failed to close %s: %s", pos.token_address[:10], e)
        await asyncio.sleep(3)  # 3s 间隔
        if closed >= 15:  # 60s 超时 ≈ 15 笔
            break
    return closed
```

---

## 五、main.py — 任务注册

```python
# CUSUM：每 5min
scheduler.add_job(run_cusum_check, IntervalTrigger(minutes=5),
                  name="Regime CUSUM", max_instances=1)

# HMM：每 30min
scheduler.add_job(run_hmm_classify, IntervalTrigger(minutes=30),
                  name="Regime HMM", max_instances=1)

# CRISIS：每 1min
scheduler.add_job(run_crisis_check, IntervalTrigger(minutes=1),
                  name="Regime Crisis", max_instances=1)

# HMM 重训练：每日 UTC 04:00
scheduler.add_job(run_hmm_retrain, CronTrigger(hour=4, minute=0, timezone="UTC"),
                  name="HMM Retrain", max_instances=1)
```

---

## 六、optimizer_tools.py — tool_read_regime_history

```python
def tool_read_regime_history(days: int = 14) -> dict:
    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    # 切换历史
    transitions = db.table("agent_regime_history").select("*") \
        .eq("is_transition", True).gte("created_at", f"{cutoff}T00:00:00Z") \
        .order("created_at", desc=True).limit(50).execute()

    # 各 regime 下交易表现
    from agent.performance_analytics import get_strategy_performance
    # ... 按 regime 分组统计 ...

    return {
        "transitions": transitions.data or [],
        "performance_by_regime": {...},
        "avg_detection_delay_minutes": ...,
        "false_transitions": ...,
        "false_transition_cost_usd": ...,
    }
```

---

## 七、API 端点

```python
@router.get("/regime")
async def get_regime():
    from agent.regime_detector import get_regime_detector
    detector = get_regime_detector()
    return detector.get_stats()

@router.get("/regime/history")
async def get_regime_history(days: int = 7):
    db = get_db()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = db.table("agent_regime_history").select("*") \
        .gte("created_at", f"{cutoff}") \
        .order("created_at", desc=True).limit(200).execute()
    return res.data or []
```

---

## 八、Migration SQL

```sql
CREATE TABLE IF NOT EXISTS agent_regime_history (
    id BIGSERIAL PRIMARY KEY,
    asset TEXT NOT NULL,
    regime TEXT NOT NULL,
    confidence NUMERIC,
    btc_price NUMERIC,
    atr_14 NUMERIC,
    funding_rate NUMERIC,
    fear_greed INT,
    hmm_state_probs JSONB,
    cusum_up NUMERIC,
    cusum_down NUMERIC,
    explanation TEXT,
    is_transition BOOLEAN DEFAULT FALSE,
    previous_regime TEXT,
    false_transition BOOLEAN,
    transition_cost_usd NUMERIC,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_regime_ts ON agent_regime_history(asset, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_regime_transition ON agent_regime_history(is_transition, created_at DESC);
```

---

## 九、灰度上线步骤

```
Week 1 (Shadow Mode):
  1. 部署 regime_detector.py
  2. CUSUM + HMM + CRISIS 全部运行
  3. 风控动态参数计算但 NOT 生效
  4. 日志记录 "如果用动态参数结果会是..."
  5. 每天 review shadow 数据

Week 2 (正式切换):
  1. 动态参数生效
  2. 硬底线保留（蜜罐/日亏损/回撤永不被覆盖）
  3. CRISIS 清仓功能开启
  4. 监控 1 周确认稳定
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-23 | 初始版本（对应 PRD-006 v1.1） |
