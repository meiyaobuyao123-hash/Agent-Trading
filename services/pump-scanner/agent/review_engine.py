"""
S07 Review Engine — 日/周/月复盘报告(真实施)

引用 docs/agent-pm/05-tool-catalog.md S07 review-engine
引用 docs/agent-pm/03-prd.md §7.7 Review Schema
引用 docs/agent-pm/17-tech-plan.md Phase 2

设计:
  v1(本次):**规则化** insights + metrics 真实数据(不调 LLM)
    - 从 agent_executions 汇总 trades + token_performance D3 涨幅
    - 规则化产出 insights:win_pattern / loss_pattern / risk_warning
    - 规则化产出 rule_proposals:基于胜率差 + 样本量 阈值
    - 不调 Claude(成本控制 + 减少 W3 D5 改动面)

  v2(后续 W7-W12):接 Claude Haiku 4.5 写 headline + body + 提议规则
    - LLM 输入:metrics + insights + 最近 5 笔代表性 trade
    - LLM 输出:headline ≤ 30 字 / body ≤ 300 字 / 2-5 条 rule_proposal

Cold start:
  trade_count=0 → "暂无交易,Agent 还在观察"
  trade_count<5 → "样本不足,以下结论仅供参考"

Python 3.9 兼容。
"""
from __future__ import annotations
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


PERIOD_TO_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}


async def generate_review(
    period: str = "daily",
    target_date: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """生成复盘报告(主入口)。

    Args:
      period: daily / weekly / monthly
      target_date: ISO date(默认今天)
      user_id: 限定用户(None 则跨用户聚合,管理用)

    Returns:
      Review schema(对齐 Flutter Review 模型)
    """
    days = PERIOD_TO_DAYS.get(period, 1)

    if target_date:
        try:
            dt = datetime.fromisoformat(target_date.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    period_to = dt
    period_from = dt - timedelta(days=days)

    # ── 拉 trade 数据 ─────────────────────────────────────────
    trades = await _load_trades(period_from, period_to, user_id)
    metrics = _compute_metrics(trades)

    # ── 规则化产出 insights + proposals ─────────────────────────
    cold_start = _cold_start_state(metrics["trade_count"])
    insights = _rule_based_insights(trades, metrics) if cold_start == "normal" else []
    rule_proposals = _rule_based_proposals(trades, metrics) if cold_start == "normal" else []

    summary = _make_summary(period, metrics, cold_start)

    return {
        "review_id": f"v1-{period}-{int(dt.timestamp())}",
        "period": period,
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "summary": summary,
        "insights": insights,
        "rule_proposals": rule_proposals,
        "metrics": metrics,
        "cold_start_state": cold_start,
        "source": "rule_engine",  # v2 升级后改 "llm"
    }


async def _load_trades(
    period_from: datetime,
    period_to: datetime,
    user_id: Optional[str],
) -> List[Dict[str, Any]]:
    """从 agent_executions 拉 period 内的 trades(带 token_performance D3 涨幅)。"""
    try:
        from database import get_db
        db = get_db()
        q = db.table("agent_executions").select("*") \
            .gte("created_at", period_from.isoformat()) \
            .lte("created_at", period_to.isoformat())
        if user_id:
            q = q.eq("user_id", user_id)
        res = q.order("created_at").limit(500).execute()
        executions = res.data or []
    except Exception as e:
        log.warning("review: load trades failed: %s", e)
        return []

    if not executions:
        return []

    # 拉 token_performance D3 涨幅(用于 win/loss 判定)
    token_addrs = list({e.get("token_address") for e in executions if e.get("token_address")})
    perf_map: Dict[str, float] = {}
    if token_addrs:
        try:
            from database import get_db
            perf_res = get_db().table("token_performance").select(
                "address, daily_highs, source, chain"
            ).in_("address", token_addrs).execute()
            for row in (perf_res.data or []):
                dh = row.get("daily_highs") or {}
                d3 = dh.get("D3") or dh.get("3") or {}
                if isinstance(d3, dict):
                    perf_map[row["address"]] = float(d3.get("pct", 0) or 0)
        except Exception as e:
            log.warning("review: load token_performance failed: %s", e)

    # 按 token 配对 buy/sell,计算每笔 trade pnl
    trades_by_token: Dict[str, List[Dict]] = defaultdict(list)
    for ex in executions:
        addr = ex.get("token_address", "")
        if addr:
            trades_by_token[addr].append(ex)

    paired: List[Dict[str, Any]] = []
    for addr, exs in trades_by_token.items():
        buys = [e for e in exs if e.get("action") == "buy"]
        sells = [e for e in exs if e.get("action") == "sell"]
        if not buys:
            continue
        avg_buy = _avg([float(b.get("executed_price") or 0) for b in buys])
        buy_usd = sum(float(b.get("amount_usd") or 0) for b in buys)
        avg_sell = _avg([float(s.get("executed_price") or 0) for s in sells]) if sells else None
        sell_usd = sum(float(s.get("amount_usd") or 0) for s in sells)

        pnl_ratio = (avg_sell / avg_buy) if (avg_buy > 0 and avg_sell) else None
        realized_pnl = sell_usd - buy_usd if sells else 0.0

        # D3 涨幅(理论收益)
        d3_pct = perf_map.get(addr, 0.0)

        paired.append({
            "token_address": addr,
            "chain": buys[0].get("chain", ""),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "buy_usd": buy_usd,
            "sell_usd": sell_usd,
            "avg_buy_price": avg_buy,
            "avg_sell_price": avg_sell,
            "pnl_ratio": pnl_ratio,
            "realized_pnl_usd": realized_pnl,
            "d3_pct": d3_pct,
            "first_executed_at": buys[0].get("created_at"),
            "is_closed": bool(sells),
            "strategy_id": buys[0].get("strategy_id", ""),
        })

    return paired


def _avg(xs: List[float]) -> float:
    xs = [x for x in xs if x > 0]
    return sum(xs) / len(xs) if xs else 0.0


def _compute_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {
            "trade_count": 0, "win_rate": 0.0, "ev_pct": 0.0,
            "sharpe": 0.0, "max_drawdown_pct": 0.0, "profit_factor": 1.0,
            "kelly_fraction": None,
        }

    closed = [t for t in trades if t["is_closed"] and t["pnl_ratio"]]
    if not closed:
        # 全开仓中,用 D3 估算
        d3_pcts = [t["d3_pct"] for t in trades if t["d3_pct"] is not None]
        wins = sum(1 for p in d3_pcts if p >= 20)
        return {
            "trade_count": len(trades),
            "win_rate": round(wins / len(d3_pcts), 3) if d3_pcts else 0.0,
            "ev_pct": round(sum(d3_pcts) / len(d3_pcts), 2) if d3_pcts else 0.0,
            "sharpe": 0.0, "max_drawdown_pct": 0.0, "profit_factor": 1.0,
            "kelly_fraction": None,
        }

    pnl_list = [t["pnl_ratio"] for t in closed]
    wins = sum(1 for r in pnl_list if r >= 1.0)
    win_rate = wins / len(pnl_list)
    ev_pct = (sum(pnl_list) / len(pnl_list) - 1.0) * 100  # 平均超额收益 %

    # 最大回撤(累积 pnl)
    cum = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in pnl_list:
        cum *= r
        peak = max(peak, cum)
        dd = (cum - peak) / peak if peak > 0 else 0
        max_dd = min(max_dd, dd)

    # Sharpe 简化:mean / stdev
    if len(pnl_list) > 1:
        mean = sum(pnl_list) / len(pnl_list) - 1.0
        var = sum((r - 1.0 - mean) ** 2 for r in pnl_list) / (len(pnl_list) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        sharpe = mean / std if std > 0 else 0.0
    else:
        sharpe = 0.0

    # Profit factor: sum(wins) / sum(losses)
    gains = sum(r - 1.0 for r in pnl_list if r >= 1.0)
    losses = abs(sum(r - 1.0 for r in pnl_list if r < 1.0))
    profit_factor = (gains / losses) if losses > 0 else (1.0 if gains == 0 else float("inf"))

    # Kelly fraction (simplified): f* = win_rate - (1 - win_rate) / win_loss_ratio
    if losses > 0 and gains > 0 and wins > 0:
        avg_win = gains / wins
        avg_loss = losses / max(1, len(pnl_list) - wins)
        b = avg_win / avg_loss if avg_loss > 0 else 0
        kelly = win_rate - (1 - win_rate) / b if b > 0 else None
    else:
        kelly = None

    return {
        "trade_count": len(trades),
        "win_rate": round(win_rate, 3),
        "ev_pct": round(ev_pct, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999.0,
        "kelly_fraction": round(kelly, 3) if kelly is not None else None,
    }


def _cold_start_state(trade_count: int) -> str:
    if trade_count == 0:
        return "no_trades"
    if trade_count < 5:
        return "few_trades"
    return "normal"


def _make_summary(period: str, metrics: Dict, cold_start: str) -> Dict[str, str]:
    period_label = {"daily": "今日", "weekly": "本周", "monthly": "本月"}.get(period, period)

    if cold_start == "no_trades":
        return {
            "headline": f"{period_label}暂无交易",
            "body": "Agent 处于观察模式,等待信号触发或用户手动创建策略。",
        }
    if cold_start == "few_trades":
        return {
            "headline": f"{period_label} {metrics['trade_count']} 笔 — 样本不足",
            "body": f"当前 {metrics['trade_count']} 笔交易样本不足以得出可靠结论,胜率 {metrics['win_rate']*100:.0f}%、EV {metrics['ev_pct']:+.2f}% 仅供参考。",
        }

    win_pct = int(metrics["win_rate"] * 100)
    headline = (
        f"{period_label} {metrics['trade_count']} 笔 — 胜率 {win_pct}%,"
        f"EV {metrics['ev_pct']:+.2f}%"
    )
    body_parts = []
    if metrics["sharpe"] >= 1.0:
        body_parts.append(f"夏普 {metrics['sharpe']}")
    if metrics["max_drawdown_pct"] < -3:
        body_parts.append(f"最大回撤 {metrics['max_drawdown_pct']:.1f}%")
    if metrics["profit_factor"] >= 1.5:
        body_parts.append(f"盈亏比 {metrics['profit_factor']}")

    if win_pct >= 60 and metrics["ev_pct"] > 0:
        body = f"整体表现良好。" + ",".join(body_parts) + "。"
    elif win_pct < 40:
        body = f"整体亏损,需要复盘策略框架。" + ",".join(body_parts) + "。"
    else:
        body = f"表现一般。" + ",".join(body_parts) + "。"

    return {"headline": headline, "body": body}


def _rule_based_insights(trades: List[Dict], metrics: Dict) -> List[Dict]:
    """基于 trade 列表规则化产出 insights。"""
    out: List[Dict] = []

    closed = [t for t in trades if t["is_closed"]]
    wins = [t for t in closed if (t["pnl_ratio"] or 0) >= 1.0]
    losses = [t for t in closed if (t["pnl_ratio"] or 0) < 1.0]

    # win_pattern: 链 + 平均涨幅
    if len(wins) >= 3:
        chain_count: Dict[str, int] = defaultdict(int)
        for w in wins:
            chain_count[w["chain"] or "?"] += 1
        top_chain, top_n = max(chain_count.items(), key=lambda x: x[1])
        if top_n >= 3:
            out.append({
                "type": "win_pattern",
                "text": f"{top_chain} 链 {top_n} 笔获利 (n={top_n}),平均收益 {_avg_pnl_pct(wins):+.1f}%",
                "evidence_trade_ids": [t["token_address"] for t in wins[:5]],
                "llm_judge_score": 0.75,
            })

    # loss_pattern: 短期亏损
    if len(losses) >= 3:
        avg_loss = _avg_pnl_pct(losses)
        out.append({
            "type": "loss_pattern",
            "text": f"亏损 {len(losses)} 笔,平均亏损 {avg_loss:.1f}%。建议复盘进场条件",
            "evidence_trade_ids": [t["token_address"] for t in losses[:5]],
            "llm_judge_score": 0.70,
        })

    # risk_warning: 大 drawdown
    if metrics["max_drawdown_pct"] < -10:
        out.append({
            "type": "risk_warning",
            "text": f"最大回撤 {metrics['max_drawdown_pct']:.1f}%,建议加风险预警",
            "evidence_trade_ids": [],
            "llm_judge_score": 0.80,
        })

    # observation: 总评
    if metrics["trade_count"] >= 5 and not out:
        out.append({
            "type": "observation",
            "text": f"{metrics['trade_count']} 笔无明显模式,Agent 继续观察",
            "evidence_trade_ids": [],
            "llm_judge_score": 0.60,
        })

    return out


def _rule_based_proposals(trades: List[Dict], metrics: Dict) -> List[Dict]:
    """规则化提议(W7-W12 接 reflection 真实施)。"""
    out: List[Dict] = []
    if metrics["trade_count"] < 10:
        return out  # 样本不足不提议

    closed = [t for t in trades if t["is_closed"]]
    losses = [t for t in closed if (t["pnl_ratio"] or 0) < 0.95]

    # 提议 1:多次亏损 → 收紧进场
    if len(losses) >= 5 and metrics["win_rate"] < 0.5:
        out.append({
            "proposal_id": f"rp-tighten-{len(losses)}",
            "human_readable": f"近期 {len(losses)} 笔亏损,建议进场条件加严(BC% 阈值 +3pp)",
            "formal_condition": {
                "when": {"recent_loss_count": {">=": 5}},
                "then": {"bc_threshold_delta": 3},
            },
            "sample_size": len(losses),
            "win_rate_diff": round((0.5 - metrics["win_rate"]) * 100, 1),
            "wilson_ci_lower": _wilson_lower(metrics["win_rate"], len(closed)),
            "active_regimes": ["RANGING", "HIGH_VOLATILITY"],
            "reflection_id": None,
        })

    # 提议 2:profit_factor > 2 → 加仓
    if metrics["profit_factor"] >= 2.0 and metrics["trade_count"] >= 15:
        out.append({
            "proposal_id": f"rp-scale-{metrics['trade_count']}",
            "human_readable": f"盈亏比 {metrics['profit_factor']:.2f},考虑提高仓位(+10%)",
            "formal_condition": {
                "when": {"profit_factor": {">=": 2.0}},
                "then": {"position_size_multiplier": 1.1},
            },
            "sample_size": metrics["trade_count"],
            "win_rate_diff": round((metrics["win_rate"] - 0.5) * 100, 1),
            "wilson_ci_lower": _wilson_lower(metrics["win_rate"], metrics["trade_count"]),
            "active_regimes": ["TRENDING_UP", "BREAKOUT"],
            "reflection_id": None,
        })

    return out


def _avg_pnl_pct(trades: List[Dict]) -> float:
    pnls = [(t["pnl_ratio"] - 1.0) * 100 for t in trades if t["pnl_ratio"]]
    return sum(pnls) / len(pnls) if pnls else 0.0


def _wilson_lower(p: float, n: int, z: float = 1.96) -> Optional[float]:
    """Wilson score interval 下界(95% CI)。"""
    if n <= 0:
        return None
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, centre - spread), 3)
