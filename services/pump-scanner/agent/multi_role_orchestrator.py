"""
PRD-007: 多角色 Agent 编排器

分级触发:
  Level 1 — 规则引擎评估（$0）
  Level 2 — 单 Agent 快速评估（~$0.003 Sonnet 一次）
  Level 3 — 全流程多角色（~$0.015：3 Haiku 并行 + 5 Sonnet 串行）

L3 触发条件（任一满足）:
  - amount > $2000  (R47 P9 — 与 04-spec §5.1 对齐;原 $30 是早期占位)
  - score > 70
  - 记忆中无该代币历史（未知代币）

流程:
  L3: 3 分析师并行 → 牛熊辩论(串行) → 决策 → 风控审查 → 执行/拒绝
  L2: 单 Sonnet 快速判断 → 规则风控 → 执行/拒绝
  L1: 纯规则引擎 → 执行/拒绝

Python 3.9 兼容。
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from agent.analysts import TechnicalAnalyst, SentimentAnalyst, OnchainAnalyst
from agent.debate import DebateEngine
from agent.decision_agent import DecisionAgent
from agent.risk_reviewer import RiskReviewer
from agent.memory import get_memory_manager
from agent.risk_manager import get_risk_manager

log = logging.getLogger(__name__)

# 成本估算常量（每次触发的 USD 成本）
COST_L1 = 0.0
COST_L2 = 0.003
COST_L3 = 0.015


class MultiRoleOrchestrator:
    """多角色 Agent 编排器"""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._technical = TechnicalAnalyst(self._api_key)
        self._sentiment = SentimentAnalyst(self._api_key)
        self._onchain = OnchainAnalyst(self._api_key)
        self._debate = DebateEngine(self._api_key)
        self._decision = DecisionAgent()
        self._risk_reviewer = RiskReviewer(self._api_key)

        # 统计
        self._stats = {
            "l1_count": 0, "l2_count": 0, "l3_count": 0,
            "l3_approved": 0, "l3_rejected": 0, "l3_reduced": 0,
            "total_tokens": 0, "total_cost_usd": 0.0,
        }

    def determine_level(
        self,
        amount_usd: float,
        score: float,
        token_address: str,
        has_trade_action: bool = True,
    ) -> int:
        """
        判断触发级别

        L1: 无交易动作（纯通知/alert）
        L2: 有交易动作但不满足 L3 条件
        L3: amount>2000 OR score>70 OR 未知代币
            R47 P9 — 与 04-spec §5.1 对齐(原 $30 是早期占位)

        Args:
            amount_usd: 交易金额
            score: 代币评分
            token_address: 代币地址
            has_trade_action: 策略是否包含 buy/sell 动作

        Returns:
            1, 2, or 3
        """
        if not has_trade_action:
            return 1

        # L3 条件
        if amount_usd > 2000:  # R47 P9 — 与 04-spec §5.1 对齐(原 $30 是早期占位)
            return 3
        if score > 70:
            return 3

        # 检查记忆中是否有该代币历史
        try:
            memory = get_memory_manager()
            recent = memory.working.get_recent(50)
            known = any(
                e.get("token", "").lower() == token_address[:8].lower()
                or e.get("token_address", "").lower() == token_address.lower()
                for e in recent
            )
            if not known:
                # 检查中期记忆
                episodes = memory.episodic.search(
                    chain="", trigger_source="", mcap_bucket="", regime="", limit=5
                )
                # 简化检查：如果最近记忆都没提到此代币，视为未知
                if not episodes:
                    return 3
        except Exception:
            pass

        return 2

    async def execute(
        self,
        level: int,
        token_data: Dict[str, Any],
        market_data: Dict[str, Any],
        strategy: Dict[str, Any],
        trade_action: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        按级别执行编排

        Args:
            level: 1/2/3
            token_data: 代币数据
            market_data: 市场数据
            strategy: 策略配置
            trade_action: 交易动作 {type, amount_usd, ...}

        Returns:
            {
                "level": int,
                "action": "buy" | "sell" | "hold" | "blocked",
                "amount_usd": float,
                "confidence": float,
                "reason": str,
                "debate_id": str | None,
                "tokens_used": int,
                "cost_usd": float,
                "duration_ms": int,
                "reports": dict | None,
                "debate_result": dict | None,
                "risk_review": dict | None,
            }
        """
        start_time = time.time()

        if level == 1:
            result = await self._execute_l1(token_data, trade_action)
        elif level == 2:
            result = await self._execute_l2(token_data, market_data, trade_action)
        else:
            result = await self._execute_l3(token_data, market_data, strategy, trade_action)

        result["level"] = level
        result["duration_ms"] = int((time.time() - start_time) * 1000)

        # 更新统计
        self._stats[f"l{level}_count"] += 1
        self._stats["total_tokens"] += result.get("tokens_used", 0)
        self._stats["total_cost_usd"] += result.get("cost_usd", 0)

        # 记录到 DB（L3 记录辩论）
        if level == 3 and result.get("debate_result"):
            debate_id = await self._save_debate(token_data, trade_action, result)
            result["debate_id"] = debate_id

        return result

    async def _execute_l1(
        self,
        token_data: Dict[str, Any],
        trade_action: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Level 1: 纯规则引擎（无 LLM 调用）"""
        # 直接通过，由 ActionDispatcher 的 risk_manager 处理
        return {
            "action": trade_action.get("type", "alert"),
            "amount_usd": float(trade_action.get("amount_usd", 0)),
            "confidence": 1.0,
            "reason": "L1 规则引擎通过",
            "debate_id": None,
            "tokens_used": 0,
            "cost_usd": COST_L1,
            "reports": None,
            "debate_result": None,
            "risk_review": None,
        }

    async def _execute_l2(
        self,
        token_data: Dict[str, Any],
        market_data: Dict[str, Any],
        trade_action: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Level 2: 单 Sonnet 快速评估"""
        if not self._api_key:
            return {
                "action": trade_action.get("type", "hold"),
                "amount_usd": float(trade_action.get("amount_usd", 0)),
                "confidence": 0.5,
                "reason": "L2: API key 未配置",
                "debate_id": None,
                "tokens_used": 0,
                "cost_usd": 0,
                "reports": None,
                "debate_result": None,
                "risk_review": None,
            }

        try:
            import anthropic

            prompt = self._build_l2_prompt(token_data, market_data, trade_action)
            client = anthropic.Anthropic(api_key=self._api_key)
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text.strip()
            tokens_used = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)

            try:
                result = json.loads(raw)
                action = result.get("action", "hold")
                confidence = float(result.get("confidence", 0.5))
                reason = result.get("reason", "L2 快速评估")
            except json.JSONDecodeError:
                action = "hold"
                confidence = 0.5
                reason = f"L2 JSON 解析失败: {raw[:100]}"

            return {
                "action": action,
                "amount_usd": float(trade_action.get("amount_usd", 0)),
                "confidence": confidence,
                "reason": reason,
                "debate_id": None,
                "tokens_used": tokens_used,
                "cost_usd": COST_L2,
                "reports": None,
                "debate_result": None,
                "risk_review": None,
            }

        except Exception as e:
            log.warning("[Orchestrator L2] Error: %s", e)
            return {
                "action": "hold",
                "amount_usd": float(trade_action.get("amount_usd", 0)),
                "confidence": 0.3,
                "reason": f"L2 评估异常: {str(e)[:100]}",
                "debate_id": None,
                "tokens_used": 0,
                "cost_usd": 0,
                "reports": None,
                "debate_result": None,
                "risk_review": None,
            }

    async def _execute_l3(
        self,
        token_data: Dict[str, Any],
        market_data: Dict[str, Any],
        strategy: Dict[str, Any],
        trade_action: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Level 3: 全流程多角色

        1. 3 分析师并行 (~1s)
        2. 牛熊辩论串行 (~10s)
        3. 决策
        4. 风控审查（条件触发）
        """
        total_tokens = 0
        amount_usd = float(trade_action.get("amount_usd", 0))

        # ── 1. 并行分析师 ──────────────────────────────
        log.info("[Orchestrator L3] Starting parallel analysts...")
        technical, sentiment, onchain = await asyncio.gather(
            self._technical.analyze(token_data, market_data),
            self._sentiment.analyze(token_data, market_data),
            self._onchain.analyze(token_data, market_data),
            return_exceptions=True,
        )

        # 降级处理
        neutral_fallback = {"direction": "neutral", "confidence": 0.3, "points": ["分析失败，使用中性默认"]}
        if isinstance(technical, Exception):
            log.warning("[Orchestrator L3] Technical analyst failed: %s", technical)
            technical = dict(neutral_fallback)
        if isinstance(sentiment, Exception):
            log.warning("[Orchestrator L3] Sentiment analyst failed: %s", sentiment)
            sentiment = dict(neutral_fallback)
        if isinstance(onchain, Exception):
            log.warning("[Orchestrator L3] Onchain analyst failed: %s", onchain)
            onchain = dict(neutral_fallback)

        reports = {
            "technical": technical,
            "sentiment": sentiment,
            "onchain": onchain,
        }

        # 累加 tokens
        for r in [technical, sentiment, onchain]:
            total_tokens += r.pop("_tokens_used", 0)

        # ── 2. 获取记忆上下文 ─────────────────────────
        memory = get_memory_manager()
        chain = token_data.get("chain", "solana")
        token_address = token_data.get("address", token_data.get("mint", ""))
        mcap = float(token_data.get("market_cap_usd", 0))

        # 获取当前 regime
        regime = token_data.get("_market_regime", "RANGING")
        if not regime or regime == "unknown":
            try:
                from agent.regime_detector import get_regime_detector
                regime = get_regime_detector().get_regime()
            except Exception:
                regime = "RANGING"

        memory_context = memory.get_context_for_decision(
            chain=chain,
            token_address=token_address,
            trigger_source=token_data.get("source", ""),
            market_cap_usd=mcap,
            market_regime=regime,
        )
        memory_text = memory.format_for_prompt(memory_context)

        # ── 3. 牛熊辩论 ───────────────────────────────
        log.info("[Orchestrator L3] Starting debate...")
        debate_result = await self._debate.run_debate(reports, memory_text)
        total_tokens += debate_result.get("tokens_used", 0)
        conclusion = debate_result.get("conclusion", {})

        # ── 4. 决策 ───────────────────────────────────
        risk_mgr = get_risk_manager()
        existing_position = token_address in risk_mgr._open_positions

        decision = self._decision.decide(
            conclusion=conclusion,
            memory_context=memory_context,
            regime=regime,
            existing_position=existing_position,
            token_address=token_address,
        )

        final_action = decision["action"]
        final_confidence = decision["confidence"]
        final_reason = decision["reason"]
        position_mult = decision.get("position_multiplier", 1.0)

        # 应用仓位倍数
        adjusted_amount = amount_usd * position_mult

        # ── 5. 风控审查（条件触发）─────────────────────
        risk_review = None
        if final_action in ("buy", "sell"):
            debate_confidence = float(conclusion.get("confidence", 0))
            if self._risk_reviewer.should_review(adjusted_amount, regime, debate_confidence):
                log.info("[Orchestrator L3] Triggering AI risk review...")

                portfolio = risk_mgr.get_risk_summary()
                risk_review = await self._risk_reviewer.review(
                    trade_details={
                        "action": final_action,
                        "token": token_data.get("symbol", token_data.get("name", token_address[:10])),
                        "chain": chain,
                        "amount_usd": adjusted_amount,
                    },
                    portfolio=portfolio,
                    regime=regime,
                    debate_conclusion=conclusion,
                )
                total_tokens += risk_review.get("tokens_used", 0)

                # 应用风控决定
                review_decision = risk_review.get("decision", "APPROVE")
                if review_decision == "REJECT":
                    self._stats["l3_rejected"] += 1
                    final_action = "blocked"
                    final_reason += f" | 风控否决: {risk_review.get('reason', '')}"
                elif review_decision == "REDUCE":
                    self._stats["l3_reduced"] += 1
                    adjusted_amount = adjusted_amount / 2
                    final_reason += f" | 风控减仓: {risk_review.get('reason', '')}"
                else:
                    self._stats["l3_approved"] += 1

        return {
            "action": final_action,
            "amount_usd": adjusted_amount,
            "confidence": final_confidence,
            "reason": final_reason,
            "debate_id": None,  # 由调用方写入 DB 后填充
            "tokens_used": total_tokens,
            "cost_usd": COST_L3,
            "reports": reports,
            "debate_result": debate_result,
            "risk_review": risk_review,
        }

    async def _save_debate(
        self,
        token_data: Dict[str, Any],
        trade_action: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Optional[str]:
        """保存辩论记录到 agent_debates 表"""
        try:
            from database import get_db

            debate_result = result.get("debate_result", {})
            conclusion = debate_result.get("conclusion", {})
            risk_review = result.get("risk_review")
            reports = result.get("reports", {})

            row = {
                "token_address": token_data.get("address", token_data.get("mint", "")),
                "chain": token_data.get("chain", ""),
                "trigger_source": token_data.get("source", ""),
                "technical_report": reports.get("technical"),
                "sentiment_report": reports.get("sentiment"),
                "onchain_report": reports.get("onchain"),
                "debate_log": debate_result.get("debate_log", ""),
                "debate_rounds": debate_result.get("rounds", 3),
                "conclusion_action": conclusion.get("action", "hold"),
                "conclusion_confidence": float(conclusion.get("confidence", 0)),
                "conclusion_winner": conclusion.get("winner", "draw"),
                "conclusion_risk": conclusion.get("risk", ""),
                "conclusion_reasoning": conclusion.get("reasoning", ""),
                "risk_review": risk_review.get("decision") if risk_review else None,
                "risk_review_reason": risk_review.get("reason") if risk_review else None,
                "final_action": result.get("action", "hold"),
                "debate_level": result.get("level", 3),
                "total_tokens_used": result.get("tokens_used", 0),
                "total_cost_usd": result.get("cost_usd", 0),
            }

            db_result = await asyncio.to_thread(
                lambda: get_db().table("agent_debates").insert(row).execute()
            )

            if db_result.data:
                debate_id = db_result.data[0].get("id")
                log.info("[Orchestrator] Debate saved: %s", debate_id)
                return debate_id
            return None

        except Exception as e:
            log.error("[Orchestrator] Failed to save debate: %s", e)
            return None

    def _build_l2_prompt(
        self,
        token_data: Dict[str, Any],
        market_data: Dict[str, Any],
        trade_action: Dict[str, Any],
    ) -> str:
        """构建 L2 快速评估 prompt"""
        symbol = token_data.get("symbol", token_data.get("name", "unknown"))
        chain = token_data.get("chain", "")
        score = token_data.get("score", 0)
        price = token_data.get("price_usd", 0)
        mcap = token_data.get("market_cap_usd", 0)
        liq = token_data.get("liquidity_usd", 0)
        action_type = trade_action.get("type", "buy")
        amount = trade_action.get("amount_usd", 0)

        return f"""快速评估以下交易是否值得执行：

代币: {symbol} ({chain})
评分: {score}
价格: ${price}
市值: ${mcap:,.0f}
流动性: ${liq:,.0f}
动作: {action_type} ${amount}

请快速判断，严格输出 JSON（不要加任何前缀或 markdown）:
{{"action": "buy"|"sell"|"hold", "confidence": 0.0~1.0, "reason": "简短理由"}}"""

    def get_stats(self) -> Dict[str, Any]:
        """获取编排器统计"""
        return dict(self._stats)


# ── 全局单例 ──────────────────────────────────────────

_orchestrator: Optional[MultiRoleOrchestrator] = None


def get_orchestrator() -> MultiRoleOrchestrator:
    """获取全局 MultiRoleOrchestrator 单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiRoleOrchestrator()
    return _orchestrator
