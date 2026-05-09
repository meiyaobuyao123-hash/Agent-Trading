"""
PRD-007: AI 风控审查 Agent (Claude Sonnet)

独立审查高价值交易，拥有否决权（veto power）。
只在特定条件下触发，不是每笔交易都走 AI 审查。

触发条件（任一满足）:
- 交易金额 > $50
- Regime = HIGH_VOLATILITY 或 RECOVERY
- 辩论 confidence < 0.7

输出: APPROVE / REJECT / REDUCE

Python 3.9 兼容。
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# R52 — L3 风控审查升级 Opus 4.7(>$2000 大额关键决策)
# 风控是最后防线,推理出错代价高,Opus 更稳
# Opus 4.7($5/$25)比 4.1 便宜 3 倍且更新
RISK_REVIEW_MODEL = "claude-opus-4-7"
SONNET_MODEL = RISK_REVIEW_MODEL  # 向后兼容

SYSTEM_PROMPT = """你是独立风控审查官。你的唯一职责是保护资金安全。
你不受交易机会诱惑，只关注风险。

你只能回答以下三种之一：
- APPROVE: 通过，允许执行
- REJECT: 否决，禁止执行（说明理由）
- REDUCE: 减仓执行，将仓位减半（说明理由）

严格输出 JSON（不要加任何前缀或 markdown）:
{
  "decision": "APPROVE" | "REJECT" | "REDUCE",
  "reason": "理由说明",
  "risk_score": 0.0 ~ 1.0
}"""


class RiskReviewer:
    """AI 风控审查 Agent"""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    def should_review(
        self,
        amount_usd: float,
        regime: str,
        debate_confidence: float,
    ) -> bool:
        """
        判断是否需要 AI 审查

        触发条件（任一满足）:
        - amount_usd > 50
        - regime in (HIGH_VOLATILITY, RECOVERY)
        - debate_confidence < 0.7
        """
        if amount_usd > 50:
            return True
        if regime in ("HIGH_VOLATILITY", "RECOVERY"):
            return True
        if debate_confidence < 0.7:
            return True
        return False

    async def review(
        self,
        trade_details: Dict[str, Any],
        portfolio: Dict[str, Any],
        regime: str,
        debate_conclusion: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行 AI 风控审查

        Args:
            trade_details: {action, token, chain, amount_usd, ...}
            portfolio: 当前持仓状态
            regime: 当前 Regime
            debate_conclusion: 辩论结论

        Returns:
            {
                "decision": "APPROVE" | "REJECT" | "REDUCE",
                "reason": str,
                "risk_score": float,
                "tokens_used": int,
            }
        """
        if not self._api_key:
            log.warning("[RiskReviewer] No API key, auto-APPROVE")
            return {
                "decision": "APPROVE",
                "reason": "API key 未配置，自动通过",
                "risk_score": 0.5,
                "tokens_used": 0,
            }

        prompt = self._build_prompt(trade_details, portfolio, regime, debate_conclusion)

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self._api_key)
            response = await asyncio.to_thread(
                client.messages.create,
                model=SONNET_MODEL,
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text.strip()
            tokens_used = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)

            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                # 尝试从文本中提取决策
                upper_raw = raw.upper()
                if "REJECT" in upper_raw:
                    decision = "REJECT"
                elif "REDUCE" in upper_raw:
                    decision = "REDUCE"
                else:
                    decision = "APPROVE"
                result = {
                    "decision": decision,
                    "reason": raw[:200],
                    "risk_score": 0.5,
                }

            # 验证 decision 值
            decision = result.get("decision", "APPROVE").upper()
            if decision not in ("APPROVE", "REJECT", "REDUCE"):
                decision = "APPROVE"

            return {
                "decision": decision,
                "reason": result.get("reason", ""),
                "risk_score": float(result.get("risk_score", 0.5)),
                "tokens_used": tokens_used,
            }

        except Exception as e:
            log.error("[RiskReviewer] Review failed: %s", e)
            # 审查失败时保守处理：通过但标记
            return {
                "decision": "APPROVE",
                "reason": f"AI 审查异常: {str(e)[:100]}，自动通过",
                "risk_score": 0.5,
                "tokens_used": 0,
            }

    def _build_prompt(
        self,
        trade_details: Dict[str, Any],
        portfolio: Dict[str, Any],
        regime: str,
        debate_conclusion: Dict[str, Any],
    ) -> str:
        """构建风控审查 prompt"""
        lines = ["以下交易即将执行，请审查："]

        # 交易详情
        lines.append(f"\n## 交易详情")
        lines.append(f"- 动作: {trade_details.get('action', 'buy')}")
        lines.append(f"- 代币: {trade_details.get('token', 'unknown')}")
        lines.append(f"- 链: {trade_details.get('chain', 'unknown')}")
        lines.append(f"- 金额: ${trade_details.get('amount_usd', 0)}")

        # 持仓状态
        lines.append(f"\n## 当前持仓")
        lines.append(f"- 组合价值: ${portfolio.get('portfolio_value', 0):.2f}")
        lines.append(f"- 持仓数: {portfolio.get('open_positions', 0)}")
        lines.append(f"- 当日 PnL: ${portfolio.get('daily_pnl', 0):.2f}")
        lines.append(f"- 回撤: {portfolio.get('drawdown_pct', 0):.1%}")

        # 市场状态
        lines.append(f"\n## 市场状态")
        lines.append(f"- Regime: {regime}")

        # 辩论结论
        lines.append(f"\n## 辩论结论")
        lines.append(f"- 胜方: {debate_conclusion.get('winner', 'unknown')}")
        lines.append(f"- 置信度: {debate_conclusion.get('confidence', 0)}")
        lines.append(f"- 建议: {debate_conclusion.get('action', 'hold')}")
        lines.append(f"- 风险: {debate_conclusion.get('risk', 'unknown')}")

        lines.append(f"\n请审查此交易，回复 APPROVE/REJECT/REDUCE。")

        return "\n".join(lines)
