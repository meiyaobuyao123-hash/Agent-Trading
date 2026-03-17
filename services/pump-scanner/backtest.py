"""
回测引擎 — 用修改后的参数对历史数据重新打分

核心逻辑：
1. 从 token_snapshots 获取历史快照（每个代币取最佳快照）
2. 用新参数重新评分
3. 选出 Top N 作为"新推荐"
4. 与实际结果（价格涨幅 / 毕业状态）对比
5. 计算 hit_rate / recall / precision / f1

"好推荐" 的定义（多维度）：
  - 价格涨幅：推荐后 market_cap_sol 相比推荐时涨幅 >= 50%
  - 毕业：代币完成 bonding curve（100% → DEX）
  - 综合：价格涨幅 >= 50% OR 毕业
"""

import logging
import math
from datetime import date, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

from database import get_db

log = logging.getLogger(__name__)

# "好代币" 的判定阈值
HIT_PRICE_INCREASE_PCT = 50.0  # 价格涨幅 >= 50% 算命中


@dataclass
class BacktestToken:
    """一个代币的回测数据"""
    mint: str
    symbol: str
    snapshot: dict           # 原始快照字段
    original_score: float    # 原始分数
    new_score: float = 0.0   # 新参数下的分数
    graduated: bool = False  # 是否毕业
    price_at_snapshot: float = 0.0  # 快照时 market_cap_sol
    best_price: float = 0.0  # 后续最高价
    price_change_pct: float = 0.0  # 实际涨幅


def run_backtest(
    param_changes: list,
    days: int = 7,
    top_n: int = 10,
) -> dict:
    """
    主回测入口。

    param_changes 示例:
    [
        {"param": "buy_sell_ratio_weight", "new": 30},  # 原25 → 30
        {"param": "smart_money_weight", "new": 25},     # 原20 → 25
        {"param": "MIN_BUYERS_HARD", "new": 4},         # 原5 → 4
        {"param": "signal_min_score", "new": 50},       # 原55 → 50
    ]
    """
    db = get_db()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    # 1. 获取历史快照
    snapshots = _load_snapshots(db, cutoff)
    if not snapshots:
        return {"error": "没有足够的历史快照数据进行回测", "token_count": 0}

    # 2. 获取毕业状态
    graduated_set = _load_graduated(db, cutoff)

    # 3. 获取后续最高价（用 token_snapshots 中同一代币的后续快照）
    best_prices = _load_best_prices(db, cutoff)

    # 4. 解析参数变更
    weight_overrides, config_overrides, score_threshold = _parse_changes(param_changes)

    # 5. 构建回测代币列表
    tokens = []
    for mint, snap in snapshots.items():
        mc = float(snap.get("market_cap_sol") or 0)
        bp = float(best_prices.get(mint, mc))
        price_change = ((bp - mc) / mc * 100) if mc > 0 else 0

        bt = BacktestToken(
            mint=mint,
            symbol=snap.get("symbol", "?"),
            snapshot=snap,
            original_score=float(snap.get("score") or 0),
            graduated=mint in graduated_set,
            price_at_snapshot=mc,
            best_price=bp,
            price_change_pct=round(price_change, 2),
        )
        tokens.append(bt)

    # 6. 用新参数重新打分
    for bt in tokens:
        bt.new_score = _rescore(bt.snapshot, weight_overrides, config_overrides)

    # 7. 应用硬过滤 + 排序
    min_buyers = config_overrides.get("MIN_BUYERS_HARD", 5)
    max_dev_sold = config_overrides.get("MAX_DEV_SOLD_PCT", 0.50)
    min_bsr = config_overrides.get("MIN_BUY_SELL_RATIO", 0.4)
    bc_min = config_overrides.get("BC_MIN_PCT", 3.0)
    bc_max = config_overrides.get("BC_MAX_PCT", 35.0)

    filtered = []
    for bt in tokens:
        s = bt.snapshot
        if (s.get("unique_buyers") or 0) < min_buyers:
            continue
        if (s.get("dev_sold_pct") or 0) > max_dev_sold * 100:
            continue
        if (s.get("buy_sell_ratio_vol") or 0) < min_bsr:
            continue
        bc = s.get("bc_progress") or 0
        if bc < bc_min or bc > bc_max:
            continue
        if bt.new_score < score_threshold:
            continue
        filtered.append(bt)

    # 排序取 Top N
    filtered.sort(key=lambda x: x.new_score, reverse=True)
    new_picks = filtered[:top_n]
    new_pick_mints = {bt.mint for bt in new_picks}

    # 8. 定义"好代币"集合（价格涨 >= 50% 或 毕业）
    good_tokens = set()
    for bt in tokens:
        if bt.price_change_pct >= HIT_PRICE_INCREASE_PCT or bt.graduated:
            good_tokens.add(bt.mint)

    # 9. 计算新参数的指标
    new_hits = new_pick_mints & good_tokens
    new_missed = good_tokens - new_pick_mints

    new_metrics = _calc_metrics(
        picks=new_pick_mints,
        good=good_tokens,
        hits=new_hits,
    )

    # 10. 计算原始参数的指标（使用原始推荐）
    orig_picks_res = db.table("daily_picks") \
        .select("mint") \
        .gte("pick_date", cutoff) \
        .execute()
    orig_pick_mints = {r["mint"] for r in orig_picks_res.data}
    orig_hits = orig_pick_mints & good_tokens

    orig_metrics = _calc_metrics(
        picks=orig_pick_mints,
        good=good_tokens,
        hits=orig_hits,
    )

    # 11. 对比
    return {
        "period_days": days,
        "total_tokens": len(tokens),
        "good_tokens_count": len(good_tokens),
        "good_tokens_definition": f"价格涨幅>={HIT_PRICE_INCREASE_PCT}% 或 毕业",
        "original": {
            **orig_metrics,
            "picks_count": len(orig_pick_mints),
            "sample_picks": [
                {"mint": bt.mint, "symbol": bt.symbol, "score": bt.original_score,
                 "price_change": bt.price_change_pct, "graduated": bt.graduated}
                for bt in tokens if bt.mint in orig_pick_mints
            ][:10],
        },
        "new_params": {
            **new_metrics,
            "picks_count": len(new_pick_mints),
            "sample_picks": [
                {"mint": bt.mint, "symbol": bt.symbol, "score": bt.new_score,
                 "price_change": bt.price_change_pct, "graduated": bt.graduated}
                for bt in new_picks
            ][:10],
        },
        "improvement": {
            "hit_rate_delta": round(new_metrics["hit_rate"] - orig_metrics["hit_rate"], 4),
            "recall_delta": round(new_metrics["recall"] - orig_metrics["recall"], 4),
            "f1_delta": round(new_metrics["f1"] - orig_metrics["f1"], 4),
        },
        "missed_good_tokens": [
            {"mint": bt.mint, "symbol": bt.symbol, "new_score": bt.new_score,
             "price_change": bt.price_change_pct, "graduated": bt.graduated}
            for bt in tokens if bt.mint in (good_tokens - new_pick_mints)
        ][:10],
        "param_changes_applied": param_changes,
    }


def _calc_metrics(picks: set, good: set, hits: set) -> dict:
    """计算分类指标"""
    total_picks = len(picks)
    total_good = len(good)
    hit_count = len(hits)

    precision = hit_count / total_picks if total_picks > 0 else 0
    recall = hit_count / total_good if total_good > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "hit_rate": round(precision, 4),  # = precision
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
        "hit_count": hit_count,
        "miss_count": len(good - picks),
        "false_positive_count": len(picks - good),
    }


def _load_snapshots(db, cutoff: str) -> Dict[str, dict]:
    """加载历史快照，每个 mint 保留分数最高的一条"""
    res = db.table("token_snapshots") \
        .select("*") \
        .gte("snapshot_at", f"{cutoff}T00:00:00Z") \
        .order("score", desc=True) \
        .limit(5000) \
        .execute()

    best = {}
    for s in res.data:
        mint = s["mint"]
        if mint not in best:
            best[mint] = s
    return best


def _load_graduated(db, cutoff: str) -> set:
    """加载毕业代币集合"""
    res = db.table("pump_tokens") \
        .select("mint") \
        .eq("complete", True) \
        .gte("created_at", f"{cutoff}T00:00:00Z") \
        .execute()
    return {r["mint"] for r in res.data}


def _load_best_prices(db, cutoff: str) -> Dict[str, float]:
    """
    对每个代币，找到其后续最高 market_cap_sol。
    这是衡量"它后来涨了多少"的关键数据。
    """
    # 方法：查询 token_snapshots 中每个 mint 的 max(market_cap_sol)
    res = db.table("token_snapshots") \
        .select("mint, market_cap_sol") \
        .gte("snapshot_at", f"{cutoff}T00:00:00Z") \
        .order("market_cap_sol", desc=True) \
        .limit(10000) \
        .execute()

    best = {}
    for r in res.data:
        mint = r["mint"]
        mc = float(r.get("market_cap_sol") or 0)
        if mint not in best or mc > best[mint]:
            best[mint] = mc
    return best


def _parse_changes(param_changes: list) -> tuple:
    """解析参数变更为 weight_overrides 和 config_overrides"""
    weight_map = {
        "buy_sell_ratio_weight": "buy_sell_ratio",
        "smart_money_weight": "smart_money",
        "inflow_acceleration_weight": "inflow_acceleration",
        "creator_history_weight": "creator_history",
        "buyer_diversity_weight": "buyer_diversity",
        "social_weight": "social",
        "progress_speed_weight": "progress_speed",
        "large_buy_bonus_weight": "large_buy_bonus",
    }

    config_params = {
        "MIN_BUYERS_HARD", "MAX_DEV_SOLD_PCT", "MIN_BUY_SELL_RATIO",
        "BC_MIN_PCT", "BC_MAX_PCT", "LARGE_BUY_SOL",
        "ENRICH_MIN_BUYERS", "ENRICH_MIN_BC_PCT",
    }

    weight_overrides = {}
    config_overrides = {}
    score_threshold = 55  # default

    for change in param_changes:
        param = change["param"]
        new_val = change["new"]

        if param in weight_map:
            weight_overrides[weight_map[param]] = new_val
        elif param in config_params:
            config_overrides[param] = new_val
        elif param == "signal_min_score":
            score_threshold = new_val
        elif param.endswith("_weight"):
            # 直接使用维度名
            dim = param.replace("_weight", "")
            weight_overrides[dim] = new_val

    return weight_overrides, config_overrides, score_threshold


def _rescore(snapshot: dict, weight_overrides: dict, config_overrides: dict) -> float:
    """用新参数对单个快照重新打分"""

    # 默认权重
    weights = {
        "buy_sell_ratio": 25,
        "smart_money": 20,
        "inflow_acceleration": 15,
        "creator_history": 15,
        "buyer_diversity": 10,
        "social": 10,
        "progress_speed": 5,
        "large_buy_bonus": 5,
    }
    weights.update(weight_overrides)

    def _linear(val, lo, hi):
        if hi <= lo:
            return 0.0
        return max(0.0, min(1.0, (val - lo) / (hi - lo)))

    detail = {}

    # 1. 买卖比
    bsr = min(float(snapshot.get("buy_sell_ratio_vol") or 0), 5.0)
    bsr_hi = config_overrides.get("buy_sell_ratio_hi", 5.0)
    detail["buy_sell_ratio"] = _linear(bsr, 1.0, bsr_hi) * weights["buy_sell_ratio"]

    # 2. 聪明钱
    sm_w = (
        float(snapshot.get("smart_elite_count") or 0) * 3.0 +
        float(snapshot.get("smart_verified_count") or 0) * 1.5 +
        float(snapshot.get("smart_watching_count") or 0) * 1.0
    )
    sm_count = min(sm_w / 3.0, 1.0) * (weights["smart_money"] * 0.75)
    sm_net = min(max(float(snapshot.get("smart_money_net_sol") or 0), 0) / 1.0, 1.0) * (weights["smart_money"] * 0.25)
    detail["smart_money"] = sm_count + sm_net

    # 3. 流入加速
    accel = float(snapshot.get("inflow_acceleration") or 0)
    if accel >= 0.5:
        detail["inflow_acceleration"] = float(weights["inflow_acceleration"])
    elif accel > 0:
        detail["inflow_acceleration"] = _linear(accel, 0, 0.5) * weights["inflow_acceleration"]
    else:
        detail["inflow_acceleration"] = 0.0

    # 4. Creator 历史
    prev = int(snapshot.get("creator_prev_tokens") or 0)
    if prev == 0:
        detail["creator_history"] = weights["creator_history"] * 0.53  # 8/15
    else:
        rate = float(snapshot.get("creator_success_rate") or 0)
        detail["creator_history"] = rate * weights["creator_history"]

    # 5. 买家分散度
    ub = int(snapshot.get("unique_buyers") or 0)
    detail["buyer_diversity"] = _linear(ub, 10, 50) * weights["buyer_diversity"]

    # 6. Social
    ss = float(snapshot.get("social_score") or 0)
    detail["social"] = (ss / 3.0) * weights["social"]

    # 7. 进度速度（简化：用 bc_progress 估算）
    bc = float(snapshot.get("bc_progress") or 0)
    if 5 <= bc <= 20:
        detail["progress_speed"] = float(weights["progress_speed"])
    else:
        detail["progress_speed"] = weights["progress_speed"] * 0.5

    # 8. 大单
    lb = int(snapshot.get("large_buy_count") or 0)
    detail["large_buy_bonus"] = min(lb * 1.0, float(weights["large_buy_bonus"]))

    total = sum(detail.values())
    return round(min(total, 100.0), 1)
