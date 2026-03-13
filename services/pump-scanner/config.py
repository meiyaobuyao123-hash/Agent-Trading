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
ENRICH_DELAY_S       = 3           # 新币出现后等 3s 再拉详情
MAX_TRACKED_TOKENS   = 2000        # 最多同时追踪（配合3h淘汰，日均可处理2万+）
DATA_RETENTION_DAYS  = 30          # 数据保留天数

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
