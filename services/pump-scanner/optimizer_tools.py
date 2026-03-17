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

    # 4. 计算指标
    recommended_mints = {p["address"] for p in perf}
    graduated_mints = {g["mint"] for g in graduated}

    # 命中：推荐了 & 毕业了
    hits = recommended_mints & graduated_mints
    # 误报：推荐了 & 没毕业
    false_positives = recommended_mints - graduated_mints
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
]

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
}
