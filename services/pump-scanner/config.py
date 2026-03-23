import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# Helius (持仓人数，免费套餐)
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")

# pump.fun
PUMPPORTAL_WS = "wss://pumpportal.fun/api/data"
PUMP_REST     = "https://frontend-api-v3.pump.fun"

# Bonding Curve 常量
VIRTUAL_SOL_INIT     = 30.0        # pump.fun 初始注入虚拟 SOL
GRADUATION_SOL       = 85.0        # 毕业所需真实 SOL
GRADUATION_SOL_LAMPS = 85_000_000_000  # lamports

# 扫描参数
SNAPSHOT_INTERVAL_S  = 60          # 每分钟打一次快照
ENRICH_DELAY_S       = 5           # 初筛通过后等 5s 再拉 REST 详情
DATA_RETENTION_DAYS  = 30          # 数据保留天数

# 三阶段架构参数
# 阶段1：WS 全量捕获（无上限，直接写DB）
# 阶段2：交易观察（内存追踪活跃币的交易）
MAX_TRADE_TRACKED    = 20_000      # 内存中最多同时追踪交易的代币数（仅交易计数，非全量详情）
TRADE_EVICT_AGE_H    = 3           # 超过3小时未毕业 → 从交易追踪中移除
TRADE_DEAD_AGE_H     = 1           # 超过1小时 + 30min无交易 → 死币移除

# 阶段3：按需 enrich（只对初筛通过的币拉 REST）
ENRICH_MIN_BUYERS    = 3           # 初筛：至少3个独立买家才触发 enrich
ENRICH_MIN_BC_PCT    = 2.0         # 初筛：至少2%进度才触发 enrich
ENRICH_CONCURRENCY   = 20          # REST 并发拉取上限
ENRICH_COOLDOWN_S    = 0.2         # 每次 REST 请求间最小间隔（防429）

# 硬过滤阈值（一票否决）— 放宽以覆盖更多早期代币
MIN_BUYERS_HARD      = 5           # 至少 5 个买家才进候选池（早期代币60s内不到10人正常）
MAX_DEV_SOLD_PCT     = 0.50        # dev 卖出超 50% 直接排除（30%太严格）
MIN_BUY_SELL_RATIO   = 0.4         # 买卖笔数比最低 0.4（早期波动大，放宽）

# 打分：进入候选池的 BC 进度窗口
BC_MIN_PCT           = 3.0         # 至少 3% 才有足够数据
BC_MAX_PCT           = 35.0        # 超过 35% 空间已小，不推

# 大单定义
LARGE_BUY_SOL        = 0.5         # 单笔 >= 0.5 SOL 算大单

# ── OKX DEX Market API v6 ─────────────────────────────────────
OKX_API_KEY    = os.getenv("OKX_API_KEY", "")
OKX_SECRET_KEY = os.getenv("OKX_SECRET_KEY", "")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")
OKX_API_BASE   = "https://www.okx.com"

# OKX chainIndex（与 HOT_CHAINS key 对应）
OKX_CHAIN_INDEX = {
    "solana": "501",
    "bsc":    "56",
    "base":   "8453",
    "eth":    "1",
}

# ── 热币榜（多链外盘）────────────────────────────────────────

# API 基础地址
GOPLUS_API       = "https://api.gopluslabs.io/api/v1"
DEXSCREENER_API  = "https://api.dexscreener.com"
HELIUS_RPC       = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# 链配置：goplus_chain → GoPlus 链ID
# mc_max_usd / liq_max_usd：各链独立上限覆盖（None → 使用全局常量）
# 4链覆盖：SOL/BSC/Base/ETH
# 发现数据源：OKX toplist（按成交量+涨幅各 Top100，合并去重）
HOT_CHAINS = {
    "solana": {"goplus_chain": "solana", "mc_max_usd": None, "liq_max_usd": None},
    "bsc":    {"goplus_chain": "56",     "mc_max_usd": None, "liq_max_usd": None},
    "base":   {"goplus_chain": "8453",   "mc_max_usd": None, "liq_max_usd": None},
    "eth":    {"goplus_chain": "1",      "mc_max_usd": None, "liq_max_usd": None},
}

# 硬过滤阈值（不满足直接排除，不进入打分）
HOT_MIN_AGE_DAYS     = 3           # 至少上线3天（排除纯pump）
HOT_MAX_AGE_DAYS     = 90          # 最多90天（聚焦新兴机会）
HOT_MIN_LIQ_USD      = 30_000      # 流动性最低 $30K
HOT_MAX_LIQ_USD      = 5_000_000   # 流动性最高 $5M（超出是巨鲸游戏）
HOT_MIN_MC_USD       = 200_000     # 市值最低 $200K
HOT_MAX_MC_USD       = 50_000_000  # 市值最高 $50M（$200K~$50M 有暴涨空间）
HOT_MIN_VOL_24H_USD  = 15_000      # 24h交易量最低 $15K
HOT_MIN_LIQ_MC_RATIO = 0.08        # 流动性/市值比 >= 8%（防流动性陷阱）

# GoPlus 安全阈值
HOT_MAX_TAX          = 10.0        # 买/卖税 > 10% 标记为风险
HOT_MAX_TOP10_PCT    = 0.80        # Top10 持仓 > 80% 标记为风险

# ── Hot Coin Optimizer Agent ─────────────────────────────────────
HOT_OPTIMIZER_API_KEY = os.getenv("HOT_OPTIMIZER_API_KEY", "")

# ── Agent 配置（PRD-004 M-03）─────────────────────────────────
SIGNAL_POOL_MIN_SCORE = int(os.getenv("SIGNAL_POOL_MIN_SCORE", "55"))
SIGNAL_POOL_BC_MIN = float(os.getenv("SIGNAL_POOL_BC_MIN", "3"))
SIGNAL_POOL_BC_MAX = float(os.getenv("SIGNAL_POOL_BC_MAX", "35"))
AGENT_MONTHLY_QUOTA = int(os.getenv("AGENT_MONTHLY_QUOTA", "20"))

# ── 风控配置（PRD-004 M-03）─────────────────────────────────
RISK_DAILY_LOSS_LIMIT = float(os.getenv("RISK_DAILY_LOSS_LIMIT", "50"))
RISK_WEEKLY_LOSS_LIMIT = float(os.getenv("RISK_WEEKLY_LOSS_LIMIT", "200"))
RISK_MAX_POSITION_USD = float(os.getenv("RISK_MAX_POSITION_USD", "100"))
RISK_MAX_DRAWDOWN_PCT = float(os.getenv("RISK_MAX_DRAWDOWN_PCT", "20"))
RISK_BTC_CRISIS_PCT = float(os.getenv("RISK_BTC_CRISIS_PCT", "3"))
RISK_TRAILING_STOP_ACTIVATION = float(os.getenv("RISK_TRAILING_STOP_ACTIVATION", "15"))

# ── BTC/ETH 信号配置（PRD-004 M-03）─────────────────────────
SIGNAL_COOLDOWN_HOURS = int(os.getenv("SIGNAL_COOLDOWN_HOURS", "4"))
DEPTH_IMBALANCE_THRESHOLD = float(os.getenv("DEPTH_IMBALANCE_THRESHOLD", "0.3"))

# ── 胜率统一定义（PRD-003）─────────────────────────────────────
WIN_RATE_PUMP_D3_PCT = 30       # Pump 内盘：D3 涨幅 ≥ 30% 算 hit
WIN_RATE_HOT_D3_PCT = 20        # 热币：D3 涨幅 ≥ 20% 算 hit
WIN_RATE_BTCETH_PNL_PCT = 2     # BTC/ETH：PnL ≥ 2% 算 hit
WIN_RATE_AGENT_BREAK_EVEN = 0   # Agent 策略：PnL ≥ 0% 就算 win

# ── PRD-006: Regime 检测配置 ─────────────────────────────────────
CUSUM_WINDOW = int(os.getenv("CUSUM_WINDOW", "24"))
CUSUM_K_FACTOR = float(os.getenv("CUSUM_K_FACTOR", "0.5"))
CUSUM_H_BTC = float(os.getenv("CUSUM_H_BTC", "3.0"))
CUSUM_H_SOL = float(os.getenv("CUSUM_H_SOL", "2.5"))
CUSUM_H_ETH = float(os.getenv("CUSUM_H_ETH", "3.0"))
REGIME_SHADOW_MODE = os.getenv("REGIME_SHADOW_MODE", "true").lower() == "true"

# ── PRD-006: Regime 风控参数（可被优化 Agent 提案修改）──────────────
REGIME_RISK_PARAMS = {
    "TRENDING_UP":     {"position_pct": 1.0, "sl_mult": 1.0, "tp_mult": 1.5, "new_trades": True,  "force_close": False},
    "TRENDING_DOWN":   {"position_pct": 0.3, "sl_mult": 0.7, "tp_mult": 0.8, "new_trades": False, "force_close": False},
    "RANGING":         {"position_pct": 0.5, "sl_mult": 0.8, "tp_mult": 0.8, "new_trades": True,  "force_close": False},
    "HIGH_VOLATILITY": {"position_pct": 0.5, "sl_mult": 1.5, "tp_mult": 1.0, "new_trades": True,  "force_close": False},
    "BREAKOUT":        {"position_pct": 0.8, "sl_mult": 1.2, "tp_mult": 2.0, "new_trades": True,  "force_close": False},
    "CRISIS":          {"position_pct": 0.0, "sl_mult": 0.5, "tp_mult": 0.0, "new_trades": False, "force_close": True},
    "RECOVERY":        {"position_pct": 0.3, "sl_mult": 0.8, "tp_mult": 1.0, "new_trades": True,  "force_close": False},
}
