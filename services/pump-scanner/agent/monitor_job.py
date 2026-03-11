"""
监控任务 — 30s 轮询评估

APScheduler 定时任务，每 30 秒执行一次：
1. 从数据库加载最新数据快照
2. 构建 DataEvent
3. 调用 Evaluator 评估所有活跃策略
4. 对触发的策略调用 ActionDispatcher

Python 3.9 兼容。
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from database import get_db
from agent.schemas import DataEvent, StrategyTriggeredEvent
from agent.evaluator import StrategyEvaluator
from agent.strategy_manager import StrategyManager
from agent.action_dispatcher import ActionDispatcher
from agent.event_bus import get_event_bus

log = logging.getLogger(__name__)

# 全局实例
_evaluator = StrategyEvaluator()
_strategy_mgr = StrategyManager()
_dispatcher = ActionDispatcher()


async def run_agent_monitor():
    """
    Agent 监控主任务（每 30s 执行一次）

    流程：
    1. 加载各数据源最新快照
    2. 对每个数据源构建事件
    3. 评估匹配的策略
    4. 分发触发动作
    """
    try:
        log.debug("Agent monitor cycle start")
        total_triggered = 0

        # 1. 处理内盘数据（pump_tokens）
        pump_events = await _build_pump_events()
        total_triggered += await _process_events(pump_events, "pump_tokens")

        # 2. 处理热币数据（hot_coins）
        hot_events = await _build_hot_coin_events()
        total_triggered += await _process_events(hot_events, "hot_coins")

        # 3. 处理 KOL 信号（kol_signals）
        kol_events = await _build_kol_events()
        total_triggered += await _process_events(kol_events, "kol_signals")

        if total_triggered > 0:
            log.info(f"Agent monitor: {total_triggered} strategies triggered")

    except Exception as e:
        log.error(f"Agent monitor error: {e}")


async def _process_events(
    events: List[DataEvent],
    source: str,
) -> int:
    """处理一组事件，返回触发的策略数"""
    if not events:
        return 0

    # 加载关联此数据源的活跃策略
    strategies = _strategy_mgr.get_active_strategies(data_source=source)
    if not strategies:
        return 0

    triggered_count = 0

    for event in events:
        triggered = _evaluator.evaluate(event, strategies)

        for trigger_event in triggered:
            # 检查每日限额
            if not _strategy_mgr.check_daily_limit(trigger_event.strategy_id):
                log.warning(
                    f"Strategy {trigger_event.strategy_id} daily limit reached"
                )
                continue

            # 获取策略动作配置
            strategy = _strategy_mgr.get_strategy(trigger_event.strategy_id)
            if not strategy:
                continue

            actions = strategy.get("actions", [])

            # 分发动作
            await _dispatcher.dispatch(trigger_event, actions)

            # 记录触发
            _strategy_mgr.record_trigger(trigger_event.strategy_id)

            # 发布事件
            await get_event_bus().publish("strategy.triggered", {
                "strategy_id": trigger_event.strategy_id,
                "user_id": trigger_event.user_id,
                "strategy_name": trigger_event.strategy_name,
                "token": trigger_event.matched_token,
                "chain": trigger_event.matched_chain,
            })

            triggered_count += 1

    return triggered_count


# ── 数据源事件构建 ────────────────────────────────────────────

async def _build_pump_events() -> List[DataEvent]:
    """从 pump_tokens 表构建数据事件"""
    try:
        # 获取最近更新的内盘代币
        result = (
            get_db()
            .table("pump_tokens")
            .select("mint, name, symbol, bc_progress, score, "
                    "smart_money_count, buyer_count, seller_count, "
                    "dev_sold_pct, buy_sell_ratio")
            .eq("complete", False)
            .eq("is_banned", False)
            .gte("bc_progress", 3.0)
            .order("updated_at", desc=True)
            .limit(100)
            .execute()
        )

        events = []  # type: List[DataEvent]
        for row in (result.data or []):
            events.append(DataEvent(
                source="pump_tokens",
                data=row,
                chain="solana",
                token_address=row.get("mint"),
                token_name=row.get("name") or row.get("symbol"),
            ))
        return events

    except Exception as e:
        log.error(f"Build pump events error: {e}")
        return []


async def _build_hot_coin_events() -> List[DataEvent]:
    """从 hot_coins 表构建数据事件"""
    try:
        result = (
            get_db()
            .table("hot_coins")
            .select("chain, address, name, symbol, score, "
                    "price_change_1h, price_change_24h, "
                    "market_cap_usd, liquidity_usd, volume_24h_usd, "
                    "holder_count")
            .gte("score", 40)
            .order("score", desc=True)
            .limit(200)
            .execute()
        )

        events = []  # type: List[DataEvent]
        for row in (result.data or []):
            events.append(DataEvent(
                source="hot_coins",
                data=row,
                chain=row.get("chain"),
                token_address=row.get("address"),
                token_name=row.get("name") or row.get("symbol"),
            ))
        return events

    except Exception as e:
        log.error(f"Build hot coin events error: {e}")
        return []


async def _build_kol_events() -> List[DataEvent]:
    """从 kol_signals 表构建数据事件"""
    try:
        # 获取最近 24h 的活跃信号
        since = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        result = (
            get_db()
            .table("kol_signals")
            .select("token_address, chain, ticker, signal_strength, "
                    "kol_count, mega_count, large_count, "
                    "avg_sentiment, bullish_ratio, total_reach")
            .eq("is_active", True)
            .gte("detected_at", since)
            .order("signal_strength", desc=True)
            .limit(50)
            .execute()
        )

        events = []  # type: List[DataEvent]
        for row in (result.data or []):
            # 构建 kol_mentions 兼容字段
            data = dict(row)
            data["mention_count_2h"] = row.get("kol_count", 0)
            data["mention_count_24h"] = row.get("kol_count", 0)
            data["mega_mention"] = 1 if row.get("mega_count", 0) > 0 else 0

            events.append(DataEvent(
                source="kol_signals",
                data=data,
                chain=row.get("chain"),
                token_address=row.get("token_address"),
                token_name=row.get("ticker"),
            ))
        return events

    except Exception as e:
        log.error(f"Build KOL events error: {e}")
        return []
