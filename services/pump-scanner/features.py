"""
特征提取模块
从原始交易数据计算所有特征，供打分引擎使用
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from config import (
    VIRTUAL_SOL_INIT, GRADUATION_SOL,
    LARGE_BUY_SOL, BC_MIN_PCT, BC_MAX_PCT,
    MIN_BUYERS_HARD, MAX_DEV_SOLD_PCT, MIN_BUY_SELL_RATIO
)


@dataclass
class TokenFeatures:
    mint: str
    name: str = ""
    symbol: str = ""

    # ── Bonding Curve ──────────────────────────
    bc_progress: float = 0.0        # 0~100 %
    v_sol: float = 0.0
    market_cap_sol: float = 0.0

    # ── 时间 ───────────────────────────────────
    age_minutes: float = 0.0        # 代币年龄（分钟）
    bc_speed_pct_per_hour: float = 0.0  # 进度增速（%/小时）

    # ── 交易流 ─────────────────────────────────
    buy_count: int = 0
    sell_count: int = 0
    buy_volume_sol: float = 0.0
    sell_volume_sol: float = 0.0
    unique_buyers: int = 0
    unique_sellers: int = 0

    buy_sell_ratio_count: float = 0.0   # 买入笔数 / 卖出笔数
    buy_sell_ratio_vol: float = 0.0     # 买入 SOL / 卖出 SOL

    inflow_rate_sol_pm: float = 0.0     # 净流入速率（SOL/分钟）
    inflow_acceleration: float = 0.0    # 近5min vs 前5min 流入对比

    large_buy_count: int = 0            # 单笔 >= 0.5 SOL 的买入次数
    max_single_buy_sol: float = 0.0

    # ── Dev 行为 ───────────────────────────────
    dev_wallet: str = ""
    dev_sold: bool = False
    dev_sold_pct: float = 0.0           # dev 卖出占初始仓位比例

    # ── 聪明钱（分层）─────────────────────────────
    smart_money_count: int = 0          # 所有层级聪明钱参与数（向后兼容）
    smart_money_net_sol: float = 0.0    # 聪明钱净流入 SOL
    smart_elite_count: int = 0          # 精英层钱包买入数
    smart_verified_count: int = 0       # 验证层钱包买入数
    smart_watching_count: int = 0       # 观察层钱包买入数

    # ── Social ─────────────────────────────────
    has_twitter: bool = False
    has_telegram: bool = False
    has_website: bool = False
    social_score: int = 0               # 0~3，有几个社交账号
    reply_count: int = 0

    # ── Creator 历史 ───────────────────────────
    creator_prev_tokens: int = 0
    creator_success_rate: float = 0.0   # 历史毕业率


def calc_bc_progress(v_sol_in_bc: float) -> float:
    """从 vSolInBondingCurve 计算内盘进度"""
    real_sol = max(0.0, v_sol_in_bc - VIRTUAL_SOL_INIT)
    return min(100.0, (real_sol / GRADUATION_SOL) * 100)


def extract_features(
    token_info: dict,
    trades: list[dict],
    smart_wallet_tiers: dict,
    created_at: datetime,
) -> TokenFeatures:
    """
    从原始数据计算完整特征集

    Args:
        token_info:          pump.fun REST API 的代币详情
        trades:              按时间升序排列的交易列表
                             每条: {trader, tx_type, sol_amount, token_amount, traded_at}
        smart_wallet_tiers:  聪明钱分级映射 {wallet → 'elite'|'verified'|'watching'}
        created_at:          代币创建时间（UTC）
    """
    now = datetime.now(timezone.utc)
    f = TokenFeatures(
        mint=token_info.get("mint", ""),
        name=token_info.get("name", ""),
        symbol=token_info.get("symbol", ""),
    )

    # ── Bonding Curve ──────────────────────────
    v_sol = token_info.get("vSolInBondingCurve") or token_info.get("v_sol", 0.0)
    f.v_sol = float(v_sol)
    f.bc_progress = calc_bc_progress(f.v_sol)
    f.market_cap_sol = float(token_info.get("market_cap_sol") or token_info.get("marketCapSol", 0))

    # ── 时间 ───────────────────────────────────
    f.age_minutes = max(0.1, (now - created_at).total_seconds() / 60)
    f.bc_speed_pct_per_hour = (f.bc_progress / f.age_minutes) * 60

    # ── 交易流统计 ─────────────────────────────
    dev_wallet = token_info.get("creator", "")
    f.dev_wallet = dev_wallet

    buys = [t for t in trades if t["tx_type"] == "buy"]
    sells = [t for t in trades if t["tx_type"] == "sell"]

    f.buy_count = len(buys)
    f.sell_count = len(sells)
    f.buy_volume_sol = sum(t["sol_amount"] for t in buys)
    f.sell_volume_sol = sum(t["sol_amount"] for t in sells)
    f.unique_buyers = len({t["trader"] for t in buys})
    f.unique_sellers = len({t["trader"] for t in sells})

    f.buy_sell_ratio_count = (
        f.buy_count / max(1, f.sell_count)
    )
    f.buy_sell_ratio_vol = (
        f.buy_volume_sol / max(0.001, f.sell_volume_sol)
    )

    # 流速（以代币年龄为分母）
    net_inflow = f.buy_volume_sol - f.sell_volume_sol
    f.inflow_rate_sol_pm = net_inflow / f.age_minutes

    # 加速度：近5min vs 前5min 净流入对比
    cutoff = now.timestamp() - 300
    recent = [t for t in trades if t["traded_at"].timestamp() > cutoff]
    earlier = [t for t in trades if t["traded_at"].timestamp() <= cutoff]
    recent_net = sum(t["sol_amount"] * (1 if t["tx_type"] == "buy" else -1) for t in recent)
    earlier_net = sum(t["sol_amount"] * (1 if t["tx_type"] == "buy" else -1) for t in earlier)
    f.inflow_acceleration = recent_net - earlier_net

    # 大单
    large_buys = [t for t in buys if t["sol_amount"] >= LARGE_BUY_SOL]
    f.large_buy_count = len(large_buys)
    f.max_single_buy_sol = max((t["sol_amount"] for t in buys), default=0.0)

    # ── Dev 行为 ───────────────────────────────
    dev_sells = [t for t in sells if t["trader"] == dev_wallet]
    dev_initial_tokens = float(token_info.get("initialBuy") or token_info.get("initial_buy_sol", 0))
    if dev_sells and dev_initial_tokens > 0:
        f.dev_sold = True
        f.dev_sold_pct = sum(t["token_amount"] for t in dev_sells) / max(1, dev_initial_tokens)

    # ── 聪明钱（分层统计）─────────────────────────
    sm_buyers_by_tier: dict = {"elite": set(), "verified": set(), "watching": set()}
    for t in buys:
        tier = smart_wallet_tiers.get(t["trader"])
        if tier in sm_buyers_by_tier:
            sm_buyers_by_tier[tier].add(t["trader"])

    f.smart_elite_count    = len(sm_buyers_by_tier["elite"])
    f.smart_verified_count = len(sm_buyers_by_tier["verified"])
    f.smart_watching_count = len(sm_buyers_by_tier["watching"])
    f.smart_money_count    = (
        f.smart_elite_count + f.smart_verified_count + f.smart_watching_count
    )

    all_smart_wallets = set(smart_wallet_tiers.keys())
    sm_in  = sum(t["sol_amount"] for t in buys  if t["trader"] in all_smart_wallets)
    sm_out = sum(t["sol_amount"] for t in sells if t["trader"] in all_smart_wallets)
    f.smart_money_net_sol = sm_in - sm_out

    # ── Social ─────────────────────────────────
    f.has_twitter = bool(token_info.get("twitter"))
    f.has_telegram = bool(token_info.get("telegram"))
    f.has_website = bool(token_info.get("website"))
    f.social_score = int(f.has_twitter) + int(f.has_telegram) + int(f.has_website)
    f.reply_count = int(token_info.get("reply_count", 0))

    # ── Creator 历史 ───────────────────────────
    f.creator_prev_tokens = int(token_info.get("creator_prev_tokens", 0))
    f.creator_success_rate = float(token_info.get("creator_success_rate") or 0.0)

    return f


def hard_filter(f: TokenFeatures) -> tuple[bool, str]:
    """
    硬过滤：返回 (通过, 拒绝原因)
    任何一条不通过 → 直接排除，不进入打分
    """
    if f.unique_buyers < MIN_BUYERS_HARD:
        return False, f"买家数不足 {f.unique_buyers}/{MIN_BUYERS_HARD}"

    if f.dev_sold and f.dev_sold_pct > MAX_DEV_SOLD_PCT:
        return False, f"Dev 已卖出 {f.dev_sold_pct:.0%}"

    if f.buy_sell_ratio_count < MIN_BUY_SELL_RATIO:
        return False, f"买卖比过低 {f.buy_sell_ratio_count:.2f}"

    if not (BC_MIN_PCT <= f.bc_progress <= BC_MAX_PCT):
        return False, f"进度不在窗口 {f.bc_progress:.1f}%"

    return True, ""


def to_snapshot_dict(f: TokenFeatures, age_minutes: float) -> dict:
    """转换为 token_snapshots 表的插入格式"""
    return {
        "mint": f.mint,
        "bc_progress": f.bc_progress,
        "v_sol": f.v_sol,
        "market_cap_sol": f.market_cap_sol,
        "buy_count": f.buy_count,
        "sell_count": f.sell_count,
        "buy_volume_sol": f.buy_volume_sol,
        "sell_volume_sol": f.sell_volume_sol,
        "unique_buyers": f.unique_buyers,
        "unique_sellers": f.unique_sellers,
        "buy_sell_ratio_count": f.buy_sell_ratio_count,
        "buy_sell_ratio_vol": f.buy_sell_ratio_vol,
        "inflow_rate_sol_pm": f.inflow_rate_sol_pm,
        "bc_progress_rate": f.bc_speed_pct_per_hour,
        "dev_sold": f.dev_sold,
        "dev_sold_pct": f.dev_sold_pct,
        "large_buy_count": f.large_buy_count,
        "reply_count": f.reply_count,
    }
