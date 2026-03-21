"""周期分析器 — 判断当前 BTC/ETH 在牛熊周期的哪个阶段

7 阶段：accumulation → recovery → breakout → bull_run → euphoria → distribution → bear

两种模式：
  1. 规则引擎（快速，不调 Claude）— 基于阈值判断
  2. Claude 深度分析（每日一次）— 综合推理
"""
import logging
import json
from typing import Dict, Any, Optional

from btc_eth.config import CYCLE_PHASES

log = logging.getLogger(__name__)


class CycleAnalyzer:
    """7 阶段周期定位"""

    PHASES = CYCLE_PHASES

    def analyze_rule_based(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """规则引擎快速判断（不调 Claude）"""
        fgi = snapshot.get("fear_greed_index", 50)
        rsi = snapshot.get("rsi_14", 50)
        funding = snapshot.get("funding_rate", 0)
        oi_change = snapshot.get("oi_change_4h", 0)
        p24h = snapshot.get("price_change_24h", 0)
        netflow = snapshot.get("exchange_netflow_usd", 0)
        momentum = snapshot.get("score_momentum", 50)
        sentiment = snapshot.get("score_sentiment", 50)

        # 简单规则树
        if fgi < 15 and rsi < 25:
            phase = "accumulation"
            confidence = 75
        elif fgi < 30 and rsi < 40 and funding < 0:
            phase = "accumulation"
            confidence = 60
        elif 30 <= fgi <= 50 and 40 <= rsi <= 55:
            phase = "recovery"
            confidence = 55
        elif 50 < fgi <= 65 and rsi > 55 and funding > 0:
            phase = "breakout"
            confidence = 55
        elif 60 < fgi <= 80 and momentum > 65 and netflow < 0:
            phase = "bull_run"
            confidence = 65
        elif fgi > 85 and funding > 0.02 and rsi > 75:
            phase = "euphoria"
            confidence = 70
        elif fgi > 70 and rsi < 45 and p24h < -5:
            phase = "distribution"
            confidence = 55
        elif fgi < 25 and rsi < 35 and momentum < 30:
            phase = "bear"
            confidence = 60
        else:
            # 默认：用动量 + 情绪综合判断
            if momentum > 60 and sentiment > 55:
                phase = "bull_run"
            elif momentum < 40 and sentiment < 45:
                phase = "bear"
            else:
                phase = "recovery"
            confidence = 40

        return {
            "phase": phase,
            "confidence": confidence,
            "method": "rule_based",
        }

    async def analyze_with_claude(
        self, asset: str, snapshot: Dict[str, Any], api_key: str
    ) -> Dict[str, Any]:
        """Claude 深度分析（每日一次）"""
        try:
            from anthropic import Anthropic
            from btc_eth.analysis.prompts import CYCLE_SYSTEM_PROMPT
            from btc_eth.config import BTCETH_CLAUDE_MODEL

            # 构建数据摘要（不发完整快照，节省 token）
            data_summary = self._build_data_summary(asset, snapshot)

            client = Anthropic(api_key=api_key)
            response = client.messages.create(
                model=BTCETH_CLAUDE_MODEL,
                max_tokens=1500,
                system=CYCLE_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"分析 {asset} 当前所处的周期阶段。\n\n当前数据：\n{data_summary}\n\n请输出 JSON 格式的分析结果。"
                }]
            )

            text = response.content[0].text
            # 提取 JSON
            if "{" in text:
                json_str = text[text.index("{"):text.rindex("}") + 1]
                result = json.loads(json_str)
                result["method"] = "claude"
                return result

        except Exception as e:
            log.warning("[CycleAnalyzer] Claude 分析失败: %s", e)

        # 降级为规则引擎
        return self.analyze_rule_based(snapshot)

    @staticmethod
    def _build_data_summary(asset: str, s: Dict[str, Any]) -> str:
        """构建发给 Claude 的数据摘要"""
        return f"""资产: {asset}
价格: ${s.get('price_usd', 0):,.2f}
24h 涨跌: {s.get('price_change_24h', 0):.2f}%
RSI(14): {s.get('rsi_14', 50):.1f}
MACD 柱状图: {s.get('macd_signal', 0):.6f}
布林带位置: {s.get('bb_position', 0.5):.2f} (0=下轨, 1=上轨)
恐慌贪婪指数: {s.get('fear_greed_index', 50)}
资金费率: {s.get('funding_rate', 0):.4f}
大户多空比: {s.get('long_short_ratio', 1):.2f}
散户多空比: {s.get('retail_long_short', 1):.2f}
主动买卖比: {s.get('taker_buy_sell_ratio', 1):.2f}
OI 变化(4h): {s.get('oi_change_4h', 0):.2%}
24h 爆仓: ${s.get('liquidation_24h_usd', 0):,.0f}
交易所净流入: ${s.get('exchange_netflow_usd', 0):,.0f}
活跃地址: {s.get('active_addresses', 0):,}
哈希率: {s.get('hash_rate', 0):.0f}
SOPR: {s.get('sopr', 1):.4f}
鲸鱼交易数: {s.get('whale_txn_count', 0)}
DXY: {s.get('dxy_index', 100):.2f}
标普500变化: {s.get('sp500_change_pct', 0):.2f}%
ETF 资金流: ${s.get('etf_flow_usd', 0):,.0f}
稳定币总市值: ${s.get('stablecoin_mcap', 0):,.0f}
社交热度: {s.get('social_volume', 0)}
新闻情绪: {s.get('news_sentiment', 0):.2f} (-1到+1)
复合评分: 动量={s.get('score_momentum', 50)} 情绪={s.get('score_sentiment', 50)} 链上={s.get('score_onchain', 50)} 宏观={s.get('score_macro', 50)} 风险={s.get('score_risk', 50)}
过期指标数: {s.get('_stale_count', 0)}"""
