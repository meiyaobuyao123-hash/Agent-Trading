"""
PRD-007 M6: 牛熊辩论引擎

3 轮辩论（Bull R1 -> Bear R1 -> Bull R2 -> Bear R2 -> Facilitator）
全部使用 Claude Sonnet，串行执行（每轮 ~2s）。

输出: {debate_log, conclusion}
conclusion = {winner, confidence, action, risk, reasoning}

Python 3.9 兼容。
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-20250514"

# ── Prompt 模板 ────────────────────────────────────────

BULL_R1_PROMPT = """基于以下 3 位分析师的报告，请从看多的角度论证为什么应该买入。

技术面分析：
{technical_report}

情绪面分析：
{sentiment_report}

链上分析：
{onchain_report}

历史记忆：
{memory_context}

请用 3 个论点说明买入理由。每个论点用 1-2 句话。"""

BEAR_R1_PROMPT = """基于相同的分析报告，请从看空的角度反驳以上看多论点并说明风险。

技术面分析：
{technical_report}

情绪面分析：
{sentiment_report}

链上分析：
{onchain_report}

看多论点：
{bull_arguments}

请用 3 个论点说明不应买入的理由。每个论点用 1-2 句话。"""

BULL_R2_PROMPT = """看空提出了以下风险：
{bear_arguments}

请回应这些风险，并补充新的看多证据。用 2-3 个论点。"""

BEAR_R2_PROMPT = """看多回应如下：
{bull_response}

请指出其论点的弱点，并补充看空证据。用 2-3 个论点。"""

FACILITATOR_PROMPT = """以下是看多和看空各 2 轮辩论的完整记录：

{full_debate_log}

请作为中立裁判总结：
1. 哪方论点更有说服力？
2. 综合胜率评估（0-1）
3. 最大风险是什么？
4. 建议动作（buy/sell/hold）及置信度

严格输出 JSON（不要加任何前缀或 markdown）:
{{
  "winner": "bull" | "bear" | "draw",
  "confidence": 0.0 ~ 1.0,
  "action": "buy" | "sell" | "hold",
  "risk": "风险描述",
  "reasoning": "总结推理过程"
}}"""


class DebateEngine:
    """牛熊辩论引擎"""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    async def run_debate(
        self,
        reports: Dict[str, Any],
        memory_context: str = "",
    ) -> Dict[str, Any]:
        """
        执行 3 轮辩论

        Args:
            reports: {"technical": {...}, "sentiment": {...}, "onchain": {...}}
            memory_context: 格式化的记忆文本

        Returns:
            {
                "debate_log": str,       # 完整辩论记录
                "conclusion": dict,       # {winner, confidence, action, risk, reasoning}
                "rounds": 3,
                "tokens_used": int,
                "duration_ms": int,
            }
        """
        if not self._api_key:
            log.warning("[DebateEngine] No API key, returning default hold")
            return self._default_result()

        start_time = time.time()
        total_tokens = 0

        tech_str = json.dumps(reports.get("technical", {}), ensure_ascii=False, indent=2)
        sent_str = json.dumps(reports.get("sentiment", {}), ensure_ascii=False, indent=2)
        chain_str = json.dumps(reports.get("onchain", {}), ensure_ascii=False, indent=2)

        try:
            # Round 1 — Bull
            bull_r1, t1 = await self._call_sonnet(
                BULL_R1_PROMPT.format(
                    technical_report=tech_str,
                    sentiment_report=sent_str,
                    onchain_report=chain_str,
                    memory_context=memory_context or "无历史记忆",
                )
            )
            total_tokens += t1

            # Round 1 — Bear
            bear_r1, t2 = await self._call_sonnet(
                BEAR_R1_PROMPT.format(
                    technical_report=tech_str,
                    sentiment_report=sent_str,
                    onchain_report=chain_str,
                    bull_arguments=bull_r1,
                )
            )
            total_tokens += t2

            # Round 2 — Bull
            bull_r2, t3 = await self._call_sonnet(
                BULL_R2_PROMPT.format(bear_arguments=bear_r1)
            )
            total_tokens += t3

            # Round 2 — Bear
            bear_r2, t4 = await self._call_sonnet(
                BEAR_R2_PROMPT.format(bull_response=bull_r2)
            )
            total_tokens += t4

            # Round 3 — Facilitator
            full_log = (
                f"=== Bull Round 1 ===\n{bull_r1}\n\n"
                f"=== Bear Round 1 ===\n{bear_r1}\n\n"
                f"=== Bull Round 2 ===\n{bull_r2}\n\n"
                f"=== Bear Round 2 ===\n{bear_r2}"
            )

            facilitator_raw, t5 = await self._call_sonnet(
                FACILITATOR_PROMPT.format(full_debate_log=full_log)
            )
            total_tokens += t5

            # 解析 Facilitator 结论
            try:
                conclusion = json.loads(facilitator_raw)
            except json.JSONDecodeError:
                log.warning("[DebateEngine] Facilitator JSON parse failed, extracting manually")
                conclusion = {
                    "winner": "draw",
                    "confidence": 0.5,
                    "action": "hold",
                    "risk": "辩论结论解析失败",
                    "reasoning": facilitator_raw[:200],
                }

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "debate_log": full_log,
                "conclusion": conclusion,
                "rounds": 3,
                "tokens_used": total_tokens,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            log.error("[DebateEngine] Debate failed: %s", e)
            return self._default_result()

    async def _call_sonnet(self, prompt: str) -> tuple:
        """
        调用 Claude Sonnet，返回 (text, tokens_used)

        使用 asyncio.to_thread 防止阻塞事件循环。
        """
        import anthropic

        client = anthropic.Anthropic(api_key=self._api_key)
        response = await asyncio.to_thread(
            client.messages.create,
            model=SONNET_MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
        return text, tokens

    def _default_result(self) -> Dict[str, Any]:
        """辩论失败时的默认结果"""
        return {
            "debate_log": "",
            "conclusion": {
                "winner": "draw",
                "confidence": 0.3,
                "action": "hold",
                "risk": "辩论未能完成",
                "reasoning": "API 不可用或辩论过程出错",
            },
            "rounds": 0,
            "tokens_used": 0,
            "duration_ms": 0,
        }
