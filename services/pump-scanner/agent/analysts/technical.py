"""
PRD-007 M5: 技术分析师 Agent (Claude Haiku)

输入: RSI/MACD/MA/ATR/支撑阻力/成交量
输出: {direction, confidence, points, key_level}

Python 3.9 兼容。
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """你是一个加密货币技术分析专家。基于以下技术指标数据，
用 3-5 个要点总结当前技术面状况和交易方向。

严格输出 JSON（不要加任何前缀或 markdown）:
{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": 0.0 ~ 1.0,
  "points": ["要点1", "要点2", "要点3"],
  "key_level": {"support": 数字, "resistance": 数字}
}"""


NEUTRAL_FALLBACK: Dict[str, Any] = {
    "direction": "neutral",
    "confidence": 0.3,
    "points": ["技术分析数据不足，使用中性默认值"],
    "key_level": {"support": 0, "resistance": 0},
}


class TechnicalAnalyst:
    """技术分析师 — Claude Haiku"""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    async def analyze(
        self,
        token_data: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        技术分析

        Args:
            token_data: 代币数据（price, score, etc）
            market_data: 市场数据（indicators, etc）

        Returns:
            结构化分析结果 JSON
        """
        if not self._api_key:
            log.warning("[TechnicalAnalyst] No API key, returning neutral")
            return dict(NEUTRAL_FALLBACK)

        # 构建输入数据摘要
        input_text = self._build_input(token_data, market_data)

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self._api_key)
            response = await asyncio.to_thread(
                client.messages.create,
                model=HAIKU_MODEL,
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": input_text}],
            )

            raw = response.content[0].text.strip()
            result = json.loads(raw)

            # 验证必要字段
            if "direction" not in result or "confidence" not in result:
                log.warning("[TechnicalAnalyst] Missing fields in response")
                return dict(NEUTRAL_FALLBACK)

            result.setdefault("points", [])
            result.setdefault("key_level", {"support": 0, "resistance": 0})

            # tokens 统计
            tokens_used = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            result["_tokens_used"] = tokens_used

            return result

        except json.JSONDecodeError as e:
            log.warning("[TechnicalAnalyst] JSON parse error: %s", e)
            return dict(NEUTRAL_FALLBACK)
        except Exception as e:
            log.warning("[TechnicalAnalyst] API error: %s", e)
            return dict(NEUTRAL_FALLBACK)

    def _build_input(
        self,
        token_data: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> str:
        """构建技术分析输入文本"""
        lines = ["当前代币技术指标数据："]

        # 价格相关
        price = token_data.get("price_usd", 0)
        if price:
            lines.append(f"- 当前价格: ${price}")

        # 涨跌幅
        for tf in ["5m", "1h", "4h", "24h"]:
            key = f"price_change_{tf}"
            val = token_data.get(key)
            if val is not None:
                lines.append(f"- {tf} 涨跌幅: {val}%")

        # 成交量
        for tf in ["5m", "1h", "4h", "24h"]:
            key = f"volume_{tf}_usd"
            val = token_data.get(key)
            if val:
                lines.append(f"- {tf} 成交量: ${val:,.0f}")

        # 买卖笔数
        buys_1h = token_data.get("buys_1h")
        sells_1h = token_data.get("sells_1h")
        if buys_1h is not None and sells_1h is not None:
            lines.append(f"- 1h 买入笔数: {buys_1h}, 卖出笔数: {sells_1h}")

        # 市值 / 流动性
        mcap = token_data.get("market_cap_usd")
        if mcap:
            lines.append(f"- 市值: ${mcap:,.0f}")
        liq = token_data.get("liquidity_usd")
        if liq:
            lines.append(f"- 流动性: ${liq:,.0f}")

        # market_data 中的技术指标（如果有）
        for key in ["rsi_14", "macd", "macd_signal", "ma7", "ma25", "ma99",
                     "atr_14", "bb_upper", "bb_lower", "support", "resistance"]:
            val = market_data.get(key)
            if val is not None:
                lines.append(f"- {key}: {val}")

        # 评分
        score = token_data.get("score")
        if score:
            lines.append(f"- 综合评分: {score}")

        # 内盘特有字段
        bc = token_data.get("bc_progress")
        if bc is not None:
            lines.append(f"- Bonding Curve 进度: {bc}%")
        bsr = token_data.get("buy_sell_ratio")
        if bsr is not None:
            lines.append(f"- 买卖比: {bsr}")

        return "\n".join(lines)
