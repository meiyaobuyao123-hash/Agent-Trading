# AiTrading Pro — AVE Cloud Skill 集成文档

## 目录

1. [项目概述](#1-项目概述)
2. [使用的 AVE Skills](#2-使用的-ave-skills)
3. [模块 1：多链热币发现](#3-模块-1多链热币发现)
4. [模块 2：代币安全检测](#4-模块-2代币安全检测)
5. [模块 3：实时价格服务](#5-模块-3实时价格服务)
6. [模块 4：聪明钱数据](#6-模块-4聪明钱数据)
7. [模块 5：交易执行](#7-模块-5交易执行)
8. [系统架构图](#8-系统架构图)
9. [API 调用明细表](#9-api-调用明细表)
10. [核心实现：ave_client.py](#10-核心实现ave_clientpy)
11. [效果指标](#11-效果指标)
12. [支持链矩阵](#12-支持链矩阵)
13. [环境配置](#13-环境配置)
14. [技术创新点](#14-技术创新点)

---

## 1. 项目概述

AiTrading Pro 是基于 AVE Cloud Skills 构建的 AI 驱动多链加密货币自动交易系统。系统通过 AVE 的数据聚合和交易基础设施，实现了从信号发现到链上执行的完整闭环。

### 核心能力

- **多链覆盖**：Solana / BSC / ETH / Base 四链并行监控
- **五源信号**：热币榜单、pump.fun 内盘、聪明钱追踪、KOL 舆情、BTC/ETH 宏观
- **三级 AI 决策**：L1 规则引擎快筛 → L2 Claude LLM 深度分析 → L3 牛熊辩论置信度评分
- **三层记忆系统**：工作记忆（当前持仓上下文）→ 情景记忆（历史交易经验）→ 语义记忆（市场模式知识库）
- **七状态市场适应**：Regime Detector 实时识别 BULL / BEAR / SIDEWAYS / VOLATILE / CRISIS / RECOVERY / ACCUMULATION
- **自托管交易**：私钥永远在本地，AVE 只负责路由和构建交易数据

### 技术栈

| 层级 | 技术 |
|------|------|
| 数据层 | AVE Data REST API (`ave-data-rest`) |
| 交易层 | AVE Chain Wallet API (`ave-trade-chain-wallet`) |
| AI 决策 | Claude Opus 4.6 (Anthropic API) |
| 后端运行时 | Python 3.9+ / asyncio / aiohttp |
| 数据库 | Supabase (PostgreSQL) |
| 前端 | Flutter (iOS/Android) + Next.js Portal |
| 部署 | Ubuntu 服务器 (systemd + nginx) |

---

## 2. 使用的 AVE Skills

### 2.1 ave-data-rest

提供多链代币数据聚合，是系统的数据基础设施。

| 端点 | 功能 | 系统用途 |
|------|------|----------|
| `/tokens/trending` | 获取链上热门代币列表 | 热币发现层，每链 50 个候选 |
| `/tokens/{addr}-{chain}` | 单个代币详情 | 实时价格、市值、流动性、成交量、持有人数 |
| `/contracts/{addr}-{chain}` | 合约安全审计 | 蜜罐检测、税率分析、风险评分、铸造权检查 |
| `/address/smart_wallet/list` | 聪明钱钱包列表 | 获取链上高利润地址，融合内部钱包库 |
| `/tokens` | 关键词搜索代币 | 补充发现未上榜代币 |

### 2.2 ave-trade-chain-wallet

提供自托管多链交易能力，私钥永远不离开本地。

| 端点 | 功能 | 系统用途 |
|------|------|----------|
| `chainWallet/getAmountOut` | 交易报价 | 买入前获取预期输出数量和价格影响 |
| `chainWallet/createSolanaTx` | 创建 Solana 交易 | 构建待签名的 Solana 交易数据 |
| `chainWallet/createEvmTx` | 创建 EVM 交易 | 构建待签名的 EVM (BSC/ETH/Base) 交易数据 |
| `chainWallet/sendSignedSolanaTx` | 发送已签名 Solana 交易 | 广播 Solana 交易到链上 |
| `chainWallet/sendSignedEvmTx` | 发送已签名 EVM 交易 | 广播 EVM 交易到链上 |

---

## 3. 模块 1：多链热币发现

### 数据流

```
AVE /tokens/trending (4链 x 50个)
        │
        ▼
   硬过滤（市值/流动性/安全）
        │
        ▼
   12 维打分引擎（M+Q+P = 100分）
        │
        ▼
   score >= 50 → 入榜 hot_coins
        │
        ▼
   PriceFeed 注册 → 毫秒级追踪
```

### AVE /tokens/trending 返回字段

系统从 AVE Trending API 获取每条链上的热门代币，每链请求 50 个候选。返回的核心字段如下：

| 字段 | 类型 | 说明 | 打分使用 |
|------|------|------|----------|
| `current_price_usd` | string | 当前 USD 价格 | 入榜基准价格 |
| `market_cap` | number | 市值 (USD) | P1 市值位置评分 |
| `tvl` | number | 锁仓总价值 | 流动性硬过滤 |
| `token_tx_volume_usd_24h` | number | 24h 成交量 | M3 成交量加速 |
| `holders` | number | 持有人数量 | Q1 持有者评分 |
| `token_price_change_1h` | number | 1h 价格变动 % | M1 短期动量 |
| `token_price_change_4h` | number | 4h 价格变动 % | M5 动量新鲜度 |
| `token_price_change_24h` | number | 24h 价格变动 % | M2 中期趋势 |
| `token_buy_tx_count` | number | 买入交易次数 | M4 买压比 |
| `token_sell_tx_count` | number | 卖出交易次数 | M4 买压比 |
| `appendix.twitter` | string | Twitter 链接 | Q2 社交存在性 |
| `appendix.telegram` | string | Telegram 链接 | Q2 社交存在性 |
| `appendix.website` | string | 官网链接 | Q2 社交存在性 |

### 12 维打分模型完整公式

总分 = M 动量 (50分) + Q 品质 (30分) + P 潜力 (20分)，满分 100。

#### M 动量维度（满分 50）

**M1. 价格 1h 涨幅（10分）**
```
pc_1h >= 10%      → 10.0
0 < pc_1h < 10%   → linear(pc_1h, 0, 10) * 10
-5% <= pc_1h <= 0 → 0.0
pc_1h < -5%       → max(-5.0, pc_1h * 0.3)   # 大跌轻微减分
```

**M2. 价格 24h 涨幅（10分）**
```
pc_24h > 300%     → max(0, 10 - (pc_24h - 300) * 0.02)  # 异常pump反减
pc_24h >= 30%     → 10.0
0 < pc_24h < 30%  → linear(pc_24h, 0, 30) * 10
pc_24h <= 0       → 0.0
```

**M3. 成交量加速（12分）**
```
accel_ratio = volume_1h / (volume_24h / 24)
ratio >= 3x → 12.0 满分
ratio 1x~3x → linear(ratio, 1, 3) * 12
ratio < 1x → 0.0
```
逻辑：近 1h 交易量与 24h 平均每小时量的比值。加速比越高，说明资金正在涌入。

**M4. 买压比（10分）**
```
buy_ratio = buys_1h / (buys_1h + sells_1h)
ratio >= 75% → 10.0
50% ~ 75%   → linear(ratio, 0.5, 0.75) * 10
ratio < 50% → 0.0
无1h数据时：用24h数据降权，上限7分
```

**M5. 动量新鲜度（8分）**
```
核心思想：1h涨速 > 24h平均涨速 → 正在启动，用户还有机会
         1h涨速 << 24h平均涨速 → 已涨完，追进去接盘

freshness = pc_1h / (pc_24h / 24)
freshness >= 5 → 8.0   # 短期爆发远超均值
freshness 2~5  → 4~8   # 动量健康
freshness 1~2  → 0~4   # 跟上均速
freshness < 1  → 负分  # 减速减分
```

#### Q 品质维度（满分 30）

**Q1. 持有者数量（10分）**
```
holders >= 1000 → 10.0
holders 150~1000 → linear 归一
holders < 150   → 3.0 (中性分)
```

**Q2. 社交存在性（6分）**
```
Twitter  → 3分
Telegram → 2分
Website  → 1分
数据来源：AVE appendix 字段中的社交链接
```

**Q3. 安全检测（8分）**
```
基础 8.0
goplus_risk 标记   → -4.0
非开源合约         → -2.0
buy_tax > 5%      → -2.0
sell_tax > 5%     → -2.0
数据来源：AVE /contracts/ API（详见模块2）
```

**Q4. 持仓分散度（6分）**
```
top10_holder_pct：Top 10 持仓集中度
集中度越低（持仓越分散）→ 分越高
linear(1 - top10_pct, 0.2, 0.8) * 6
```

#### P 潜力维度（满分 20）

**P1. 市值位置（10分）**
```
对数缩放：市值越低，上涨空间越大
MC <= $200K   → 10.0
MC >= $50M    → 0.0
中间区间：log_ratio = log10(MC / 200K) / log10(50M / 200K)
          score = (1 - log_ratio) * 10
```

**P2. 代币年龄（4分）**
```
7~30 天黄金区间 → 4.0（经过验证但尚未老化）
< 7 天 → linear(age, 3, 7) * 4
> 30 天 → 随年龄衰减至 0
```

**P3. 多时间帧共振（6分）**
```
timeframe_hits = 出现在多少个时间帧的 toplist (5m/1h/4h/24h)
4 个时间帧全活跃 → 6.0  # 持续强势
3 个 → 4.0
2 个 → 2.0
1 个 → 0.0
```

### 推荐等级

| 分数区间 | 等级 | 含义 |
|----------|------|------|
| >= 72 | `strong` | 强烈推荐，多维度共振 |
| 50 ~ 71 | `normal` | 正常推荐，值得关注 |
| < 50 | `skip` | 跳过，不入榜 |

### 退出机制

入榜后的代币持续受 PriceFeed 毫秒级监控，任一条件触发即退出：

| 条件 | 参数 | 含义 |
|------|------|------|
| 连续低分 | score < 35，连续 3 次 | 基本面持续恶化 |
| 冲高回落 | 24h > 200% 且 1h < -5% | 典型 pump & dump |
| 流动性枯竭 | 1h 量 < 24h 均值 10% | 没人交易了 |
| 卖压碾压 | 买压 < 35% | 抛压过重 |
| 热度消退 | 连续 5 轮发现扫描不出现 | 市场已遗忘 |

退出后继续追踪 3 天，评估退出时机是否合理。

---

## 4. 模块 2：代币安全检测

### AVE /contracts/ API

每个候选代币入榜前必须通过安全检测。系统调用 AVE `/contracts/{address}-{chain}` 获取合约审计数据。

### 原始返回字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `is_honeypot` | int | -1=未知, 0=否, 1=是 |
| `buy_tax` | float | 买入税率 (%) |
| `sell_tax` | float | 卖出税率 (%) |
| `has_code` | int | 是否开源 (0/1) |
| `has_mint_method` | int | 是否有铸造方法 (0/1) |
| `has_black_method` | int | 是否有黑名单方法 (0/1) |
| `can_take_back_ownership` | string | 能否夺回所有权 ("0"/"1") |
| `risk_score` | int | 综合风险评分 (0-100) |
| `holders_detail` | array | 持仓明细 [{address, percent, ...}] |

### 格式转换：AVE → 内部 goplus_risk 格式

系统通过 `_convert_risk_to_goplus()` 方法将 AVE 原始数据转换为内部统一格式：

```python
{
    "is_honeypot":     bool,     # hp_raw == 1
    "buy_tax":         float,    # 直接使用
    "sell_tax":        float,    # 直接使用
    "is_open_source":  bool,     # has_code == 1
    "top10_holder_pct": float,   # 从 holders_detail 前10求和
    "top1_holder_pct":  float,   # holders_detail[0].percent
    "risk_score":      int,      # 直接使用
    "has_mint_method":  bool,    # has_mint_method == 1
    "has_black_method": bool,    # has_black_method == 1
    "can_take_back_ownership": bool,  # "1" → True
    "_ave_raw":        dict,     # 原始数据保留
}
```

### 安全检测逻辑

安全检测在两个阶段执行：

**阶段 1：硬过滤（入榜前）**
- `is_honeypot == True` → 直接拒绝，不入榜
- `sell_tax > 30%` → 直接拒绝
- `risk_score >= 90` → 直接拒绝

**阶段 2：打分减分（Q3 维度）**
- `goplus_risk` 标记 → -4 分
- `is_open_source == False` → -2 分
- `buy_tax > 5%` 或 `sell_tax > 5%` → -2 分

**阶段 3：交易前二次校验**
- Agent 决策买入前，再次调用 `/contracts/` 确认安全状态未变化
- 如果检测到新增风险标记，取消交易

### 持仓分析

`holders_detail` 数组提供 Top N 持仓地址和占比。系统计算：

- **Top 10 集中度**：前 10 地址持仓百分比之和，用于 Q4 持仓分散度评分
- **Top 1 集中度**：最大单一持仓占比，极端集中时触发额外风控警告

---

## 5. 模块 3：实时价格服务

### PriceFeed 架构

PriceFeed 是全局价格缓存管理器，采用多路数据源并行推送。AVE `/tokens/{addr}-{chain}` 作为代币价格的核心轮询源。

```
┌────────────────────────────────────────────────────────┐
│                   PriceFeed 单例                        │
├────────────────────────────────────────────────────────┤
│ ① Binance bookTicker WS  → SOL/ETH/BNB/BTC  ~10-100ms │
│ ② Helius logsSubscribe   → Solana 代币 swap   ~400ms   │
│ ③ AVE /tokens/ 轮询      → 全链代币价格       ~2s      │
└────────────────────────────────────────────────────────┘
         │ update_price(addr, price)
         ▼
  ┌──────────────────────┐
  │   三个回调消费者       │
  │  ① HotCoinManager    │ → 实时打分 → 进出榜单
  │  ② SimTrader         │ → TP/SL 止盈止损判定
  │  ③ PerformanceTracker│ → D0~D30 每日最高涨幅
  └──────────────────────┘
```

### AVE 价格轮询实现

PriceFeed 的 `_poll_ave_prices()` 方法每 2 秒轮询一次所有注册代币的价格：

```python
async def _poll_ave_prices(self, addrs: list, dex_chain: str) -> None:
    from ave_client import ave
    ave_chain = {"solana": "solana", "ethereum": "eth",
                 "bsc": "bsc", "base": "base"}.get(dex_chain, dex_chain)
    for addr in addrs:
        detail = await ave.get_token_detail(addr, ave_chain)
        if detail:
            price_str = detail.get("current_price_usd")
            if price_str:
                self.update_price(addr, float(price_str))
```

### 引用计数架构

PriceFeed 使用引用计数管理代币的生命周期追踪，确保资源不浪费：

```
场景：BONK 同时被 HotCoinManager 和 SimTrader 关注

1. HotCoinManager 入榜 BONK:
   price_feed.register_token("BONK_addr", "solana", source="hot_coin")
   → refcount["BONK"] = 1

2. SimTrader 开仓 BONK:
   price_feed.register_token("BONK_addr", "solana", source="sim_trader")
   → refcount["BONK"] = 2

3. HotCoinManager 退榜 BONK:
   price_feed.unregister_token("BONK_addr", source="hot_coin")
   → refcount["BONK"] = 1, 继续追踪（SimTrader 还需要）

4. SimTrader 平仓 BONK:
   price_feed.unregister_token("BONK_addr", source="sim_trader")
   → refcount["BONK"] = 0, 停止追踪，释放资源
```

### 价格变更回调

价格变动超过 0.01% 才触发回调，避免噪音：

```python
if abs(price - old) / max(old, 1e-12) > 0.0001:
    for cb in self._callbacks:
        cb(addr, price)
```

三个回调消费者各司其职：

| 消费者 | 回调行为 | 频率 |
|--------|----------|------|
| HotCoinManager | 重新打分 → 退出判定 → 节流写 DB (15s) | 每次价格变动 |
| SimTrader | 检查止盈止损触发条件 | 每次价格变动 |
| PerformanceTracker | 更新 D0~D30 每日最高涨幅 | 每次价格变动 |

---

## 6. 模块 4：聪明钱数据

### AVE /address/smart_wallet/list

系统调用 AVE 聪明钱 API 获取链上高利润钱包地址：

```python
async def get_smart_wallets(self, chain: str, limit: int = 100) -> List[dict]:
    data = await self._data_get(
        "/address/smart_wallet/list", {"chain": c, "limit": limit}
    )
```

### 与内部钱包库的融合

系统维护 15,000+ 聪明钱地址（SOL ~5,222 + EVM ~10,540），来自三个供给层：

| 来源 | 说明 | 地址数 |
|------|------|--------|
| AVE Smart Wallet API | 直接获取链上高利润钱包 | 持续补充 |
| 内部 Miner | 从毕业代币早期买家中挖掘 | ~12+ |
| Dune Analytics | 4 链查询批量导入 | ~493+ |
| Top Holders 晋升 | 热币 D3 涨 20%+ 的 Top 10 持仓地址 | 动态增长 |

### v3 五维度评估体系

每个聪明钱地址通过五维度评估打分，总分 100：

| 维度 | 满分 | 说明 |
|------|------|------|
| 胜率 (Win Rate) | 20 | 盈利交易占总交易的比例 |
| PNL (利润) | 20 | 累计已实现利润 |
| 交易规模 (Scale) | 20 | 平均单笔交易金额 |
| 活跃度 (Activity) | 20 | 近期交易频率 |
| 时效性 (Recency) | 20 | 最近一笔交易距今时间 |

### 等级划分

| 等级 | 分数 | 权限 |
|------|------|------|
| `elite` | >= 75 | 信号权重最高，优先跟单 |
| `verified` | >= 55 | 正常跟单权重 |
| `watching` | >= 35 | 观察期，降低权重 |
| `blacklisted` | < 30 | 自动移除，不再追踪 |

### Heat Score 公式

聪明钱信号的热度评分综合以下因子：

```
heat_score = w1 * wallet_score      # 钱包五维度总分权重
           + w2 * position_size     # 仓位大小
           + w3 * timing_score      # 入场时机（越早越高）
           + w4 * cluster_count     # 同时关注该代币的聪明钱数量
```

多个高评级聪明钱同时买入同一代币时，cluster_count 飙升，产生强烈信号。

### 实时监控

- SOL 链：Helius WebSocket `logsSubscribe` 监听 DEX 程序，~400ms 延迟
- EVM 链：公共 WebSocket RPC 订阅 Swap 事件 topic，~2-12s（取决于出块时间）
- 评估周期：每 2 小时重新计算五维度评分
- 降级规则：14 天无交易降级，28 天无交易移除
- Bot 检测：实时过滤 MEV bot 和夹子机器人

---

## 7. 模块 5：交易执行

### 完整交易流程

AVE Chain Wallet API 提供自托管交易能力。整个流程分为四步：

```
Step 1: 报价          Step 2: 创建交易       Step 3: 本地签名       Step 4: 发送交易
────────────────      ────────────────      ────────────────      ────────────────
getAmountOut          createSolanaTx        solders.sign()        sendSignedSolanaTx
                      createEvmTx           eth_account.sign()    sendSignedEvmTx
    ↓                      ↓                      ↓                      ↓
获取预期输出量         获取原始交易数据        私钥本地签名            广播到链上
价格影响评估           requestTxId 返回       绝不上传私钥            返回 txHash
```

### Solana 交易详细流程

```python
# 1. 报价
quote = await ave.get_quote("solana", "sol", token_addr, amount, "buy")
estimate_out = quote["estimateOut"]

# 2. 创建交易
tx_data = await ave.create_solana_tx(
    in_token="sol",
    out_token=token_addr,
    amount=amount_raw,
    swap_type="buy",
    slippage=1.0,
    wallet_address=wallet_addr,
    fee=0.0005,           # SOL 优先费
)
request_tx_id = tx_data["requestTxId"]
raw_tx = tx_data["rawTransaction"]

# 3. 本地签名（solders 库）
signed = sign_solana_tx(raw_tx, private_key)

# 4. 发送
result = await ave.send_signed_solana_tx(request_tx_id, signed)
tx_hash = result["txHash"]
```

### EVM 交易详细流程

```python
# 1. 报价
quote = await ave.get_quote("bsc", usdt_addr, token_addr, amount, "buy")

# 2. 创建交易
tx_data = await ave.create_evm_tx(
    chain="bsc",
    in_token=usdt_addr,
    out_token=token_addr,
    amount=amount_raw,
    swap_type="buy",
    slippage=1.0,
    wallet_address=wallet_addr,
)
request_tx_id = tx_data["requestTxId"]

# 3. 本地签名（eth-account 库）
signed = sign_evm_tx(tx_data, private_key, chain_id=56)

# 4. 发送
result = await ave.send_signed_evm_tx("bsc", request_tx_id, signed)
tx_hash = result["txHash"]
```

### Solana 与 EVM 的关键差异

| 特性 | Solana | EVM (BSC/ETH/Base) |
|------|--------|---------------------|
| 创建 API | `createSolanaTx` | `createEvmTx` |
| 发送 API | `sendSignedSolanaTx` | `sendSignedEvmTx` |
| 签名库 | `solders` | `eth-account` |
| 原生代币 | SOL (wSOL) | ETH/BNB (EEE...地址) |
| 优先费 | fee 参数 (0.0005 SOL) | gas price 由链决定 |
| Approve | 不需要 | 卖出前需要 ERC20 approve |
| 确认时间 | ~400ms (1 slot) | 2s (Base) ~ 12s (ETH) |

### 自托管安全保证

```
┌─────────────────────────────────────────────────────────┐
│                    安全边界                               │
│                                                          │
│  本地服务器                        AVE Cloud              │
│  ┌─────────────┐                 ┌──────────────┐       │
│  │ 私钥存储     │ ──createTx──→ │ 路由+构建交易  │       │
│  │ (环境变量)   │ ←──rawTx────  │ (不接触私钥)   │       │
│  │             │                │               │       │
│  │ 本地签名     │ ──signedTx─→  │ 广播到链上     │       │
│  │ (solders /  │ ←──txHash───  │ 返回交易哈希   │       │
│  │  eth-account)│               └──────────────┘       │
│  └─────────────┘                                        │
│                                                          │
│  私钥永远不离开本地服务器                                  │
│  AVE 只负责：路由聚合 + 构建交易数据 + 广播签名后的交易     │
└─────────────────────────────────────────────────────────┘
```

### 滑点分层策略

| 场景 | 滑点 | 说明 |
|------|------|------|
| 模拟盘 (SimTrader) | 1.5% | 模拟环境宽松 |
| 正常买入/卖出 | 1.0% | 默认值 |
| 止损卖出 | 2.0% | 需要快速成交 |
| CRISIS 市场状态 | 5.0% | 极端行情下紧急平仓 |

---

## 8. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AiTrading Pro 系统架构                             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                        数据采集层                                    │     │
│  │                                                                      │     │
│  │  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐   │     │
│  │  │ AVE Trending    │  │ AVE Contracts  │  │ AVE Smart Wallets   │   │     │
│  │  │ /tokens/trending│  │ /contracts/    │  │ /smart_wallet/list  │   │     │
│  │  │ 4链x50=200候选  │  │ 安全检测        │  │ 聪明钱地址           │   │     │
│  │  └───────┬────────┘  └───────┬────────┘  └────────┬────────────┘   │     │
│  │          │                    │                     │                │     │
│  │  ┌───────┴───────┐  ┌───────┴──────┐    ┌────────┴───────┐       │     │
│  │  │ pump.fun WS   │  │ Helius WS    │    │ KOL Monitor    │       │     │
│  │  │ 内盘新币       │  │ SOL DEX swap │    │ 212 KOL 追踪   │       │     │
│  │  └───────┬───────┘  └───────┬──────┘    └────────┬───────┘       │     │
│  └──────────┼──────────────────┼─────────────────────┼───────────────┘     │
│             │                  │                      │                      │
│  ┌──────────┼──────────────────┼─────────────────────┼───────────────┐     │
│  │          ▼ 价格服务层       ▼                      │                │     │
│  │  ┌──────────────────────────────────────┐          │                │     │
│  │  │           PriceFeed 单例              │          │                │     │
│  │  │  Binance WS (主流币) ~10-100ms        │          │                │     │
│  │  │  Helius WS (SOL 代币) ~400ms          │          │                │     │
│  │  │  AVE /tokens/ (全链代币) ~2s 轮询      │          │                │     │
│  │  │  引用计数管理 + 价格变更回调            │          │                │     │
│  │  └──────────────┬───────────────────────┘          │                │     │
│  └─────────────────┼──────────────────────────────────┼───────────────┘     │
│                    │                                   │                      │
│  ┌─────────────────┼───────────────────────────────────┼───────────────┐     │
│  │                 ▼ AI 决策层                          ▼                │     │
│  │  ┌──────────────────────┐  ┌──────────────────────────────────┐    │     │
│  │  │ L1 规则引擎 (快筛)    │  │ 三层记忆系统                       │    │     │
│  │  │ 15 项风控检查         │  │  Working: 当前持仓上下文            │    │     │
│  │  │ EventBus 事件驱动     │  │  Episodic: 历史交易经验            │    │     │
│  │  └─────────┬────────────┘  │  Semantic: 市场模式知识库           │    │     │
│  │            ▼                └──────────┬───────────────────────┘    │     │
│  │  ┌──────────────────────┐              │                            │     │
│  │  │ L2 Claude LLM 分析   │◄─────────────┘                            │     │
│  │  │ 7 状态 Regime 识别    │                                           │     │
│  │  │ 动态风控参数          │                                           │     │
│  │  └─────────┬────────────┘                                           │     │
│  │            ▼                                                         │     │
│  │  ┌──────────────────────┐                                           │     │
│  │  │ L3 牛熊辩论           │                                           │     │
│  │  │ Bull vs Bear 对抗     │                                           │     │
│  │  │ 置信度评分 → 最终决策  │                                           │     │
│  │  └─────────┬────────────┘                                           │     │
│  └────────────┼────────────────────────────────────────────────────────┘     │
│               │                                                              │
│  ┌────────────┼────────────────────────────────────────────────────────┐     │
│  │            ▼ 交易执行层                                              │     │
│  │  ┌──────────────────────────────────────────────────────────┐      │     │
│  │  │                  AVE Chain Wallet                         │      │     │
│  │  │  getAmountOut → createTx → 本地签名 → sendSignedTx        │      │     │
│  │  │  Solana: createSolanaTx + sendSignedSolanaTx              │      │     │
│  │  │  EVM:    createEvmTx    + sendSignedEvmTx                 │      │     │
│  │  │  自托管：私钥永不上传                                       │      │     │
│  │  └──────────────────────────────────────────────────────────┘      │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ 展示层                                                              │     │
│  │  Flutter App (iOS/Android)  +  Next.js Portal (Web)                │     │
│  │  实时热币榜 + 交易信号 + AI 优化审批 + 绩效看板                      │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. API 调用明细表

### ave-data-rest

| 端点 | 方法 | 频率 | 用途 | 请求参数 | 响应关键字段 |
|------|------|------|------|----------|-------------|
| `/tokens/trending` | GET | 每 10min, 每链 1 次 | 热币发现 | `chain`, `limit=50` | `tokens[]`: current_price_usd, market_cap, tvl, holders, price_change_1h/4h/24h, buy_tx_count, sell_tx_count, appendix |
| `/tokens/{addr}-{chain}` | GET | 每 2s 轮询 | 实时价格 | 路径参数 | `token`: current_price_usd, market_cap, tvl, token_tx_volume_usd_24h, holders |
| `/contracts/{addr}-{chain}` | GET | 入榜时 + 交易前 | 安全检测 | 路径参数 | is_honeypot, buy_tax, sell_tax, has_code, has_mint_method, has_black_method, can_take_back_ownership, risk_score, holders_detail[] |
| `/address/smart_wallet/list` | GET | 每 2h | 聪明钱列表 | `chain`, `limit=100` | list[]: address, profit, win_rate, trade_count |
| `/tokens` | GET | 按需 | 关键词搜索 | `keyword` | tokens[]: address, name, symbol, chain |

### ave-trade-chain-wallet

| 端点 | 方法 | 频率 | 用途 | 请求参数 | 响应关键字段 |
|------|------|------|------|----------|-------------|
| `/v1/thirdParty/chainWallet/getAmountOut` | POST | 每笔交易前 | 报价 | chain, inAmount, inTokenAddress, outTokenAddress, swapType | estimateOut, decimals, priceImpact |
| `/v1/thirdParty/chainWallet/createSolanaTx` | POST | SOL 买入/卖出 | 创建交易 | chain=solana, inAmount, inTokenAddress, outTokenAddress, swapType, slippage, userAddress, fee | requestTxId, rawTransaction |
| `/v1/thirdParty/chainWallet/createEvmTx` | POST | EVM 买入/卖出 | 创建交易 | chain, inAmount, inTokenAddress, outTokenAddress, swapType, slippage, userAddress | requestTxId, rawTransaction, tx |
| `/v1/thirdParty/chainWallet/sendSignedSolanaTx` | POST | SOL 交易发送 | 广播 | chain=solana, requestTxId, signedTx | txHash, tx_hash |
| `/v1/thirdParty/chainWallet/sendSignedEvmTx` | POST | EVM 交易发送 | 广播 | chain, requestTxId, signedTx | txHash, tx_hash |

### 请求认证

| API 类型 | Header | 说明 |
|----------|--------|------|
| Data REST | `X-API-KEY: {AVE_API_KEY}` | 数据查询认证 |
| Trade Chain Wallet | `AVE-ACCESS-KEY: {AVE_API_KEY}` | 交易操作认证 |

---

## 10. 核心实现：ave_client.py

### AveClient 类

`ave_client.py` 是 AVE Cloud API 的统一客户端，所有 AVE 调用集中在此文件。

#### 类结构

```python
class AveClient:
    """AVE Cloud API 统一客户端（1 RPS 限速）"""

    _session: aiohttp.ClientSession    # HTTP 会话复用
    _last_req_ts: float                # 上次请求时间戳
    _lock: asyncio.Lock                # 限速并发锁
```

#### 公开方法

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `get_token_detail(address, chain)` | 代币地址, 链名 | `Optional[dict]` | 获取单个代币详情 |
| `get_batch_prices(pairs)` | `["addr-chain", ...]` | `Dict[str, float]` | 批量价格查询 |
| `get_trending(chain, limit)` | 链名, 数量(默认50) | `List[dict]` | 获取链上热门代币 |
| `check_risk(address, chain)` | 代币地址, 链名 | `Optional[dict]` | 合约安全检测 (goplus 格式) |
| `get_smart_wallets(chain, limit)` | 链名, 数量 | `List[dict]` | 获取聪明钱列表 |
| `get_quote(chain, in_token, out_token, amount, swap_type)` | 链/输入/输出/数量/类型 | `Optional[dict]` | 交易报价 |
| `create_solana_tx(...)` | 多参数 | `Optional[dict]` | 创建 Solana 交易 |
| `create_evm_tx(...)` | 多参数 | `Optional[dict]` | 创建 EVM 交易 |
| `send_signed_solana_tx(request_tx_id, signed_tx)` | 交易ID, 签名数据 | `Optional[dict]` | 发送 Solana 交易 |
| `send_signed_evm_tx(chain, request_tx_id, signed_tx)` | 链/交易ID/签名 | `Optional[dict]` | 发送 EVM 交易 |

#### 限速机制

AVE Free Plan 限制 1 RPS。客户端通过异步锁实现精确限速：

```python
async def _throttle(self) -> None:
    async with self._lock:
        now = time.time()
        gap = now - self._last_req_ts
        if gap < 1.0:
            await asyncio.sleep(1.0 - gap)
        self._last_req_ts = time.time()
```

- 使用 `asyncio.Lock` 保证并发安全
- 计算距上次请求的间隔，不足 1 秒则等待
- 所有 `_data_get` 和 `_trade_post` 调用前自动触发

#### 链名映射

```python
_CHAIN_MAP = {
    "solana": "solana",
    "bsc": "bsc",
    "base": "base",
    "eth": "eth",
    "ethereum": "eth",     # 兼容内部用 "ethereum" 的模块
}
```

#### Session 复用

```python
def _get_session(self) -> aiohttp.ClientSession:
    if self._session is None or self._session.closed:
        self._session = aiohttp.ClientSession()
    return self._session
```

- 惰性创建 aiohttp.ClientSession
- 自动检测关闭状态并重建
- 全局单例 `ave = AveClient()` 保证进程内只有一个 HTTP 连接池

#### Data REST 请求格式

```python
async def _data_get(self, path: str, params: dict = None) -> Optional[dict]:
    url = f"{AVE_DATA_BASE}{path}"    # https://data.ave-api.xyz/v2{path}
    headers = {
        "X-API-KEY": AVE_API_KEY,
        "Content-Type": "application/json",
    }
    # 响应格式: {"status": 1, "data": {...}, "msg": "..."}
    # status == 1 表示成功
    return data.get("data")
```

#### Trade REST 请求格式

```python
async def _trade_post(self, path: str, body: dict) -> Optional[dict]:
    url = f"{AVE_TRADE_BASE}{path}"   # https://bot-api.ave.ai{path}
    headers = {
        "AVE-ACCESS-KEY": AVE_API_KEY,
        "Content-Type": "application/json",
    }
    # 响应格式: {"status": 200, "data": {...}, "msg": "..."}
    # status == 200 或 1 表示成功
    return data.get("data")
```

#### 格式转换

`_convert_risk_to_goplus()` 静态方法将 AVE 安全检测结果转换为内部标准格式，使整个系统无需关心数据源差异：

- `is_honeypot`: int(-1/0/1) → bool
- `has_code`: int(0/1) → bool `is_open_source`
- `holders_detail`: array → `top10_holder_pct` + `top1_holder_pct`
- 保留 `_ave_raw` 原始数据，供调试使用

---

## 11. 效果指标

### 数据覆盖

| 指标 | 数值 | 说明 |
|------|------|------|
| 热币覆盖 | 4 链 ~200 活跃代币 | 每链 50 个 Trending 候选，score >= 50 入榜 |
| 聪明钱地址 | 15,000+ 钱包 | SOL ~5,222 + EVM ~10,540，三层供给 |
| KOL 监控 | 212 个 | Twitter KOL 实时舆情 |
| 支持链 | 4 条 | Solana, BSC, ETH, Base |

### 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 主流币价格延迟 | ~10-100ms | Binance bookTicker WebSocket |
| SOL 代币价格延迟 | ~400ms | Helius logsSubscribe 触发 |
| 全链代币价格轮询 | 2s | AVE /tokens/ REST 轮询周期 |
| 安全检测响应 | < 1s | AVE /contracts/ 单次查询 |
| 交易执行全流程 | 3-15s | 报价 + 创建 + 签名 + 发送 |

### 交易能力

| 指标 | 数值 | 说明 |
|------|------|------|
| 模拟盘仓位 | 250+ | 活跃模拟交易仓位 |
| TP/SL 触发 | 3 分钟内 | PriceFeed 回调驱动 |
| 风控检查 | 15 项 | 含 BTC 大盘 + 同链集中度 |

### AI 决策

| 指标 | 数值 | 说明 |
|------|------|------|
| AI 模型 | Claude Opus 4.6 | Anthropic API |
| 决策层级 | L1 → L2 → L3 | 规则快筛 → LLM 分析 → 辩论置信度 |
| 市场状态 | 7 种 Regime | BULL/BEAR/SIDEWAYS/VOLATILE/CRISIS/RECOVERY/ACCUMULATION |
| 记忆层 | 3 层 | Working + Episodic + Semantic |
| 辩论角色 | Bull vs Bear | 对抗式评估，置信度评分 |

---

## 12. 支持链矩阵

| 功能 | Solana | BSC | ETH | Base |
|------|--------|-----|-----|------|
| 热币发现 (Trending) | AVE | AVE | AVE | AVE |
| 实时价格 (Price) | AVE + Helius WS | AVE | AVE | AVE |
| 安全检测 (Risk) | AVE | AVE | AVE | AVE |
| 聪明钱 (Smart Wallet) | AVE + Helius | AVE + EVM WS | AVE + EVM WS | AVE + EVM WS |
| 交易报价 (Quote) | AVE | AVE | AVE | AVE |
| 创建交易 (Create Tx) | AVE createSolanaTx | AVE createEvmTx | AVE createEvmTx | AVE createEvmTx |
| 发送交易 (Send Tx) | AVE sendSignedSolanaTx | AVE sendSignedEvmTx | AVE sendSignedEvmTx | AVE sendSignedEvmTx |
| 出块时间 | ~400ms | ~3s | ~12s | ~2s |
| 原生代币 | SOL (wSOL) | BNB | ETH | ETH |
| 链 ID | 501 | 56 | 1 | 8453 |

---

## 13. 环境配置

### 必需环境变量

```bash
# AVE Cloud Skill
AVE_API_KEY=<your-ave-api-key>

# AVE 已内置的基础 URL（无需配置）
# AVE_DATA_BASE=https://data.ave-api.xyz/v2
# AVE_TRADE_BASE=https://bot-api.ave.ai

# 启用 AVE
USE_AVE=true
```

### 钱包配置（交易执行需要）

```bash
# Solana 钱包
SOLANA_WALLET_ADDRESS=<your-solana-address>
SOLANA_PRIVATE_KEY=<your-solana-private-key>

# EVM 钱包（BSC/ETH/Base 共用）
EVM_WALLET_ADDRESS=<your-evm-address>
EVM_PRIVATE_KEY=<your-evm-private-key>
```

### 辅助数据源（增强）

```bash
# Helius（Solana DEX 实时监控）
HELIUS_API_KEY=<your-helius-key>

# Claude AI（决策引擎）
ANTHROPIC_API_KEY=<your-anthropic-key>

# Supabase（数据库）
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-supabase-key>
```

### 启动命令

```bash
cd services/pump-scanner
USE_AVE=true python main.py
```

---

## 14. 技术创新点

### 14.1 基于 AVE 的统一数据层

传统方案需要对接多个独立 API（DexScreener、GoPlus、OKX DEX 等），存在认证碎片化、格式不统一、限速各异等问题。AiTrading Pro 通过 AVE Cloud Skill 实现统一数据层：

- **单一 API Key**：一个 AVE Key 覆盖数据查询 + 安全检测 + 交易执行
- **统一格式**：`ave_client.py` 内部做一次格式转换，上层模块完全无感
- **统一限速**：1 RPS 限速器统管所有请求，不会因为某个模块超频导致封禁

### 14.2 三级 AI 决策引擎 (L1/L2/L3)

```
信号输入 → L1 规则引擎（毫秒级）
              │ 通过 15 项快筛
              ▼
         L2 Claude LLM（秒级）
              │ 结合 Regime + 记忆 + 市场数据
              ▼
         L3 牛熊辩论（秒级）
              │ Bull Agent vs Bear Agent
              │ 裁判综合置信度评分
              ▼
         最终决策：BUY / SELL / HOLD + 置信度 + 仓位建议
```

- L1：事件驱动，EventBus 毫秒级分发，规则引擎硬过滤
- L2：Claude Opus 4.6 深度分析，注入 Regime 状态 + 三层记忆
- L3：多角色辩论机制，Bull 和 Bear Agent 各自论证，裁判评估置信度

### 14.3 三层记忆自学习系统

| 层级 | 存储 | 内容 | 更新 |
|------|------|------|------|
| Working Memory | 内存 | 当前持仓、未平仓位、最近事件 | 实时 |
| Episodic Memory | DB | 历史交易经验、盈亏案例 | 每笔交易后 |
| Semantic Memory | DB | 市场模式知识、代币特征 | 反思周期 (每 6h) |

记忆注入到 L2 决策 Prompt 中，使 AI 能从过去的成功和失败中学习，避免重复同样的错误。

### 14.4 七状态 Regime 自适应

Regime Detector 实时识别当前市场状态，动态调整所有交易参数：

| Regime | 含义 | 仓位上限 | 风控松紧 |
|--------|------|----------|----------|
| BULL | 牛市 | 较高 | 正常 |
| BEAR | 熊市 | 最低 | 最严 |
| SIDEWAYS | 横盘 | 中等 | 正常 |
| VOLATILE | 高波动 | 降低 | 收紧 |
| CRISIS | 危机 | 最低 | 紧急平仓 |
| RECOVERY | 复苏 | 逐步恢复 | 谨慎 |
| ACCUMULATION | 吸筹 | 中等 | 正常 |

参数包括：最大持仓数、单笔仓位比例、止损/止盈倍率、买入频率上限等。

### 14.5 PriceFeed 引用计数

创新的引用计数架构解决了代币追踪生命周期管理问题：

- 多个消费者（HotCoinManager / SimTrader / PerformanceTracker）可以独立注册和注销同一代币
- 只要有一个消费者还在关注，价格追踪就继续
- 全部消费者注销后，自动停止轮询，释放 API 配额
- 避免了"退榜后模拟盘无法止损"和"重复订阅浪费配额"两个常见问题

### 14.6 牛熊辩论机制

L3 决策层引入对抗式推理：

```
┌────────────┐        ┌────────────┐
│ Bull Agent │        │ Bear Agent │
│ "应该买入"  │        │ "不应买入"  │
│ 论据+数据   │        │ 论据+数据   │
└──────┬─────┘        └──────┬─────┘
       │      ┌──────┐       │
       └─────→│ 裁判  │←─────┘
              │ Agent │
              └──┬───┘
                 │
                 ▼
         置信度评分 (0-100)
         最终决策 + 理由
```

- 避免了单一模型的确认偏差
- 强制考虑反面论据
- 置信度评分决定仓位大小：高置信度 → 大仓位，低置信度 → 小仓位或放弃

---

## 附录 A：API 基础 URL

| 服务 | URL |
|------|-----|
| AVE Data REST | `https://data.ave-api.xyz/v2` |
| AVE Trade Chain Wallet | `https://bot-api.ave.ai` |

## 附录 B：项目仓库结构

```
Agent-Trading/
├── services/pump-scanner/        # Python 后端
│   ├── ave_client.py             # AVE 统一客户端
│   ├── hot_coin_manager.py       # 热币实时管理器
│   ├── hot_scorer.py             # 12 维打分引擎
│   ├── price_feed.py             # 实时价格服务
│   ├── smart_money_tracker.py    # 聪明钱追踪
│   ├── collector.py              # pump.fun 数据采集
│   ├── config.py                 # 配置（含 AVE 凭证）
│   ├── main.py                   # 启动入口
│   └── agent/
│       ├── trade_executor.py     # 交易执行（含 AVE 路径）
│       ├── decision_agent.py     # L2 AI 决策
│       ├── debate.py             # L3 牛熊辩论
│       ├── rule_engine.py        # L1 规则引擎
│       ├── regime_detector.py    # 7 状态市场识别
│       ├── risk_manager.py       # 15 项风控检查
│       ├── event_listener.py     # EventBus 事件驱动
│       ├── position_monitor.py   # 仓位监控 + TP/SL
│       └── memory/
│           ├── working_memory.py # 工作记忆
│           ├── episodic_memory.py# 情景记忆
│           └── semantic_memory.py# 语义记忆
├── apps/app/                     # Flutter 移动端
└── apps/portal/                  # Next.js 管理后台
```

## 附录 C：数据库核心表

| 表名 | 说明 | AVE 相关 |
|------|------|----------|
| `hot_coins` | 热币榜单 | AVE Trending 入榜 |
| `hot_funnel_stats` | 热币漏斗统计 | 入榜/退出原因 |
| `smart_wallets` | 聪明钱地址库 | AVE Smart Wallet 补充 |
| `smart_money_txns` | 聪明钱交易记录 | 实时监控写入 |
| `agent_trades` | Agent 交易记录 | AVE Chain Wallet 执行 |
| `agent_memory` | Agent 记忆 | AI 决策上下文 |
| `agent_regime_history` | Regime 历史 | 市场状态变迁 |
| `agent_debates` | 辩论记录 | L3 牛熊辩论 |
| `paper_trades` | 模拟盘交易 | 模拟执行记录 |
