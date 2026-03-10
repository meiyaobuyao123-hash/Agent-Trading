"""
规则打分引擎（冷启动阶段，2周后逐步替换为 ML 模型）

总分 0~100，各维度权重：
  买卖比（资金流向）   25%
  聪明钱参与         20%
  流入加速度         15%
  Creator 历史       15%
  持仓集中度         10%  (暂用 unique_buyers 近似)
  Social 完整度      10%
  进度速度           5%
"""

from dataclasses import dataclass
from features import TokenFeatures
import math


@dataclass
class ScoreResult:
    total: float                    # 0~100 综合分
    detail: dict                    # 各维度得分
    recommendation: str             # 'strong' | 'normal' | 'skip'


def score(f: TokenFeatures) -> ScoreResult:
    detail = {}

    # ── 1. 买卖比（25分）────────────────────────
    # buy_sell_ratio_vol: 理想 > 3，满分；< 1 得 0
    bsr = min(f.buy_sell_ratio_vol, 5.0)
    detail["buy_sell_ratio"] = round(_linear(bsr, lo=1.0, hi=5.0) * 25, 1)

    # ── 2. 聪明钱（20分）分层加权 ───────────────
    # 精英(3x) + 验证(1.5x) + 观察(1x) → 等效钱包数，>= 3 满分
    sm_weighted = (
        f.smart_elite_count    * 3.0 +
        f.smart_verified_count * 1.5 +
        f.smart_watching_count * 1.0
    )
    sm_count_score = min(sm_weighted / 3.0, 1.0) * 15
    # smart_money_net_sol >= 1 SOL 额外加分
    sm_net_score = min(max(f.smart_money_net_sol, 0) / 1.0, 1.0) * 5
    detail["smart_money"] = round(sm_count_score + sm_net_score, 1)

    # ── 3. 流入加速度（15分）────────────────────
    # inflow_acceleration > 0 说明最近5min 比之前更热
    accel = f.inflow_acceleration
    if accel >= 0.5:
        accel_score = 15.0
    elif accel > 0:
        accel_score = _linear(accel, lo=0, hi=0.5) * 15
    else:
        accel_score = 0.0
    detail["inflow_acceleration"] = round(accel_score, 1)

    # ── 4. Creator 历史（15分）──────────────────
    if f.creator_prev_tokens == 0:
        # 新人：中性，给 8 分（不奖不罚）
        creator_score = 8.0
    else:
        # 有历史：按成功率打分
        creator_score = f.creator_success_rate * 15
    detail["creator_history"] = round(creator_score, 1)

    # ── 5. 买家分散度（10分）────────────────────
    # unique_buyers 越多越分散（不集中）
    # >= 50 买家满分，< 10 给 0
    detail["buyer_diversity"] = round(_linear(f.unique_buyers, lo=10, hi=50) * 10, 1)

    # ── 6. Social 完整度（10分）─────────────────
    # social_score 0~3
    detail["social"] = round((f.social_score / 3.0) * 10, 1)

    # ── 7. 进度速度（5分）───────────────────────
    # bc_speed_pct_per_hour: 5~20%/h 区间满分
    spd = f.bc_speed_pct_per_hour
    if 5 <= spd <= 20:
        speed_score = 5.0
    elif spd < 5:
        speed_score = _linear(spd, lo=0, hi=5) * 5
    else:
        # 太快（>20%/h）可能是机器人，轻微减分
        speed_score = max(0, 5.0 - (spd - 20) * 0.1)
    detail["progress_speed"] = round(speed_score, 1)

    # ── 大单奖励（+5 bonus）──────────────────────
    bonus = min(f.large_buy_count * 1.0, 5.0)
    detail["large_buy_bonus"] = round(bonus, 1)

    # ── 总分 ─────────────────────────────────────
    total = sum(detail.values())
    total = round(min(total, 100.0), 1)

    # 推荐等级
    if total >= 75:
        rec = "strong"
    elif total >= 55:
        rec = "normal"
    else:
        rec = "skip"

    return ScoreResult(total=total, detail=detail, recommendation=rec)


def _linear(val: float, lo: float, hi: float) -> float:
    """线性归一化到 0~1"""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (val - lo) / (hi - lo)))
