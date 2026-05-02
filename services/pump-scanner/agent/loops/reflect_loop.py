"""
Reflect Loop — 反思 → JSON-diff dedupe → 5 条硬晋升 → agent_memory

引用 docs/agent-pm/05-tool-catalog.md S07 review-engine(共用 reflection 数据)
引用 docs/agent-pm/06-memory-spec.md §3.2 episodic + §3.3 semantic 5 条硬晋升
引用 docs/agent-pm/17-tech-plan.md Phase 2 Reflect Loop

触发:
  - daily(cron 20:00)
  - count(每 10 笔闭仓)
  - emergency(单笔 -25% + amount ≥ $30)

流程(单 cycle):
  ReflectLoop.run_cycle(device_id, trigger='daily'|'count'|'emergency')
    1. _gather_recent_trades:从 agent_executions 拉最近 N 笔(配对 buy/sell + pnl_pct)
    2. _gather_active_rules:从 agent_memory 拉当前 active semantic rules
    3. ReflectionEngine.run_reflection(trades, active_rules):
       Claude Sonnet 输出 {winning_pattern, losing_pattern, new_rules: [...]}
       LLM 失败 → 跳过本次 cycle(不阻断,等下次)
    4. ReflectionEngine.deduplicate_proposed_rules(new_rules, active_rules):
       JSON-diff < 20% → 跳过(更新 propose_count_so_far 留给下次)
    5. 对每条去重后的 new_rule:
       - _aggregate_compliance_samples:从 trades 算 comply/violate pnls + regimes
       - SemanticMemory.check_strict_promotion_gates(...) 5 门槛
         * 全过 → try_promote_strict 写 agent_memory + 14d Shadow Mode
         * 任一不过 → 写 episodic(记录提议但未晋升)
    6. 写 reflection 总结到 episodic_memory(供下次反思参考)
    7. 返 ReflectResult(promoted_count + dedupe_skipped + gate_blocked)

设计原则:
  - LLM 失败永远不抛错(返 ReflectResult ok=False + reason)
  - 单条 rule 写入失败不阻断其他 rule
  - emergency trigger 加 daily limit(对齐 ReflectionEngine.MAX_EMERGENCY_PER_DAY)
"""
from __future__ import annotations
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


DEFAULT_TRADE_LOOKBACK_DAYS = 7  # daily 反思看最近 7 天


@dataclass
class ReflectResult:
    ok: bool
    trigger: str
    trades_analyzed: int = 0
    new_rules_proposed: int = 0
    dedupe_skipped: int = 0
    gate_blocked: int = 0
    promoted: int = 0
    reflection_id: Optional[str] = None
    promoted_rule_ids: List[str] = field(default_factory=list)
    error: Optional[str] = None
    latency_ms: int = 0


class ReflectLoop:
    """反思 loop;一次 run_cycle 完成完整反思 → 晋升流程。"""

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")

    async def run_cycle(
        self,
        device_id: Optional[str] = None,
        trigger: str = "daily",
        lookback_days: int = DEFAULT_TRADE_LOOKBACK_DAYS,
        emergency_pnl_pct: Optional[float] = None,
        emergency_amount_usd: Optional[float] = None,
    ) -> ReflectResult:
        """主入口。

        Args:
          device_id: 限定用户(None=跨用户聚合,管理用)
          trigger: 'daily' / 'count' / 'emergency'
          lookback_days: 拉多久的 trades
          emergency_pnl_pct / emergency_amount_usd: emergency 触发时用于
            ReflectionEngine.should_emergency_reflect 判断 + daily limit
        """
        t0 = time.monotonic()

        from agent.memory import get_memory_manager
        try:
            mem = get_memory_manager()
        except Exception as e:
            return ReflectResult(
                ok=False, trigger=trigger,
                error=f"memory_manager_init_failed: {e}",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # emergency:先验证是否真满足 + daily limit
        if trigger == "emergency":
            if (emergency_pnl_pct is None
                    or emergency_amount_usd is None
                    or not mem.reflection.should_emergency_reflect(
                        emergency_pnl_pct, emergency_amount_usd)):
                return ReflectResult(
                    ok=False, trigger=trigger,
                    error="emergency_threshold_not_met",
                    latency_ms=int((time.monotonic() - t0) * 1000),
                )

        # 1. 拉 trades
        trades = await self._gather_recent_trades(device_id, lookback_days)
        if not trades:
            return ReflectResult(
                ok=True, trigger=trigger,
                error="no_trades_to_reflect",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # 2. 拉 active rules
        active_rules = self._gather_active_rules(mem)

        # 3. 调 LLM 反思
        is_emergency = (trigger == "emergency")
        try:
            reflection = await mem.reflection.run_reflection(
                trades=trades, active_rules=active_rules,
                is_emergency=is_emergency,
            )
        except Exception as e:
            return ReflectResult(
                ok=False, trigger=trigger,
                trades_analyzed=len(trades),
                error=f"llm_failed: {e}",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        if reflection is None:
            return ReflectResult(
                ok=False, trigger=trigger,
                trades_analyzed=len(trades),
                error="reflection_returned_none",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        new_rules = list(reflection.get("new_rules") or [])

        # 4. JSON-diff dedupe
        kept_rules = mem.reflection.deduplicate_proposed_rules(
            new_rules, active_rules, threshold=0.20,
        )
        dedupe_skipped = len(new_rules) - len(kept_rules)

        # 5. 每条 kept_rule 走 5 条硬晋升
        promoted_ids: List[str] = []
        gate_blocked = 0
        for rule in kept_rules:
            comply_pnls, violate_pnls, regimes = self._aggregate_compliance_samples(
                rule_condition=str(rule.get("condition", "")),
                trades=trades,
            )

            # reflections_count:占位用 1(下次累积);W7-W12 接 propose_count_so_far
            reflections_count = max(
                1,
                int((rule.get("propose_count_so_far") or 0)) + 1,
            )

            promote_result = mem.semantic.try_promote_strict(
                condition=str(rule.get("condition", "")),
                action=str(rule.get("action", "skip_buy")),
                reflections_count=reflections_count,
                comply_pnls=comply_pnls,
                violate_pnls=violate_pnls,
                regimes_observed=regimes,
                metadata={
                    "content": rule.get("evidence", str(rule)[:200]),
                },
            )
            if promote_result.get("ok"):
                rid = promote_result.get("promoted_rule_id")
                if rid:
                    promoted_ids.append(rid)
                else:
                    promoted_ids.append("(no_id)")
            else:
                gate_blocked += 1
                # 写一条 episodic 记录(propose_count++ 留给下次)
                try:
                    mem.episodic.add({
                        "type": "reflection_proposal",
                        "content": (rule.get("evidence", "") or "")[:200],
                        "trigger_source": "reflect_loop",
                        "structured_data": {
                            "condition": rule.get("condition"),
                            "action": rule.get("action"),
                            "gates_failed_summary": promote_result.get("reason", ""),
                            "propose_count_so_far": reflections_count,
                        },
                    })
                except Exception as e:
                    log.debug("[reflect_loop] episodic add proposal failed: %s", e)

        # 6. 反思总结写 episodic
        reflection_id: Optional[str] = None
        try:
            summary_text = (
                f"Reflection {trigger}:{len(trades)} trades, "
                f"new={len(new_rules)},kept={len(kept_rules)},"
                f"promoted={len(promoted_ids)},blocked={gate_blocked}"
            )
            reflection_id = mem.episodic.add({
                "type": "reflection_summary",
                "content": summary_text + " | win_pattern: " + str(reflection.get("winning_pattern", ""))[:200],
                "trigger_source": "reflect_loop",
                "structured_data": {
                    "trigger": trigger,
                    "trades_count": len(trades),
                    "new_rules_proposed": len(new_rules),
                    "dedupe_skipped": dedupe_skipped,
                    "promoted_count": len(promoted_ids),
                    "gate_blocked": gate_blocked,
                    "winning_pattern": reflection.get("winning_pattern", ""),
                    "losing_pattern": reflection.get("losing_pattern", ""),
                },
            })
        except Exception as e:
            log.debug("[reflect_loop] episodic write summary failed: %s", e)

        # 重置交易计数(若是 count 触发)
        if trigger == "count":
            try:
                mem.reflection.reset_trade_count()
            except Exception:
                pass

        return ReflectResult(
            ok=True,
            trigger=trigger,
            trades_analyzed=len(trades),
            new_rules_proposed=len(new_rules),
            dedupe_skipped=dedupe_skipped,
            gate_blocked=gate_blocked,
            promoted=len(promoted_ids),
            promoted_rule_ids=promoted_ids,
            reflection_id=reflection_id,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    # ── helpers ──────────────────────────────────────────────

    async def _gather_recent_trades(
        self, device_id: Optional[str], lookback_days: int,
    ) -> List[Dict[str, Any]]:
        """从 agent_executions 拉最近 N 天 trades(配对 buy/sell + pnl_pct)。

        复用 review_engine._load_trades(已经做了配对 + d3_pct + pnl_ratio)。
        给 ReflectionEngine 用的字段:pnl_pct, amount_usd, regime, trigger_source 等
        映射到 trade dict。
        """
        try:
            from agent.review_engine import _load_trades
            now = datetime.now(timezone.utc)
            paired = await _load_trades(
                period_from=now - timedelta(days=lookback_days),
                period_to=now,
                user_id=device_id,
            )
        except Exception as e:
            log.warning("[reflect_loop] load_trades failed: %s", e)
            return []

        # 转成 reflection prompt 期望的格式
        out = []
        for p in paired:
            pnl_ratio = p.get("pnl_ratio")
            pnl_pct = ((pnl_ratio - 1.0) * 100) if pnl_ratio else None
            out.append({
                "token_address": p.get("token_address"),
                "chain": p.get("chain"),
                "amount_usd": p.get("buy_usd", 0.0),
                "pnl_pct": pnl_pct,
                "d3_pct": p.get("d3_pct"),
                "is_closed": p.get("is_closed"),
                "first_executed_at": p.get("first_executed_at"),
                "strategy_id": p.get("strategy_id"),
            })
        return out

    def _gather_active_rules(self, mem) -> List[Dict[str, Any]]:
        try:
            return list(mem.semantic.get_all_active() or [])
        except Exception as e:
            log.warning("[reflect_loop] get_all_active failed: %s", e)
            return []

    def _aggregate_compliance_samples(
        self, rule_condition: str, trades: List[Dict[str, Any]],
    ) -> Tuple[List[float], List[float], List[str]]:
        """v0:简化版 compliance 聚合。

        把 trades 全部算 comply(因为没法直接 evaluate condition vs trade ctx 不接 SemanticMemory.check_compliance)
        实际:W7-W12 接 SemanticMemory._matches_condition 真匹配。

        v0 用 trade 的 chain 和 d3 是否匹配 condition 字符串简单 heuristic:
          comply:trade.chain 在 condition 中提到 → 算 comply
          violate:trade.chain 不在 condition 中 → algorithm violate
        regimes:trade 自带 regime 字段(若有)
        """
        comply_pnls: List[float] = []
        violate_pnls: List[float] = []
        regimes: List[str] = []
        cond_upper = (rule_condition or "").upper()
        for t in trades:
            pnl = t.get("pnl_pct")
            if pnl is None:
                continue
            chain = (t.get("chain") or "").upper()
            if chain and chain in cond_upper:
                comply_pnls.append(float(pnl))
            else:
                violate_pnls.append(float(pnl))
            r = t.get("regime")
            if r:
                regimes.append(r)
        return comply_pnls, violate_pnls, regimes


# ── singleton ────────────────────────────────────────────


_loop: Optional[ReflectLoop] = None


def get_reflect_loop() -> ReflectLoop:
    global _loop
    if _loop is None:
        _loop = ReflectLoop()
    return _loop


def reset_loop_for_test() -> None:
    global _loop
    _loop = None
