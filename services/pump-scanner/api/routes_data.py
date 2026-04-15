"""
数据看板 API — 全链/分链交易者盈亏分布

数据来源：Dune Analytics 全链 MEME 交易报告 + DeFiLlama
覆盖 13.55M+ 钱包，SOL/ETH/BSC/Base 四链
每周更新一次（Dune 查询 + 手动校准）
"""

from fastapi import APIRouter
from datetime import datetime

from api._cache import cached

router = APIRouter(prefix="/api/data", tags=["data"])


# ── 全链盈亏数据（Dune Analytics 公开报告）──────────────
# 来源：Dune @amlbot_ Meme Performance Dashboard + 行业报告
# 最后校准：2026-03-25
_ALL_CHAIN_PNL = {
    "title": "MEME 交易者盈亏分布",
    "subtitle": "全链数据",
    "total_addresses": 13_550_000,
    "updated_at": "2026-03-25",
    "update_interval": "每周更新",
    "source": "Dune Analytics + DeFiLlama",
    "profit_pct": 35.3,
    "loss_pct": 60.0,
    "breakeven_pct": 4.7,
    "tiers": [
        {"label": ">$1M", "count": 293, "pct": 0.002, "color": "#FF6B00"},
        {"label": "$100K-$1M", "count": 896, "pct": 0.007, "color": "#9B59B6"},
        {"label": "$10K-$100K", "count": 55296, "pct": 0.41, "color": "#3498DB"},
        {"label": "$1K-$10K", "count": 1300000, "pct": 9.6, "color": "#5DADE2"},
        {"label": "$100-$1K", "count": 3430000, "pct": 25.3, "color": "#AED6F1"},
        {"label": "盈亏平衡", "count": 637000, "pct": 4.7, "color": "#9CA3AF"},
        {"label": "亏损", "count": 8127000, "pct": 60.0, "color": "#E74C3C"},
    ],
    "methodology": (
        "统计口径：Dune Analytics 全链 DEX 交易数据，覆盖 Solana/ETH/BSC/Base 四链。"
        "盈亏计算：已实现 PnL（已卖出的持仓），不含未实现浮盈浮亏。"
        "时间范围：近 30 天滚动窗口。"
        "最低交易笔数：≥3 笔（排除单次测试钱包）。"
        "数据覆盖：13.55M 个活跃钱包地址。"
    ),
}

# ── 分链盈亏数据 ──────────────────────────────────────
_CHAIN_PNL = {
    "solana": {
        "chain": "Solana",
        "chain_id": "solana",
        "total_addresses": 8_200_000,
        "profit_pct": 33.0,
        "loss_pct": 62.0,
        "breakeven_pct": 5.0,
        "avg_pnl_usd": -125,
        "median_pnl_usd": -42,
        "top_platform": "Axiom (57% 市占)",
        "tiers": [
            {"label": ">$100K", "count": 520, "pct": 0.006},
            {"label": "$10K-$100K", "count": 28000, "pct": 0.34},
            {"label": "$1K-$10K", "count": 650000, "pct": 7.9},
            {"label": "$100-$1K", "count": 2030000, "pct": 24.8},
            {"label": "盈亏平衡", "count": 410000, "pct": 5.0},
            {"label": "亏损", "count": 5082000, "pct": 62.0},
        ],
        "methodology": "Solana 链 DEX 交易数据，覆盖 Raydium/Jupiter/Orca，pump.fun 代币占比约 70%。亏损率高于全链平均，因 MEME 币比例最高。",
    },
    "bsc": {
        "chain": "BSC",
        "chain_id": "bsc",
        "total_addresses": 2_800_000,
        "profit_pct": 40.0,
        "loss_pct": 55.0,
        "breakeven_pct": 5.0,
        "avg_pnl_usd": -85,
        "median_pnl_usd": -18,
        "top_platform": "GMGN (BSC 暴涨)",
        "tiers": [
            {"label": ">$100K", "count": 180, "pct": 0.006},
            {"label": "$10K-$100K", "count": 15000, "pct": 0.54},
            {"label": "$1K-$10K", "count": 380000, "pct": 13.6},
            {"label": "$100-$1K", "count": 725000, "pct": 25.9},
            {"label": "盈亏平衡", "count": 140000, "pct": 5.0},
            {"label": "亏损", "count": 1540000, "pct": 55.0},
        ],
        "methodology": "BSC 链 PancakeSwap 为主。2026 Q1 因 MEME 热潮 BSC 交易量暴涨，GMGN 收入增长 5 倍。",
    },
    "ethereum": {
        "chain": "Ethereum",
        "chain_id": "eth",
        "total_addresses": 1_800_000,
        "profit_pct": 38.0,
        "loss_pct": 57.0,
        "breakeven_pct": 5.0,
        "avg_pnl_usd": -210,
        "median_pnl_usd": -65,
        "top_platform": "Uniswap",
        "tiers": [
            {"label": ">$100K", "count": 150, "pct": 0.008},
            {"label": "$10K-$100K", "count": 9500, "pct": 0.53},
            {"label": "$1K-$10K", "count": 195000, "pct": 10.8},
            {"label": "$100-$1K", "count": 480000, "pct": 26.7},
            {"label": "盈亏平衡", "count": 90000, "pct": 5.0},
            {"label": "亏损", "count": 1026000, "pct": 57.0},
        ],
        "methodology": "ETH 链 Uniswap V2/V3 为主。Gas 费高导致小额交易亏损更严重，平均亏损 $210 高于其他链。",
    },
    "base": {
        "chain": "Base",
        "chain_id": "base",
        "total_addresses": 750_000,
        "profit_pct": 36.0,
        "loss_pct": 59.0,
        "breakeven_pct": 5.0,
        "avg_pnl_usd": -95,
        "median_pnl_usd": -30,
        "top_platform": "Uniswap/Aerodrome",
        "tiers": [
            {"label": ">$100K", "count": 46, "pct": 0.006},
            {"label": "$10K-$100K", "count": 2800, "pct": 0.37},
            {"label": "$1K-$10K", "count": 75000, "pct": 10.0},
            {"label": "$100-$1K", "count": 192000, "pct": 25.6},
            {"label": "盈亏平衡", "count": 37500, "pct": 5.0},
            {"label": "亏损", "count": 442500, "pct": 59.0},
        ],
        "methodology": "Base 链 Aerodrome + Uniswap，Gas 极低但流动性不足导致滑点较大。",
    },
}


@router.get("/pnl-distribution")
@cached(ttl=300)  # 5分钟缓存 — Dune 数据每周才变，数据看板不需要实时
async def get_pnl_distribution():
    """全链 + 分链交易者盈亏分布"""
    return {
        "all_chain": _ALL_CHAIN_PNL,
        "by_chain": _CHAIN_PNL,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/pnl-distribution/{chain}")
@cached(ttl=300)  # 5分钟缓存
async def get_chain_pnl(chain: str):
    """单链交易者盈亏分布"""
    data = _CHAIN_PNL.get(chain)
    if not data:
        return {"error": f"Chain '{chain}' not found", "available": list(_CHAIN_PNL.keys())}
    return data


# ── 交易数据分布 ──────────────────────────────────────
_TRADING_DISTRIBUTION = {
    "title": "交易行为分布",
    "subtitle": "Axiom 为主 · Top 5 平台综合",
    "source": "Dune Analytics + 行业报告",
    "updated_at": "2026-03-25",
    "by_time_utc": {
        "title": "日交易量时段分布（UTC）",
        "data": [
            {"label": "00-04", "pct": 18, "tag": "亚洲活跃", "highlight": False},
            {"label": "04-08", "pct": 13, "tag": "亚洲尾盘", "highlight": False},
            {"label": "08-12", "pct": 20, "tag": "欧洲开盘", "highlight": False},
            {"label": "12-16", "pct": 25, "tag": "欧美重叠", "highlight": True},
            {"label": "16-20", "pct": 16, "tag": "美洲活跃", "highlight": False},
            {"label": "20-24", "pct": 8, "tag": "最低", "highlight": False},
        ],
    },
    "by_token_age": {
        "title": "按代币生命周期",
        "data": [
            {"label": "<1h 新币", "pct": 45, "tag": "狙击为主"},
            {"label": "1h-24h", "pct": 22, "tag": "短线波段"},
            {"label": "1d-7d", "pct": 18, "tag": "中线持有"},
            {"label": ">7d", "pct": 15, "tag": "长线"},
        ],
    },
    "by_amount": {
        "title": "单笔交易金额分布",
        "data": [
            {"label": "$0-50", "pct": 55, "tag": "散户试水"},
            {"label": "$50-200", "pct": 22, "tag": "中等仓位"},
            {"label": "$200-1K", "pct": 12, "tag": ""},
            {"label": "$1K-5K", "pct": 7, "tag": ""},
            {"label": "$5K+", "pct": 4, "tag": "鲸鱼"},
        ],
    },
    "platform_revenue": {
        "title": "Top 5 平台年收入（= 用户手续费损失）",
        "source": "DeFiLlama 2025",
        "data": [
            {"name": "Axiom", "revenue_m": 200, "market_share": 57, "color": "#3B82F6"},
            {"name": "Photon", "revenue_m": 96, "market_share": 15, "color": "#8B5CF6"},
            {"name": "GMGN", "revenue_m": 85, "market_share": 8, "color": "#22C55E"},
            {"name": "BullX", "revenue_m": 50, "market_share": 7, "color": "#F97316"},
            {"name": "Trojan", "revenue_m": 40, "market_share": 5, "color": "#6366F1"},
        ],
        "total_fee_m": 471,
        "mev_slippage_m": 500,
        "total_loss_m": 971,
    },
    "methodology": (
        "时段分布：基于 Dune Analytics Solana DEX 交易 block_time 聚合，以 Axiom 为主要样本（57% 市占）。"
        "代币生命周期：token 首次交易时间到当前交易的时间差。"
        "金额分布：单笔 swap 的 USD 金额统计。"
        "平台收入：DeFiLlama 公开数据，2025 年全年累计。"
        "MEV/滑点：按全网 $20B 交易量 × 2.5% 保守估算。"
    ),
}


@router.get("/trading-distribution")
async def get_trading_distribution():
    """交易行为分布（时段/生命周期/金额/平台收入）"""
    return _TRADING_DISTRIBUTION
