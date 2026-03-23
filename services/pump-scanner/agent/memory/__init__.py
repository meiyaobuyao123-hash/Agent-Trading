"""
MemoryManager — 统一接口

PRD-005: 三层记忆（短期/中期/长期） + 反思引擎。
提供统一的写入、检索、格式化接口。

Python 3.9 兼容。
"""

import logging
from typing import Dict, Any, List, Optional

from .working_memory import WorkingMemory
from .episodic_memory import EpisodicMemory
from .semantic_memory import SemanticMemory
from .reflection import ReflectionEngine

log = logging.getLogger(__name__)


def _mcap_bucket(mcap: float) -> str:
    """市值分桶"""
    if mcap < 100_000:
        return "<100K"
    elif mcap < 1_000_000:
        return "100K-1M"
    elif mcap < 10_000_000:
        return "1M-10M"
    else:
        return ">10M"


class MemoryManager:
    """三层记忆系统的统一管理器"""

    def __init__(self):
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.reflection = ReflectionEngine()
        log.info("[MemoryManager] Initialized (working/episodic/semantic/reflection)")

    # ── 写入接口 ──────────────────────────────────────────

    def add_event(self, event: Dict[str, Any]) -> None:
        """写入短期记忆"""
        self.working.add(event)

    def add_trade_review(self, review: Dict[str, Any]) -> Optional[str]:
        """写入中期记忆（交易复盘）"""
        review.setdefault("category", "trade_review")
        return self.episodic.add(review)

    def add_risk_lesson(self, lesson: Dict[str, Any]) -> Optional[str]:
        """写入中期记忆（风控教训）"""
        lesson["category"] = "risk_lesson"
        return self.episodic.add(lesson)

    def add_market_pattern(self, pattern: Dict[str, Any]) -> Optional[str]:
        """写入中期记忆（市场模式）"""
        pattern["category"] = "market_pattern"
        return self.episodic.add(pattern)

    # ── 检索接口 ──────────────────────────────────────────

    def get_context_for_decision(
        self,
        chain: str,
        token_address: str,
        trigger_source: str,
        market_cap_usd: float,
        market_regime: str,
    ) -> Dict[str, Any]:
        """
        获取决策上下文（注入 prompt 用）

        返回:
        {
            "short_term": [...],   # 最近 10 条（24h 内）
            "episodic": [...],     # 相关性 Top 3
            "semantic": [...],     # 相关性 Top 10
        }
        """
        mcap_b = _mcap_bucket(market_cap_usd)
        return {
            "short_term": self.working.get_recent(10),
            "episodic": self.episodic.search(
                chain=chain,
                trigger_source=trigger_source,
                mcap_bucket=mcap_b,
                regime=market_regime,
                limit=3,
            ),
            "semantic": self.semantic.get_relevant(
                chain=chain,
                trigger_source=trigger_source,
                limit=10,
            ),
        }

    def check_rules(self, trade_context: Dict[str, Any]) -> List[Dict]:
        """检查交易是否违反规则（warn only，不 block）"""
        return self.semantic.check_compliance(trade_context)

    # ── 格式化 ──────────────────────────────────────────

    def format_for_prompt(self, context: Dict[str, Any]) -> str:
        """将记忆格式化为 prompt 文本"""
        lines: List[str] = []

        # 短期
        st = context.get("short_term", [])
        if st:
            lines.append("【短期记忆（最近24h事件）】")
            for e in st:
                summary = e.get("summary", "")
                if not summary:
                    summary = str(e)[:80]
                lines.append(f"- {summary}")

        # 中期
        ep = context.get("episodic", [])
        if ep:
            lines.append("\n【近期经验（相关交易复盘）】")
            for m in ep:
                content = m.get("content", "")[:120]
                lines.append(f"- {content}")

        # 长期
        sem = context.get("semantic", [])
        if sem:
            lines.append("\n【交易规则（已验证）】")
            for r in sem:
                sd = r.get("structured_data") or {}
                if not isinstance(sd, dict):
                    continue
                cw = r.get("comply_win", 0) or 0
                cl = r.get("comply_lose", 0) or 0
                total = cw + cl
                wr = f"{cw / total * 100:.0f}%" if total > 0 else "N/A"
                cond = sd.get("condition", "")
                action = sd.get("action", "")
                lines.append(
                    f"- Rule: {cond} -> {action}"
                    f"（遵守胜率{wr}，样本{total}笔）"
                )

        return "\n".join(lines)

    # ── 统计 ──────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计信息"""
        return {
            "working_memory_size": self.working.size_valid(),
            "working_memory_total": self.working.size(),
            "episodic_cached": len(self.episodic._cache),
            "semantic_rules": len(self.semantic._rules),
            "reflection_trade_counter": self.reflection._trade_counter,
            "reflection_emergency_today": self.reflection._emergency_count_today,
        }


# ── 全局单例 ──────────────────────────────────────────

_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """获取全局 MemoryManager 单例"""
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
