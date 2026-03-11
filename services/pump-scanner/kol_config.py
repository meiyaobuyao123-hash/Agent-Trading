"""
KOL 舆情采集系统 — 配置文件
Python 3.9 兼容
"""

import os
import re
from typing import Dict, FrozenSet, List, Pattern, Set, Tuple

# ============================================================
# Twitter 数据采集配置
# ============================================================

# twscrape 数据库路径
TWSCRAPE_DB_PATH: str = os.getenv(
    "TWSCRAPE_DB_PATH",
    os.path.join(os.path.dirname(__file__), "twscrape_accounts.db"),
)

# twitterapi.io API Key
TWITTERAPI_IO_KEY: str = os.getenv("TWITTERAPI_IO_KEY", "")

# 扫描间隔（秒）
SCAN_INTERVAL_S: int = 600          # 每 10 分钟扫描一轮
SCAN_BATCH_SIZE: int = 20           # 每批扫描 KOL 数
SCAN_DELAY_BETWEEN_S: float = 2.0   # 单个 KOL 请求间隔（秒）
TWEETS_PER_KOL: int = 20            # 每次拉取最新 N 条推文

# 推文回溯窗口
TWEET_LOOKBACK_HOURS: int = 24      # 只处理最近 24h 的推文

# ============================================================
# KOL 分层阈值（按粉丝数）
# ============================================================

TIER_THRESHOLDS: Dict[str, Tuple[int, int]] = {
    "mega":   (500_000, 999_999_999),   # >500K
    "large":  (100_000, 499_999),       # 100K-500K
    "medium": (20_000,  99_999),        # 20K-100K
    "small":  (5_000,   19_999),        # 5K-20K
}

# 各层信号权重（用于共振信号计算）
TIER_WEIGHTS: Dict[str, float] = {
    "mega":   5.0,
    "large":  3.0,
    "medium": 1.5,
    "small":  1.0,
}

# ============================================================
# KOL 分类
# ============================================================

KOL_CATEGORIES: List[str] = [
    "crypto",       # 综合加密货币
    "defi",         # DeFi 协议/研究
    "nft",          # NFT 市场
    "meme",         # Meme 币专家
    "vc",           # 风投/机构
    "media",        # 媒体/新闻
    "analyst",      # 链上分析师
    "developer",    # 开发者/技术
]

# ============================================================
# 情绪分析词库
# ============================================================

BULLISH_KEYWORDS: FrozenSet[str] = frozenset([
    # 英文看多词
    "bullish", "moon", "mooning", "pump", "pumping", "rally",
    "breakout", "breaking out", "all time high", "ath",
    "buy", "buying", "accumulate", "accumulating", "load up",
    "long", "longing", "undervalued", "gem", "hidden gem",
    "100x", "1000x", "10x", "send it", "lfg",
    "wagmi", "gm", "bullrun", "bull run", "parabolic",
    "massive", "explosive", "skyrocket",
    # 中文看多词
    "看多", "看涨", "暴涨", "起飞", "拉盘",
    "抄底", "建仓", "加仓", "冲", "上车",
    "百倍", "千倍", "十倍", "低估",
])

BEARISH_KEYWORDS: FrozenSet[str] = frozenset([
    # 英文看空词
    "bearish", "dump", "dumping", "crash", "crashing",
    "sell", "selling", "short", "shorting", "overvalued",
    "rug", "rugpull", "rug pull", "scam", "ponzi",
    "dead", "rekt", "rip", "ngmi", "exit",
    "bubble", "top signal", "distribution", "breakdown",
    "capitulation", "liquidation", "bloodbath", "plunge",
    "tank", "tanking", "fade", "fading",
    # 中文看空词
    "看空", "看跌", "暴跌", "崩盘", "砸盘",
    "出货", "减仓", "清仓", "跑路", "归零",
    "骗局", "貔貅", "割韭菜", "高位",
])

# ============================================================
# Emoji 信号映射
# ============================================================

BULLISH_EMOJIS: FrozenSet[str] = frozenset([
    "\U0001F680",  # rocket
    "\U0001F525",  # fire
    "\U0001F48E",  # gem
    "\U0001F4B0",  # money bag
    "\U0001F4B8",  # money with wings
    "\U0001F4C8",  # chart increasing
    "\U0001F31D",  # full moon face
    "\U0001F7E2",  # green circle
    "\U00002705",  # check mark
    "\U0001F3AF",  # dart / bullseye
    "\U0001F451",  # crown
    "\U0001F4AA",  # flexed biceps
    "\U0001F929",  # star-struck
    "\U00002B06\uFE0F",  # up arrow
    "\U0001F6A8",  # rotating light (alert/bullish signal)
])

BEARISH_EMOJIS: FrozenSet[str] = frozenset([
    "\U0001F480",  # skull
    "\U00002620\uFE0F",  # skull and crossbones
    "\U0001F4C9",  # chart decreasing
    "\U0001F534",  # red circle
    "\U0000274C",  # cross mark
    "\U0001F6A9",  # red flag
    "\U00002B07\uFE0F",  # down arrow
    "\U0001F4A9",  # pile of poo
    "\U0001F627",  # anguished face
    "\U0001F62D",  # loudly crying face
    "\U000026A0\uFE0F",  # warning
    "\U0001F6D1",  # stop sign
])

# ============================================================
# 广告/推广过滤关键词
# ============================================================

PROMO_KEYWORDS: FrozenSet[str] = frozenset([
    "#ad", "#sponsored", "#promotion", "#paid",
    "sponsored by", "paid partnership", "in partnership with",
    "not financial advice", "nfa", "dyor",
    "use my code", "use code", "referral", "affiliate",
    "sign up with", "register with", "use my link",
    "giveaway", "airdrop alert", "free tokens",
    "dm me for", "join my group", "join telegram",
    "presale", "private sale", "whitelist spot",
    "guaranteed returns", "guaranteed profit",
    "100% safe", "zero risk", "no risk",
])

# ============================================================
# 代币提取正则表达式
# ============================================================

# $TICKER 格式：$后跟 1-10 个大小写字母
TICKER_PATTERN: Pattern[str] = re.compile(
    r'\$([A-Za-z]{1,10})\b'
)

# Solana 地址：Base58，32-44 字符
SOL_ADDRESS_PATTERN: Pattern[str] = re.compile(
    r'\b([1-9A-HJ-NP-Za-km-z]{32,44})\b'
)

# EVM 地址：0x + 40 hex 字符
EVM_ADDRESS_PATTERN: Pattern[str] = re.compile(
    r'\b(0x[a-fA-F0-9]{40})\b'
)

# ============================================================
# 排除的常见 ticker（非具体可交易代币）
# ============================================================

EXCLUDED_TICKERS: FrozenSet[str] = frozenset([
    # 法币 & 稳定币
    "USD", "USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP",
    "EUR", "GBP", "JPY", "CNY", "KRW",
    # 主流大币（通常不是 meme/小币信号）
    "BTC", "ETH", "BNB", "SOL", "ADA", "DOT", "AVAX",
    "XRP", "DOGE", "MATIC", "LINK", "UNI", "ATOM",
    "LTC", "BCH", "FIL", "NEAR", "APT", "SUI", "TRX",
    "TON", "ARB", "OP",
    # 常见英文单词误匹配
    "THE", "AND", "FOR", "NOT", "ALL", "ARE", "BUT",
    "HAS", "HIS", "HER", "HOW", "ITS", "LET", "MAY",
    "NEW", "NOW", "OLD", "OUR", "OUT", "OWN", "SAY",
    "SHE", "TOO", "USE", "WAY", "WHO", "BOY", "DID",
    "GET", "HIM", "MAN", "RUN", "SET", "TOP", "WIN",
    "AI", "GM", "GN", "CT", "NFT", "CEO", "CTO",
    "DAO", "TVL", "APY", "APR", "ROI", "ATH", "ATL",
    "IDO", "ICO", "IEO", "DEX", "CEX", "LP", "AMM",
    "FDV", "API", "SDK",
])

# ============================================================
# 共振信号检测配置
# ============================================================

SIGNAL_WINDOW_HOURS: int = 24        # 检测窗口：24 小时
SIGNAL_MIN_KOL_COUNT: int = 3        # 至少 3 个 KOL 提及才算共振
SIGNAL_DECAY_HOURS: int = 48         # 信号衰减：48 小时后过期

# 共振强度计算中 K 维度评分权重（满分 100）
SIGNAL_WEIGHTS: Dict[str, float] = {
    "mention_count": 4.0,   # 提及次数权重
    "quality":       3.0,   # KOL 质量权重（tier + accuracy）
    "sentiment":     3.0,   # 情绪一致性权重
}

# K 维度评分权重（kol_scorer.py 使用，满分 10）
K_SCORE_WEIGHTS: Dict[str, float] = {
    "mention_count":       4.0,   # K1: 提及次数 (4分)
    "quality_weighted":    3.0,   # K2: KOL 质量加权 (3分)
    "sentiment_consensus": 3.0,   # K3: 情绪一致性 (3分)
}

# 信号强度分级
SIGNAL_LEVELS: Dict[str, Tuple[float, float]] = {
    "strong":  (70.0, 100.0),   # 强信号
    "medium":  (40.0, 70.0),    # 中等信号
    "weak":    (20.0, 40.0),    # 弱信号
}

# ============================================================
# 情绪分析配置
# ============================================================

# 情绪判定阈值
SENTIMENT_BULLISH_THRESHOLD: float = 0.3    # score > 0.3 → bullish
SENTIMENT_BEARISH_THRESHOLD: float = -0.3   # score < -0.3 → bearish

# 关键词权重
KEYWORD_SENTIMENT_WEIGHT: float = 0.4
EMOJI_SENTIMENT_WEIGHT: float = 0.2
ENGAGEMENT_SENTIMENT_WEIGHT: float = 0.2
CONTEXT_SENTIMENT_WEIGHT: float = 0.2

# ============================================================
# 互动率计算
# ============================================================

ENGAGEMENT_WEIGHTS: Dict[str, float] = {
    "reply":   1.0,
    "retweet": 2.0,
    "like":    0.5,
    "quote":   3.0,
}

# ============================================================
# 准确率追踪配置
# ============================================================

# 价格检查时间点
ACCURACY_CHECK_HOURS: List[int] = [24, 72, 168]   # 1d, 3d, 7d

# 翻倍（2x）判定
ACCURACY_2X_THRESHOLD: float = 2.0                 # 价格达到提及时 2 倍
ACCURACY_2X_WINDOW_DAYS: int = 7                   # 7 天内观察

# KOL 准确率更新间隔
ACCURACY_UPDATE_INTERVAL_HOURS: int = 6

# ============================================================
# 数据保留
# ============================================================

KOL_DATA_RETENTION_DAYS: int = 90      # 推文保留 90 天
SIGNAL_RETENTION_DAYS: int = 30        # 信号保留 30 天

# ============================================================
# 速率限制
# ============================================================

TWITTER_RATE_LIMIT_PER_15MIN: int = 15   # twitterapi.io 每15分钟请求上限
TWITTER_RATE_LIMIT_BUFFER: float = 1.2   # 安全缓冲系数

# ============================================================
# 日志
# ============================================================

KOL_LOG_PREFIX: str = "[KOL]"
