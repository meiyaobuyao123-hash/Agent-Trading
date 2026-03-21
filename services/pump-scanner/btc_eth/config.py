"""BTC/ETH 模块配置"""
import os

# ── Binance ──────────────────────────────────────────────
BINANCE_WS_URL = "wss://stream.binance.com:9443/stream"
BINANCE_REST_URL = "https://api.binance.com"
BINANCE_FAPI_URL = "https://fapi.binance.com"

BINANCE_STREAMS = [
    "btcusdt@kline_1h", "btcusdt@kline_4h", "btcusdt@ticker",
    "ethusdt@kline_1h", "ethusdt@kline_4h", "ethusdt@ticker",
]

# ── Blockchain.com ───────────────────────────────────────
BLOCKCHAIN_WS_URL = "wss://ws.blockchain.info/inv"
BLOCKCHAIN_CHARTS_URL = "https://api.blockchain.info/charts"
WHALE_TX_THRESHOLD_BTC = 50  # >50 BTC = 鲸鱼交易

# ── 第三方数据源 ─────────────────────────────────────────
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
CRYPTOPANIC_URL = "https://cryptopanic.com/api/free/v1/posts/"

COINALYZE_URL = "https://api.coinalyze.net/v1"

MEMPOOL_URL = "https://mempool.space/api"

DEFILAMA_URL = "https://api.llama.fi"

TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")
TWELVE_DATA_URL = "https://api.twelvedata.com"

LUNARCRUSH_API_KEY = os.getenv("LUNARCRUSH_API_KEY", "")
LUNARCRUSH_URL = "https://lunarcrush.com/api4/public"

ALTERNATIVE_ME_URL = "https://api.alternative.me/fng/"

ULTRASOUND_URL = "https://ultrasound.money/api/v2"

# ── Dune ─────────────────────────────────────────────────
DUNE_API_KEY = os.getenv("DUNE_API_KEY", "ERCPCGBGaYY11v30KyWLmlfgHs2fcZ1G")
DUNE_URL = "https://api.dune.com/api/v1"
# 交易所流入/SOPR 查询 ID（需要在 Dune 网页创建后填入）
DUNE_BTC_EXCHANGE_FLOW_QUERY = os.getenv("DUNE_BTC_EXCHANGE_FLOW_QUERY", "")
DUNE_ETH_EXCHANGE_FLOW_QUERY = os.getenv("DUNE_ETH_EXCHANGE_FLOW_QUERY", "")

# ── OKX（复用现有 Key）──────────────────────────────────
OKX_API_KEY = os.getenv("OKX_API_KEY", "")
OKX_SECRET = os.getenv("OKX_SECRET", "")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")

# ── Claude ───────────────────────────────────────────────
BTCETH_CLAUDE_API_KEY = os.getenv("BTCETH_CLAUDE_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
BTCETH_CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ── 采集频率（秒）────────────────────────────────────────
INTERVAL_HIGH_FREQ = 300      # 5 min
INTERVAL_MID_FREQ = 1800      # 30 min
INTERVAL_LOW_FREQ = 14400     # 4 h
INTERVAL_DAILY = 86400        # 24 h

# ── 指标引擎 ─────────────────────────────────────────────
KLINE_BUFFER_SIZE = 200       # K线缓存条数
INDICATOR_PERSIST_INTERVAL = 300  # 5min 写一次 DB
STALE_THRESHOLD = {
    "high_freq": 600,         # 10 min
    "mid_freq": 3600,         # 1 h
    "low_freq": 28800,        # 8 h
    "daily": 172800,          # 48 h
}

# ── 信号生成 ─────────────────────────────────────────────
SIGNAL_RSI_OVERSOLD = 30
SIGNAL_RSI_OVERBOUGHT = 70
SIGNAL_FUNDING_EXTREME_HIGH = 0.03   # 3% 资金费率 = 极端多头
SIGNAL_FUNDING_EXTREME_LOW = -0.01   # 负费率 = 空头拥挤
SIGNAL_OI_CHANGE_THRESHOLD = 0.10    # OI 变化 > 10% = 显著
SIGNAL_CONFIDENCE_MIN = 60           # 低于 60 不发信号

# ── 模拟盘 ───────────────────────────────────────────────
PAPER_DEFAULT_CAPITAL = 10000.0
PAPER_MAX_POSITION_PCT = 0.30        # 单笔最大仓位 30%
PAPER_STOP_LOSS_DEFAULT_PCT = 0.05   # 默认止损 5%
PAPER_TAKE_PROFIT_DEFAULT_PCT = 0.10 # 默认止盈 10%

# ── 周期分析 ─────────────────────────────────────────────
CYCLE_PHASES = [
    "accumulation", "recovery", "breakout",
    "bull_run", "euphoria", "distribution", "bear"
]

# ── 断路器 ───────────────────────────────────────────────
COLLECTOR_MAX_FAILURES = 5
COLLECTOR_BACKOFF_BASE = 2       # 指数退避基数（秒）
COLLECTOR_BACKOFF_MAX = 300      # 最大退避（秒）
