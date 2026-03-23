"""
PRD-007 M5: 情绪分析师 Agent (Claude Haiku)

输入: 恐慌贪婪指数/资金费率/多空比/聪明钱/新闻/KOL
输出: {direction, confidence, points, smart_money_signal}

Python 3.9 兼容。
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """你是一个加密市场情绪分析专家。基于以下情绪和资金数据，
用 3-5 个要点总结当前市场情绪和聪明钱动向。

严格输出 JSON（不要加任何前缀或 markdown）:
{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": 0.0 ~ 1.0,
  "points": ["要点1", "要点2", "要点3"],
  "smart_money_signal": "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell"
}"""


NEUTRAL_FALLBACK: Dict[str, Any] = {
    "direction": "neutral",
    "confidence": 0.3,
    "points": ["情绪分析数据不足，使用中性默认值"],
    "smart_money_signal": "neutral",
}


class SentimentAnalyst:
    """情绪分析师 — Claude Haiku"""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    async def analyze(
        self,
        token_data: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        情绪分析

        Args:
            token_data: 代币数据
            market_data: 市场数据（fear_greed, funding, etc）

        Returns:
            结构化分析结果 JSON
        """
        if not self._api_key:
            log.warning("[SentimentAnalyst] No API key, returning neutral")
            return dict(NEUTRAL_FALLBACK)

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

            if "direction" not in result or "confidence" not in result:
                log.warning("[SentimentAnalyst] Missing fields in response")
                return dict(NEUTRAL_FALLBACK)

            result.setdefault("points", [])
            result.setdefault("smart_money_signal", "neutral")

            tokens_used = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            result["_tokens_used"] = tokens_used

            return result

        except json.JSONDecodeError as e:
            log.warning("[SentimentAnalyst] JSON parse error: %s", e)
            return dict(NEUTRAL_FALLBACK)
        except Exception as e:
            log.warning("[SentimentAnalyst] API error: %s", e)
            return dict(NEUTRAL_FALLBACK)

    def _build_input(
        self,
        token_data: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> str:
        """构建情绪分析输入文本"""
        lines = ["当前市场情绪和资金数据："]

        # 恐慌贪婪指数
        fg = market_data.get("fear_greed_index")
        if fg is not None:
            lines.append(f"- 恐慌贪婪指数: {fg}")

        # 资金费率
        fr = market_data.get("funding_rate")
        if fr is not None:
            lines.append(f"- 资金费率: {fr}")

        # 多空比
        ls = market_data.get("long_short_ratio")
        if ls is not None:
            lines.append(f"- 多空比: {ls}")

        # 聪明钱
        sm_count = token_data.get("smart_money_count", 0)
        if sm_count:
            lines.append(f"- 聪明钱钱包数: {sm_count}")

        sm_signals = market_data.get("smart_money_signals", [])
        if sm_signals:
            for s in sm_signals[:5]:
                lines.append(f"  - 聪明钱: {s.get('action', '')} "
                             f"${s.get('amount_usd', 0):,.0f} "
                             f"({s.get('tier', '')})")

        # KOL 信号
        kol_count = token_data.get("kol_count", 0) or token_data.get("mention_count_2h", 0)
        if kol_count:
            lines.append(f"- KOL 提及数: {kol_count}")
        avg_sent = token_data.get("avg_sentiment")
        if avg_sent is not None:
            lines.append(f"- KOL 平均情绪: {avg_sent}")
        bullish_r = token_data.get("bullish_ratio")
        if bullish_r is not None:
            lines.append(f"- 看多比例: {bullish_r}")

        # 新闻
        news = market_data.get("news_sentiment")
        if news is not None:
            lines.append(f"- 新闻情绪: {news}")

        # 社交热度
        social = market_data.get("social_volume")
        if social is not None:
            lines.append(f"- 社交热度: {social}")

        # 代币基本信息
        symbol = token_data.get("symbol", token_data.get("name", ""))
        if symbol:
            lines.append(f"- 代币: {symbol}")
        chain = token_data.get("chain", "")
        if chain:
            lines.append(f"- 链: {chain}")

        return "\n".join(lines)
