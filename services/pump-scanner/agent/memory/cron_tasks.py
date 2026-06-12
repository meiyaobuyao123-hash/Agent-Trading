"""
PRD-005 定时任务 — 每日反思 + 风控事件价格回填

Python 3.9 兼容。
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from database import get_db

log = logging.getLogger(__name__)


async def run_daily_reflection():
    """
    每日记忆维护(只清理,不反思)。

    ⚠️ per-user 反思已迁移至 reflect_loop.run_per_user_cycle(按用户计费,R47 P9)。
    本函数过去会跨用户聚合 agent_executions 跑一次 run_reflection(不传 user_id)→
    平台白吞 LLM 成本 + 把所有用户的交易混在一起出规则写进共享 semantic 表。
    现在它只保留两件 reflect_loop 不做的事:清理过期 episodic + 废弃失效 semantic 规则。
    """
    from agent.memory import get_memory_manager

    mem = get_memory_manager()
    try:
        mem.reflection.reset_trade_count()
        mem.episodic.cleanup_expired()
        deprecated = mem.semantic.deprecate_stale()
        log.info(
            "[DailyMemoryMaintenance] cleanup done, %d stale rules deprecated",
            deprecated,
        )
    except Exception as e:
        log.error("[DailyMemoryMaintenance] Failed: %s", e)


def _check_promotion(mem, new_rules: list) -> None:
    """检查 episodic 规则是否可晋升为 semantic"""
    try:
        db = get_db()
        for rule in new_rules:
            condition = rule.get("condition", "")
            if not condition:
                continue

            # 查找含有相同 condition 的 episodic 记忆数量
            res = db.table("agent_memory").select("id, structured_data") \
                .eq("type", "episodic") \
                .eq("is_active", True) \
                .execute()

            appearances = 0
            for m in (res.data or []):
                sd = m.get("structured_data") or {}
                if isinstance(sd, dict) and sd.get("condition", "").upper() == condition.upper():
                    appearances += 1

            if appearances >= 3:
                mem.semantic.try_promote(
                    condition=condition,
                    appearances=appearances,
                    comply_win=0,
                    comply_lose=0,
                    violate_win=0,
                    violate_lose=0,
                    metadata=rule,
                )
    except Exception as e:
        log.debug("Promotion check error: %s", e)


def backfill_risk_events():
    """
    每 6h 回填 agent_risk_events 的后续价格

    数据源优先级：
    1. hot_coins 表（代币仍在榜）
    2. 标记 price=0, was_correct=True（代币归零/下架 = 正确不买）
    """
    db = get_db()

    try:
        # 找未回填的 risk_events（24h 价格为空，且创建时间 > 1h）
        cutoff_1h = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        cutoff_24h_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        cutoff_4h_ago = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()

        # 回填 1h 价格
        _backfill_window(db, "token_price_1h_later", cutoff_1h)
        # 回填 4h 价格
        _backfill_window(db, "token_price_4h_later", cutoff_4h_ago)
        # 回填 24h 价格 + was_correct
        _backfill_24h(db, cutoff_24h_ago)

    except Exception as e:
        log.error("[RiskBackfill] Failed: %s", e)


def _backfill_window(db, price_field: str, cutoff: str) -> int:
    """回填指定时间窗口的价格"""
    try:
        res = db.table("agent_risk_events").select("id, chain, token_address") \
            .is_(price_field, "null") \
            .lt("created_at", cutoff) \
            .limit(50).execute()

        filled = 0
        for event in (res.data or []):
            price = _get_token_price(db, event.get("chain", ""), event.get("token_address", ""))
            if price is not None:
                db.table("agent_risk_events").update({
                    price_field: price,
                }).eq("id", event["id"]).execute()
                filled += 1

        if filled:
            log.info("[RiskBackfill] %s: filled %d events", price_field, filled)
        return filled
    except Exception as e:
        log.debug("Backfill %s error: %s", price_field, e)
        return 0


def _backfill_24h(db, cutoff: str) -> int:
    """回填 24h 价格 + 计算 was_correct"""
    try:
        res = db.table("agent_risk_events").select(
            "id, chain, token_address, token_price_at_event, "
            "token_price_1h_later, token_price_4h_later"
        ) \
            .is_("token_price_24h_later", "null") \
            .lt("created_at", cutoff) \
            .limit(50).execute()

        filled = 0
        for event in (res.data or []):
            price = _get_token_price(db, event.get("chain", ""), event.get("token_address", ""))
            p_at = float(event.get("token_price_at_event") or 0)

            update: Dict = {}

            if price is not None:
                update["token_price_24h_later"] = price

                # 计算 min_price 和 max_drawdown
                prices = [p_at]
                for pf in ["token_price_1h_later", "token_price_4h_later"]:
                    pv = event.get(pf)
                    if pv is not None:
                        prices.append(float(pv))
                prices.append(price)
                prices = [p for p in prices if p > 0]

                if prices:
                    min_price = min(prices)
                    update["token_min_price_24h"] = min_price
                    if p_at > 0:
                        max_dd = (p_at - min_price) / p_at * 100
                        update["token_max_drawdown_24h"] = round(max_dd, 2)
                        # was_correct: 回撤 > 20% → 正确拦截
                        update["was_correct"] = max_dd > 20
                    else:
                        update["was_correct"] = True
            else:
                # 代币归零/下架 → 正确不买
                update["token_price_24h_later"] = 0
                update["token_min_price_24h"] = 0
                update["token_max_drawdown_24h"] = 100
                update["was_correct"] = True

            if update:
                db.table("agent_risk_events").update(update).eq("id", event["id"]).execute()
                filled += 1

        if filled:
            log.info("[RiskBackfill] 24h: filled %d events", filled)
        return filled
    except Exception as e:
        log.debug("Backfill 24h error: %s", e)
        return 0


def _get_token_price(db, chain: str, token_address: str) -> Optional[float]:
    """
    获取代币当前价格

    数据源优先级：
    1. hot_coins 表
    2. 返回 None（代币不可用）
    """
    if not token_address:
        return None

    try:
        # 从 hot_coins 查
        res = db.table("hot_coins").select("price_usd") \
            .eq("address", token_address).limit(1).execute()
        if res.data and res.data[0].get("price_usd"):
            return float(res.data[0]["price_usd"])
    except Exception:
        pass

    return None
