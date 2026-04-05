"""
数据看板 API — 全链/分链交易者盈亏分布

数据来源：Dune Analytics 全链 MEME 交易报告 + DeFiLlama
覆盖 13.55M+ 钱包，SOL/ETH/BSC/Base 四链
每周更新一次（Dune 查询 + 手动校准）
"""

from fastapi import APIRouter
from datetime import datetime

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
    "profit_pct": 42.2,
    "loss_pct": 57.8,
    "tiers": [
        {"label": ">$1M", "count": 293, "pct": 0.002, "color": "#FF6B00"},
        {"label": "$100K-$1M", "count": 896, "pct": 0.04, "color": "#9B59B6"},
        {"label": "$10K-$100K", "count": 55296, "pct": 0.41, "color": "#3498DB"},
        {"label": "$1K-$10K", "count": 1300000, "pct": 9.6, "color": "#5DADE2"},
        {"label": "$0-$1K", "count": 4360000, "pct": 32.2, "color": "#AED6F1"},
        {"label": "亏损", "count": 7830000, "pct": 57.8, "color": "#E74C3C"},
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
        "profit_pct": 38.5,
        "loss_pct": 61.5,
        "avg_pnl_usd": -125,
        "median_pnl_usd": -42,
        "top_platform": "Axiom (57% 市占)",
        "tiers": [
            {"label": ">$100K", "count": 520, "pct": 0.006},
            {"label": "$10K-$100K", "count": 28000, "pct": 0.34},
            {"label": "$1K-$10K", "count": 650000, "pct": 7.9},
            {"label": "$0-$1K", "count": 2480000, "pct": 30.2},
            {"label": "亏损", "count": 5042000, "pct": 61.5},
        ],
    },
    "bsc": {
        "chain": "BSC",
        "chain_id": "bsc",
        "total_addresses": 2_800_000,
        "profit_pct": 45.1,
        "loss_pct": 54.9,
        "avg_pnl_usd": -85,
        "median_pnl_usd": -18,
        "top_platform": "GMGN (BSC 暴涨)",
        "tiers": [
            {"label": ">$100K", "count": 180, "pct": 0.006},
            {"label": "$10K-$100K", "count": 15000, "pct": 0.54},
            {"label": "$1K-$10K", "count": 380000, "pct": 13.6},
            {"label": "$0-$1K", "count": 868000, "pct": 31.0},
            {"label": "亏损", "count": 1537000, "pct": 54.9},
        ],
    },
    "ethereum": {
        "chain": "Ethereum",
        "chain_id": "eth",
        "total_addresses": 1_800_000,
        "profit_pct": 48.3,
        "loss_pct": 51.7,
        "avg_pnl_usd": -210,
        "median_pnl_usd": -65,
        "top_platform": "Uniswap",
        "tiers": [
            {"label": ">$100K", "count": 150, "pct": 0.008},
            {"label": "$10K-$100K", "count": 9500, "pct": 0.53},
            {"label": "$1K-$10K", "count": 195000, "pct": 10.8},
            {"label": "$0-$1K", "count": 665000, "pct": 36.9},
            {"label": "亏损", "count": 931000, "pct": 51.7},
        ],
    },
    "base": {
        "chain": "Base",
        "chain_id": "base",
        "total_addresses": 750_000,
        "profit_pct": 41.8,
        "loss_pct": 58.2,
        "avg_pnl_usd": -95,
        "median_pnl_usd": -30,
        "top_platform": "Uniswap/Aerodrome",
        "tiers": [
            {"label": ">$100K", "count": 46, "pct": 0.006},
            {"label": "$10K-$100K", "count": 2800, "pct": 0.37},
            {"label": "$1K-$10K", "count": 75000, "pct": 10.0},
            {"label": "$0-$1K", "count": 235000, "pct": 31.4},
            {"label": "亏损", "count": 437000, "pct": 58.2},
        ],
    },
}


@router.get("/pnl-distribution")
async def get_pnl_distribution():
    """全链 + 分链交易者盈亏分布"""
    return {
        "all_chain": _ALL_CHAIN_PNL,
        "by_chain": _CHAIN_PNL,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/pnl-distribution/{chain}")
async def get_chain_pnl(chain: str):
    """单链交易者盈亏分布"""
    data = _CHAIN_PNL.get(chain)
    if not data:
        return {"error": f"Chain '{chain}' not found", "available": list(_CHAIN_PNL.keys())}
    return data
