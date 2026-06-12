"""
动作分发器 — Alert 写入 + Push 通知

接收 StrategyTriggeredEvent，根据策略中的 actions 配置：
1. 生成告警消息（模板渲染）
2. 写入 agent_alerts 表
3. 发送推送通知（Phase 2）
4. 执行交易（Phase 3）

Python 3.9 兼容。
"""
import re
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from database import get_db
from agent.schemas import StrategyTriggeredEvent
from agent.risk_manager import get_risk_manager
from agent.memory import get_memory_manager

log = logging.getLogger(__name__)


class ActionDispatcher:
    """动作分发器"""

    async def dispatch(
        self,
        event: StrategyTriggeredEvent,
        actions: List[Dict[str, Any]],
    ):
        """
        分发策略触发后的动作

        Args:
            event: 策略触发事件
            actions: 动作配置列表
        """
        for action in actions:
            try:
                action_type = action.get("type", "alert")

                if action_type == "alert":
                    await self._handle_alert(event, action)
                elif action_type == "push":
                    await self._handle_push(event, action)
                elif action_type == "webhook":
                    await self._handle_webhook(event, action)
                elif action_type in ("buy", "sell"):
                    await self._handle_trade(event, action)
                else:
                    log.warning(f"Unknown action type: {action_type}")

            except Exception as e:
                log.error(
                    f"Action dispatch error ({action.get('type')}): {e}"
                )

    async def _handle_alert(
        self,
        event: StrategyTriggeredEvent,
        action: Dict[str, Any],
    ):
        """处理 alert 动作 → 写入 agent_alerts"""
        # 渲染消息模板
        template = action.get(
            "message_template",
            "{{token_name}} 触发策略 {{strategy_name}}"
        )
        message = self._render_template(template, event)

        severity = action.get("severity", "info")
        title = f"策略触发: {event.strategy_name}"

        alert_row = {
            "user_id": event.user_id,
            "strategy_id": event.strategy_id,
            "trigger_context": event.trigger_context,
            "token_address": event.matched_token,
            "token_name": event.token_name,
            "chain": event.matched_chain,
            "title": title,
            "message": message,
            "severity": severity,
            "is_read": False,
            "is_pushed": False,
        }

        try:
            result = get_db().table("agent_alerts").insert(alert_row).execute()
            if result.data:
                alert_id = result.data[0].get("id", "")
                log.info(
                    f"Alert created: {alert_id} for strategy {event.strategy_id}"
                )

                # 发布告警事件到事件总线
                from agent.event_bus import get_event_bus
                await get_event_bus().publish("alert.created", {
                    "alert_id": alert_id,
                    "user_id": event.user_id,
                    "strategy_id": event.strategy_id,
                    "title": title,
                    "message": message,
                    "severity": severity,
                })

                # 同步推送通知到用户设备
                try:
                    from agent.push_service import send_push, build_deep_link
                    push_data = {
                        "type": "alert",
                        "alert_id": str(alert_id),
                        "severity": severity,
                        "token_address": event.matched_token or "",
                        "chain": event.matched_chain or "",
                        "category": "token_alert",
                        "deep_link": build_deep_link(
                            "token_alert",
                            chain=event.matched_chain,
                            address=event.matched_token,
                        ),
                    }
                    await send_push(
                        user_id=event.user_id,
                        title=title,
                        body=message,
                        data=push_data,
                    )
                    # 标记已推送
                    get_db().table("agent_alerts").update(
                        {"is_pushed": True}
                    ).eq("id", alert_id).execute()
                except Exception as push_err:
                    log.warning("Push after alert failed: %s", push_err)

        except Exception as e:
            log.error(f"Failed to create alert: {e}")

    async def _handle_push(
        self,
        event: StrategyTriggeredEvent,
        action: Dict[str, Any],
    ):
        """
        处理 push 动作 → FCM/APNs 推送

        通过 Firebase Admin SDK 发送推送通知到用户设备。
        缺少 Firebase 配置时 graceful fallback。
        """
        template = action.get(
            "message_template",
            "{{token_name}} 触发策略 {{strategy_name}}"
        )
        message = self._render_template(template, event)
        title = f"策略触发: {event.strategy_name}"

        # 构建推送附加数据（用于 Flutter 端路由跳转）
        from agent.push_service import build_deep_link
        push_data = {
            "type": "strategy_trigger",
            "strategy_id": event.strategy_id or "",
            "token_address": event.matched_token or "",
            "chain": event.matched_chain or "",
            "category": "strategy_triggered",
            "deep_link": build_deep_link(
                "strategy_triggered",
                strategy_id=event.strategy_id,
            ),
        }

        from agent.push_service import send_push
        sent = await send_push(
            user_id=event.user_id,
            title=title,
            body=message,
            data=push_data,
        )

        if sent > 0:
            log.info(
                "Push sent to %d devices for user %s: %s",
                sent, event.user_id, title,
            )
        else:
            log.debug(
                "Push not delivered (no devices or Firebase disabled): "
                "user=%s title=%s",
                event.user_id, title,
            )

    async def _handle_webhook(
        self,
        event: StrategyTriggeredEvent,
        action: Dict[str, Any],
    ):
        """
        处理 webhook 动作 → HTTP POST

        Phase 2 实现，当前仅记录日志
        """
        url = action.get("webhook_url", "")
        log.info(f"[Webhook TODO] POST {url} for strategy {event.strategy_id}")

        # Phase 2: HTTP POST
        # async with aiohttp.ClientSession() as session:
        #     await session.post(url, json=payload)

    async def _handle_trade(
        self,
        event: StrategyTriggeredEvent,
        action: Dict[str, Any],
    ):
        """
        处理 buy/sell 动作 → 检查 paper/live 模式 → 风控检查 → 执行

        PRD-008: paper 模式走 PaperEngine（模拟交易），live 模式走 OKX DEX。
        """
        action_type = action.get("type", "buy")
        amount_usd = action.get("amount_usd", 0)
        token_address = event.matched_token or ""
        chain = event.matched_chain or ""

        # ── PRD-008: Paper 模式分流 ──────────────────────────
        strategy_mode = await self._get_strategy_mode(event.strategy_id)
        if strategy_mode == "paper" and action_type == "buy":
            await self._handle_paper_trade(event, action)
            return

        # ── PRD-005: 规则合规检查（warn only，不 block）──
        memory = get_memory_manager()
        _matched_rules: list = []
        try:
            trade_ctx = {
                "chain": chain,
                "trigger_source": (event.trigger_context or {}).get("source", ""),
                "rsi": (event.trigger_context or {}).get("rsi", 50),
                "regime": (event.trigger_context or {}).get("market_regime", "unknown"),
                "mcap_bucket": (event.trigger_context or {}).get("mcap_bucket", ""),
                "hold_hours": 0,
            }
            violations = memory.check_rules(trade_ctx)
            for v in violations:
                if v.get("action", "").startswith("skip") and action_type == "buy":
                    log.warning(
                        "[Memory] Rule violation (warn): %s -> %s (token=%s)",
                        v["condition"], v["action"], event.token_name,
                    )
                    memory.add_event({
                        "type": "rule_violation",
                        "rule": v["condition"],
                        "action": v["action"],
                        "token": event.token_name,
                        "summary": f"违反规则: {v['condition']} -> {v['action']}",
                    })
                    _matched_rules.append(v)
        except Exception as e:
            log.debug("Rule compliance check error: %s", e)

        # ── 风控检查 ──
        risk_mgr = get_risk_manager()
        token_data = event.trigger_context or {}
        risk_result = risk_mgr.check_trade(
            token_address=token_address,
            chain=chain,
            action=action_type,
            amount_usd=amount_usd,
            token_data=token_data,
        )

        if not risk_result.passed:
            log.warning(
                f"Trade BLOCKED by risk manager: {risk_result.reason} "
                f"(token={event.token_name}, action={action_type})"
            )
            # 写入风控告警
            try:
                alert_row = {
                    "user_id": event.user_id,
                    "strategy_id": event.strategy_id,
                    "trigger_context": {
                        "type": "risk_blocked",
                        "reason": risk_result.reason,
                        "risk_level": risk_result.risk_level,
                        "action_type": action_type,
                        "amount_usd": amount_usd,
                    },
                    "token_address": token_address,
                    "token_name": event.token_name,
                    "chain": chain,
                    "title": f"Risk Blocked: {event.strategy_name}",
                    "message": f"Trade blocked: {risk_result.reason}",
                    "severity": "warning",
                    "is_read": False,
                    "is_pushed": False,
                }
                get_db().table("agent_alerts").insert(alert_row).execute()
            except Exception as e:
                log.error(f"Failed to create risk block alert: {e}")
            return

        # 风控通过 — 执行真实交易
        log.info(
            f"Trade APPROVED: {action_type} ${amount_usd} of "
            f"{event.token_name} on {chain} (risk: {risk_result.risk_level})"
        )

        # OKX DEX v6 Swap 执行
        from agent.trade_executor import get_trade_executor
        executor = get_trade_executor()
        slippage = action.get("max_slippage_pct", 1.0)

        # R47 P6 — HITL 自动化分层(只对 live 模式生效;paper 已在前面 _handle_paper_trade 路径分流)
        # < $500 → auto 直接发
        # ≥ $500 → semi 写 pending_semi_auto_trades + 推送 + 10s 倒计时撤销
        if strategy_mode == "live":
            try:
                from agent.hitl_router import decide_automation_level
                level, cancel_sec = decide_automation_level(
                    amount_usd=amount_usd, side=action_type,
                )
            except Exception as e:
                log.warning("[hitl] decide_automation_level fail, fallback auto: %s", e)
                level, cancel_sec = ("auto", 0)

            if level == "semi":
                # 写 pending 表 + 推送(本期推送 wire 留 P9,后端先入表)
                try:
                    from agent import semi_auto_service
                    pending_id = semi_auto_service.create_pending(
                        user_id=event.user_id,
                        strategy_id=event.strategy_id,
                        chain=chain,
                        token_address=token_address,
                        token_symbol=event.token_name,
                        action=action_type,
                        amount_usd=amount_usd,
                        slippage_pct=slippage,
                        trigger_context=event.trigger_context or {},
                        cancel_window_sec=cancel_sec,
                    )
                    log.info(
                        "[hitl] R47 P6 SEMI-AUTO 入队: pending=%s amount=$%.2f window=%ds — "
                        "cron 1s 后开始扫,过 %ds 自动执行(用户可调 /trades/pending/%s/cancel 撤销)",
                        (pending_id or "?")[:8], amount_usd, cancel_sec, cancel_sec,
                        (pending_id or "?")[:8],
                    )
                    # 写一条 alert 通知用户(复用现有 push 路径)
                    try:
                        get_db().table("agent_alerts").insert({
                            "user_id": event.user_id,
                            "strategy_id": event.strategy_id,
                            "title": f"💰 半自动交易({cancel_sec}s 撤销)",
                            "message": f"{action_type.upper()} ${amount_usd:.0f} {event.token_name} — "
                                       f"{cancel_sec} 秒后自动执行,可点击撤销",
                            "severity": "warning",
                            "metadata": {
                                "kind": "semi_auto_pending",
                                "pending_id": pending_id,
                                "amount_usd": amount_usd,
                                "cancel_window_sec": cancel_sec,
                            },
                        }).execute()
                    except Exception as e:
                        log.debug("[hitl] alert insert fail: %s", e)
                    return  # 不直接发,等 cron
                except Exception as e:
                    log.error("[hitl] R47 P6 semi pending create fail, fallback auto: %s", e)
                    # fallback: 直接发(不阻塞业务,但 audit 留痕)

        # R59 P0:idempotency key — 同一 strategy 同一 signal 同一 side+金额
        # 任何 retry 都算同一笔交易,防 trade_executor → dex_router 重发 tx。
        # 用 cents(int) 防止 float 精度问题(amount_usd=100.0 vs 100.00 同 key)。
        request_id = (
            f"{event.strategy_id or 'no_strategy'}"
            f"-{event.id or event.token_address or 'no_event'}"
            f"-{action_type}"
            f"-{int(round(amount_usd * 100))}"
        )

        # auto 路径(原 R47 P5 修复):透传 user_id + safety_ctx + request_id
        result = await executor.execute_trade(
            chain=chain,
            token_address=token_address,
            action=action_type,
            amount_usd=amount_usd,
            slippage_pct=slippage,
            user_id=event.user_id,
            safety_ctx={
                "user_id": event.user_id,
                "strategy_id": event.strategy_id,
                "mode": strategy_mode,
            },
            request_id=request_id,    # R59 P0
        )

        if result.success:
            risk_mgr.record_trade(
                token_address=token_address, chain=chain,
                action=action_type, amount_usd=amount_usd,
                price=result.price, pnl_usd=0.0,
            )
            # PRD-005: 写入短期记忆 + 交易计数
            try:
                memory.add_event({
                    "type": "trade",
                    "action": action_type,
                    "token": event.token_name,
                    "chain": chain,
                    "amount_usd": amount_usd,
                    "price": result.price,
                    "summary": f"{'买入' if action_type == 'buy' else '卖出'} {event.token_name} ${amount_usd:.0f} @{result.price:.6f}",
                })
                memory.reflection.increment_trade_count()
                # 存储匹配的规则 ID，用于交易闭环后回填 comply/violate
                if _matched_rules:
                    try:
                        get_db().table("agent_executions").update({
                            "trigger_context": {
                                **(event.trigger_context or {}),
                                "_matched_rules": [
                                    {"rule_id": r["rule_id"], "condition": r["condition"], "action": r["action"]}
                                    for r in _matched_rules
                                ],
                            }
                        }).eq("token_address", token_address).eq("status", "confirmed").eq("action", action_type).execute()
                    except Exception:
                        pass
            except Exception as e:
                log.debug("Memory write after trade error: %s", e)
            # 写入成功告警
            try:
                get_db().table("agent_alerts").insert({
                    "user_id": event.user_id,
                    "strategy_id": event.strategy_id,
                    "trigger_context": {
                        "type": "trade_executed",
                        "action": action_type,
                        "amount_usd": amount_usd,
                        "tx_hash": result.tx_hash,
                        "price": result.price,
                        "to_amount": result.to_amount,
                    },
                    "token_address": token_address,
                    "token_name": event.token_name,
                    "chain": chain,
                    "title": f"Trade Executed: {action_type.upper()} {event.token_name}",
                    "message": f"{action_type.upper()} ${amount_usd} → tx: {result.tx_hash[:16]}...",
                    "severity": "info",
                    "is_read": False,
                    "is_pushed": False,
                }).execute()
            except Exception as e:
                log.error(f"Failed to create trade alert: {e}")
        else:
            log.error(
                f"Trade FAILED: {action_type} {event.token_name} — {result.error}"
            )
            try:
                get_db().table("agent_alerts").insert({
                    "user_id": event.user_id,
                    "strategy_id": event.strategy_id,
                    "trigger_context": {
                        "type": "trade_failed",
                        "action": action_type,
                        "amount_usd": amount_usd,
                        "error": result.error,
                    },
                    "token_address": token_address,
                    "token_name": event.token_name,
                    "chain": chain,
                    "title": f"Trade Failed: {action_type.upper()} {event.token_name}",
                    "message": f"Error: {result.error[:100]}",
                    "severity": "warning",
                    "is_read": False,
                    "is_pushed": False,
                }).execute()
            except Exception as e:
                log.error(f"Failed to create trade fail alert: {e}")

    # ── PRD-008: Paper mode helpers ─────────────────────────────

    async def _get_strategy_mode(self, strategy_id: Optional[str]) -> str:
        """获取策略的 mode (paper/live)，默认 live"""
        if not strategy_id:
            return "live"
        try:
            result = (
                get_db()
                .table("agent_strategies")
                .select("mode")
                .eq("id", strategy_id)
                .execute()
            )
            if result.data:
                return result.data[0].get("mode", "live")
        except Exception as e:
            log.debug("_get_strategy_mode error: %s", e)
        return "live"

    async def _handle_paper_trade(
        self,
        event: StrategyTriggeredEvent,
        action: Dict[str, Any],
    ):
        """
        PRD-008: Paper 模式 — 模拟买入（不调 DEX）

        用 PriceFeed 实时价格 + 1.5% 滑点模拟。
        """
        from agent.paper_engine import get_paper_engine
        from price_feed import price_feed

        token_address = event.matched_token or ""
        chain = event.matched_chain or ""
        amount_usd = action.get("amount_usd", 0)

        # 获取实时价格
        current_price = price_feed.get_token_price(token_address)
        if current_price is None:
            # 尝试从 trigger_context 获取价格
            tc = event.trigger_context or {}
            current_price = tc.get("price_usd") or tc.get("price")
            if current_price is not None:
                current_price = float(current_price)

        if not current_price:
            log.warning(
                "Paper trade skipped: no price for %s (strategy=%s)",
                token_address, event.strategy_id,
            )
            return

        # 读取风控参数
        risk_params = {}
        try:
            strat = (
                get_db()
                .table("agent_strategies")
                .select("filters")
                .eq("id", event.strategy_id)
                .execute()
            )
            if strat.data:
                risk_params = (strat.data[0].get("filters") or {}).get(
                    "risk_params", {}
                )
        except Exception:
            pass

        # R71: 归一化 sl/tp 单位。部分策略 risk_params 存的是 ratio(0.1=10%),
        # 原样透传会让 paper 仓 sl_pct<1 被跳过卡死、live 仓 0.1% 即时止损。
        def _norm_pct(v, default):
            try:
                f = float(v)
            except (TypeError, ValueError):
                return float(default)
            if f <= 0:
                return float(default)
            return round(f * 100, 4) if f < 1 else f
        sl_pct = _norm_pct(risk_params.get("stop_loss_pct"), 25)
        tp_pct = _norm_pct(risk_params.get("take_profit_pct"), 100)

        engine = get_paper_engine()
        await engine.open_position(
            strategy_id=event.strategy_id or "",
            user_id=event.user_id or "",
            token_address=token_address,
            token_symbol=event.token_name or "",
            chain=chain,
            price=current_price,
            amount_usd=amount_usd,
            sl_pct=sl_pct,
            tp_pct=tp_pct,
            trigger_context=event.trigger_context,
        )

        # 写入告警通知
        try:
            get_db().table("agent_alerts").insert({
                "user_id": event.user_id,
                "strategy_id": event.strategy_id,
                "token_address": token_address,
                "token_name": event.token_name,
                "chain": chain,
                "title": f"Paper Trade: BUY {event.token_name}",
                "message": f"模拟买入 ${amount_usd} @{current_price:.8f} (含 1.5% 滑点)",
                "severity": "info",
                "is_read": False,
                "is_pushed": False,
                "trigger_context": {
                    "type": "paper_trade",
                    "action": "buy",
                    "amount_usd": amount_usd,
                    "price": current_price,
                },
            }).execute()
        except Exception as e:
            log.error("Paper trade alert error: %s", e)

    def _render_template(
        self,
        template: str,
        event: StrategyTriggeredEvent,
    ) -> str:
        """
        渲染消息模板

        支持 {{变量名}} 替换，变量来自事件上下文
        """
        context = {
            "strategy_name": event.strategy_name,
            "token_name": event.token_name or "Unknown",
            "token_address": event.matched_token or "",
            "chain": event.matched_chain or "",
            "timestamp": event.timestamp.strftime("%Y-%m-%d %H:%M UTC"),
        }

        # 从 trigger_context 中提取常用字段
        tc = event.trigger_context or {}
        for key in [
            # 通用
            "score", "market_cap_usd", "bc_progress",
            # 价格（OKX: price_usd / 旧: price）
            "price_usd", "price",
            # 涨跌幅
            "price_change_5m", "price_change_1h",
            "price_change_4h", "price_change_24h",
            # 交易量
            "volume_5m_usd", "volume_1h_usd",
            "volume_4h_usd", "volume_24h_usd",
            # 持有者 / 流动性
            "holder_count", "liquidity_usd",
            # 子评分
            "score_m", "score_q", "score_p",
            # 推荐等级 / 流通量
            "recommendation", "circ_supply",
            # 买卖笔数
            "buys_1h", "sells_1h", "buys_24h", "sells_24h",
            # 买卖税
            "buy_tax_rate", "sell_tax_rate",
            # KOL 相关
            "mention_count", "mention_count_2h", "mention_count_24h",
            "signal_strength", "kol_count", "total_reach",
            "avg_sentiment", "bullish_ratio", "mega_mention",
            # 内盘
            "buy_sell_ratio", "buyer_count", "dev_sold_pct",
            "smart_money_count",
        ]:
            if key in tc:
                context[key] = str(tc[key])

        # 兼容别名：price 和 price_usd 互为 fallback
        if "price" not in context and "price_usd" in context:
            context["price"] = context["price_usd"]
        elif "price_usd" not in context and "price" in context:
            context["price_usd"] = context["price"]

        # 替换 {{xxx}}
        def replacer(match: re.Match) -> str:
            var_name = match.group(1).strip()
            return context.get(var_name, match.group(0))

        return re.sub(r'\{\{(\s*\w+\s*)\}\}', replacer, template)


# ── 告警辅助函数 ──────────────────────────────────────────────

def get_user_alerts(
    user_id: str,
    limit: int = 50,
    unread_only: bool = False,
) -> List[Dict[str, Any]]:
    """获取用户告警列表"""
    try:
        query = (
            get_db()
            .table("agent_alerts")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if unread_only:
            query = query.eq("is_read", False)

        result = query.execute()
        return result.data or []
    except Exception as e:
        log.error(f"get_user_alerts error: {e}")
        return []


def mark_alert_read(alert_id: str, user_id: str = "") -> bool:
    """标记告警已读（需验证告警归属当前用户）"""
    try:
        query = get_db().table("agent_alerts").update(
            {"is_read": True}
        ).eq("id", alert_id)
        if user_id:
            query = query.eq("user_id", user_id)
        query.execute()
        return True
    except Exception as e:
        log.error(f"mark_alert_read error: {e}")
        return False


def get_unread_count(user_id: str) -> int:
    """获取未读告警数量"""
    try:
        result = (
            get_db()
            .table("agent_alerts")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .execute()
        )
        return result.count or 0
    except Exception as e:
        log.error(f"get_unread_count error: {e}")
        return 0
