"""
PRD-007 M7: 决策 Agent

结合辩论结论 + 记忆规则 + Regime → 最终交易动作。
不独立调用 LLM，使用辩论 Facilitator 的结论。

Python 3.9 兼容。
"""

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


class DecisionAgent:
    """决策 Agent — 结合辩论结论 + 记忆 + Regime 做最终决策"""

    def decide(
        self,
        conclusion: Dict[str, Any],
        memory_context: Dict[str, Any],
        regime: str,
        existing_position: bool = False,
        token_address: str = "",
    ) -> Dict[str, Any]:
        """
        最终决策

        Args:
            conclusion: 辩论 Facilitator 的结论
                {winner, confidence, action, risk, reasoning}
            memory_context: 记忆系统上下文
                {short_term, episodic, semantic}
            regime: 当前市场 Regime (TRENDING_UP/DOWN/RANGING/HIGH_VOLATILITY/CRISIS/RECOVERY)
            existing_position: 是否已持有该代币
            token_address: 代币地址

        Returns:
            {
                "action": "buy" | "sell" | "hold",
                "confidence": 0.0 ~ 1.0,
                "reason": str,
                "position_multiplier": float,  # 仓位倍数（regime 调整）
                "skipped_reason": str | None,   # 如果跳过，原因
            }
        """
        action = conclusion.get("action", "hold")
        confidence = float(conclusion.get("confidence", 0))
        reasoning = conclusion.get("reasoning", "")

        # ── 1. 置信度门槛 ──────────────────────────────
        if action == "buy" and confidence < 0.6:
            return {
                "action": "hold",
                "confidence": confidence,
                "reason": f"买入置信度不足 ({confidence:.2f} < 0.6)",
                "position_multiplier": 0,
                "skipped_reason": "low_confidence_buy",
            }

        if action == "sell" and confidence < 0.5:
            return {
                "action": "hold",
                "confidence": confidence,
                "reason": f"卖出置信度不足 ({confidence:.2f} < 0.5)",
                "position_multiplier": 0,
                "skipped_reason": "low_confidence_sell",
            }

        # ── 2. Regime 调整 ─────────────────────────────
        position_mult = 1.0
        regime_note = ""

        if regime == "CRISIS":
            if action == "buy":
                return {
                    "action": "hold",
                    "confidence": confidence,
                    "reason": "CRISIS regime: 禁止新买入",
                    "position_multiplier": 0,
                    "skipped_reason": "crisis_regime",
                }
            position_mult = 0.0
            regime_note = "CRISIS: force close"
        elif regime == "TRENDING_DOWN":
            if action == "buy":
                return {
                    "action": "hold",
                    "confidence": confidence,
                    "reason": "TRENDING_DOWN regime: 暂停买入",
                    "position_multiplier": 0,
                    "skipped_reason": "trending_down_regime",
                }
            position_mult = 0.3
            regime_note = "TRENDING_DOWN: position 30%"
        elif regime == "HIGH_VOLATILITY":
            position_mult = 0.5
            regime_note = "HIGH_VOLATILITY: position 50%"
        elif regime == "RECOVERY":
            position_mult = 0.3
            regime_note = "RECOVERY: position 30%"
        elif regime == "BREAKOUT":
            position_mult = 0.8
            regime_note = "BREAKOUT: position 80%"
        elif regime == "TRENDING_UP":
            position_mult = 1.0
            regime_note = "TRENDING_UP: full position"
        else:
            # RANGING or unknown
            position_mult = 0.5
            regime_note = "RANGING: position 50%"

        # ── 3. 记忆规则检查 ────────────────────────────
        rule_violations = []
        semantic_rules = memory_context.get("semantic", [])
        for rule in semantic_rules:
            sd = rule.get("structured_data") or {}
            if not isinstance(sd, dict):
                continue
            rule_action = sd.get("action", "")
            # 如果规则建议跳过同类交易，记录（warn only，不 block）
            if "skip" in rule_action.lower() and action == "buy":
                cw = rule.get("comply_win", 0) or 0
                cl = rule.get("comply_lose", 0) or 0
                total = cw + cl
                if total >= 3 and cw / total > 0.6:
                    rule_violations.append(sd.get("condition", "unknown rule"))

        # ── 4. 已持仓检查 ──────────────────────────────
        if action == "buy" and existing_position:
            return {
                "action": "hold",
                "confidence": confidence,
                "reason": "已持有该代币，不重复买入",
                "position_multiplier": 0,
                "skipped_reason": "already_holding",
            }

        # ── 5. 构建最终决策 ────────────────────────────
        reason_parts = [reasoning]
        if regime_note:
            reason_parts.append(f"Regime: {regime_note}")
        if rule_violations:
            reason_parts.append(f"规则提醒: {'; '.join(rule_violations)}")

        return {
            "action": action,
            "confidence": confidence,
            "reason": " | ".join(reason_parts),
            "position_multiplier": position_mult,
            "skipped_reason": None,
        }
