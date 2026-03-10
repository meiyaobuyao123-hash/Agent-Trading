import os
from dotenv import load_dotenv

load_dotenv()

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
MAX_TRACKED_TOKENS   = 500         # 最多同时追踪的候选币数量
DATA_RETENTION_DAYS  = 30          # 数据保留天数

# 硬过滤阈值（一票否决）
MIN_BUYERS_HARD      = 10          # 至少 10 个买家才进候选池
MAX_DEV_SOLD_PCT     = 0.30        # dev 卖出超 30% 直接排除
MIN_BUY_SELL_RATIO   = 0.6         # 买卖笔数比最低 0.6

# 打分：进入候选池的 BC 进度窗口
BC_MIN_PCT           = 3.0         # 至少 3% 才有足够数据
BC_MAX_PCT           = 35.0        # 超过 35% 空间已小，不推

# 大单定义
LARGE_BUY_SOL        = 0.5         # 单笔 >= 0.5 SOL 算大单

# ── 热币榜（多链外盘）────────────────────────────────────────

# API 基础地址
GECKO_API        = "https://api.geckoterminal.com/api/v2"
GOPLUS_API       = "https://api.gopluslabs.io/api/v1"
DEXSCREENER_API  = "https://api.dexscreener.com"
HELIUS_RPC       = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# 链配置：gecko_net → GeckoTerminal 网络名；goplus_chain → GoPlus 链ID
# mc_max_usd / liq_max_usd：各链独立上限覆盖（None → 使用全局常量）
# 注：仅 SOL/BSC/Base 的 trending_pools 含大量 3~90d 新兴项目（符合热币策略）
#     ETH/Arbitrum/Polygon/Avalanche/TON 趋势池均为成熟协议(>90d)或过新(<3d)，不适合
HOT_CHAINS = {
    "solana": {"gecko_net": "solana", "goplus_chain": "solana", "mc_max_usd": None, "liq_max_usd": None},
    "bsc":    {"gecko_net": "bsc",    "goplus_chain": "56",     "mc_max_usd": None, "liq_max_usd": None},
    "base":   {"gecko_net": "base",   "goplus_chain": "8453",   "mc_max_usd": None, "liq_max_usd": None},
}

# GeckoTerminal 分页（trending + new_pools 各 GECKO_PAGES 页，每页20条）
# 3链 × 2端点 × 3页 = 18个请求，配合2.5s间隔 + 8s链间冷却，总耗时约4分钟
GECKO_PAGES = 3

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
