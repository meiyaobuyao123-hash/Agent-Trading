"""
热币榜打分引擎

总分 0~100：
  M 动量（50分）= 价格1h + 价格24h + 成交量加速 + 买压比 + 6h趋势
  Q 品质（30分）= 持有者数量 + 社交存在性 + 安全检测 + 持仓分散度
  P 潜力（20分）= 市值位置（对数） + 代币年龄（黄金区间）

推荐等级：strong(≥72) | normal(≥50) | skip(<50)
"""

import math
from dataclasses import dataclass


@dataclass
class HotScoreResult:
    total:          float   # 0~100 综合分
    score_m:        float   # 动量分（满50）
    score_q:        float   # 品质分（满30）
    score_p:        float   # 潜力分（满20）
    detail:         dict    # 各子维度明细
    recommendation: str     # 'strong' | 'normal' | 'skip'


def score_hot_coin(c: dict) -> HotScoreResult:
    detail: dict = {}

    # ── M 动量（50分）────────────────────────────────────────

    # M1. 价格 1h 涨幅（10分）
    pc_1h = c.get("price_change_1h") or 0
    if pc_1h >= 10:
        m1 = 10.0
    elif pc_1h > 0:
        m1 = _linear(pc_1h, 0, 10) * 10
    elif pc_1h >= -5:
        m1 = 0.0
    else:
        m1 = max(-5.0, pc_1h * 0.3)    # 大跌轻微减分
    detail["price_1h"] = round(m1, 1)

    # M2. 价格 24h 涨幅（10分）
    # 涨幅 > 300% 视为异常 pump，反向减分
    pc_24h = c.get("price_change_24h") or 0
    if pc_24h > 300:
        m2 = max(0.0, 10.0 - (pc_24h - 300) * 0.02)
    elif pc_24h >= 30:
        m2 = 10.0
    elif pc_24h > 0:
        m2 = _linear(pc_24h, 0, 30) * 10
    else:
        m2 = 0.0
    detail["price_24h"] = round(m2, 1)

    # M3. 成交量加速（12分）— 近1h量 vs 24h平均小时量
    vol_1h  = c.get("volume_1h_usd")  or 0
    vol_24h = c.get("volume_24h_usd") or 1
    avg_1h  = vol_24h / 24
    if avg_1h > 0:
        accel_ratio = vol_1h / avg_1h
        # ≥ 3x 均速满分，线性归一到 [1x, 3x]
        m3 = min(_linear(accel_ratio, 1.0, 3.0) * 12, 12.0)
    else:
        m3 = 0.0
    detail["vol_accel"] = round(m3, 1)

    # M4. 买压比（10分）— 1h 买单数 / 1h 总交易数
    buys_1h  = c.get("buys_1h")  or 0
    sells_1h = c.get("sells_1h") or 0
    total_1h = buys_1h + sells_1h
    buy_ratio = buys_1h / total_1h if total_1h > 0 else 0.5
    # 买压 ≥ 75% 满分，< 50% 得 0
    m4 = _linear(buy_ratio, 0.50, 0.75) * 10
    detail["buy_pressure"] = round(m4, 1)

    # M5. 6h 趋势（8分）— 用 price_change_6h 代理中期动量
    pc_6h = c.get("price_change_6h") or 0
    if pc_6h >= 20:
        m5 = 8.0
    elif pc_6h > 0:
        m5 = _linear(pc_6h, 0, 20) * 8
    elif pc_6h >= -10:
        m5 = 0.0
    else:
        m5 = max(-4.0, pc_6h * 0.2)    # 6h 大跌减分
    detail["trend_6h"] = round(m5, 1)

    score_m = m1 + m2 + m3 + m4 + m5

    # ── Q 品质（30分）────────────────────────────────────────

    # Q1. 持有者数量（10分）
    holders = c.get("holder_count") or 0
    if holders >= 1000:
        q1 = 10.0
    elif holders >= 150:
        q1 = _linear(holders, 150, 1000) * 10
    else:
        q1 = 3.0    # GoPlus 无数据时给中性分
    detail["holders"] = round(q1, 1)

    # Q2. 社交存在性（6分）— Twitter(3) + Telegram(2) + 网站(1)
    q2 = (
        3.0 * int(bool(c.get("has_twitter")))
        + 2.0 * int(bool(c.get("has_telegram")))
        + 1.0 * int(bool(c.get("has_website")))
    )
    detail["social"] = round(q2, 1)

    # Q3. 安全检测（8分）— GoPlus 风险标记减分
    q3 = 8.0
    if c.get("goplus_risk"):
        q3 -= 4.0
    if not c.get("is_open_source", True):
        q3 -= 2.0
    buy_tax  = c.get("buy_tax")  or 0
    sell_tax = c.get("sell_tax") or 0
    if buy_tax > 5 or sell_tax > 5:
        q3 -= 2.0
    q3 = max(0.0, q3)
    detail["security"] = round(q3, 1)

    # Q4. 持仓分散度（6分）— top10 集中度越低越好
    top10_pct = c.get("top10_holder_pct") or 0
    if top10_pct > 0:
        # top10 < 20% → 极度分散满分；> 80% → 已被风险过滤，此处 0 分
        q4 = max(0.0, _linear(1.0 - top10_pct, 0.20, 0.80) * 6)
    else:
        q4 = 3.0    # 无数据给中性分
    detail["concentration"] = round(q4, 1)

    score_q = q1 + q2 + q3 + q4

    # ── P 潜力（20分）────────────────────────────────────────

    # P1. 市值位置（14分）— 对数缩放，MC 越低潜力越大
    mc     = c.get("market_cap_usd") or 0
    mc_min = 200_000
    mc_max = 50_000_000
    if mc <= mc_min:
        p1 = 14.0
    elif mc >= mc_max:
        p1 = 0.0
    else:
        # 每增大10倍，得分线性下降
        log_ratio = math.log10(mc / mc_min) / math.log10(mc_max / mc_min)
        p1 = (1.0 - log_ratio) * 14.0
    detail["mc_potential"] = round(p1, 1)

    # P2. 代币年龄（6分）— 7~30天黄金区间；太新/太老降分
    age = c.get("age_days") or 0
    if 7 <= age <= 30:
        p2 = 6.0
    elif age < 7:
        p2 = _linear(age, 3, 7) * 6        # 3~7天爬坡
    else:
        # 30~90天线性衰减
        p2 = max(0.0, _linear(90 - age, 0, 60) * 6)
    detail["age_score"] = round(p2, 1)

    score_p = p1 + p2

    # ── 总分 ─────────────────────────────────────────────────
    total = round(min(score_m + score_q + score_p, 100.0), 1)

    if total >= 72:
        rec = "strong"
    elif total >= 50:
        rec = "normal"
    else:
        rec = "skip"

    return HotScoreResult(
        total=total,
        score_m=round(score_m, 1),
        score_q=round(score_q, 1),
        score_p=round(score_p, 1),
        detail=detail,
        recommendation=rec,
    )


# ── 工具函数 ──────────────────────────────────────────────

def _linear(val: float, lo: float, hi: float) -> float:
    """线性归一化到 [0, 1]"""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (val - lo) / (hi - lo)))
