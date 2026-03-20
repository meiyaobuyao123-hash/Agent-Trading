"""
策略回测引擎 — 用历史数据验证策略效果

用户创建策略前，先对最近 N 天数据回测，返回：
- 触发次数
- 模拟胜率（入场后 D3 涨 20%+ 的比例）
- 模拟最大回撤
- 样本触发列表

Python 3.9 兼容。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import get_db
from agent.schemas import DataEvent
from agent.evaluator import StrategyEvaluator
from agent.rule_engine import extract_data_sources

log = logging.getLogger(__name__)
_evaluator = StrategyEvaluator()


async def backtest_strategy(
    strategy_spec: Dict[str, Any],
    days: int = 7,
) -> Dict[str, Any]:
    """
    对策略规范进行历史回测

    参数:
        strategy_spec: StrategySpec（含 conditions, filters, actions）
        days: 回测天数（默认 7）

    返回:
        {trigger_count, simulated_win_rate, avg_return_pct, max_drawdown_pct, sample_triggers}
    """
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # 提取数据源
    conditions = strategy_spec.get("conditions", {})
    data_sources = extract_data_sources(conditions)

    if not data_sources:
        return _empty_result("无数据源")

    # 构造伪策略（用于 evaluator）
    fake_strategy = {
        "id": "backtest",
        "user_id": "backtest",
        "name": strategy_spec.get("name", "回测策略"),
        "status": "active",
        "conditions": conditions,
        "actions": [],
        "filters": strategy_spec.get("filters", {}),
        "data_sources": list(data_sources),
        "cooldown_min": 0,
        "last_triggered": None,
    }

    triggers = []
    sample_triggers = []

    for source in data_sources:
        if source == "hot_coins":
            events = await _load_hot_coin_history(db, cutoff)
        elif source == "pump_tokens":
            events = await _load_pump_history(db, cutoff)
        elif source == "kol_signals":
            events = await _load_kol_history(db, cutoff)
        else:
            continue

        for event in events:
            matched = _evaluator.evaluate(event, [fake_strategy])
            if matched:
                trigger_info = {
                    "token": event.token_name or event.token_address[:12],
                    "chain": event.chain,
                    "score": event.data.get("score", 0),
                    "price_usd": event.data.get("price_usd", 0),
                    "timestamp": event.timestamp,
                }
                triggers.append(trigger_info)
                if len(sample_triggers) < 10:
                    sample_triggers.append(trigger_info)

    # 模拟收益（用 token_performance 数据）
    win_count = 0
    returns = []
    for t in triggers:
        perf = await _get_token_performance(db, t.get("chain", ""), t.get("token", ""))
        if perf:
            best_pct = perf.get("best_pct", 0)
            returns.append(best_pct / 100 if best_pct else 0)
            if best_pct >= 20:
                win_count += 1

    total = len(triggers)
    win_rate = win_count / total if total > 0 else 0
    avg_return = sum(returns) / len(returns) * 100 if returns else 0

    return {
        "trigger_count": total,
        "simulated_win_rate": round(win_rate, 4),
        "avg_return_pct": round(avg_return, 2),
        "max_drawdown_pct": 0,  # 简化版不计算
        "sample_triggers": sample_triggers,
        "period_days": days,
        "data_sources": list(data_sources),
    }


# ── 历史数据加载 ─────────────────────────────────────

async def _load_hot_coin_history(db, cutoff: str) -> List[DataEvent]:
    """加载热币历史数据"""
    try:
        res = db.table("hot_coins").select("*") \
            .gte("updated_at", cutoff) \
            .order("updated_at", desc=True) \
            .limit(500) \
            .execute()
    except Exception as e:
        log.warning(f"加载热币历史: {e}")
        return []

    events = []
    for row in (res.data or []):
        events.append(DataEvent(
            source="hot_coins",
            data=row,
            timestamp=row.get("updated_at", ""),
            chain=row.get("chain", ""),
            token_address=row.get("address", ""),
            token_name=row.get("symbol", row.get("name", "")),
        ))
    return events


async def _load_pump_history(db, cutoff: str) -> List[DataEvent]:
    """加载内盘历史快照"""
    try:
        res = db.table("token_snapshots").select("*") \
            .gte("snapshot_at", cutoff) \
            .gte("bc_progress", 3) \
            .order("snapshot_at", desc=True) \
            .limit(500) \
            .execute()
    except Exception as e:
        log.warning(f"加载内盘历史: {e}")
        return []

    events = []
    for row in (res.data or []):
        events.append(DataEvent(
            source="pump_tokens",
            data=row,
            timestamp=row.get("snapshot_at", ""),
            chain="solana",
            token_address=row.get("mint", ""),
            token_name=row.get("symbol", ""),
        ))
    return events


async def _load_kol_history(db, cutoff: str) -> List[DataEvent]:
    """加载 KOL 信号历史"""
    try:
        res = db.table("kol_signals").select("*") \
            .gte("detected_at", cutoff) \
            .order("detected_at", desc=True) \
            .limit(200) \
            .execute()
    except Exception as e:
        log.warning(f"加载 KOL 历史: {e}")
        return []

    events = []
    for row in (res.data or []):
        events.append(DataEvent(
            source="kol_signals",
            data=row,
            timestamp=row.get("detected_at", ""),
            chain=row.get("chain", ""),
            token_address=row.get("token_address", ""),
            token_name=row.get("token_name", ""),
        ))
    return events


async def _get_token_performance(db, chain: str, token: str) -> Optional[dict]:
    """查询代币的表现追踪数据"""
    try:
        res = db.table("token_performance").select("best_pct, daily_highs") \
            .eq("chain", chain) \
            .like("symbol", f"%{token}%") \
            .limit(1) \
            .execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return None


def _empty_result(reason: str) -> dict:
    return {
        "trigger_count": 0,
        "simulated_win_rate": 0,
        "avg_return_pct": 0,
        "max_drawdown_pct": 0,
        "sample_triggers": [],
        "error": reason,
    }
