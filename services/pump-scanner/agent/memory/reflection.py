"""
反思引擎 — Claude Sonnet 结构化分析

PRD-005 M13:
- 触发条件：累计 10 笔 / 每日 UTC 20:00 / 紧急反思（亏损>25% 且金额>$30）
- 用 Claude Sonnet（不是 Haiku）
- 结构化 JSON 输出：condition/action/confidence/evidence
- 最多 3 条 new_rules
- 紧急反思每日最多 2 次
- 规则晋升检查在反思后执行

Python 3.9 兼容。
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)

REFLECTION_MODEL = "claude-sonnet-4-20250514"
MAX_EMERGENCY_PER_DAY = 2
EMERGENCY_LOSS_PCT = 25
EMERGENCY_LOSS_MIN_USD = 30
MAX_NEW_RULES = 3

REFLECTION_PROMPT = """你是一个加密货币交易复盘专家。分析以下交易记录，输出 JSON。

交易记录：
{trades_json}

当前活跃规则：
{active_rules}

请输出严格 JSON 格式（不要 markdown 代码块）：
{{
  "winning_pattern": "赢钱交易的共同特征（1-2句话）",
  "losing_pattern": "亏钱交易的共同原因（1-2句话）",
  "new_rules": [
    {{
      "condition": "field op value AND field op value",
      "action": "skip_buy | reduce_position | tighten_stop",
      "confidence": 0.5,
      "evidence": "基于哪些交易得出的"
    }}
  ],
  "deprecated_rule_ids": ["rule_id_1"],
  "summary": "一句话总结"
}}

规则：
- condition 格式必须是 "field op value"，field 用小写（如 rsi, regime, trigger_source, hold_hours, mcap_bucket）
- op 只能用 > >= < <= =
- 最多输出 {max_rules} 条 new_rules
- 只在有充分证据时才输出 deprecated_rule_ids
- confidence 范围 0.5-1.0"""


class ReflectionEngine:
    """反思引擎 — Claude Sonnet 结构化分析"""

    def __init__(self):
        self._emergency_count_today: int = 0
        self._last_reset_date: str = ""
        self._trade_counter: int = 0  # 交易计数（用于 10 笔触发）
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")

    def increment_trade_count(self) -> int:
        """递增交易计数，返回当前值"""
        self._trade_counter += 1
        return self._trade_counter

    def reset_trade_count(self) -> None:
        """重置交易计数（反思完成后调用）"""
        self._trade_counter = 0

    def should_reflect_by_count(self) -> bool:
        """是否达到 10 笔触发条件"""
        return self._trade_counter >= 10

    async def run_reflection(
        self,
        trades: List[Dict],
        active_rules: List[Dict],
        is_emergency: bool = False,
    ) -> Optional[Dict]:
        """
        执行一次反思

        Args:
            trades: 最近的交易记录（最多 10 笔）
            active_rules: 当前活跃的 semantic 规则
            is_emergency: 是否紧急反思

        Returns:
            反思结果 dict，或 None（失败/跳过）
        """
        if not self._api_key:
            log.warning("No ANTHROPIC_API_KEY for reflection")
            return None

        # 紧急反思冷却
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self._emergency_count_today = 0
            self._last_reset_date = today

        if is_emergency:
            if self._emergency_count_today >= MAX_EMERGENCY_PER_DAY:
                log.info("Emergency reflection skipped: daily limit reached (%d/%d)",
                         self._emergency_count_today, MAX_EMERGENCY_PER_DAY)
                return None
            self._emergency_count_today += 1

        # 构造 prompt
        trades_text = json.dumps(
            trades[:10], ensure_ascii=False, indent=2, default=str
        )
        rules_text = json.dumps(
            [
                {
                    "id": r.get("id", ""),
                    "content": r.get("content", ""),
                    "condition": (r.get("structured_data") or {}).get("condition", ""),
                }
                for r in active_rules[:20]
            ],
            ensure_ascii=False,
            indent=2,
        )
        prompt = REFLECTION_PROMPT.format(
            trades_json=trades_text,
            active_rules=rules_text,
            max_rules=MAX_NEW_RULES,
        )

        # 调用 Claude Sonnet
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self._api_key)
            response = await asyncio.to_thread(
                client.messages.create,
                model=REFLECTION_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()

            # 清理可能的 markdown 代码块包裹
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(text)

            # 限制 new_rules 数量
            if "new_rules" in result and len(result["new_rules"]) > MAX_NEW_RULES:
                result["new_rules"] = result["new_rules"][:MAX_NEW_RULES]

            log.info(
                "[Reflection] Done: %d new rules, summary: %s",
                len(result.get("new_rules", [])),
                result.get("summary", "")[:80],
            )
            return result

        except json.JSONDecodeError as e:
            log.warning("Reflection JSON parse failed: %s (text: %s)", e, text[:200] if text else "")
            return None
        except Exception as e:
            log.error("Reflection failed: %s", e)
            return None

    def should_emergency_reflect(self, pnl_pct: float, amount_usd: float) -> bool:
        """
        判断是否需要紧急反思

        条件：亏损 > 25% 且金额 > $30
        """
        return pnl_pct <= -EMERGENCY_LOSS_PCT and amount_usd >= EMERGENCY_LOSS_MIN_USD

    # ── W3 D5+ JSON-diff 去重 ─────────────────────────────────

    @staticmethod
    def _normalize_rule_keys(rule: Dict[str, Any]) -> Dict[str, Any]:
        """提取做 diff 用的核心字段(忽略 evidence/confidence 等噪声字段)。"""
        return {
            "condition": (rule.get("condition") or "").strip().upper(),
            "action": (rule.get("action") or "").strip().lower(),
        }

    @staticmethod
    def jaccard_distance(a: Dict[str, Any], b: Dict[str, Any]) -> float:
        """简易 Jaccard 距离 — 1 - intersection/union of (k:v) pair set。
        用于规则 dedupe(condition + action 完全一样则距离 0)。
        """
        sa = {(k, v) for k, v in a.items()}
        sb = {(k, v) for k, v in b.items()}
        if not sa and not sb:
            return 0.0
        inter = len(sa & sb)
        uni = len(sa | sb)
        return 1.0 - (inter / uni if uni > 0 else 0.0)

    def deduplicate_proposed_rules(
        self,
        new_rules: List[Dict],
        existing_rules: List[Dict],
        threshold: float = 0.20,
    ) -> List[Dict]:
        """W3 D5+:JSON-diff dedupe(对齐 17-tech-plan.md "JSON diff < 20% 重复检测")

        对每条 new_rule:
          - 与 existing_rules 中 (type=semantic) 的 condition+action 算 Jaccard
          - 距离 < threshold(默认 20%)→ 认为重复,跳过
          - 否则保留(并标记 propose_count_so_far += 1)

        Returns: 去重后的 new_rules(每条会加 _is_duplicate / _matched_existing_id 元数据用于审计)
        """
        existing_keys = []
        for r in existing_rules or []:
            sd = r.get("structured_data") or {}
            if isinstance(sd, dict):
                key = self._normalize_rule_keys({
                    "condition": sd.get("condition", ""),
                    "action": sd.get("action", ""),
                })
                existing_keys.append((str(r.get("id", "")), key))

        kept: List[Dict] = []
        for n in (new_rules or []):
            n_key = self._normalize_rule_keys(n)
            duplicate = False
            matched_id = None
            for ex_id, ex_key in existing_keys:
                d = self.jaccard_distance(n_key, ex_key)
                if d < threshold:
                    duplicate = True
                    matched_id = ex_id
                    break
            if duplicate:
                log.info(
                    "[Reflection] Dedupe: '%s' matches existing %s (distance < %.2f)",
                    n_key.get("condition", "")[:50], matched_id, threshold,
                )
                # 不保留,但下游可能需要 propose_count++(留给调用方处理)
                continue
            kept.append(n)
        return kept
