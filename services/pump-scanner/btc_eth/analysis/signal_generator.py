"""信号生成器 — 两阶段：规则预筛 + Claude 确认

Stage 1（规则预筛，每 5 分钟）：
  检查 RSI/费率/OI/爆仓 是否到达极值
  通过 → 进入 Stage 2

Stage 2（Claude 确认，只在 Stage 1 通过时调用）：
  综合分析 → 输出信号或拒绝
  降低 Claude 调用频率（从 288/天 → ~12/天）
"""
import json
import logging
import time
from typing import Dict, Any, Optional

from btc_eth.config import (
    SIGNAL_RSI_OVERSOLD, SIGNAL_RSI_OVERBOUGHT,
    SIGNAL_FUNDING_EXTREME_HIGH, SIGNAL_FUNDING_EXTREME_LOW,
    SIGNAL_OI_CHANGE_THRESHOLD, SIGNAL_CONFIDENCE_MIN,
    BTCETH_CLAUDE_API_KEY, BTCETH_CLAUDE_MODEL,
)

log = logging.getLogger(__name__)


class SignalGenerator:
    """短线交易信号生成"""

    def __init__(self):
        self._last_signal_time = {}  # type: Dict[str, float]  # "BTC_long" -> timestamp
        self._signal_cooldown = 14400  # 4 小时内同方向不重复

    def pre_filter(self, asset: str, snapshot: Dict[str, Any]) -> Optional[str]:
        """Stage 1: 规则预筛 — 返回 'long'/'short'/None"""
        rsi = snapshot.get("rsi_14")
        funding = snapshot.get("funding_rate", 0)
        oi_change = snapshot.get("oi_change_4h", 0)
        depth_imb = snapshot.get("depth_imbalance", 0)
        taker_ratio = snapshot.get("taker_buy_sell_ratio", 1)
        liq_long_pct = snapshot.get("liq_long_pct", 0.5)

        if rsi is None:
            return None

        # 做多条件（至少 2/4）
        long_signals = 0
        if rsi < SIGNAL_RSI_OVERSOLD:
            long_signals += 1
        if funding < SIGNAL_FUNDING_EXTREME_LOW:
            long_signals += 1  # 空头拥挤 = 做多机会
        if depth_imb > 0.3:
            long_signals += 1  # 买单远多于卖单
        if liq_long_pct < 0.3:
            long_signals += 1  # 空头大量爆仓

        if long_signals >= 2:
            key = f"{asset}_long"
            if self._check_cooldown(key):
                return "long"

        # 做空/减仓条件（至少 2/4）
        short_signals = 0
        if rsi > SIGNAL_RSI_OVERBOUGHT:
            short_signals += 1
        if funding > SIGNAL_FUNDING_EXTREME_HIGH:
            short_signals += 1  # 多头极度拥挤
        if depth_imb < -0.3:
            short_signals += 1  # 卖单远多于买单
        if liq_long_pct > 0.7:
            short_signals += 1  # 多头大量爆仓

        if short_signals >= 2:
            key = f"{asset}_short"
            if self._check_cooldown(key):
                return "short"

        return None

    async def generate_signal(
        self, asset: str, direction: str, snapshot: Dict[str, Any],
        cycle_phase: str, api_key: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Stage 2: Claude 确认（或规则降级）"""
        api_key = api_key or BTCETH_CLAUDE_API_KEY

        if api_key:
            signal = await self._claude_confirm(asset, direction, snapshot, cycle_phase, api_key)
            if signal:
                self._trigger_sim(asset, signal)
                return signal

        # Claude 不可用时降级为规则引擎
        signal = self._rule_based_signal(asset, direction, snapshot)
        if signal:
            self._trigger_sim(asset, signal)
        return signal

    def _trigger_sim(self, asset: str, signal: Dict[str, Any]):
        """触发模拟盘买入（只跟做多信号）"""
        if signal.get("signal_type") != "long":
            return
        try:
            from hot_sim_trader import get_sim_trader
            get_sim_trader().on_token_enter(
                address=f"{asset.lower()}_spot",
                chain="btc_eth",
                symbol=asset,
                price=signal.get("entry_price", 0),
                score=signal.get("confidence", 50),
                source="btc_eth",
            )
        except Exception:
            pass

    async def _claude_confirm(
        self, asset: str, direction: str, snapshot: Dict[str, Any],
        cycle_phase: str, api_key: str
    ) -> Optional[Dict[str, Any]]:
        """调用 Claude 确认信号"""
        try:
            from anthropic import Anthropic
            from btc_eth.analysis.prompts import SIGNAL_SYSTEM_PROMPT
            from btc_eth.analysis.cycle_analyzer import CycleAnalyzer

            data_summary = CycleAnalyzer._build_data_summary(asset, snapshot)

            client = Anthropic(api_key=api_key)
            response = client.messages.create(
                model=BTCETH_CLAUDE_MODEL,
                max_tokens=800,
                system=SIGNAL_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": (
                        f"资产: {asset}\n"
                        f"预筛方向: {direction}\n"
                        f"当前周期: {cycle_phase}\n\n"
                        f"市场数据:\n{data_summary}\n\n"
                        f"请判断是否发出 {direction} 信号。"
                    )
                }]
            )

            text = response.content[0].text
            if "{" in text:
                json_str = text[text.index("{"):text.rindex("}") + 1]
                result = json.loads(json_str)

                if not result.get("has_signal"):
                    log.info("[Signal] Claude 拒绝 %s %s 信号", asset, direction)
                    return None

                if result.get("confidence", 0) < SIGNAL_CONFIDENCE_MIN:
                    log.info("[Signal] Claude 置信度不足 %d < %d", result["confidence"], SIGNAL_CONFIDENCE_MIN)
                    return None

                # 记录冷却
                self._last_signal_time[f"{asset}_{direction}"] = time.time()

                return {
                    "asset": asset,
                    "signal_type": result.get("signal_type", direction),
                    "entry_price": float(result.get("entry_price", snapshot.get("price_usd", 0))),
                    "stop_loss": float(result.get("stop_loss", 0)),
                    "target_price": float(result.get("target_price", 0)),
                    "risk_reward": float(result.get("risk_reward", 0)),
                    "confidence": int(result.get("confidence", 60)),
                    "reasoning": result.get("reasoning", "Claude analysis"),
                    "indicator_snapshot": {k: v for k, v in snapshot.items() if not str(k).startswith("_")},
                    "method": "claude",
                }

        except Exception as e:
            log.warning("[Signal] Claude 确认失败: %s", e)
        return None

    def _rule_based_signal(
        self, asset: str, direction: str, snapshot: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """规则降级信号（Claude 不可用时）"""
        price = snapshot.get("price_usd", 0)
        atr = snapshot.get("atr_14", 0)
        if price <= 0 or atr <= 0:
            return None

        if direction == "long":
            stop_loss = price - 2 * atr
            target = price + 3 * atr
        else:
            stop_loss = price + 2 * atr
            target = price - 3 * atr

        risk = abs(price - stop_loss)
        reward = abs(target - price)
        rr = reward / risk if risk > 0 else 0

        if rr < 1.5:
            return None

        self._last_signal_time[f"{asset}_{direction}"] = time.time()

        return {
            "asset": asset,
            "signal_type": direction,
            "entry_price": price,
            "stop_loss": round(stop_loss, 2),
            "target_price": round(target, 2),
            "risk_reward": round(rr, 2),
            "confidence": 55,
            "reasoning": [
                f"RSI={snapshot.get('rsi_14', 50):.1f}",
                f"Funding={snapshot.get('funding_rate', 0):.4f}",
                f"Depth imbalance={snapshot.get('depth_imbalance', 0):.2f}",
            ],
            "method": "rule_based",
        }

    def _check_cooldown(self, key: str) -> bool:
        """检查冷却（同方向 4h 内不重复）"""
        last = self._last_signal_time.get(key, 0)
        return (time.time() - last) > self._signal_cooldown
