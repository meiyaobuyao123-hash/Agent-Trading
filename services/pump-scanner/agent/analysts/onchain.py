"""
PRD-007 M5: 链上分析师 Agent (Claude Haiku)

输入: holder分布/流动性/成交量/资金流向
输出: {direction, confidence, points, risk_flag}

Python 3.9 兼容。
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """你是一个区块链链上数据分析专家。基于以下链上数据，
用 3-5 个要点总结链上活动和资金流向。

严格输出 JSON（不要加任何前缀或 markdown）:
{
  "direction": "bullish" | "bearish" | "neutral",
  "confidence": 0.0 ~ 1.0,
  "points": ["要点1", "要点2", "要点3"],
  "risk_flag": "low" | "medium" | "high" | "critical"
}"""


NEUTRAL_FALLBACK: Dict[str, Any] = {
    "direction": "neutral",
    "confidence": 0.3,
    "points": ["链上分析数据不足，使用中性默认值"],
    "risk_flag": "medium",
}


class OnchainAnalyst:
    """链上分析师 — Claude Haiku"""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    async def analyze(
        self,
        token_data: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        链上分析

        Args:
            token_data: 代币数据（holder, liquidity, volume, etc）
            market_data: 可选市场数据

        Returns:
            结构化分析结果 JSON
        """
        if not self._api_key:
            log.warning("[OnchainAnalyst] No API key, returning neutral")
            return dict(NEUTRAL_FALLBACK)

        input_text = self._build_input(token_data, market_data or {})

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
                log.warning("[OnchainAnalyst] Missing fields in response")
                return dict(NEUTRAL_FALLBACK)

            result.setdefault("points", [])
            result.setdefault("risk_flag", "medium")

            tokens_used = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            result["_tokens_used"] = tokens_used

            return result

        except json.JSONDecodeError as e:
            log.warning("[OnchainAnalyst] JSON parse error: %s", e)
            return dict(NEUTRAL_FALLBACK)
        except Exception as e:
            log.warning("[OnchainAnalyst] API error: %s", e)
            return dict(NEUTRAL_FALLBACK)

    def _build_input(
        self,
        token_data: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> str:
        """构建链上分析输入文本"""
        lines = ["当前代币链上数据："]

        # 持有人
        holders = token_data.get("holder_count")
        if holders:
            lines.append(f"- 持有人数: {holders}")

        top10 = token_data.get("top10_holder_pct")
        if top10 is not None:
            lines.append(f"- Top10 持仓占比: {top10:.1%}")

        # 流动性
        liq = token_data.get("liquidity_usd")
        if liq:
            lines.append(f"- 流动性: ${liq:,.0f}")

        # 市值
        mcap = token_data.get("market_cap_usd")
        if mcap:
            lines.append(f"- 市值: ${mcap:,.0f}")
            if liq and mcap > 0:
                lines.append(f"- 流动性/市值比: {liq/mcap:.2%}")

        # 成交量
        for tf in ["5m", "1h", "4h", "24h"]:
            key = f"volume_{tf}_usd"
            val = token_data.get(key)
            if val:
                lines.append(f"- {tf} 成交量: ${val:,.0f}")

        # 买卖笔数
        for tf in ["1h", "24h"]:
            b = token_data.get(f"buys_{tf}")
            s = token_data.get(f"sells_{tf}")
            if b is not None and s is not None:
                lines.append(f"- {tf} 买入: {b}, 卖出: {s}")

        # 内盘特有
        bc = token_data.get("bc_progress")
        if bc is not None:
            lines.append(f"- Bonding Curve 进度: {bc}%")
        bsr = token_data.get("buy_sell_ratio")
        if bsr is not None:
            lines.append(f"- 买卖SOL比: {bsr}")
        dev_sold = token_data.get("dev_sold_pct")
        if dev_sold is not None:
            lines.append(f"- 开发者卖出: {dev_sold:.0%}")
        buyer_count = token_data.get("buyer_count")
        if buyer_count:
            lines.append(f"- 独立买家数: {buyer_count}")

        # 热币特有 — 入榜涨幅
        entry_gain = token_data.get("entry_gain_pct")
        if entry_gain is not None:
            lines.append(f"- 入榜以来涨幅: {entry_gain:.1f}%")

        # 资金流向
        net_flow = market_data.get("net_flow_24h")
        if net_flow is not None:
            lines.append(f"- 24h 净流入: ${net_flow:,.0f}")

        # 链
        chain = token_data.get("chain", "")
        if chain:
            lines.append(f"- 链: {chain}")

        return "\n".join(lines)
