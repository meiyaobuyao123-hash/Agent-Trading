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
    risk_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    对策略规范进行历史回测

    参数:
        strategy_spec: StrategySpec（含 conditions, filters, actions）
        days: 回测天数（默认 7）
        risk_params: 策略风控参数(R60 — 含 max_slippage_pct 用作手续费假设)
                     若 None,用 config.DEX_FEE_PCT_SINGLE 各链默认

    返回:
        R60 新格式:
        {
            trigger_count,
            simulated_win_rate,       # 扣手续费后(net)
            gross_win_rate,           # 不扣手续费(对比)
            avg_return_pct,           # 扣手续费后(net)
            gross_return_pct,         # 不扣手续费
            fee_assumptions: {fee_single_pct, fee_round_trip_pct, source},
            max_drawdown_pct,         # 暂返 null,Phase B 加 daily_lows 后启用
            max_drawdown_status,      # "collecting" / "ready"
            sample_triggers,
            period_days,
            data_sources,
        }
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
                    "token_address": event.token_address,
                    "chain": event.chain,
                    "score": event.data.get("score", 0),
                    "price_usd": event.data.get("price_usd", 0),
                    "timestamp": event.timestamp,
                }
                triggers.append(trigger_info)
                if len(sample_triggers) < 10:
                    sample_triggers.append(trigger_info)

    # ── R60: 模拟收益 + 扣手续费 + win 判定 ─────────────────────
    # 双轨:gross(不扣)+ net(扣完手续费),给用户对比看到真实净收益
    from config import (
        WIN_RATE_PUMP_D3_PCT,
        WIN_RATE_HOT_D3_PCT,
        DEX_FEE_PCT_SINGLE,
        DEX_FEE_PCT_DEFAULT_SINGLE,
    )

    # 判断 fee_single 来源:用户 risk_params.max_slippage_pct 覆盖,否则用 chain 默认
    user_slippage = (risk_params or {}).get("max_slippage_pct")
    fee_source = "user" if user_slippage and user_slippage > 0 else "default"
    # 用第一个 trigger 的 chain 决定默认费率(策略一般固定链)
    first_chain = triggers[0].get("chain", "") if triggers else "solana"
    if fee_source == "user":
        # 用户传的 max_slippage_pct 单位是 0.01 = 1%(R47 P4 规范)
        fee_single_pct = float(user_slippage) * 100
    else:
        fee_single_pct = DEX_FEE_PCT_SINGLE.get(
            first_chain, DEX_FEE_PCT_DEFAULT_SINGLE)
    fee_single = fee_single_pct / 100.0
    fee_round_trip_pct = fee_single_pct * 2
    fee_round_trip = fee_single * 2

    gross_win_count = 0
    net_win_count = 0
    gross_returns = []
    net_returns = []

    for t in triggers:
        perf = await _get_token_performance(
            db, t.get("chain", ""), t.get("token_address", ""))
        if not perf:
            continue
        best_pct = perf.get("best_pct", 0) or 0
        gross_return = best_pct / 100  # 整段最高涨幅(理想出场)
        # 扣手续费:入场实付 = price × (1+fee_single);出场实收 = price × (1-fee_single)
        # net 收益 = (1+gross) × (1-fee_rt) - 1 ≈ gross - fee_rt(gross 小时)
        net_return = (1 + gross_return) * (1 - fee_round_trip) - 1
        gross_returns.append(gross_return)
        net_returns.append(net_return)

        # win 判定:用 D3 涨幅(扣手续费前后两个版本)
        dh = perf.get("daily_highs") or {}
        d3 = dh.get("D3") or dh.get("3") or {}
        d3_pct = d3.get("pct", 0) if isinstance(d3, dict) else 0
        d3_gross = d3_pct / 100
        d3_net = (1 + d3_gross) * (1 - fee_round_trip) - 1

        source = perf.get("source", "")
        if source in ("pump", "pump_live"):
            gross_thresh = WIN_RATE_PUMP_D3_PCT / 100
        elif source in ("hot", "hot_live"):
            gross_thresh = WIN_RATE_HOT_D3_PCT / 100
        else:
            gross_thresh = 0.0  # 默认不亏算 win

        if d3_gross >= gross_thresh:
            gross_win_count += 1
        if d3_net >= gross_thresh:
            net_win_count += 1

    total = len(triggers)
    gross_win_rate = gross_win_count / total if total > 0 else 0
    net_win_rate = net_win_count / total if total > 0 else 0
    gross_avg_return = (
        sum(gross_returns) / len(gross_returns) * 100
        if gross_returns else 0
    )
    net_avg_return = (
        sum(net_returns) / len(net_returns) * 100
        if net_returns else 0
    )

    return {
        "trigger_count": total,
        # 默认显示 net(扣完手续费,诚实)
        "simulated_win_rate": round(net_win_rate, 4),
        "avg_return_pct": round(net_avg_return, 2),
        # 对比版(不扣手续费),让用户能 toggle 看
        "gross_win_rate": round(gross_win_rate, 4),
        "gross_return_pct": round(gross_avg_return, 2),
        # 手续费假设
        "fee_assumptions": {
            "fee_single_pct": round(fee_single_pct, 2),
            "fee_round_trip_pct": round(fee_round_trip_pct, 2),
            "chain": first_chain,
            "source": fee_source,  # "user" or "default"
        },
        # R60 Phase B:max_drawdown 数据收集中
        "max_drawdown_pct": None,
        "max_drawdown_status": "collecting",
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


async def _get_token_performance(db, chain: str, token_address: str) -> Optional[dict]:
    """查询代币的表现追踪数据(按合约地址精确匹配,不用 symbol 模糊匹配防张冠李戴)"""
    if not token_address:
        return None
    try:
        res = db.table("token_performance").select("best_pct, daily_highs") \
            .eq("chain", chain) \
            .eq("address", token_address) \
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
