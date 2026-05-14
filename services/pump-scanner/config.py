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

# ── AVE Cloud Skill（黑客松开关）──────────────────────────
# USE_AVE=true → 数据/安全/交易全部走 AVE Cloud API
# USE_AVE=false → 走现有方案（DexScreener + GoPlus + OKX DEX）
USE_AVE       = os.getenv("USE_AVE", "false").lower() == "true"
AVE_API_KEY   = os.getenv("AVE_API_KEY", "")
AVE_DATA_BASE = "https://data.ave-api.xyz/v2"
AVE_TRADE_BASE = "https://bot-api.ave.ai"

# ── 模拟盘过滤配置（基于真实数据校准，支持环境变量覆盖）────
def _parse_int_set(env_val: str) -> set:
    try:
        return {int(x.strip()) for x in env_val.split(",") if x.strip()}
    except Exception:
        return set()

# 垃圾时段（UTC 小时），逗号分隔；默认基于历史胜率 <40% 的时段
SIM_BAD_HOURS_UTC = _parse_int_set(os.getenv("SIM_BAD_HOURS_UTC", "0,10,18,21,22"))

# 链权重（0.0-1.5）：>=1.0 全通过，<1.0 按权重概率通过
SIM_CHAIN_WEIGHTS = {
    "bsc":      float(os.getenv("SIM_WEIGHT_BSC", "1.5")),
    "base":     float(os.getenv("SIM_WEIGHT_BASE", "1.0")),
    "eth":      float(os.getenv("SIM_WEIGHT_ETH", "1.0")),
    "ethereum": float(os.getenv("SIM_WEIGHT_ETH", "1.0")),
    "solana":   float(os.getenv("SIM_WEIGHT_SOLANA", "0.6")),
    "btc_eth":  1.0,
}

# TP/SL 配置：按链差异化（tp_pct, sl_pct）
SIM_TP_SL_BY_CHAIN = {
    "solana":   (float(os.getenv("SIM_TP_SOLANA",  "40")), float(os.getenv("SIM_SL_SOLANA",  "8"))),
    "bsc":      (float(os.getenv("SIM_TP_BSC",     "25")), float(os.getenv("SIM_SL_BSC",     "12"))),
    "base":     (float(os.getenv("SIM_TP_BASE",    "25")), float(os.getenv("SIM_SL_BASE",    "12"))),
    "eth":      (float(os.getenv("SIM_TP_ETH",     "20")), float(os.getenv("SIM_SL_ETH",     "10"))),
    "ethereum": (float(os.getenv("SIM_TP_ETH",     "20")), float(os.getenv("SIM_SL_ETH",     "10"))),
    "btc_eth":  (float(os.getenv("SIM_TP_BTC_ETH", "15")), float(os.getenv("SIM_SL_BTC_ETH", "10"))),
}
SIM_TP_DEFAULT = float(os.getenv("SIM_TP_DEFAULT", "20"))
SIM_SL_DEFAULT = float(os.getenv("SIM_SL_DEFAULT", "10"))

# Score 阈值按 source 区分
# 结构：{source: {"pass_above": [score, weight], ...}}
# weight=1.0 必过，<1.0 按概率通过
# 基于 hot 源 617 笔真实统计
SIM_SCORE_THRESHOLDS = {
    "hot": {
        "ranges": [
            (80.0, 999.0, 1.0),   # 80+ 必过
            (70.0, 80.0,  0.5),   # 70-80 虚高分，50% 概率
            (60.0, 70.0,  1.0),   # 60-70 甜点区，必过
            (50.0, 60.0,  0.4),   # 50-60 最差段，40% 概率
        ],
    },
    "pump": {
        # pump 打分模型不同，保守策略：只在 75+ 必过，55-75 全过
        "ranges": [
            (75.0, 999.0, 1.0),
            (55.0, 75.0,  1.0),
        ],
    },
    "smart_money": {
        # smart_money 的 score 是 heat_score，另有触发阈值控制，这里直接通过
        "ranges": [(0.0, 999.0, 1.0)],
    },
}
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

# ── R60: 回测扣手续费用 — 各链 DEX 单边综合成本 ────────────────
# 单边 = 进单 OR 出单(LP fee + 平均滑点 + Gas 摊销)
# 往返 = 进 + 出 = single × 2
# 用户在 strategy.risk_params.max_slippage_pct 改过 → 优先用户值
# 保守估计:实盘可能偏离 0.2%-2%(取决于池子流动性 / 单笔金额)
DEX_FEE_PCT_SINGLE = {
    "solana": 1.0,    # Jupiter LP 0.85% + 平均滑点 0.15%(meme 币偏保守)
    "eth":    0.8,    # Uniswap V3 0.3% + gas + slippage
    "base":   0.6,    # Uniswap V3 0.3% + Base gas 极低 + slippage
    "bsc":    0.7,    # PancakeSwap 0.25% + BSC gas + slippage
}
DEX_FEE_PCT_DEFAULT_SINGLE = 1.0  # 未知链 fallback

# ── PRD-009: 多 DEX 执行路由 ─────────────────────────────────────
# Jupiter (SOL) — 免费，无需 API Key
JUPITER_BASE_URL = "https://quote-api.jup.ag/v6"
JUPITER_QUOTE_TIMEOUT = float(os.getenv("JUPITER_QUOTE_TIMEOUT", "5"))

# 1inch (EVM) — 可选，需 API Key (v1.1 Q9: 未配置则跳过)
ONEINCH_API_KEY = os.getenv("ONEINCH_API_KEY", "")
ONEINCH_BASE_URL = "https://api.1inch.dev/swap/v6.0"
ONEINCH_QUOTE_TIMEOUT = float(os.getenv("ONEINCH_QUOTE_TIMEOUT", "5"))

# DEX 路由参数
DEX_PARALLEL_QUOTE_TIMEOUT = float(os.getenv("DEX_PARALLEL_QUOTE_TIMEOUT", "2.0"))  # v1.1 Q10
DEX_SPLIT_IMPACT_THRESHOLD = float(os.getenv("DEX_SPLIT_IMPACT_THRESHOLD", "0.02"))  # v1.1 Q11: 2%
DEX_MIN_SPLIT_AMOUNT_USD = float(os.getenv("DEX_MIN_SPLIT_AMOUNT_USD", "20"))
DEX_SPLIT_INTERVAL_S = float(os.getenv("DEX_SPLIT_INTERVAL_S", "2"))

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
