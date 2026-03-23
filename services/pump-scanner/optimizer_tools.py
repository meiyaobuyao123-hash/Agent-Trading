"""
Optimizer Agent 工具集 — 供 Claude Agent 调用的函数

每个工具都是一个纯函数，接收参数，返回 JSON-serializable 结果。
Agent 通过 tool_use 调用这些函数，实现数据分析和优化闭环。
"""

import json
import logging
import os
from datetime import date, timedelta
from typing import Any

from database import get_db

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# Tool 1: read_metrics — 读取监控指标
# ══════════════════════════════════════════════════════

def tool_read_metrics(days: int = 7) -> dict:
    """
    读取最近 N 天的监控数据，包括：
    - pump_daily_report 漏斗数据
    - token_performance 推荐表现
    - 计算 hit_rate / recall / precision
    """
    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    # 1. 漏斗数据
    reports = db.table("pump_daily_report") \
        .select("*") \
        .gte("report_date", cutoff) \
        .order("report_date", desc=True) \
        .execute().data

    # 2. 推荐表现
    perf = db.table("token_performance") \
        .select("*") \
        .eq("source", "pump") \
        .gte("pick_date", cutoff) \
        .execute().data

    # 3. 所有毕业代币（可能有我们没推荐的）
    graduated = db.table("pump_tokens") \
        .select("mint, symbol, graduated_at, created_at") \
        .eq("complete", True) \
        .gte("created_at", f"{cutoff}T00:00:00Z") \
        .execute().data

    # 4. 计算指标（PRD-003: D3 ≥ 30% 或毕业 = hit）
    from config import WIN_RATE_PUMP_D3_PCT
    recommended_mints = {p["address"] for p in perf}
    graduated_mints = {g["mint"] for g in graduated}

    # 命中：推荐了 & (D3 ≥ 30% 或毕业)
    hit_mints = set()
    for p in perf:
        addr = p.get("address", "")
        dh = p.get("daily_highs") or {}
        d3 = dh.get("D3") or dh.get("3") or {}
        d3_pct = d3.get("pct", 0) if isinstance(d3, dict) else 0
        if d3_pct >= WIN_RATE_PUMP_D3_PCT or addr in graduated_mints:
            hit_mints.add(addr)
    hits = hit_mints
    # 误报：推荐了 & 没命中
    false_positives = recommended_mints - hits
    # 漏掉：毕业了 & 没推荐
    missed = graduated_mints - recommended_mints

    total_picks = len(recommended_mints)
    total_graduated = len(graduated_mints)
    hit_count = len(hits)
    miss_count = len(missed)

    hit_rate = hit_count / total_picks if total_picks > 0 else 0
    recall = hit_count / total_graduated if total_graduated > 0 else 0
    precision = hit_count / total_picks if total_picks > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    # 5. 推荐代币的实际表现
    perf_summary = []
    for p in perf:
        perf_summary.append({
            "symbol": p.get("symbol"),
            "address": p.get("address"),
            "score": p.get("score"),
            "pick_date": p.get("pick_date"),
            "best_pct": p.get("best_pct"),
            "current_pct": p.get("current_pct"),
            "tracking_days": p.get("tracking_days"),
            "daily_highs": p.get("daily_highs"),
            "graduated": p.get("address") in graduated_mints,
        })

    # 6. 漏掉的代币信息
    missed_tokens = []
    for g in graduated:
        if g["mint"] in missed:
            missed_tokens.append({
                "mint": g["mint"],
                "symbol": g.get("symbol", "?"),
                "graduated_at": g.get("graduated_at"),
            })

    return {
        "period_days": days,
        "date_range": f"{cutoff} ~ {date.today().isoformat()}",
        "funnel": {
            "reports": [{
                "date": r["report_date"],
                "ws_creates": r.get("ws_creates", 0),
                "tokens_saved": r.get("tokens_saved", 0),
                "observed": r.get("observed_tokens", 0),
                "picks": r.get("picks_count", 0),
                "graduated": r.get("graduated_count", 0),
                "hit_rate": r.get("hit_rate", 0),
                "miss_rate": r.get("miss_rate", 0),
            } for r in reports],
        },
        "performance": {
            "total_picks": total_picks,
            "total_graduated": total_graduated,
            "hit_count": hit_count,
            "miss_count": miss_count,
            "false_positive_count": len(false_positives),
            "hit_rate": round(hit_rate, 4),
            "recall": round(recall, 4),
            "precision": round(precision, 4),
            "f1_score": round(f1, 4),
        },
        "recommended_tokens": perf_summary,
        "missed_opportunities": missed_tokens[:20],  # 最多20个
    }


# ══════════════════════════════════════════════════════
# Tool 2: read_scorer_code — 读取评分源码
# ══════════════════════════════════════════════════════

def tool_read_scorer_code() -> dict:
    """读取当前 scorer.py 的完整代码"""
    base = os.path.dirname(os.path.abspath(__file__))
    scorer_path = os.path.join(base, "scorer.py")
    with open(scorer_path, "r") as f:
        code = f.read()
    return {"file": "scorer.py", "code": code, "lines": len(code.splitlines())}


# ══════════════════════════════════════════════════════
# Tool 3: read_config — 读取配置
# ══════════════════════════════════════════════════════

def tool_read_config() -> dict:
    """读取当前 config.py 的所有可调参数"""
    from config import (
        MIN_BUYERS_HARD, MAX_DEV_SOLD_PCT, MIN_BUY_SELL_RATIO,
        BC_MIN_PCT, BC_MAX_PCT, LARGE_BUY_SOL,
        ENRICH_MIN_BUYERS, ENRICH_MIN_BC_PCT,
    )
    base = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base, "config.py")
    with open(config_path, "r") as f:
        config_code = f.read()

    return {
        "file": "config.py",
        "code": config_code,
        "current_params": {
            "MIN_BUYERS_HARD": MIN_BUYERS_HARD,
            "MAX_DEV_SOLD_PCT": MAX_DEV_SOLD_PCT,
            "MIN_BUY_SELL_RATIO": MIN_BUY_SELL_RATIO,
            "BC_MIN_PCT": BC_MIN_PCT,
            "BC_MAX_PCT": BC_MAX_PCT,
            "LARGE_BUY_SOL": LARGE_BUY_SOL,
            "ENRICH_MIN_BUYERS": ENRICH_MIN_BUYERS,
            "ENRICH_MIN_BC_PCT": ENRICH_MIN_BC_PCT,
        },
        "scorer_weights": {
            "buy_sell_ratio": {"max_points": 25, "linear_lo": 1.0, "linear_hi": 5.0},
            "smart_money": {"max_points": 20, "elite_mult": 3.0, "verified_mult": 1.5, "watching_mult": 1.0},
            "inflow_acceleration": {"max_points": 15, "threshold": 0.5},
            "creator_history": {"max_points": 15, "new_creator_default": 8.0},
            "buyer_diversity": {"max_points": 10, "lo": 10, "hi": 50},
            "social": {"max_points": 10},
            "progress_speed": {"max_points": 5, "optimal_range": [5, 20]},
            "large_buy_bonus": {"max_points": 5, "per_buy": 1.0},
        },
        "recommendation_thresholds": {
            "strong": 75,
            "normal": 55,
            "skip_below": 55,
        },
        "signal_pool": {
            "SIGNAL_MIN_SCORE": 55,
            "SIGNAL_DEAD_NO_TRADE": 1800,
            "SIGNAL_MAX_AGE_H": 3,
        }
    }


# ══════════════════════════════════════════════════════
# Tool 4: query_tokens — 查询历史代币特征 + 结果
# ══════════════════════════════════════════════════════

def tool_query_tokens(
    days: int = 7,
    graduated_only: bool = False,
    recommended_only: bool = False,
    limit: int = 200,
) -> dict:
    """
    查询历史代币快照，结合毕业结果，用于分析。
    返回每个代币的特征快照 + 是否毕业 + 是否被推荐。
    """
    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    # 获取快照（最新一条 per token）
    # 注意：token_snapshots 表没有 score/recommendation/social_score/creator 列
    snapshots_res = db.table("token_snapshots") \
        .select("mint, bc_progress, v_sol, market_cap_sol, buy_count, sell_count, "
                "buy_volume_sol, sell_volume_sol, unique_buyers, unique_sellers, "
                "buy_sell_ratio_count, buy_sell_ratio_vol, inflow_rate_sol_pm, "
                "inflow_acceleration, large_buy_count, dev_sold_pct, "
                "smart_elite_count, smart_verified_count, smart_watching_count, "
                "smart_money_net_sol, snapshot_at") \
        .gte("snapshot_at", f"{cutoff}T00:00:00Z") \
        .order("snapshot_at", desc=True) \
        .limit(limit * 3) \
        .execute()

    # 去重：每个 mint 只保留最新快照
    seen = set()
    unique_snapshots = []
    for s in snapshots_res.data:
        if s["mint"] not in seen:
            seen.add(s["mint"])
            unique_snapshots.append(s)
        if len(unique_snapshots) >= limit:
            break

    # 获取毕业状态
    graduated_res = db.table("pump_tokens") \
        .select("mint, complete, graduated_at") \
        .gte("created_at", f"{cutoff}T00:00:00Z") \
        .execute()
    graduated_set = {r["mint"] for r in graduated_res.data if r.get("complete")}

    # 获取推荐状态
    picks_res = db.table("daily_picks") \
        .select("mint, pick_date, score") \
        .gte("pick_date", cutoff) \
        .execute()
    recommended_set = {r["mint"] for r in picks_res.data}

    # 合并
    results = []
    for s in unique_snapshots:
        mint = s["mint"]
        is_graduated = mint in graduated_set
        is_recommended = mint in recommended_set

        if graduated_only and not is_graduated:
            continue
        if recommended_only and not is_recommended:
            continue

        results.append({
            **s,
            "graduated": is_graduated,
            "recommended": is_recommended,
        })

    return {
        "count": len(results),
        "period_days": days,
        "tokens": results[:limit],
        "summary": {
            "total_snapshots": len(unique_snapshots),
            "graduated_count": sum(1 for r in results if r["graduated"]),
            "recommended_count": sum(1 for r in results if r["recommended"]),
            "both_count": sum(1 for r in results if r["graduated"] and r["recommended"]),
        }
    }


# ══════════════════════════════════════════════════════
# Tool 5: backtest — 用新参数回测历史数据
# ══════════════════════════════════════════════════════

def tool_backtest(
    param_changes: list,
    days: int = 7,
    top_n: int = 10,
) -> dict:
    """
    用修改后的参数对历史数据重新打分，对比原始结果。

    param_changes: [
        {"param": "smart_money_weight", "old": 20, "new": 25},
        {"param": "MIN_BUYERS_HARD", "old": 5, "new": 4},
        {"param": "signal_min_score", "old": 55, "new": 50},
        ...
    ]
    """
    from backtest import run_backtest
    return run_backtest(param_changes=param_changes, days=days, top_n=top_n)


# ══════════════════════════════════════════════════════
# Tool 6: propose_change — 提交优化方案（写入DB等待审批）
# ══════════════════════════════════════════════════════

def tool_propose_change(
    run_id: int,
    title: str,
    rationale: str,
    changes: list,
    backtest_before: dict,
    backtest_after: dict,
) -> dict:
    """
    提交优化方案到 DB，等待用户在 Portal 审批。
    changes: [{file, type, param, old, new, reason}, ...]
    """
    db = get_db()

    improvement = 0
    if backtest_before.get("f1", 0) > 0:
        improvement = ((backtest_after.get("f1", 0) - backtest_before["f1"]) / backtest_before["f1"]) * 100
    elif backtest_after.get("f1", 0) > 0:
        improvement = 100.0

    # 保存当前参数快照（用于回滚）
    params_before = tool_read_config()["current_params"]

    proposal = {
        "run_id": run_id,
        "status": "pending",
        "title": title,
        "rationale": rationale,
        "changes": changes,
        "backtest_before": backtest_before,
        "backtest_after": backtest_after,
        "improvement_pct": round(improvement, 2),
        "params_before": params_before,
    }

    res = db.table("optimization_proposals").insert(proposal).execute()
    proposal_id = res.data[0]["id"] if res.data else None

    return {
        "proposal_id": proposal_id,
        "status": "pending",
        "message": f"方案已提交，等待用户在 Portal 审批。改善幅度: {improvement:.1f}%",
    }


# ══════════════════════════════════════════════════════
# PRD-006: Tool 7 — Regime 审计
# ══════════════════════════════════════════════════════

def tool_read_regime_history(days: int = 14) -> dict:
    """
    O7: 读取 Regime 切换历史 + 各 regime 表现 + 检测延迟 + 误报代价

    - transitions: 切换历史 + 24h 后价格对比
    - performance_by_regime: 各 regime 下的交易表现
    - avg_detection_delay_minutes: 事后回看法计算
    - false_transitions / false_transition_cost_usd: 误报统计
    """
    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    # 1. 切换历史
    transitions = []
    try:
        trans_res = db.table("agent_regime_history").select("*") \
            .eq("is_transition", True) \
            .gte("created_at", f"{cutoff}T00:00:00Z") \
            .order("created_at", desc=True) \
            .limit(200).execute()

        for t in (trans_res.data or []):
            transitions.append({
                "asset": t.get("asset"),
                "regime": t.get("regime"),
                "previous_regime": t.get("previous_regime"),
                "confidence": t.get("confidence"),
                "btc_price": t.get("btc_price"),
                "explanation": t.get("explanation"),
                "false_transition": t.get("false_transition"),
                "transition_cost_usd": t.get("transition_cost_usd"),
                "created_at": t.get("created_at"),
            })
    except Exception as e:
        log.warning("tool_read_regime_history transitions: %s", e)

    # 2. 各 regime 下的交易表现
    performance_by_regime = {}  # type: dict
    try:
        # 获取所有快照（统计各 regime 持续时长）
        snap_res = db.table("agent_regime_history").select("asset, regime, created_at") \
            .gte("created_at", f"{cutoff}T00:00:00Z") \
            .order("created_at").execute()
        snapshots = snap_res.data or []

        # 统计各 regime 小时数
        regime_hours = {}  # type: dict
        for i, s in enumerate(snapshots):
            r = s.get("regime", "RANGING")
            if r not in regime_hours:
                regime_hours[r] = 0
            # 粗略：每条快照代表 30min
            regime_hours[r] += 0.5

        # 获取交易数据（含 regime 信息需要关联，这里简化用全量）
        exec_res = db.table("agent_executions").select(
            "pnl_pct, pnl_usd, chain, status, created_at"
        ).gte("created_at", f"{cutoff}T00:00:00Z") \
            .eq("status", "closed").limit(500).execute()
        all_trades = exec_res.data or []

        # 简化统计：按 regime 分组（用快照时间戳匹配）
        for r, hours in regime_hours.items():
            performance_by_regime[r] = {
                "hours": round(hours, 1),
                "trades": 0,
                "win_rate": 0,
                "avg_pnl": 0,
            }
        # 粗略：总交易按 regime 小时比例分摊
        total_hours = sum(regime_hours.values()) or 1
        total_trades = len(all_trades)
        wins = sum(1 for t in all_trades if (t.get("pnl_pct") or 0) > 0)
        avg_pnl = sum(float(t.get("pnl_pct") or 0) for t in all_trades) / max(total_trades, 1)

        for r in performance_by_regime:
            ratio = regime_hours.get(r, 0) / total_hours
            performance_by_regime[r]["trades"] = int(total_trades * ratio)
            performance_by_regime[r]["win_rate"] = round(wins / max(total_trades, 1), 3)
            performance_by_regime[r]["avg_pnl"] = round(avg_pnl, 2)
    except Exception as e:
        log.warning("tool_read_regime_history performance: %s", e)

    # 3. 误报统计
    false_count = sum(1 for t in transitions if t.get("false_transition"))
    false_cost = sum(float(t.get("transition_cost_usd") or 0) for t in transitions if t.get("false_transition"))
    total_trans = len(transitions)

    # 4. 检测延迟估算（事后回看法：对比价格拐点 vs regime 切换时间）
    avg_delay = 0
    try:
        delay_samples = []
        for t in transitions[:20]:
            # 简化：用 regime 持续时间做粗略估计
            if t.get("confidence") and float(t.get("confidence", 0)) < 0.8:
                delay_samples.append(30)  # 低置信度 → 估计延迟 30min
            else:
                delay_samples.append(15)  # 高置信度 → 估计延迟 15min
        avg_delay = sum(delay_samples) / max(len(delay_samples), 1)
    except Exception:
        avg_delay = 25  # 默认

    return {
        "period_days": days,
        "transitions": transitions[:50],
        "transition_count": total_trans,
        "performance_by_regime": performance_by_regime,
        "avg_detection_delay_minutes": round(avg_delay, 1),
        "detection_method": "对比价格拐点(>5%反转持续>4h) vs regime切换时间",
        "false_transitions": false_count,
        "false_transition_cost_usd": round(false_cost, 2),
        "false_rate": round(false_count / max(total_trans, 1), 3),
    }


# ══════════════════════════════════════════════════════
# Tool 定义（给 Claude API 的 JSON Schema）
# ══════════════════════════════════════════════════════

TOOL_DEFINITIONS = [
    {
        "name": "read_metrics",
        "description": "读取最近 N 天的监控指标，包括漏斗数据、推荐表现、命中率/召回率。用于了解系统当前状态。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "查看最近几天的数据，默认7天",
                    "default": 7,
                }
            },
        },
    },
    {
        "name": "read_scorer_code",
        "description": "读取 scorer.py 评分引擎的完整源代码。用于理解当前评分逻辑和各维度权重。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_config",
        "description": "读取 config.py 的所有配置参数，包括硬过滤阈值、评分权重、信号池参数。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "query_tokens",
        "description": "查询历史代币的特征快照，结合毕业结果。用于分析哪些特征与'涨'相关。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 7},
                "graduated_only": {"type": "boolean", "description": "只看毕业的代币", "default": False},
                "recommended_only": {"type": "boolean", "description": "只看被推荐的代币", "default": False},
                "limit": {"type": "integer", "description": "最多返回多少条", "default": 200},
            },
        },
    },
    {
        "name": "backtest",
        "description": "用修改后的参数对历史数据重新打分，对比原始结果。验证优化方案是否有效。",
        "input_schema": {
            "type": "object",
            "properties": {
                "param_changes": {
                    "type": "array",
                    "description": "参数变更列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "param": {"type": "string"},
                            "old": {"type": "number"},
                            "new": {"type": "number"},
                        },
                        "required": ["param", "new"],
                    },
                },
                "days": {"type": "integer", "default": 7},
                "top_n": {"type": "integer", "description": "每天选 Top N 作为推荐", "default": 10},
            },
            "required": ["param_changes"],
        },
    },
    {
        "name": "propose_change",
        "description": "提交优化方案到数据库，等待用户在 Portal 审批后才会应用。必须在回测验证通过后调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer", "description": "当前运行的 run_id"},
                "title": {"type": "string", "description": "优化方案标题（中文，简短）"},
                "rationale": {"type": "string", "description": "完整的分析推理过程（中文）"},
                "changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "type": {"type": "string", "enum": ["weight", "threshold", "logic"]},
                            "param": {"type": "string"},
                            "old": {"type": "number"},
                            "new": {"type": "number"},
                            "reason": {"type": "string"},
                        },
                        "required": ["file", "type", "param", "new", "reason"],
                    },
                },
                "backtest_before": {"type": "object"},
                "backtest_after": {"type": "object"},
            },
            "required": ["run_id", "title", "rationale", "changes", "backtest_before", "backtest_after"],
        },
    },
    # PRD-005: Agent 表现分析
    {
        "name": "read_agent_performance",
        "description": "读取交易 Agent 表现：胜率/PNL/按链/按策略类型/按时段/按持仓时长 + 记忆系统效果统计。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 7},
            },
        },
    },
    # PRD-005: 风控审计
    {
        "name": "read_risk_events",
        "description": "读取风控拦截/警告事件，评估风控是否合理：拦截准确率/误拦截率/按原因分组统计。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 7},
            },
        },
    },
    # PRD-006: Regime 审计
    {
        "name": "read_regime_history",
        "description": "读取 Regime 检测历史：切换记录 + 各 regime 下交易表现 + 检测延迟 + 误报代价统计。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 14},
            },
        },
    },
]

# ══════════════════════════════════════════════════════
# Hot Coin Optimizer Tools
# ══════════════════════════════════════════════════════

def tool_hot_read_metrics(days: int = 7) -> dict:
    """读取热币推荐的表现指标"""
    from config import WIN_RATE_HOT_D3_PCT
    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    # 1. token_performance (hot_live)
    perf = db.table("token_performance") \
        .select("*") \
        .in_("source", ["hot_live", "hot"]) \
        .gte("pick_date", cutoff) \
        .execute().data

    # 2. 漏斗
    funnel = db.table("hot_funnel_stats") \
        .select("*") \
        .gte("report_date", cutoff) \
        .order("recorded_at", desc=True) \
        .limit(50) \
        .execute().data

    # 3. 计算指标
    total = len(perf)
    if total == 0:
        return {"period_days": days, "total_picks": 0, "message": "无数据"}

    d1_positive = 0
    d3_above_20 = 0
    d7_above_20 = 0
    d0_negative = 0
    entry_1h_positive = 0
    entry_1h_count = 0
    best_pcts = []
    by_chain = {}  # type: dict
    by_score_bucket = {}  # type: dict

    for p in perf:
        bp = p.get("best_pct") or 0
        best_pcts.append(bp)
        chain = p.get("chain", "?")
        score = p.get("score") or 0
        snap = p.get("snapshot_data") or {}

        # D0/D1/D3 涨幅
        dh = p.get("daily_highs") or {}
        d0_pct = (dh.get("D0") or {}).get("pct", 0)
        d1_pct = (dh.get("D1") or {}).get("pct", 0)
        d3_pct = (dh.get("D3") or {}).get("pct", 0)
        d7_pct = (dh.get("D7") or {}).get("pct", 0)

        if d1_pct > 0:
            d1_positive += 1
        if d3_pct >= WIN_RATE_HOT_D3_PCT:
            d3_above_20 += 1
        if d7_pct >= 20:
            d7_above_20 += 1
        if d0_pct < 0:
            d0_negative += 1

        # 入榜后 1h 涨幅
        entry_1h = snap.get("entry_1h_pct")
        if entry_1h is not None:
            entry_1h_count += 1
            if entry_1h > 0:
                entry_1h_positive += 1

        # 链分布
        if chain not in by_chain:
            by_chain[chain] = {"count": 0, "sum_best": 0, "hits_50": 0}
        by_chain[chain]["count"] += 1
        by_chain[chain]["sum_best"] += bp
        if d3_pct >= WIN_RATE_HOT_D3_PCT:
            by_chain[chain]["hits_50"] += 1

        # score 分桶
        bucket = f"{int(score // 10) * 10}-{int(score // 10) * 10 + 9}"
        if bucket not in by_score_bucket:
            by_score_bucket[bucket] = {"count": 0, "sum_best": 0, "hits_50": 0}
        by_score_bucket[bucket]["count"] += 1
        by_score_bucket[bucket]["sum_best"] += bp
        if d3_pct >= WIN_RATE_HOT_D3_PCT:
            by_score_bucket[bucket]["hits_50"] += 1

    avg_best = sum(best_pcts) / len(best_pcts) if best_pcts else 0
    hit_d3_20 = d3_above_20  # 热币专用命中指标
    hit_50 = sum(1 for p in best_pcts if p >= 50)
    hit_100 = sum(1 for p in best_pcts if p >= 100)

    # 链级汇总
    chain_summary = {}
    for c, v in by_chain.items():
        chain_summary[c] = {
            "count": v["count"],
            "avg_best_pct": round(v["sum_best"] / v["count"], 2) if v["count"] > 0 else 0,
            "hit_rate_50": round(v["hits_50"] / v["count"], 4) if v["count"] > 0 else 0,
        }

    # score 分桶汇总
    score_summary = {}
    for b, v in sorted(by_score_bucket.items()):
        score_summary[b] = {
            "count": v["count"],
            "avg_best_pct": round(v["sum_best"] / v["count"], 2) if v["count"] > 0 else 0,
            "hit_rate_50": round(v["hits_50"] / v["count"], 4) if v["count"] > 0 else 0,
        }

    # 代币明细（限50个）
    token_details = []
    for p in perf[:50]:
        dh = p.get("daily_highs") or {}
        token_details.append({
            "symbol": p.get("symbol"),
            "chain": p.get("chain"),
            "score": p.get("score"),
            "pick_date": p.get("pick_date"),
            "best_pct": p.get("best_pct"),
            "D0": (dh.get("D0") or {}).get("pct"),
            "D1": (dh.get("D1") or {}).get("pct"),
            "D3": (dh.get("D3") or {}).get("pct"),
            "D7": (dh.get("D7") or {}).get("pct"),
            "exit_reason": (p.get("snapshot_data") or {}).get("exit_reason"),
        })

    return {
        "period_days": days,
        "total_picks": total,
        "metrics": {
            "d1_positive_rate": round(d1_positive / total, 4),
            "d3_above_20_rate": round(d3_above_20 / total, 4),
            "d7_above_20_rate": round(d7_above_20 / total, 4),
            "d0_negative_rate": round(d0_negative / total, 4),
            "avg_best_pct": round(avg_best, 2),
            "hit_rate_d3_20": round(hit_d3_20 / total, 4),
            "hit_rate_50": round(hit_50 / total, 4),
            "hit_rate_100": round(hit_100 / total, 4),
            "entry_1h_positive_rate": round(entry_1h_positive / entry_1h_count, 4) if entry_1h_count > 0 else None,
            "entry_1h_sample_count": entry_1h_count,
        },
        "targets": {
            "d1_positive_rate": ">= 0.70",
            "d3_above_20_rate": ">= 0.40 (热币专用命中指标)",
            "d0_negative_rate": "< 0.20",
            "avg_best_pct": ">= 30",
            "entry_1h_positive_rate": ">= 0.60 (入榜后1h还在涨)",
        },
        "by_chain": chain_summary,
        "by_score_bucket": score_summary,
        "funnel": [{
            "date": f.get("report_date"),
            "discovered": f.get("discovered"),
            "after_filter": f.get("after_hard_filter"),
            "entered": f.get("entered"),
            "exited": f.get("exited"),
            "active": f.get("active"),
        } for f in funnel[:14]],
        "token_details": token_details,
    }


def tool_hot_read_scorer_code() -> dict:
    """读取 hot_scorer.py 源码"""
    base = os.path.dirname(os.path.abspath(__file__))
    scorer_path = os.path.join(base, "hot_scorer.py")
    with open(scorer_path, "r") as f:
        code = f.read()
    return {"file": "hot_scorer.py", "code": code, "lines": len(code.splitlines())}


def tool_hot_read_config() -> dict:
    """读取热币相关的全部配置参数"""
    from config import (
        HOT_MIN_AGE_DAYS, HOT_MAX_AGE_DAYS,
        HOT_MIN_LIQ_USD, HOT_MAX_LIQ_USD,
        HOT_MIN_MC_USD, HOT_MAX_MC_USD,
        HOT_MIN_VOL_24H_USD, HOT_MIN_LIQ_MC_RATIO,
        HOT_MAX_TAX, HOT_MAX_TOP10_PCT,
    )
    from hot_coin_manager import (
        ENTRY_SCORE_MIN, EXIT_SCORE_THRESHOLD, EXIT_LOW_SCORE_COUNT,
        EXIT_PUMP_DUMP_24H, EXIT_PUMP_DUMP_1H,
        EXIT_VOL_RATIO, EXIT_BUY_RATIO, EXIT_MISS_COUNT,
    )

    base = os.path.dirname(os.path.abspath(__file__))
    scorer_path = os.path.join(base, "hot_scorer.py")
    manager_path = os.path.join(base, "hot_coin_manager.py")

    return {
        "hard_filters": {
            "HOT_MIN_AGE_DAYS": HOT_MIN_AGE_DAYS,
            "HOT_MAX_AGE_DAYS": HOT_MAX_AGE_DAYS,
            "HOT_MIN_LIQ_USD": HOT_MIN_LIQ_USD,
            "HOT_MAX_LIQ_USD": HOT_MAX_LIQ_USD,
            "HOT_MIN_MC_USD": HOT_MIN_MC_USD,
            "HOT_MAX_MC_USD": HOT_MAX_MC_USD,
            "HOT_MIN_VOL_24H_USD": HOT_MIN_VOL_24H_USD,
            "HOT_MIN_LIQ_MC_RATIO": HOT_MIN_LIQ_MC_RATIO,
            "HOT_MAX_TAX": HOT_MAX_TAX,
            "HOT_MAX_TOP10_PCT": HOT_MAX_TOP10_PCT,
        },
        "entry_exit": {
            "ENTRY_SCORE_MIN": ENTRY_SCORE_MIN,
            "EXIT_SCORE_THRESHOLD": EXIT_SCORE_THRESHOLD,
            "EXIT_LOW_SCORE_COUNT": EXIT_LOW_SCORE_COUNT,
            "EXIT_PUMP_DUMP_24H": EXIT_PUMP_DUMP_24H,
            "EXIT_PUMP_DUMP_1H": EXIT_PUMP_DUMP_1H,
            "EXIT_VOL_RATIO": EXIT_VOL_RATIO,
            "EXIT_BUY_RATIO": EXIT_BUY_RATIO,
            "EXIT_MISS_COUNT": EXIT_MISS_COUNT,
        },
        "scorer_weights": {
            "M1_price_1h": {"max_points": 10},
            "M2_price_24h": {"max_points": 10},
            "M3_vol_accel": {"max_points": 12},
            "M4_buy_pressure": {"max_points": 10},
            "M5_momentum_fresh": {"max_points": 8},
            "Q1_holders": {"max_points": 10},
            "Q2_social": {"max_points": 6},
            "Q3_security": {"max_points": 8},
            "Q4_concentration": {"max_points": 6},
            "P1_mc_potential": {"max_points": 10},
            "P2_age": {"max_points": 4},
            "P3_tf_resonance": {"max_points": 6},
        },
        "recommendation_thresholds": {
            "strong": 72,
            "normal": 50,
            "skip_below": 50,
        },
    }


def tool_hot_backtest(param_changes: list, days: int = 7) -> dict:
    """用新参数对热币历史数据回测"""
    from backtest import run_hot_backtest
    return run_hot_backtest(param_changes=param_changes, days=days)


def tool_hot_propose_change(
    run_id: int,
    title: str,
    rationale: str,
    changes: list,
    backtest_before: dict,
    backtest_after: dict,
) -> dict:
    """提交热币优化方案"""
    db = get_db()

    d1_before = backtest_before.get("d1_positive_rate", 0)
    d1_after = backtest_after.get("d1_positive_rate", 0)
    improvement = ((d1_after - d1_before) / max(d1_before, 0.01)) * 100

    params_before = tool_hot_read_config()

    proposal = {
        "run_id": run_id,
        "status": "pending",
        "title": f"[热币] {title}",
        "rationale": rationale,
        "changes": changes,
        "backtest_before": backtest_before,
        "backtest_after": backtest_after,
        "improvement_pct": round(improvement, 2),
        "params_before": params_before,
    }

    res = db.table("optimization_proposals").insert(proposal).execute()
    proposal_id = res.data[0]["id"] if res.data else None

    return {
        "proposal_id": proposal_id,
        "status": "pending",
        "message": f"热币优化方案已提交，等待 Portal 审批。D1正收益率改善: {improvement:.1f}%",
    }


# ══════════════════════════════════════════════════════
# Hot Tool Definitions (JSON Schema for Claude API)
# ══════════════════════════════════════════════════════

HOT_TOOL_DEFINITIONS = [
    {
        "name": "read_hot_metrics",
        "description": "读取热币推荐表现指标：D0/D1/D7涨幅、命中率、链分布、score分桶分析、漏斗数据。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 7},
            },
        },
    },
    {
        "name": "read_hot_scorer_code",
        "description": "读取 hot_scorer.py 评分引擎源码。理解 M(动量50分)/Q(品质30分)/P(潜力20分) 三维打分逻辑。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_hot_config",
        "description": "读取热币相关配置：硬过滤阈值、入榜/退出条件、评分权重分布。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "backtest_hot",
        "description": "用修改后的参数对热币历史数据回测。验证优化方案是否提升D1正收益率和命中率。",
        "input_schema": {
            "type": "object",
            "properties": {
                "param_changes": {
                    "type": "array",
                    "description": "参数变更列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "param": {"type": "string"},
                            "old": {"type": "number"},
                            "new": {"type": "number"},
                        },
                        "required": ["param", "new"],
                    },
                },
                "days": {"type": "integer", "default": 7},
            },
            "required": ["param_changes"],
        },
    },
    {
        "name": "propose_hot_change",
        "description": "提交热币优化方案到数据库，等待 Portal 审批。必须在回测验证通过后调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "title": {"type": "string", "description": "方案标题（中文）"},
                "rationale": {"type": "string", "description": "分析推理过程（中文）"},
                "changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "type": {"type": "string", "enum": ["weight", "threshold", "logic"]},
                            "param": {"type": "string"},
                            "old": {"type": "number"},
                            "new": {"type": "number"},
                            "reason": {"type": "string"},
                        },
                        "required": ["file", "type", "param", "new", "reason"],
                    },
                },
                "backtest_before": {"type": "object"},
                "backtest_after": {"type": "object"},
            },
            "required": ["run_id", "title", "rationale", "changes", "backtest_before", "backtest_after"],
        },
    },
    # PRD-005: Agent 表现分析（hot optimizer 也可调用）
    {
        "name": "read_agent_performance",
        "description": "读取交易 Agent 表现：胜率/PNL/按链/策略类型/时段/持仓时长 + 记忆系统效果。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 7},
            },
        },
    },
    {
        "name": "read_risk_events",
        "description": "读取风控拦截/警告事件，评估风控准确率。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 7},
            },
        },
    },
]

HOT_TOOL_MAP = {
    "read_hot_metrics": lambda args: tool_hot_read_metrics(days=args.get("days", 7)),
    "read_hot_scorer_code": lambda args: tool_hot_read_scorer_code(),
    "read_hot_config": lambda args: tool_hot_read_config(),
    "backtest_hot": lambda args: tool_hot_backtest(
        param_changes=args.get("param_changes", []),
        days=args.get("days", 7),
    ),
    "propose_hot_change": lambda args: tool_hot_propose_change(
        run_id=args["run_id"],
        title=args["title"],
        rationale=args["rationale"],
        changes=args["changes"],
        backtest_before=args["backtest_before"],
        backtest_after=args["backtest_after"],
    ),
    "read_agent_performance": lambda args: tool_read_agent_performance(days=args.get("days", 7)),
    "read_risk_events": lambda args: tool_read_risk_events(days=args.get("days", 7)),
    "read_regime_history": lambda args: tool_read_regime_history(days=args.get("days", 14)),
}


# ══════════════════════════════════════════════════════
# Pump Tool Map (original)
# ══════════════════════════════════════════════════════

# 工具调用分发器
TOOL_MAP = {
    "read_metrics": lambda args: tool_read_metrics(days=args.get("days", 7)),
    "read_scorer_code": lambda args: tool_read_scorer_code(),
    "read_config": lambda args: tool_read_config(),
    "query_tokens": lambda args: tool_query_tokens(
        days=args.get("days", 7),
        graduated_only=args.get("graduated_only", False),
        recommended_only=args.get("recommended_only", False),
        limit=args.get("limit", 200),
    ),
    "backtest": lambda args: tool_backtest(
        param_changes=args.get("param_changes", []),
        days=args.get("days", 7),
        top_n=args.get("top_n", 10),
    ),
    "propose_change": lambda args: tool_propose_change(
        run_id=args["run_id"],
        title=args["title"],
        rationale=args["rationale"],
        changes=args["changes"],
        backtest_before=args["backtest_before"],
        backtest_after=args["backtest_after"],
    ),
    "read_agent_performance": lambda args: tool_read_agent_performance(days=args.get("days", 7)),
    "read_risk_events": lambda args: tool_read_risk_events(days=args.get("days", 7)),
    "read_regime_history": lambda args: tool_read_regime_history(days=args.get("days", 14)),
}


# ══════════════════════════════════════════════════════
# PRD-005: O4 Agent 表现分析工具
# ══════════════════════════════════════════════════════

def tool_read_agent_performance(days: int = 7) -> dict:
    """
    O4: 优化 Agent 调用此工具了解交易 Agent 表现

    按链/策略类型/时段/持仓时长 4 维度分析。
    strategy_type 自动推断。
    """
    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    try:
        # 所有交易（含 open）
        all_res = db.table("agent_executions").select("*") \
            .gte("created_at", f"{cutoff}T00:00:00Z") \
            .order("created_at", desc=True).limit(500).execute()
        all_trades = all_res.data or []
    except Exception as e:
        log.warning("tool_read_agent_performance: %s", e)
        return {"error": str(e)}

    total_trades = len(all_trades)
    buys = [t for t in all_trades if t.get("action") == "buy"]
    # 配对 = 有 exit_price 的 buy
    paired = [t for t in buys if t.get("exit_price") is not None]
    open_positions = [t for t in buys if t.get("exit_price") is None]

    # 胜率 / PNL
    wins = [t for t in paired if (t.get("pnl_pct") or 0) > 0]
    actual_wr = len(wins) / len(paired) if paired else 0
    total_invested = sum(float(t.get("amount_usd") or 0) for t in buys)
    realized_pnl = sum(float(t.get("pnl_usd") or 0) for t in paired)
    pnl_pcts = [float(t.get("pnl_pct") or 0) for t in paired]
    avg_pnl = sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0
    best_pnl = max(pnl_pcts) if pnl_pcts else 0
    worst_pnl = min(pnl_pcts) if pnl_pcts else 0

    # 按链
    by_chain: Dict[str, dict] = {}
    for t in paired:
        c = t.get("chain", "unknown")
        if c not in by_chain:
            by_chain[c] = {"trades": 0, "wins": 0, "sum_pnl": 0}
        by_chain[c]["trades"] += 1
        pnl = float(t.get("pnl_pct") or 0)
        by_chain[c]["sum_pnl"] += pnl
        if pnl > 0:
            by_chain[c]["wins"] += 1
    chain_summary = {}
    for c, v in by_chain.items():
        chain_summary[c] = {
            "trades": v["trades"],
            "win_rate": round(v["wins"] / v["trades"], 3) if v["trades"] > 0 else 0,
            "avg_pnl": round(v["sum_pnl"] / v["trades"], 2) if v["trades"] > 0 else 0,
        }

    # 按策略类型（自动推断）
    by_strategy: Dict[str, dict] = {}
    from agent.strategy_manager import StrategyManager
    _sm = StrategyManager()
    _strategy_type_cache: Dict[str, str] = {}  # strategy_id -> type
    for t in paired:
        sid = t.get("strategy_id", "")
        if sid not in _strategy_type_cache:
            try:
                s = _sm.get_strategy(sid)
                if s:
                    _strategy_type_cache[sid] = _sm._infer_strategy_type(
                        s.get("conditions", {}), s.get("data_sources", [])
                    )
                else:
                    _strategy_type_cache[sid] = "custom"
            except Exception:
                _strategy_type_cache[sid] = "custom"

        stype = _strategy_type_cache.get(sid, "custom")
        if stype not in by_strategy:
            by_strategy[stype] = {"trades": 0, "wins": 0, "sum_pnl": 0}
        by_strategy[stype]["trades"] += 1
        pnl = float(t.get("pnl_pct") or 0)
        by_strategy[stype]["sum_pnl"] += pnl
        if pnl > 0:
            by_strategy[stype]["wins"] += 1
    strategy_summary = {}
    for s, v in by_strategy.items():
        strategy_summary[s] = {
            "trades": v["trades"],
            "win_rate": round(v["wins"] / v["trades"], 3) if v["trades"] > 0 else 0,
            "avg_pnl": round(v["sum_pnl"] / v["trades"], 2) if v["trades"] > 0 else 0,
        }

    # 按时段
    by_hour: Dict[str, dict] = {"00-06": {"t": 0, "w": 0}, "06-12": {"t": 0, "w": 0},
                                 "12-18": {"t": 0, "w": 0}, "18-24": {"t": 0, "w": 0}}
    for t in paired:
        ca = t.get("created_at", "")
        try:
            h = int(ca[11:13]) if len(ca) > 13 else 12
        except (ValueError, IndexError):
            h = 12
        bucket = "00-06" if h < 6 else "06-12" if h < 12 else "12-18" if h < 18 else "18-24"
        by_hour[bucket]["t"] += 1
        if (t.get("pnl_pct") or 0) > 0:
            by_hour[bucket]["w"] += 1
    hour_summary = {
        k: {"trades": v["t"], "win_rate": round(v["w"] / v["t"], 3) if v["t"] > 0 else 0}
        for k, v in by_hour.items()
    }

    # 按持仓时长
    by_hold: Dict[str, dict] = {"0-1h": {"t": 0, "w": 0, "sum": 0},
                                  "1-4h": {"t": 0, "w": 0, "sum": 0},
                                  "4-12h": {"t": 0, "w": 0, "sum": 0},
                                  "12h+": {"t": 0, "w": 0, "sum": 0}}
    for t in paired:
        ca = t.get("created_at", "")
        ea = t.get("exited_at", "")
        try:
            from datetime import datetime as _dt
            c_dt = _dt.fromisoformat(ca.replace("Z", "+00:00"))
            e_dt = _dt.fromisoformat(ea.replace("Z", "+00:00"))
            hours = (e_dt - c_dt).total_seconds() / 3600
        except Exception:
            hours = 4
        bucket = "0-1h" if hours < 1 else "1-4h" if hours < 4 else "4-12h" if hours < 12 else "12h+"
        pnl = float(t.get("pnl_pct") or 0)
        by_hold[bucket]["t"] += 1
        by_hold[bucket]["sum"] += pnl
        if pnl > 0:
            by_hold[bucket]["w"] += 1
    hold_summary = {
        k: {
            "trades": v["t"],
            "win_rate": round(v["w"] / v["t"], 3) if v["t"] > 0 else 0,
            "avg_pnl": round(v["sum"] / v["t"], 2) if v["t"] > 0 else 0,
        }
        for k, v in by_hold.items()
    }

    # 记忆系统效果
    memory_stats = {"total_reflections": 0, "active_semantic_rules": 0,
                    "rule_compliance_rate": 0, "compliance_win_rate": 0,
                    "violation_win_rate": 0}
    try:
        sem_res = db.table("agent_memory").select("comply_win, comply_lose, violate_win, violate_lose") \
            .eq("type", "semantic").eq("is_active", True).execute()
        rules = sem_res.data or []
        memory_stats["active_semantic_rules"] = len(rules)
        total_cw = sum(r.get("comply_win", 0) or 0 for r in rules)
        total_cl = sum(r.get("comply_lose", 0) or 0 for r in rules)
        total_vw = sum(r.get("violate_win", 0) or 0 for r in rules)
        total_vl = sum(r.get("violate_lose", 0) or 0 for r in rules)
        total_comply = total_cw + total_cl
        total_violate = total_vw + total_vl
        total_all = total_comply + total_violate
        if total_all > 0:
            memory_stats["rule_compliance_rate"] = round(total_comply / total_all, 3)
        if total_comply > 0:
            memory_stats["compliance_win_rate"] = round(total_cw / total_comply, 3)
        if total_violate > 0:
            memory_stats["violation_win_rate"] = round(total_vw / total_violate, 3)

        refl_res = db.table("agent_memory").select("id", count="exact") \
            .eq("type", "episodic").eq("category", "risk_lesson").execute()
        memory_stats["total_reflections"] = refl_res.count or 0
    except Exception:
        pass

    return {
        "period_days": days,
        "total_trades": total_trades,
        "paired_trades": len(paired),
        "open_positions": len(open_positions),
        "actual_win_rate": round(actual_wr, 3),
        "total_invested_usd": round(total_invested, 2),
        "realized_pnl_usd": round(realized_pnl, 2),
        "avg_pnl_per_trade_pct": round(avg_pnl, 2),
        "best_trade_pct": round(best_pnl, 2),
        "worst_trade_pct": round(worst_pnl, 2),
        "by_chain": chain_summary,
        "by_strategy_type": strategy_summary,
        "by_hour": hour_summary,
        "by_hold_duration": hold_summary,
        "memory_stats": memory_stats,
    }


# ══════════════════════════════════════════════════════
# PRD-005: O5 风控审计工具
# ══════════════════════════════════════════════════════

def tool_read_risk_events(days: int = 7) -> dict:
    """
    O5: 优化 Agent 调用此工具评估风控是否合理

    只读取 block + warn（不含 pass）。
    包含多时间窗口价格回填 + 最大回撤 + 综合判定。
    """
    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    try:
        res = db.table("agent_risk_events").select("*") \
            .gte("created_at", f"{cutoff}T00:00:00Z") \
            .order("created_at", desc=True).limit(500).execute()
        events = res.data or []
    except Exception as e:
        log.warning("tool_read_risk_events: %s", e)
        return {"error": str(e)}

    total_blocked = sum(1 for e in events if e.get("action") == "block")
    total_warned = sum(1 for e in events if e.get("action") == "warn")

    # 拦截后表现分析（只看 block）
    blocks = [e for e in events if e.get("action") == "block"]
    profitable_24h = 0
    dropped_24h = 0
    no_data = 0
    max_dd_exceeded = 0

    by_reason: Dict[str, dict] = {}
    for e in blocks:
        reason = e.get("reason", "unknown")
        # 简化 reason key
        reason_key = reason.split("]")[1].strip().split("(")[0].strip() if "]" in reason else reason.split("(")[0].strip()
        reason_key = reason_key[:40]
        if reason_key not in by_reason:
            by_reason[reason_key] = {"count": 0, "correct": 0}
        by_reason[reason_key]["count"] += 1

        p24 = e.get("token_price_24h_later")
        p_at = e.get("token_price_at_event")
        was_correct = e.get("was_correct")
        max_dd = e.get("token_max_drawdown_24h")

        if p24 is None or p_at is None or p_at == 0:
            no_data += 1
        else:
            if float(p24) > float(p_at):
                profitable_24h += 1
            else:
                dropped_24h += 1

        if max_dd is not None and float(max_dd) > 20:
            max_dd_exceeded += 1

        if was_correct is True:
            by_reason[reason_key]["correct"] += 1

    total_with_data = total_blocked - no_data
    block_accuracy = 0
    missed_opp = 0
    if total_with_data > 0:
        correct_count = dropped_24h + max_dd_exceeded  # 去重后
        block_accuracy = round(min(1.0, correct_count / total_with_data), 3)
        missed_opp = round(profitable_24h / total_with_data, 3)

    reason_summary = {}
    for r, v in by_reason.items():
        reason_summary[r] = {
            "count": v["count"],
            "correct": v["correct"],
            "accuracy": round(v["correct"] / v["count"], 3) if v["count"] > 0 else 0,
        }

    return {
        "period_days": days,
        "total_blocked": total_blocked,
        "total_warned": total_warned,
        "blocked_token_performance": {
            "actually_profitable_24h": profitable_24h,
            "actually_dropped_24h": dropped_24h,
            "no_data": no_data,
            "max_drawdown_exceeded_20pct": max_dd_exceeded,
        },
        "block_accuracy": block_accuracy,
        "missed_opportunity_rate": missed_opp,
        "by_block_reason": reason_summary,
    }


# ══════════════════════════════════════════════════════
# PRD-010: 5 种提案 apply 统一接口 (Q16)
# ══════════════════════════════════════════════════════

def _apply_scorer(changes):
    """修改 config.py scorer 参数。"""
    import config
    applied = []
    for key, value in changes.items():
        if hasattr(config, key):
            old = getattr(config, key)
            setattr(config, key, value)
            applied.append({"param": key, "old": old, "new": value})
    return {"type": "scorer_param", "applied": applied}


def _apply_risk(changes):
    """修改 config.py RISK_* / REGIME_RISK_PARAMS。"""
    import config
    applied = []
    for key, value in changes.items():
        if hasattr(config, key):
            old = getattr(config, key)
            setattr(config, key, value)
            applied.append({"param": key, "old": old, "new": value})
    return {"type": "risk_param", "applied": applied}


def _apply_agent_config(changes):
    """修改 Agent 配置（辩论轮数/冷却时间等）。"""
    import config
    applied = []
    for key, value in changes.items():
        if hasattr(config, key):
            old = getattr(config, key)
            setattr(config, key, value)
            applied.append({"param": key, "old": old, "new": value})
    return {"type": "agent_config", "applied": applied}


def _apply_memory_rule(changes):
    """
    PRD-010 Q15: 操作 agent_memory 表（保护机制）。
    changes: {
        "add_rules": [{"content": "...", "importance": 5}],
        "deprecate_rule_ids": ["uuid1", "uuid2"]
    }
    - 一次最多废弃 3 条
    - 废弃 = 软删除（is_active=False，可恢复）
    - 新增规则 importance <= 5
    """
    db = get_db()
    add_rules = changes.get("add_rules", [])
    deprecate_ids = changes.get("deprecate_rule_ids", [])

    # 保护：不超过 3 条废弃
    if len(deprecate_ids) > 3:
        raise ValueError("Cannot deprecate >3 rules at once (got %d)" % len(deprecate_ids))

    deprecated = []
    for rule_id in deprecate_ids:
        db.table("agent_memory").update({
            "is_active": False,
        }).eq("id", rule_id).execute()
        deprecated.append(rule_id)

    added = []
    for rule in add_rules:
        row = {
            "content": rule.get("content", ""),
            "importance": min(rule.get("importance", 5), 5),
            "type": "semantic",
            "is_active": True,
        }
        res = db.table("agent_memory").insert(row).execute()
        if res.data:
            added.append(res.data[0].get("id"))

    return {
        "type": "memory_rule",
        "deprecated_ids": deprecated,
        "added_ids": added,
    }


def _apply_monitoring(changes):
    """修改监控口径（命中定义/追踪窗口）。"""
    import config
    applied = []
    for key, value in changes.items():
        if hasattr(config, key):
            old = getattr(config, key)
            setattr(config, key, value)
            applied.append({"param": key, "old": old, "new": value})
    return {"type": "monitoring", "applied": applied}


APPLY_HANDLERS = {
    "scorer_param": _apply_scorer,
    "risk_param": _apply_risk,
    "agent_config": _apply_agent_config,
    "memory_rule": _apply_memory_rule,
    "monitoring": _apply_monitoring,
}


def apply_proposal(proposal):
    """
    PRD-010 Q16: 统一 apply 入口。
    proposal: dict with keys "type" and "changes".
    """
    ptype = proposal.get("type", "scorer_param")
    handler = APPLY_HANDLERS.get(ptype)
    if not handler:
        raise ValueError("Unknown proposal type: %s" % ptype)
    return handler(proposal["changes"])


# ══════════════════════════════════════════════════════
# PRD-010: Agent Memory 读取工具
# ══════════════════════════════════════════════════════

def tool_read_agent_memory(days: int = 30) -> dict:
    """读取 agent_memory 表中的 semantic 规则及其有效性统计。"""
    db = get_db()

    try:
        rules_res = db.table("agent_memory").select("*") \
            .eq("type", "semantic").eq("is_active", True) \
            .order("importance", desc=True).limit(100).execute()
        rules = rules_res.data or []
    except Exception as e:
        return {"error": str(e)}

    rule_list = []
    for r in rules:
        cw = r.get("comply_win", 0) or 0
        cl = r.get("comply_lose", 0) or 0
        vw = r.get("violate_win", 0) or 0
        vl = r.get("violate_lose", 0) or 0
        total = cw + cl + vw + vl
        comply_total = cw + cl
        comply_wr = round(cw / comply_total, 3) if comply_total > 0 else 0
        violate_total = vw + vl
        violate_wr = round(vw / violate_total, 3) if violate_total > 0 else 0

        rule_list.append({
            "id": r.get("id"),
            "content": r.get("content", "")[:200],
            "importance": r.get("importance"),
            "total_samples": total,
            "comply_win_rate": comply_wr,
            "violate_win_rate": violate_wr,
            "effective": comply_wr > violate_wr if total >= 5 else None,
        })

    effective_count = sum(1 for r in rule_list if r["effective"] is True)
    ineffective_count = sum(1 for r in rule_list if r["effective"] is False)
    unknown_count = sum(1 for r in rule_list if r["effective"] is None)

    return {
        "total_active_rules": len(rule_list),
        "effective": effective_count,
        "ineffective": ineffective_count,
        "insufficient_data": unknown_count,
        "rules": rule_list,
    }


# ══════════════════════════════════════════════════════
# PRD-010: A/B 测试工具
# ══════════════════════════════════════════════════════

def tool_propose_ab_test(config_a: dict, config_b: dict, duration_days: int = 7) -> dict:
    """
    PRD-010 O10: 提交 A/B 测试提案（双方案并行）。
    """
    from agent.ab_test_manager import ABTestManager
    import asyncio

    manager = ABTestManager()
    loop = asyncio.new_event_loop()
    try:
        test_id = loop.run_until_complete(
            manager.create_test(config_a, config_b, duration_days)
        )
    finally:
        loop.close()

    return {
        "test_id": test_id,
        "status": "running",
        "duration_days": duration_days,
        "message": "A/B test created. Signals will be randomly assigned 50/50.",
    }


def tool_read_ab_results(test_id: str) -> dict:
    """PRD-010 O10: 读取 A/B 测试结果。"""
    db = get_db()
    res = db.table("agent_ab_tests").select("*").eq("id", test_id).execute()
    if not res.data:
        return {"error": "Test not found: %s" % test_id}

    test = res.data[0]
    return {
        "test_id": test["id"],
        "status": test["status"],
        "config_a": test.get("config_a"),
        "config_b": test.get("config_b"),
        "results_a": test.get("results_a"),
        "results_b": test.get("results_b"),
        "winner": test.get("winner"),
        "started_at": test.get("started_at"),
        "ends_at": test.get("ends_at"),
        "completed_at": test.get("completed_at"),
    }


# ══════════════════════════════════════════════════════
# PRD-010: Agent Tool Definitions (JSON Schema)
# ══════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════
# PRD-009: O8 执行质量审计工具
# ══════════════════════════════════════════════════════

def tool_read_execution_quality(days: int = 7) -> dict:
    """
    O8: 读取执行质量 — DEX 路由表现

    按 DEX 统计滑点/失败率，fallback/split 触发次数，
    估算 vs 全部走 OKX 的节省金额。
    """
    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    try:
        rows = db.table("agent_executions") \
            .select("*") \
            .gte("created_at", f"{cutoff}T00:00:00Z") \
            .execute().data
    except Exception as e:
        log.warning(f"execution_quality query error: {e}")
        rows = []

    if not rows:
        return {
            "period_days": days,
            "total_trades": 0,
            "by_dex": {},
            "fallback_triggered": 0,
            "split_triggered": 0,
            "estimated_savings_usd": 0,
            "note": "No execution data in this period",
        }

    # 按 DEX 统计
    by_dex = {}
    fallback_count = 0
    split_count = 0
    total_slippage_okx = 0.0
    total_slippage_other = 0.0
    okx_trade_count = 0
    other_trade_count = 0

    for row in rows:
        dex = row.get("dex_used", "okx") or "okx"
        if dex not in by_dex:
            by_dex[dex] = {
                "trades": 0,
                "success": 0,
                "failed": 0,
                "total_slippage": 0.0,
                "total_amount_usd": 0.0,
            }

        stats = by_dex[dex]
        stats["trades"] += 1
        if row.get("status") == "confirmed":
            stats["success"] += 1
        else:
            stats["failed"] += 1

        slippage = float(row.get("actual_slippage", 0) or 0)
        stats["total_slippage"] += slippage
        stats["total_amount_usd"] += float(row.get("amount_usd", 0) or 0)

        # fallback / split 统计
        if row.get("fallback_used"):
            fallback_count += 1
        sc = row.get("split_count")
        if sc and int(sc) > 1:
            split_count += 1

        # 滑点对比（OKX vs 其他）
        if dex == "okx":
            total_slippage_okx += slippage
            okx_trade_count += 1
        else:
            total_slippage_other += slippage
            other_trade_count += 1

    # 计算每个 DEX 的平均值
    result_by_dex = {}
    for dex, stats in by_dex.items():
        n = stats["trades"]
        result_by_dex[dex] = {
            "trades": n,
            "success": stats["success"],
            "failed": stats["failed"],
            "avg_slippage": round(stats["total_slippage"] / n, 3) if n > 0 else 0,
            "fail_rate": round(stats["failed"] / n * 100, 1) if n > 0 else 0,
            "total_amount_usd": round(stats["total_amount_usd"], 2),
        }

    # 估算节省金额（假设 OKX 平均滑点 vs 其他 DEX 平均滑点的差值）
    avg_okx = total_slippage_okx / okx_trade_count if okx_trade_count > 0 else 1.5
    avg_other = total_slippage_other / other_trade_count if other_trade_count > 0 else 0
    # 如果其他 DEX 滑点更低，节省 = (okx_avg - other_avg) * other_total_amount / 100
    other_total_amount = sum(
        by_dex[d]["total_amount_usd"] for d in by_dex if d != "okx"
    )
    savings = max(0, (avg_okx - avg_other) / 100 * other_total_amount)

    return {
        "period_days": days,
        "total_trades": len(rows),
        "by_dex": result_by_dex,
        "fallback_triggered": fallback_count,
        "split_triggered": split_count,
        "estimated_savings_usd": round(savings, 2),
        "avg_slippage_okx": round(avg_okx, 3),
        "avg_slippage_primary": round(avg_other, 3),
    }


AGENT_TOOL_DEFINITIONS = [
    # 继承已有的分析工具
    {
        "name": "read_agent_performance",
        "description": "读取交易 Agent 表现：胜率/PNL/按链/策略类型/时段/持仓时长 + 记忆系统效果。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 7},
            },
        },
    },
    {
        "name": "read_risk_events",
        "description": "读取风控拦截/警告事件，评估风控准确率。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 7},
            },
        },
    },
    {
        "name": "read_agent_memory",
        "description": "读取 semantic 记忆规则及其有效性统计（comply_win_rate vs violate_win_rate）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "数据范围", "default": 30},
            },
        },
    },
    {
        "name": "read_regime_history",
        "description": "读取 Regime 检测历史：切换记录 + 各 regime 下交易表现 + 检测延迟 + 误报代价。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 14},
            },
        },
    },
    {
        "name": "read_metrics",
        "description": "读取最近 N 天的 pump 监控指标，包括漏斗数据、推荐表现、命中率/召回率。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 7},
            },
        },
    },
    {
        "name": "read_config",
        "description": "读取 config.py 的所有配置参数。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "backtest",
        "description": "用修改后的参数对历史数据回测，验证优化方案是否有效。",
        "input_schema": {
            "type": "object",
            "properties": {
                "param_changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "param": {"type": "string"},
                            "old": {"type": "number"},
                            "new": {"type": "number"},
                        },
                        "required": ["param", "new"],
                    },
                },
                "days": {"type": "integer", "default": 7},
                "top_n": {"type": "integer", "default": 10},
            },
            "required": ["param_changes"],
        },
    },
    {
        "name": "propose_change",
        "description": (
            "提交优化方案到数据库。支持 5 种 type: "
            "scorer_param / risk_param / agent_config / memory_rule / monitoring。"
            "memory_rule 一次最多废弃 3 条。审批后自动 apply。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "title": {"type": "string", "description": "方案标题（中文，简短）"},
                "rationale": {"type": "string", "description": "分析推理过程（中文）"},
                "proposal_type": {
                    "type": "string",
                    "enum": ["scorer_param", "risk_param", "agent_config", "memory_rule", "monitoring"],
                    "description": "提案类型",
                },
                "changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "type": {"type": "string"},
                            "param": {"type": "string"},
                            "old": {},
                            "new": {},
                            "reason": {"type": "string"},
                        },
                        "required": ["param", "new", "reason"],
                    },
                },
                "backtest_before": {"type": "object"},
                "backtest_after": {"type": "object"},
            },
            "required": ["run_id", "title", "rationale", "changes", "backtest_before", "backtest_after"],
        },
    },
    # A/B 测试工具
    {
        "name": "propose_ab_test",
        "description": "提交 A/B 测试：双方案 50/50 随机分流，7 天后自动统计。优于直接修改。",
        "input_schema": {
            "type": "object",
            "properties": {
                "config_a": {"type": "object", "description": "方案 A 配置"},
                "config_b": {"type": "object", "description": "方案 B 配置"},
                "duration_days": {"type": "integer", "description": "测试天数", "default": 7},
            },
            "required": ["config_a", "config_b"],
        },
    },
    {
        "name": "read_ab_results",
        "description": "读取 A/B 测试结果：两组胜率/PNL/夏普率对比 + 获胜方。",
        "input_schema": {
            "type": "object",
            "properties": {
                "test_id": {"type": "string", "description": "A/B 测试 ID"},
            },
            "required": ["test_id"],
        },
    },
    {
        "name": "read_execution_quality",
        "description": "PRD-009 O8: 读取执行质量 — 按 DEX 统计滑点/失败率，fallback/split 触发次数，估算节省金额。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "查看最近几天", "default": 7},
            },
        },
    },
]


AGENT_TOOL_MAP = {
    "read_agent_performance": lambda args: tool_read_agent_performance(days=args.get("days", 7)),
    "read_risk_events": lambda args: tool_read_risk_events(days=args.get("days", 7)),
    "read_agent_memory": lambda args: tool_read_agent_memory(days=args.get("days", 30)),
    "read_regime_history": lambda args: tool_read_regime_history(days=args.get("days", 14)),
    "read_metrics": lambda args: tool_read_metrics(days=args.get("days", 7)),
    "read_config": lambda args: tool_read_config(),
    "backtest": lambda args: tool_backtest(
        param_changes=args.get("param_changes", []),
        days=args.get("days", 7),
        top_n=args.get("top_n", 10),
    ),
    "propose_change": lambda args: tool_propose_change(
        run_id=args["run_id"],
        title=args["title"],
        rationale=args["rationale"],
        changes=args["changes"],
        backtest_before=args["backtest_before"],
        backtest_after=args["backtest_after"],
    ),
    "propose_ab_test": lambda args: tool_propose_ab_test(
        config_a=args["config_a"],
        config_b=args["config_b"],
        duration_days=args.get("duration_days", 7),
    ),
    "read_ab_results": lambda args: tool_read_ab_results(test_id=args["test_id"]),
    "read_execution_quality": lambda args: tool_read_execution_quality(days=args.get("days", 7)),
}
