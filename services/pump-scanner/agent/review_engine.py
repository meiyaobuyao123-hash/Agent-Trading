"""
S07 Review Engine — 日/周/月复盘报告(真实施)

引用 docs/agent-pm/05-tool-catalog.md S07 review-engine
引用 docs/agent-pm/03-prd.md §7.7 Review Schema
引用 docs/agent-pm/17-tech-plan.md Phase 2

设计:
  v1:**规则化** insights + metrics 真实数据(rule_engine source)
  v2(W3 D5+ autonomous-loop 续 7):接 P13 prompt + Claude Haiku 4.5 写
    - headline ≤ 30 字 / body ≤ 300 字三段式 / tone
    - LLM 失败降级 v1 规则化 summary(rule_engine source)
    - prompt_invocations 表写入(A/B 追踪 + cost)

Cold start:
  trade_count=0 → "暂无交易,Agent 还在观察"
  trade_count<5 → "样本不足,以下结论仅供参考"

Python 3.9 兼容。
"""
from __future__ import annotations
import asyncio
import json
import logging
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


PERIOD_TO_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}

# v2 LLM 配置
LLM_REVIEW_MODEL = "claude-haiku-4-5-20251001"
LLM_REVIEW_TIMEOUT_S = 30
USE_LLM_DEFAULT = os.getenv("REVIEW_ENGINE_USE_LLM", "true").lower() == "true"


async def generate_review(
    period: str = "daily",
    target_date: Optional[str] = None,
    user_id: Optional[str] = None,
    use_llm: Optional[bool] = None,
) -> Dict[str, Any]:
    """生成复盘报告(主入口)。

    v2 流程:
      1. _load_trades + _compute_metrics(同 v1)
      2. _rule_based_insights / _rule_based_proposals(规则化产出)
      3. **若 use_llm 且 cold_start=normal**:调 P13 prompt + Claude Haiku
         生成 headline + body + tone(替换 _make_summary 的规则化文案)
      4. LLM 失败 → fallback 到 v1 规则化 summary

    Args:
      period: daily / weekly / monthly
      target_date: ISO date(默认今天)
      user_id: 限定用户
      use_llm: None=按 env REVIEW_ENGINE_USE_LLM(默认 true);True/False 覆盖
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

    # ── 规则化产出 insights + proposals(LLM 路径也复用) ────
    cold_start = _cold_start_state(metrics["trade_count"])
    insights = _rule_based_insights(trades, metrics) if cold_start == "normal" else []
    rule_proposals = _rule_based_proposals(trades, metrics) if cold_start == "normal" else []

    # ── Summary:LLM 优先,失败降级规则化 ────────────────────
    use_llm_resolved = USE_LLM_DEFAULT if use_llm is None else use_llm
    summary, source = await _make_summary_with_llm(
        period=period, metrics=metrics, cold_start=cold_start,
        insights=insights, regime_today=None, regime_yesterday=None,
        user_id=user_id, use_llm=use_llm_resolved,
    )

    review_id_prefix = "v2" if source == "llm" else "v1"
    return {
        "review_id": f"{review_id_prefix}-{period}-{int(dt.timestamp())}",
        "period": period,
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "summary": summary,
        "insights": insights,
        "rule_proposals": rule_proposals,
        "metrics": metrics,
        "cold_start_state": cold_start,
        "source": source,
    }


async def _make_summary_with_llm(
    period: str,
    metrics: Dict[str, Any],
    cold_start: str,
    insights: List[Dict[str, Any]],
    regime_today: Optional[str],
    regime_yesterday: Optional[str],
    user_id: Optional[str],
    use_llm: bool,
) -> "tuple[Dict[str, str], str]":
    """v2 summary 生成器。

    Returns: (summary_dict, source) — source ∈ {"llm", "rule_engine"}
    """
    # cold_start 不正常时直接走规则化(LLM 没什么可写)
    if cold_start != "normal":
        return _make_summary(period, metrics, cold_start), "rule_engine"

    if not use_llm:
        return _make_summary(period, metrics, cold_start), "rule_engine"

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.warning("[review_engine v2] ANTHROPIC_API_KEY not set,fallback to rule_engine")
        return _make_summary(period, metrics, cold_start), "rule_engine"

    # 构造 P13 prompt vars
    persona = "intermediate"  # TODO: 从 user_profile 拉,W7-W12
    vars_ = {
        "metrics_json": json.dumps(metrics, ensure_ascii=False),
        "insights_json": json.dumps(
            [{"type": i.get("type"), "text": i.get("text"),
              "evidence_trade_ids": i.get("evidence_trade_ids", [])} for i in insights],
            ensure_ascii=False,
        ),
        "regime_today": regime_today or "UNKNOWN",
        "regime_yesterday": regime_yesterday or "UNKNOWN",
        "persona": persona,
    }

    try:
        from agent.prompt_loader import get_prompt_loader
        loader = get_prompt_loader()
        device_id = user_id or "system"
        request = loader.to_messages_request(
            "P13", device_id, user_message="生成本期复盘", vars=vars_,
        )
    except Exception as e:
        log.warning("[review_engine v2] prompt_loader failed: %s,fallback", e)
        return _make_summary(period, metrics, cold_start), "rule_engine"

    # 调 Claude
    raw_text = ""
    tokens_used = 0
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=LLM_REVIEW_TIMEOUT_S)
        response = await asyncio.to_thread(
            client.messages.create,
            **request,
        )
        raw_text = response.content[0].text.strip()
        try:
            tokens_used = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
        except Exception:
            tokens_used = 0
    except Exception as e:
        log.warning("[review_engine v2] Claude call failed: %s,fallback", e)
        return _make_summary(period, metrics, cold_start), "rule_engine"

    # 解析 JSON(去掉可能的 markdown 包裹)
    parsed = _parse_llm_json(raw_text)
    if not parsed or "headline" not in parsed or "body" not in parsed:
        log.warning("[review_engine v2] LLM JSON parse failed,fallback. raw=%s", raw_text[:200])
        return _make_summary(period, metrics, cold_start), "rule_engine"

    summary = {
        "headline": str(parsed["headline"])[:60],
        "body": str(parsed["body"])[:600],
    }
    if "tone" in parsed:
        summary["tone"] = str(parsed["tone"])

    # 异步写 prompt_invocations(失败不阻断)
    asyncio.create_task(_log_prompt_invocation(
        prompt_id="P13",
        version_used=request.get("model", LLM_REVIEW_MODEL),
        device_id=user_id or "system",
        tokens_used=tokens_used,
        latency_ms=0,  # TODO: 实际测;v0 占位
        ok=True,
    ))
    return summary, "llm"


def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
    """从 LLM 输出抽 JSON;支持 ```json ... ``` 包裹。"""
    s = text.strip()
    if s.startswith("```"):
        # 去掉首行 ``` 和尾行 ```
        lines = s.splitlines()
        if lines:
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            s = "\n".join(lines).strip()
    try:
        return json.loads(s)
    except Exception:
        # 尝试找第一个 { ... } 子串
        first = s.find("{")
        last = s.rfind("}")
        if first >= 0 and last > first:
            try:
                return json.loads(s[first:last + 1])
            except Exception:
                return None
        return None


async def _log_prompt_invocation(
    prompt_id: str,
    version_used: str,
    device_id: str,
    tokens_used: int,
    latency_ms: int,
    ok: bool,
    *,
    skill_name: Optional[str] = None,
    loop_name: Optional[str] = None,
) -> None:
    """非阻塞:写本地 PG prompt_invocations 表。失败 swallow。

    schema(migration 038):id/ts/device_id/prompt_id/version_used/bucket/
    input_tokens/output_tokens/cost_usd/cache_hit/latency_ms/skill_name/loop_name/outcome
    """
    try:
        from local_db import _get_conn
        conn = _get_conn()
        # device_id 必须是 UUID;非 UUID(如 "system")则跳过(表 NOT NULL 约束)
        import re as _re
        if not _re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            device_id, _re.IGNORECASE,
        ):
            return
        outcome = "success" if ok else "parse_fail"
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO prompt_invocations
                (device_id, prompt_id, version_used, output_tokens, latency_ms,
                 outcome, skill_name, loop_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (device_id, prompt_id, version_used, tokens_used, latency_ms,
                 outcome, skill_name, loop_name),
            )
    except Exception as e:
        # 表不存在 / DB 不可达 都不阻断主流程
        log.debug("[review_engine v2] prompt_invocations log skipped: %s", e)


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
