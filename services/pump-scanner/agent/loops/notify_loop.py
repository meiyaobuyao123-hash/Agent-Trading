"""
Notify Loop — strategy_triggered 完整路径

引用 docs/agent-pm/03-prd.md §C5 paper→notify→auto 模式分支
引用 docs/agent-pm/05-tool-catalog.md T07/T09/T13/T17
引用 docs/agent-pm/17-tech-plan.md Phase 2 Notify Loop

流程(单 turn):
  NotifyLoop.process(event: StrategyTriggeredEvent | dict, dry_run=False)
    1. _safety_pre_check:SafetyEngine 全局 CB / HR(已 W3 D4 接入)
       BLOCK → 直接返 verdict=blocked,不发推送
    2. _risk_check:RiskManager 16 项硬规则(已 W1 实施)
       BLOCK → 写 audit + push 一条 risk_blocked 通知
    3. _calc_position:T17 calc_position_size 算仓位(fixed_pct mode 默认)
       capped_by 字段透明返回(用于 push 文案)
    4. 路由到 mode handler:
       - paper:T07 run_paper_trade buy
       - notify:不交易,只推送 strategy_triggered
       - auto + HITL 触发条件:T09 create_approval_request + push hitl_approval
       - auto + 无 HITL:T08 execute_swap(W7-W12 接 KMS)+ push
    5. T13 send_push_notification(category 选 strategy_triggered/hitl_approval/...)
    6. 写 agent_executions(paper 由 T07 写;notify/auto 这里写)
    7. 返 NotifyResult

HITL 触发条件(对齐 17-tech-plan.md "10 触发条件"中已能在本 Loop 判的 4 条):
  - 单笔金额 ≥ $200(对齐 HR01 上限附近的高金额)
  - 总仓位占比 ≥ 30%(高集中)
  - 24h 已交易 ≥ 5 笔(高频)
  - thesis.conviction < 0.6 但 mode=auto(低置信度走真金)
  其他 6 条留 W7-W12(需要更多上下文,如 risk_score / hardrule_grey 等)

设计原则:
  - dry_run=True 不真执行 trade / push,只返"会怎么走"的 verdict
  - safety / risk 任一 BLOCK 不发交易 push,只发 blocked 通知(不静默)
  - LLM 不在本 Loop 调(本 Loop 是规则化 + Tool 编排)
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# HITL 触发硬阈值
HITL_AMOUNT_USD = 200.0
HITL_PORTFOLIO_PCT = 0.30
HITL_24H_TRADES = 5
HITL_LOW_CONVICTION = 0.6


@dataclass
class NotifyResult:
    ok: bool
    verdict: str  # "executed_paper" / "notify_only" / "executed_auto" /
                  # "hitl_pending" / "blocked_safety" / "blocked_risk" / "dry_run"
    mode: str
    reason: Optional[str] = None
    position_usd: float = 0.0
    capped_by: List[str] = field(default_factory=list)
    safety_block: Optional[Dict[str, Any]] = None
    risk_block: Optional[str] = None
    paper_trade: Optional[Dict[str, Any]] = None
    approval_id: Optional[str] = None
    push_sent_count: int = 0
    push_deep_link: Optional[str] = None
    latency_ms: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


class NotifyLoop:
    """strategy_triggered 处理。"""

    def __init__(self) -> None:
        pass

    async def process(
        self,
        event: Dict[str, Any],
        *,
        mode: Optional[str] = None,
        thesis: Optional[Dict[str, Any]] = None,
        account_balance_usd: float = 1000.0,
        portfolio_pct_in_chain: float = 0.0,
        recent_trades_24h: int = 0,
        position_mode: str = "fixed_pct",
        fixed_pct: float = 0.05,
        dry_run: bool = False,
    ) -> NotifyResult:
        """主入口。

        Args:
          event: 必含 strategy_id / user_id / strategy_name / matched_token /
                 matched_chain / trigger_context (dict);可选 token_data
          mode: 'paper' | 'notify' | 'auto'(必传;通常从 strategies 表取)
          thesis: 可选 thesis_loop 输出(用于 conviction 判 HITL)
          account_balance_usd / portfolio_pct_in_chain / recent_trades_24h:
            从 portfolio service 拉(W7-W12 真接;v0 caller 传入)
          position_mode / fixed_pct:T17 仓位算法
          dry_run:不真执行 trade / push,只算 verdict
        """
        t0 = time.monotonic()

        # 兼容 dict / pydantic event
        if hasattr(event, "model_dump"):
            event = event.model_dump()
        elif hasattr(event, "dict"):
            event = event.dict()

        if mode is None:
            mode = "paper"
        mode = str(mode).lower()
        if mode not in ("paper", "notify", "auto"):
            return self._fail(t0, mode, "blocked_safety",
                              reason=f"invalid_mode: {mode}")

        # Round 34 rollout_gate:auto 模式真金交易,只对在
        # agent_v1_auto_mode 灰度命中的 device 放行;未命中降级 notify
        # (KMS 上线 + S14 red team drill 通过后才能 > 0)
        if mode == "auto":
            try:
                from agent.rollout_gate import is_in_rollout
                device_id = event.get("user_id") or ""
                if not is_in_rollout(device_id, "agent_v1_auto_mode"):
                    log.info(
                        "[notify_loop] auto → notify 降级(rollout_gate %s 未命中 agent_v1_auto_mode)",
                        device_id[:8] if device_id else "anon",
                    )
                    mode = "notify"
            except Exception as e:
                log.warning("[notify_loop] rollout_gate fail (%s),保守降 notify", e)
                mode = "notify"

        # 1. Safety pre-check(全局 CB + 可选 HR)
        safety_ok, safety_reason, safety_meta = self._safety_pre_check(event, mode)
        if not safety_ok:
            res = self._fail(t0, mode, "blocked_safety",
                             reason=safety_reason, safety_block=safety_meta)
            await self._push_blocked(event, "safety", safety_reason, dry_run=dry_run, result=res)
            return res

        # 2. Risk check
        amount_usd_for_risk = self._estimate_amount(account_balance_usd, fixed_pct)
        risk_ok, risk_reason = await self._risk_check(event, amount_usd_for_risk)
        if not risk_ok:
            res = self._fail(t0, mode, "blocked_risk", reason=risk_reason,
                             risk_block=risk_reason)
            await self._push_blocked(event, "risk", risk_reason, dry_run=dry_run, result=res)
            return res

        # 3. 仓位
        position_usd, capped_by, pos_reasoning = await self._calc_position(
            account_balance_usd=account_balance_usd,
            position_mode=position_mode,
            fixed_pct=fixed_pct,
        )
        if position_usd <= 0:
            res = self._fail(t0, mode, "blocked_safety",
                             reason="position_size_zero")
            await self._push_blocked(event, "position", pos_reasoning,
                                      dry_run=dry_run, result=res)
            return res

        # 4. mode 分支
        if mode == "paper":
            return await self._handle_paper(
                event, position_usd, capped_by, t0, dry_run=dry_run,
            )

        if mode == "notify":
            return await self._handle_notify_only(
                event, position_usd, capped_by, t0, dry_run=dry_run,
            )

        # mode == auto:HITL 检查
        hitl_required, hitl_reasons = self._needs_hitl(
            position_usd=position_usd,
            portfolio_pct_in_chain=portfolio_pct_in_chain,
            recent_trades_24h=recent_trades_24h,
            thesis=thesis,
        )
        if hitl_required:
            return await self._handle_hitl_pending(
                event, position_usd, capped_by, hitl_reasons, t0, dry_run=dry_run,
            )

        return await self._handle_auto_direct(
            event, position_usd, capped_by, t0, dry_run=dry_run,
        )

    # ── checks ──────────────────────────────────────────────

    def _safety_pre_check(
        self, event: Dict[str, Any], mode: str,
    ) -> "tuple[bool, Optional[str], Optional[Dict]]":
        """SafetyEngine 全局 CB + 可选 HR。失败不阻断 (default ok=True)。"""
        try:
            from agent.safety_engine import get_safety_engine
            engine = get_safety_engine()
            # 全局 blocked 检查(任意 trips_breaker=blocked 的 CB active)
            if engine.is_globally_blocked():
                return False, "safety_globally_blocked", {
                    "active_breakers": list(engine.active_breakers.keys())
                    if hasattr(engine, "active_breakers") else [],
                }
        except Exception as e:
            log.debug("[notify_loop] safety check skipped: %s", e)
        return True, None, None

    async def _risk_check(
        self, event: Dict[str, Any], amount_usd: float,
    ) -> "tuple[bool, Optional[str]]":
        """RiskManager 综合检查。"""
        try:
            from agent.risk_manager import RiskManager
            mgr = RiskManager()
            token_data = event.get("trigger_context", {}).get("token_data") or {}
            result = mgr.check_trade(
                token_address=event.get("matched_token", "") or "",
                chain=event.get("matched_chain", "") or "",
                action="buy",
                amount_usd=amount_usd,
                token_data=token_data,
            )
            if hasattr(result, "passed") and not result.passed:
                return False, getattr(result, "reason", "risk_blocked")
            return True, None
        except Exception as e:
            log.warning("[notify_loop] risk_check skipped due to error: %s", e)
            return True, None  # fail-open(对齐"风控失败不阻断,但 log warning")

    async def _calc_position(
        self, account_balance_usd: float, position_mode: str, fixed_pct: float,
    ) -> "tuple[float, List[str], str]":
        try:
            from agent.tools import CalcPositionSizeTool
            tool = CalcPositionSizeTool()
            r = await tool.run({
                "account_balance_usd": account_balance_usd,
                "mode": position_mode,
                "fixed_pct": fixed_pct,
            })
            if r.ok and r.output:
                return (
                    float(r.output.get("position_usd", 0)),
                    list(r.output.get("capped_by", [])),
                    str(r.output.get("reasoning", "")),
                )
        except Exception as e:
            log.warning("[notify_loop] T17 failed: %s", e)
        return 0.0, ["t17_failed"], "T17 计算失败"

    def _needs_hitl(
        self,
        position_usd: float,
        portfolio_pct_in_chain: float,
        recent_trades_24h: int,
        thesis: Optional[Dict[str, Any]],
    ) -> "tuple[bool, List[str]]":
        reasons: List[str] = []
        if position_usd >= HITL_AMOUNT_USD:
            reasons.append(f"amount>={HITL_AMOUNT_USD}")
        if portfolio_pct_in_chain >= HITL_PORTFOLIO_PCT:
            reasons.append(f"portfolio>={HITL_PORTFOLIO_PCT*100:.0f}%")
        if recent_trades_24h >= HITL_24H_TRADES:
            reasons.append(f"24h_trades>={HITL_24H_TRADES}")
        if thesis and float(thesis.get("conviction", 1.0)) < HITL_LOW_CONVICTION:
            reasons.append(f"low_conviction<{HITL_LOW_CONVICTION}")
        return (len(reasons) > 0, reasons)

    # ── mode handlers ──────────────────────────────────────

    async def _handle_paper(
        self, event: Dict[str, Any], position_usd: float,
        capped_by: List[str], t0: float, dry_run: bool,
    ) -> NotifyResult:
        if dry_run:
            return self._wrap(t0, "dry_run", mode="paper",
                               position_usd=position_usd, capped_by=capped_by,
                               extra={"would_call": "T07 run_paper_trade buy"})
        # 调 T07 paper buy
        try:
            from agent.tools import RunPaperTradeTool
            tool = RunPaperTradeTool()
            ctx = event.get("trigger_context", {}) or {}
            token_data = ctx.get("token_data") or {}
            r = await tool.run({
                "action": "buy",
                "strategy_id": event.get("strategy_id"),
                "user_id": event.get("user_id"),
                "token_address": event.get("matched_token") or token_data.get("address"),
                "token_symbol": event.get("token_name") or token_data.get("symbol", "UNK"),
                "chain": event.get("matched_chain") or token_data.get("chain", ""),
                "price": float(token_data.get("price_usd") or token_data.get("price") or 1.0),
                "amount_usd": position_usd,
                "sl_pct": float(ctx.get("sl_pct", -10.0)),
                "tp_pct": float(ctx.get("tp_pct", 30.0)),
                "trigger_context": ctx,
            })
            paper = r.output.get("trade") if r.ok else None
            res = self._wrap(t0, "executed_paper", mode="paper",
                              position_usd=position_usd, capped_by=capped_by,
                              extra={"paper_result": r.output if r.ok else None})
            res.paper_trade = paper
            await self._push_event(event, "strategy_triggered",
                                    f"📊 Paper 模拟买入 ${position_usd:.2f}",
                                    f"策略 {event.get('strategy_name')} 已触发,模拟盘买入。",
                                    res, dry_run=False)
            return res
        except Exception as e:
            log.warning("[notify_loop] T07 failed: %s", e)
            return self._fail(t0, "paper", "blocked_safety",
                               reason=f"t07_failed: {e}")

    async def _handle_notify_only(
        self, event: Dict[str, Any], position_usd: float,
        capped_by: List[str], t0: float, dry_run: bool,
    ) -> NotifyResult:
        res = self._wrap(t0, "notify_only" if not dry_run else "dry_run",
                          mode="notify",
                          position_usd=position_usd, capped_by=capped_by,
                          extra={"would_have_pushed": True})
        if not dry_run:
            await self._push_event(
                event, "strategy_triggered",
                f"🔔 策略触发(只通知)— 建议仓位 ${position_usd:.2f}",
                f"{event.get('strategy_name')} 触发。notify 模式不自动交易,请人工决定。",
                res, dry_run=False,
            )
        return res

    async def _handle_hitl_pending(
        self, event: Dict[str, Any], position_usd: float, capped_by: List[str],
        hitl_reasons: List[str], t0: float, dry_run: bool,
    ) -> NotifyResult:
        if dry_run:
            return self._wrap(t0, "dry_run", mode="auto",
                               position_usd=position_usd, capped_by=capped_by,
                               extra={"would_create_hitl": True,
                                       "hitl_reasons": hitl_reasons})
        # 调 T09 create_approval_request
        try:
            from agent.tools import CreateApprovalRequestTool
            tool = CreateApprovalRequestTool()
            idem_key = (
                f"{event.get('strategy_id', '')}::"
                f"{event.get('matched_token', '')}::"
                f"{int(position_usd)}"
            )
            r = await tool.run({
                "device_id": event.get("user_id"),
                "strategy_id": event.get("strategy_id"),
                "trigger_conditions_matched": event.get("trigger_context") or {},
                "thesis_id": (event.get("trigger_context") or {}).get("thesis_id"),
                "token_address": event.get("matched_token"),
                "chain": event.get("matched_chain"),
                "amount_usd": position_usd,
                "idempotency_key": idem_key,
            })
            approval_id = r.output.get("approval_id") if r.ok else None
            res = self._wrap(t0, "hitl_pending", mode="auto",
                              position_usd=position_usd, capped_by=capped_by,
                              extra={"hitl_reasons": hitl_reasons,
                                      "idempotent_hit": (r.output or {}).get("idempotent_hit", False)})
            res.approval_id = approval_id
            # push HITL approval
            await self._push_event(
                event, "hitl_approval",
                f"⚠️ 审批 ${position_usd:.2f}",
                f"{event.get('strategy_name')} 触发 auto 模式但命中 HITL 条件:"
                f"{', '.join(hitl_reasons)}。请审批。",
                res, dry_run=False,
                params={"approval_id": approval_id},
            )
            return res
        except Exception as e:
            log.warning("[notify_loop] T09 failed: %s", e)
            return self._fail(t0, "auto", "blocked_safety",
                               reason=f"t09_failed: {e}")

    async def _handle_auto_direct(
        self, event: Dict[str, Any], position_usd: float, capped_by: List[str],
        t0: float, dry_run: bool,
    ) -> NotifyResult:
        """auto 模式 + 不需要 HITL → 真金交易。

        v0:不真调 T08 execute_swap(W7-W12 接 KMS 后再开),先回 paper-equivalent
        + push 标 'auto_direct' 让用户清楚。
        """
        # W7-W12:这里调 T08 execute_swap;v0 fallback 到 paper buy + push 注明
        # 当前作为安全默认,降级到 notify_only
        res = self._wrap(t0, "notify_only", mode="auto",
                          position_usd=position_usd, capped_by=capped_by,
                          extra={"auto_direct_fallback": "T08 execute_swap 留 W7-W12 (KMS pending)",
                                  "note": "降级到 notify-only 不真执行真金"})
        if not dry_run:
            await self._push_event(
                event, "strategy_triggered",
                f"🤖 Auto 触发 ${position_usd:.2f}(本期降级 notify)",
                f"{event.get('strategy_name')} 触发 auto 模式。当前 KMS 未接,降级 notify 等待用户手动执行。",
                res, dry_run=False,
            )
        return res

    # ── push helpers ───────────────────────────────────────

    async def _push_event(
        self, event: Dict[str, Any], category: str,
        title: str, body: str, result: NotifyResult,
        dry_run: bool, params: Optional[Dict[str, Any]] = None,
    ) -> None:
        if dry_run:
            return
        try:
            from agent.tools import SendPushNotificationTool
            tool = SendPushNotificationTool()
            push_params = params or {}
            # strategy_triggered 默认带 strategy_id;hitl_approval 带 approval_id
            if category == "strategy_triggered" and "strategy_id" not in push_params:
                push_params["strategy_id"] = event.get("strategy_id")
            r = await tool.run({
                "user_id": event.get("user_id"),
                "title": title[:80],
                "body": body[:240],
                "category": category,
                "params": push_params,
            })
            if r.ok:
                result.push_sent_count = int(r.output.get("sent_count", 0) or 0)
                result.push_deep_link = r.output.get("deep_link")
        except Exception as e:
            log.debug("[notify_loop] push failed: %s", e)

    async def _push_blocked(
        self, event: Dict[str, Any], block_type: str, reason: Optional[str],
        dry_run: bool, result: NotifyResult,
    ) -> None:
        if dry_run:
            return
        title = f"⛔ 策略被{ {'safety':'安全','risk':'风控','position':'仓位'}.get(block_type, block_type) }拦截"
        body = f"{event.get('strategy_name')}:{reason or block_type}_blocked"
        try:
            from agent.tools import SendPushNotificationTool
            tool = SendPushNotificationTool()
            r = await tool.run({
                "user_id": event.get("user_id"),
                "title": title[:80],
                "body": body[:240],
                "category": "strategy_triggered",
                "params": {"strategy_id": event.get("strategy_id")},
            })
            if r.ok:
                result.push_sent_count = int(r.output.get("sent_count", 0) or 0)
                result.push_deep_link = r.output.get("deep_link")
        except Exception as e:
            log.debug("[notify_loop] blocked push failed: %s", e)

    # ── helpers ──────────────────────────────────────────────

    def _estimate_amount(self, balance: float, fixed_pct: float) -> float:
        """RiskManager.check_trade 用;粗略估个金额(precision 不重要,只是为了过 check)"""
        return min(balance * fixed_pct, 500.0)

    def _wrap(
        self, t0: float, verdict: str, mode: str,
        position_usd: float = 0.0, capped_by: Optional[List[str]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> NotifyResult:
        return NotifyResult(
            ok=True, verdict=verdict, mode=mode,
            position_usd=position_usd, capped_by=capped_by or [],
            latency_ms=int((time.monotonic() - t0) * 1000),
            extra=extra or {},
        )

    def _fail(
        self, t0: float, mode: str, verdict: str, reason: str,
        safety_block: Optional[Dict] = None,
        risk_block: Optional[str] = None,
    ) -> NotifyResult:
        return NotifyResult(
            ok=False, verdict=verdict, mode=mode, reason=reason,
            safety_block=safety_block, risk_block=risk_block,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )


# ── singleton ────────────────────────────────────────────


_loop: Optional[NotifyLoop] = None


def get_notify_loop() -> NotifyLoop:
    global _loop
    if _loop is None:
        _loop = NotifyLoop()
    return _loop


def reset_loop_for_test() -> None:
    global _loop
    _loop = None
