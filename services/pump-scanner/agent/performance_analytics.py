"""
策略表现分析 — 胜率/PNL/夏普率/最大回撤

从 agent_executions 表计算策略表现指标。

Python 3.9 兼容。
"""

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import get_db

log = logging.getLogger(__name__)


async def get_strategy_performance(
    strategy_id: str, days: int = 30
) -> Dict[str, Any]:
    """计算单个策略的完整表现指标"""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        res = db.table("agent_executions").select("*") \
            .eq("strategy_id", strategy_id) \
            .gte("created_at", cutoff) \
            .order("created_at") \
            .execute()
    except Exception as e:
        log.error(f"查询 agent_executions 失败: {e}")
        return _empty_performance()

    executions = res.data or []
    if not executions:
        return _empty_performance()

    # 按代币分组，配对买卖
    trades_by_token = defaultdict(list)  # {token_address: [exec1, exec2, ...]}
    for ex in executions:
        addr = ex.get("token_address", "")
        if addr:
            trades_by_token[addr].append(ex)

    # 计算胜率和 PNL
    wins = 0
    losses = 0
    pnl_list = []  # 每笔配对交易的收益率
    total_invested = 0.0
    total_returned = 0.0

    for token_addr, token_execs in trades_by_token.items():
        buys = [e for e in token_execs if e.get("action") == "buy"]
        sells = [e for e in token_execs if e.get("action") == "sell"]

        if not buys:
            continue

        avg_buy = sum(float(b.get("executed_price") or 0) for b in buys) / len(buys)
        buy_amount = sum(float(b.get("amount_usd") or 0) for b in buys)
        total_invested += buy_amount

        if sells:
            avg_sell = sum(float(s.get("executed_price") or 0) for s in sells) / len(sells)
            sell_amount = sum(float(s.get("amount_usd") or 0) for s in sells)
            total_returned += sell_amount

            if avg_buy > 0:
                pnl_ratio = avg_sell / avg_buy
                pnl_list.append(pnl_ratio)
                if pnl_ratio >= 1.0:
                    wins += 1
                else:
                    losses += 1

    total_trades = wins + losses
    win_rate = wins / total_trades if total_trades > 0 else 0
    avg_pnl = sum(pnl_list) / len(pnl_list) if pnl_list else 0
    realized_pnl = total_returned - total_invested

    # 理论胜率（PRD-003: 基于 D3 涨幅，与 optimizer/backtester 统一口径）
    from config import WIN_RATE_PUMP_D3_PCT
    theo_wins = 0
    theo_total = 0
    for token_addr, token_execs in trades_by_token.items():
        buys = [e for e in token_execs if e.get("action") == "buy"]
        if not buys:
            continue
        theo_total += 1
        # 查 token_performance 获取 D3 涨幅
        try:
            perf_res = db.table("token_performance").select("daily_highs") \
                .eq("address", token_addr).limit(1).execute()
            if perf_res.data:
                dh = perf_res.data[0].get("daily_highs") or {}
                d3 = dh.get("D3") or dh.get("3") or {}
                d3_pct = d3.get("pct", 0) if isinstance(d3, dict) else 0
                if d3_pct >= WIN_RATE_PUMP_D3_PCT:
                    theo_wins += 1
        except Exception:
            pass
    theoretical_win_rate = theo_wins / theo_total if theo_total > 0 else 0

    # 最大回撤（基于累积 PNL 曲线）
    max_drawdown = _calc_max_drawdown(pnl_list)

    # 夏普率（简化版：平均收益 / 标准差）
    sharpe = _calc_sharpe(pnl_list)

    return {
        "strategy_id": strategy_id,
        "period_days": days,
        "total_executions": len(executions),
        "paired_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "actual_win_rate": round(win_rate, 4),
        "theoretical_win_rate": round(theoretical_win_rate, 4),
        "win_rate": round(win_rate, 4),  # 向后兼容
        "avg_pnl_ratio": round(avg_pnl, 4),
        "total_invested_usd": round(total_invested, 2),
        "total_returned_usd": round(total_returned, 2),
        "realized_pnl_usd": round(realized_pnl, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "sharpe_ratio": round(sharpe, 4),
    }


async def get_daily_pnl_summary(
    user_id: str, days: int = 7
) -> List[Dict[str, Any]]:
    """按日汇总用户 P&L"""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        res = db.table("agent_executions").select("*") \
            .eq("user_id", user_id) \
            .gte("created_at", cutoff) \
            .order("created_at") \
            .execute()
    except Exception as e:
        log.error(f"查询 daily PNL 失败: {e}")
        return []

    executions = res.data or []
    daily = defaultdict(lambda: {"buys": 0.0, "sells": 0.0, "count": 0})

    for ex in executions:
        date_str = ex.get("created_at", "")[:10]
        amount = float(ex.get("amount_usd") or 0)
        daily[date_str]["count"] += 1
        if ex.get("action") == "buy":
            daily[date_str]["buys"] += amount
        elif ex.get("action") == "sell":
            daily[date_str]["sells"] += amount

    result = []
    for date_str in sorted(daily.keys()):
        d = daily[date_str]
        result.append({
            "date": date_str,
            "buys_usd": round(d["buys"], 2),
            "sells_usd": round(d["sells"], 2),
            "net_pnl_usd": round(d["sells"] - d["buys"], 2),
            "trade_count": d["count"],
        })
    return result


async def get_portfolio_summary(user_id: str) -> Dict[str, Any]:
    """用户持仓汇总"""
    db = get_db()
    try:
        res = db.table("agent_executions").select("*") \
            .eq("user_id", user_id) \
            .eq("status", "confirmed") \
            .order("created_at") \
            .execute()
    except Exception as e:
        log.error(f"查询 portfolio 失败: {e}")
        return {"total_invested": 0, "total_returned": 0, "open_positions": 0}

    executions = res.data or []
    positions = defaultdict(lambda: {"buy_total": 0.0, "sell_total": 0.0, "buy_count": 0, "sell_count": 0})

    for ex in executions:
        addr = ex.get("token_address", "")
        amount = float(ex.get("amount_usd") or 0)
        if ex.get("action") == "buy":
            positions[addr]["buy_total"] += amount
            positions[addr]["buy_count"] += 1
        elif ex.get("action") == "sell":
            positions[addr]["sell_total"] += amount
            positions[addr]["sell_count"] += 1

    total_invested = sum(p["buy_total"] for p in positions.values())
    total_returned = sum(p["sell_total"] for p in positions.values())
    open_positions = sum(1 for p in positions.values() if p["buy_count"] > p["sell_count"])

    return {
        "total_invested_usd": round(total_invested, 2),
        "total_returned_usd": round(total_returned, 2),
        "realized_pnl_usd": round(total_returned - total_invested, 2),
        "open_positions": open_positions,
        "total_tokens_traded": len(positions),
    }


# ── 辅助函数 ─────────────────────────────────────────

def _calc_max_drawdown(pnl_list: List[float]) -> float:
    """计算最大回撤"""
    if not pnl_list:
        return 0
    cumulative = 1.0
    peak = 1.0
    max_dd = 0.0
    for pnl in pnl_list:
        cumulative *= pnl
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _calc_sharpe(pnl_list: List[float], risk_free: float = 0) -> float:
    """简化夏普率"""
    if len(pnl_list) < 2:
        return 0
    returns = [p - 1 for p in pnl_list]
    avg = sum(returns) / len(returns)
    variance = sum((r - avg) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(variance) if variance > 0 else 0
    if std == 0:
        return 0
    return (avg - risk_free) / std


def _empty_performance() -> dict:
    return {
        "total_executions": 0, "paired_trades": 0,
        "wins": 0, "losses": 0, "win_rate": 0,
        "avg_pnl_ratio": 0, "total_invested_usd": 0,
        "total_returned_usd": 0, "realized_pnl_usd": 0,
        "max_drawdown_pct": 0, "sharpe_ratio": 0,
    }
