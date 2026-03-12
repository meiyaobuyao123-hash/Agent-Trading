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

        except Exception as e:
            log.error(f"Failed to create alert: {e}")

    async def _handle_push(
        self,
        event: StrategyTriggeredEvent,
        action: Dict[str, Any],
    ):
        """
        处理 push 动作 → FCM/APNs 推送

        Phase 2 实现，当前仅记录日志
        """
        template = action.get(
            "message_template",
            "{{token_name}} 触发策略 {{strategy_name}}"
        )
        message = self._render_template(template, event)
        log.info(f"[Push TODO] User {event.user_id}: {message}")

        # Phase 2: 集成 FCM/APNs
        # await push_notification(event.user_id, title, message)

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
        处理 buy/sell 动作 → OKX DEX 执行

        Phase 3 实现，当前仅记录日志
        """
        action_type = action.get("type", "buy")
        amount_usd = action.get("amount_usd", 0)
        log.info(
            f"[Trade TODO] {action_type} ${amount_usd} of "
            f"{event.token_name} on {event.matched_chain}"
        )

        # Phase 3: OKX DEX v6 API
        # from agent.trade_executor import execute_trade
        # await execute_trade(event, action)

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


def mark_alert_read(alert_id: str) -> bool:
    """标记告警已读"""
    try:
        get_db().table("agent_alerts").update(
            {"is_read": True}
        ).eq("id", alert_id).execute()
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
