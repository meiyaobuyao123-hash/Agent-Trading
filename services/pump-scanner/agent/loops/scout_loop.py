"""
Scout Loop — 信号 → 策略命中 → 触发 NotifyLoop

引用 docs/agent-pm/05-tool-catalog.md S04/S05 信号 trigger
引用 docs/agent-pm/17-tech-plan.md Phase 2 Scout Loop
复用 agent/event_bus.py(EventBus 4 类信号订阅)
复用 agent/evaluator.py:StrategyEvaluator(已有的策略匹配)
复用 agent/rule_engine.py(规则评估)

设计:
  与现有 event_listener.py 共存(不破坏线上)。
  本 Loop 提供:
    - evaluate_signal(signal_payload, source) → 命中 strategies 列表
    - dispatch_to_notify_loop(triggered_events, mode_hint=None)
    - process(signal_payload, source) — 完整一次性 evaluate + dispatch
  ScoutLoop 不做 EventBus 订阅(那是 main.py / event_listener 的活)
  本 Loop 是给 manual /scout/evaluate endpoint 用的可测桥

流程:
  ScoutLoop.process(signal_payload: DataEvent dict, source, dry_run=False)
    1. _gather_active_strategies(source):从 strategy_manager 拉关联此源的策略
    2. _evaluator.evaluate(data_event, strategies) → 命中 strategies
    3. 对每条命中:
       - check_daily_limit
       - 拼 NotifyLoop event 参数(继承 trigger_context)
       - 调 NotifyLoop.process(event, mode=strategy.mode, dry_run=...)
    4. 收集所有 NotifyResult,聚合返 ScoutResult

支持 source:
  - hot_coin / pump / kol / smart_money / regime / btc_eth(对齐 event_listener 的 4 大类)
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class ScoutResult:
    ok: bool
    source: str
    strategies_evaluated: int = 0
    triggered: int = 0
    dispatched: int = 0
    skipped_daily_limit: int = 0
    notify_results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    latency_ms: int = 0


class ScoutLoop:
    """signal → strategy match → NotifyLoop。"""

    def __init__(self) -> None:
        pass

    async def process(
        self,
        signal_payload: Dict[str, Any],
        source: str,
        *,
        chain: Optional[str] = None,
        token_address: Optional[str] = None,
        token_name: Optional[str] = None,
        mode_override: Optional[str] = None,
        dry_run: bool = False,
        max_dispatch: int = 5,
    ) -> ScoutResult:
        """主入口。

        Args:
          signal_payload: 数据载荷(对齐 DataEvent.data)
          source: 信号源名(hot_coin / pump / kol / smart_money / ...)
          chain / token_address / token_name: 信号关联的代币
          mode_override: 强制覆盖 strategy.mode(测试用;None=按 strategy 自身)
          dry_run: 不真触发 NotifyLoop / 不真推送
          max_dispatch: 单次最多 dispatch 多少条(防爆炸,默认 5)
        """
        t0 = time.monotonic()

        # 1. 构造 DataEvent
        try:
            from agent.schemas import DataEvent
            event = DataEvent(
                source=source,
                data=dict(signal_payload),
                chain=chain,
                token_address=token_address,
                token_name=token_name,
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            return ScoutResult(
                ok=False, source=source, error=f"data_event_build_failed: {e}",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # 2. 拉 active strategies
        try:
            from agent.strategy_manager import StrategyManager
            mgr = StrategyManager()
            strategies = mgr.get_active_strategies(data_source=source)
        except Exception as e:
            log.warning("[scout_loop] get_active_strategies failed: %s", e)
            strategies = []

        # 3. 评估
        try:
            from agent.evaluator import StrategyEvaluator
            triggered = StrategyEvaluator().evaluate(event, strategies)
        except Exception as e:
            return ScoutResult(
                ok=False, source=source,
                strategies_evaluated=len(strategies),
                error=f"evaluator_failed: {e}",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # 4. 对每条 triggered 调 NotifyLoop
        notify_results: List[Dict[str, Any]] = []
        skipped_dlim = 0
        dispatched = 0

        from agent.loops.notify_loop import get_notify_loop
        notify = get_notify_loop()
        try:
            from agent.strategy_manager import StrategyManager
            sm = StrategyManager()
        except Exception:
            sm = None

        for ev in triggered[:max_dispatch]:
            # daily_limit 检查
            if sm is not None:
                try:
                    if not sm.check_daily_limit(ev.strategy_id):
                        skipped_dlim += 1
                        continue
                except Exception:
                    pass

            # 拼 NotifyLoop event(StrategyTriggeredEvent 兼容 dict)
            ev_dict = ev.model_dump() if hasattr(ev, "model_dump") else (
                ev.dict() if hasattr(ev, "dict") else ev
            )
            # 把信号原始数据补到 trigger_context
            if isinstance(ev_dict, dict):
                ctx = ev_dict.get("trigger_context") or {}
                if isinstance(ctx, dict) and "token_data" not in ctx:
                    ctx["token_data"] = signal_payload
                ev_dict["trigger_context"] = ctx

            # 取 strategy.mode(若有)
            chosen_mode = mode_override
            if chosen_mode is None and sm is not None:
                try:
                    s = sm.get_strategy(ev.strategy_id) if hasattr(ev, "strategy_id") else None
                    if s:
                        chosen_mode = s.get("mode", "paper")
                except Exception:
                    chosen_mode = "paper"
            chosen_mode = chosen_mode or "paper"

            try:
                nr = await notify.process(
                    event=ev_dict, mode=chosen_mode, dry_run=dry_run,
                )
                notify_results.append({
                    "strategy_id": getattr(ev, "strategy_id", ""),
                    "mode": chosen_mode,
                    "verdict": nr.verdict,
                    "ok": nr.ok,
                    "position_usd": nr.position_usd,
                    "approval_id": nr.approval_id,
                    "push_sent_count": nr.push_sent_count,
                    "reason": nr.reason,
                })
                dispatched += 1
                # record_trigger(避免重复触发)
                if sm is not None and not dry_run:
                    try:
                        sm.record_trigger(ev.strategy_id)
                    except Exception:
                        pass
            except Exception as e:
                log.warning("[scout_loop] notify dispatch failed: %s", e)
                notify_results.append({
                    "strategy_id": getattr(ev, "strategy_id", ""),
                    "ok": False, "verdict": "error",
                    "reason": str(e)[:200],
                })

        return ScoutResult(
            ok=True, source=source,
            strategies_evaluated=len(strategies),
            triggered=len(triggered),
            dispatched=dispatched,
            skipped_daily_limit=skipped_dlim,
            notify_results=notify_results,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )


# ── singleton ────────────────────────────────────────────


_loop: Optional[ScoutLoop] = None


def get_scout_loop() -> ScoutLoop:
    global _loop
    if _loop is None:
        _loop = ScoutLoop()
    return _loop


def reset_loop_for_test() -> None:
    global _loop
    _loop = None
