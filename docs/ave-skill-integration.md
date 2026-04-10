# AVE Cloud Skills 深度集成文档 — AiTrading Pro

> 基于 AVE Cloud Skills 构建的 AI 多链加密货币自动交易系统
> 版本: 2.0 | 更新日期: 2026-04-10

---

## 目录

1. [项目概述](#1-项目概述)
2. [使用的 AVE Skills](#2-使用的-ave-skills)
3. [模块一：热币发现引擎](#3-模块一热币发现引擎)
4. [模块二：安全检测系统](#4-模块二安全检测系统)
5. [模块三：实时价格基础设施](#5-模块三实时价格基础设施)
6. [模块四：聪明钱情报网络](#6-模块四聪明钱情报网络)
7. [模块五：交易执行层](#7-模块五交易执行层)
8. [系统架构全景图](#8-系统架构全景图)
9. [API 调用明细表](#9-api-调用明细表)
10. [核心实现 ave_client.py](#10-核心实现-ave_clientpy)
11. [AI 决策引擎概览](#11-ai-决策引擎概览)
12. [效果指标与运营数据](#12-效果指标与运营数据)
13. [链支持矩阵](#13-链支持矩阵)
14. [技术创新点](#14-技术创新点)
15. [环境配置](#15-环境配置)
16. [License](#16-license)

---

## 1. 项目概述

AiTrading Pro 是基于 AVE Cloud Skills 构建的 AI 多链加密货币自动交易系统。系统覆盖从信号发现到链上执行的完整闭环，横跨 Solana、BSC、Ethereum、Base 四条公链，通过五大独立信号源（热币趋势、pump.fun 内盘、聪明钱跟踪、KOL 舆情、BTC/ETH 大盘）驱动三层 AI 决策引擎（规则过滤 + Claude 快评 + 多角色辩论），最终经由 AVE 链上交易基础设施完成自托管 DEX 交易。

### AVE 在系统中的定位

AVE Cloud Skills 是系统的数据与交易基础设施。从代币发现、实时价格获取、合约安全审计、聪明钱情报到最终的链上 Swap 执行，所有与链上世界的交互均通过 AVE 的两大 Skill 完成：

- **ave-data-rest**：多链代币数据聚合，提供趋势发现、实时报价、合约风险扫描、聪明钱地址库
- **ave-trade-chain-wallet**：自托管交易执行，支持报价查询、交易构造、签名提交的完整生命周期

整套系统实现了「AVE 提供链上基础设施 + AI 提供策略智能 + 本地自托管保障资金安全」的三位一体架构。

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

提供多链代币数据聚合能力，是系统的数据心脏。

| 端点 | HTTP 方法 | 请求参数 | 返回关键字段 | 系统用途 |
|------|-----------|----------|-------------|---------|
| `/tokens/trending` | GET | `chain` (solana/bsc/eth/base), `limit` (默认50) | `tokens[]`: `current_price_usd`, `market_cap`, `tvl`, `token_tx_volume_usd_24h`, `holders`, `token_price_change_1h`, `token_price_change_4h`, `token_price_change_24h`, `token_buy_tx_count`, `token_sell_tx_count`, `appendix` (含 `twitter`, `telegram`, `website`) | 热币发现、趋势捕获 |
| `/tokens/{addr}-{chain}` | GET | 路径参数：代币地址 + 链名 | `current_price_usd`, `market_cap`, `tvl`, `token_tx_volume_usd_24h`, `holders`, 价格变化系列, 买卖计数 | 实时价格、代币详情 |
| `/contracts/{addr}-{chain}` | GET | 路径参数：合约地址 + 链名 | `is_honeypot` (-1未知/0安全/1蜜罐), `buy_tax`, `sell_tax`, `has_code`, `has_mint_method`, `has_black_method`, `risk_score`, `holders_detail` (含 Top10 持仓占比) | 安全检测、风控拦截 |
| `/address/smart_wallet/list` | GET | `chain`, `limit` | `wallets[]`: `address`, `pnl`, `win_rate` | 聪明钱地址获取 |
| `/tokens?keyword=` | GET | `keyword` 搜索词 | 匹配代币列表 | 代币搜索 |

### 2.2 ave-trade-chain-wallet

提供自托管多链交易能力，是系统的执行手臂。

| 端点 | HTTP 方法 | 请求参数 | 返回关键字段 | 系统用途 |
|------|-----------|----------|-------------|---------|
| `chainWallet/getAmountOut` | POST | `chainIndex`, `inTokenAddress`, `outTokenAddress`, `amount`, `swapType` | `estimateOut`, `decimals` | 交易报价 |
| `chainWallet/createSolanaTx` | POST | `inTokenAddress`, `outTokenAddress`, `amount`, `walletAddress`, `slippage`, `requestTxId` | `rawTransaction`, `requestTxId` | SOL 交易构造 |
| `chainWallet/createEvmTx` | POST | `chainIndex`, `inTokenAddress`, `outTokenAddress`, `amount`, `walletAddress`, `slippage` | `rawTransaction`, `requestTxId` | EVM 交易构造 |
| `chainWallet/sendSignedSolanaTx` | POST | `requestTxId`, `signedTransaction` | `txHash` | SOL 交易广播 |
| `chainWallet/sendSignedEvmTx` | POST | `chainIndex`, `requestTxId`, `signedTransaction` | `txHash` | EVM 交易广播 |

---

## 3. 模块一：热币发现引擎

### 数据流全景

```
AVE /tokens/trending (4链 x 50代币, 每10分钟)
        │
        ▼
┌───────────────────────────────────────┐
│         硬过滤 6 关 (Hard Filter)      │
│                                        │
│  [1] 代币年龄: 3天 ~ 90天              │
│  [2] 流动性: >= $30,000                │
│  [3] 市值: $200,000 ~ $50,000,000     │
│  [4] 24h交易量: >= $15,000             │
│  [5] 持有人数: >= 100                  │
│  [6] 安全检测通过 (调用模块二)           │
└────────────────┬──────────────────────┘
                 │ 通过 6 关的代币
                 ▼
┌───────────────────────────────────────┐
│       100 分打分系统 (Scoring)          │
│                                        │
│  Momentum (M) = 50 分                 │
│  Quality  (Q) = 30 分                 │
│  Potential (P) = 20 分                 │
│                                        │
│  总分 = M + Q + P                      │
└────────────────┬──────────────────────┘
                 │ score >= 50
                 ▼
         入榜 → 实时监控 → PriceFeed 注册
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
数据来源：AVE /contracts/ API（详见模块二）
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

### 退出机制（5 条规则）

入榜后的代币持续受 PriceFeed 毫秒级监控，任一条件触发即退出：

| 条件 | 参数 | 含义 |
|------|------|------|
| 冲高回落 | 24h > 200% 且 1h < -5% | 典型 pump & dump |
| 流动性枯竭 | 1h 量 < 24h 均值 10% | 没人交易了 |
| 卖压碾压 | 买压比 < 35% | 抛压过重 |
| 连续低分 | score < 35，连续 3 次 | 基本面持续恶化 |
| 热度消退 | 连续 5 轮发现扫描不出现 | 市场已遗忘 |

退出后继续追踪 3 天，评估退出时机是否合理，数据回馈优化系统。

---

## 4. 模块二：安全检测系统

### AVE /contracts/ 返回字段

每个候选代币入榜前必须通过安全检测。系统调用 AVE `/contracts/{address}-{chain}` 获取合约审计数据。

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

```
AVE 原始返回                          系统内部格式
─────────────────────────────────────────────────────────
is_honeypot: -1                  →    honeypot_status: "unknown"
is_honeypot: 0                   →    is_honeypot: False
is_honeypot: 1                   →    is_honeypot: True

buy_tax: 0.05                    →    buy_tax: 5.0 (百分比)
sell_tax: 0.08                   →    sell_tax: 8.0 (百分比)

has_code: 1                      →    is_open_source: True
has_code: 0                      →    is_open_source: False

has_mint_method: 1               →    has_mint_method: True
has_black_method: 1              →    has_black_method: True

risk_score: 72                   →    risk_score: 72

holders_detail[0..9].percent     →    top10_holder_pct: sum(前10)
holders_detail[0].percent        →    top1_holder_pct: 最大单一持仓

_ave_raw: dict                   →    保留原始数据供调试
```

### 安全检测逻辑

安全检测在两个阶段执行：

**阶段 1：硬过滤（入榜前）**

```
AVE /contracts/{addr}-{chain}
    │
    ▼
┌──────────────────────────────────────────────┐
│              安全检测决策树                      │
│                                               │
│  [检查1] is_honeypot == 1                     │
│          → BLOCK (蜜罐合约，无法卖出)            │
│                                               │
│  [检查2] buy_tax > 10%                        │
│          → BLOCK (买入税过高)                    │
│                                               │
│  [检查3] sell_tax > 10%                       │
│          → BLOCK (卖出税过高，利润被吞噬)         │
│                                               │
│  [检查4] top10_concentration > 80%            │
│          → BLOCK (筹码高度集中，拉盘砸盘风险)      │
│                                               │
│  [检查5] sell_tax > 30%                       │
│          → BLOCK (极端卖出税)                    │
│                                               │
│  [检查6] risk_score >= 90                     │
│          → BLOCK (综合风险极高)                  │
│                                               │
│  全部通过 → 进入阶段2打分                       │
└──────────────────────────────────────────────┘
```

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

## 5. 模块三：实时价格基础设施

### PriceFeed 架构

PriceFeed 是全局价格缓存管理器。AVE `/tokens/{addr}-{chain}` 是代币价格的核心数据源，每 2 秒轮询一次所有注册代币的价格。

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
  │  ② SimTrader         │ → TP/SL 止盈止损判定 (15% 阈值)
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
   → refcount["BONK"] = 0, 停止追踪，释放 API 配额
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
| SimTrader | 检查止盈(+15%)/止损(-15%)触发条件 | 每次价格变动 |
| PerformanceTracker | 更新 D0~D30 每日最高涨幅 | 每次价格变动 |

---

## 6. 模块四：聪明钱情报网络

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

```
┌────────────────────────────────────────────────┐
│            聪明钱三层供给体系                      │
│                                                 │
│  第 1 层: AVE 外部数据                           │
│    /address/smart_wallet/list                   │
│    → 4 链各 100 地址，持续补充                    │
│                                                 │
│  第 2 层: 内部数据挖掘                           │
│    smart_wallet_miner.py                        │
│    → 毕业代币早期买家挖掘                         │
│    → 热币 Top Holders 晋升                       │
│    → 累计 ~12,000 地址                           │
│                                                 │
│  第 3 层: Dune Analytics 批量导入                │
│    → 4 链 Query，~5,000 候选                     │
│    → 经五维度评估后入库                           │
│                                                 │
│  合计: 15,000+ 活跃聪明钱地址                     │
└────────────────────────────────────────────────┘
```

### Heat Score 公式

聪明钱信号的热度评分综合以下因子：

```
heat_score = w1 * wallet_score      # 钱包五维度总分权重
           + w2 * position_size     # 仓位大小
           + w3 * timing_score      # 入场时机（越早越高）
           + w4 * cluster_count     # 同时关注该代币的聪明钱数量

tier_weight:
  elite (score >= 75):      权重 3.0
  verified (score >= 55):   权重 2.0
  watching (score >= 35):   权重 1.0
  blacklisted (score < 30): 权重 0 (不参与计算)

concentration_bonus:
  3+ 个不同聪明钱在 1h 内买入同一代币 → +20 bonus
  5+ 个不同聪明钱在 1h 内买入同一代币 → +50 bonus
```

### v3 五维度评估体系

每个聪明钱地址按以下五个维度打分，总分 100：

| 维度 | 满分 | 评估内容 | 评估周期 |
|------|------|---------|---------|
| 胜率 (Win Rate) | 20 | 盈利交易占总交易的比例 | 90 天滚动 |
| PNL (利润) | 20 | 累计已实现利润 | 90 天滚动 |
| 交易规模 (Scale) | 20 | 平均单笔交易金额 | 90 天滚动 |
| 活跃度 (Activity) | 20 | 近期交易频率 | 30 天滚动 |
| 时效性 (Recency) | 20 | 最近一笔交易距今时间 | 90 天滚动 |

### 等级划分

| 等级 | 分数 | 权限 |
|------|------|------|
| `elite` | >= 75 | 信号权重最高，优先跟单 |
| `verified` | >= 55 | 正常跟单权重 |
| `watching` | >= 35 | 观察期，降低权重 |
| `blacklisted` | < 30 | 自动移除，不再追踪 |

### 实时监控

- SOL 链：Helius WebSocket `logsSubscribe` 监听 DEX 程序，~400ms 延迟
- EVM 链：公共 WebSocket RPC 订阅 Swap 事件 topic，~2-12s（取决于出块时间）
- 评估周期：每 2 小时重新计算五维度评分
- 降级规则：14 天无交易降级，28 天无交易移除
- Bot 检测：交易间隔 < 1s 且模式规律 → 自动 blacklist

---

## 7. 模块五：交易执行层

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

### Step 1: 报价查询

```
POST chainWallet/getAmountOut

请求:
  chainIndex:        501 (SOL) / 56 (BSC) / 1 (ETH) / 8453 (Base)
  inTokenAddress:    SOL / USDT 等基础代币地址
  outTokenAddress:   目标代币地址
  amount:            交易金额 (最小单位)
  swapType:          "buy" / "sell"

返回:
  estimateOut:       预估获得数量
  decimals:          代币精度

系统处理:
  计算实际滑点 = |actualOut - estimateOut| / estimateOut
  若滑点 > 阈值 → 拒绝交易
```

### Step 2: 交易构造

```
Solana: POST chainWallet/createSolanaTx
EVM:    POST chainWallet/createEvmTx

请求 (Solana):
  inTokenAddress, outTokenAddress, amount
  walletAddress:     用户钱包公钥
  slippage:          滑点容忍度 (百分比)
  requestTxId:       请求追踪 ID
  fee:               优先费 (0.0005 SOL)

请求 (EVM):
  chainIndex, inTokenAddress, outTokenAddress, amount
  walletAddress, slippage

返回:
  rawTransaction:    未签名的原始交易数据
  requestTxId:       用于后续提交的请求 ID
```

### Step 3: 本地签名（自托管核心）

```
私钥始终保存在本地服务器，从不发送到 AVE 或任何外部服务

Solana: 使用 solders 库签名
  keypair = Keypair.from_seed(private_key_bytes)
  signed_tx = Transaction.sign(raw_tx, keypair)

EVM: 使用 eth_account 库签名
  account = Account.from_key(private_key_hex)
  signed_tx = account.sign_transaction(raw_tx)
```

### Step 4: 签名交易广播

```
Solana: POST chainWallet/sendSignedSolanaTx
EVM:    POST chainWallet/sendSignedEvmTx

请求:
  requestTxId:        来自 Step 2 的追踪 ID
  signedTransaction:  Step 3 签名后的交易数据
  chainIndex (EVM):   链标识

返回:
  txHash:             链上交易哈希

系统处理:
  记录 txHash 到 DB → 等待链上确认 → 更新仓位状态
```

### Solana 交易代码示例

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

### EVM 交易代码示例

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

## 8. 系统架构全景图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AiTrading Pro 系统架构                             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                        数据采集层                                    │     │
│  │                                                                      │     │
│  │  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐   │     │
│  │  │ ◆ AVE Trending │  │ ◆ AVE Contract │  │ ◆ AVE Smart Wallet  │   │     │
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
│  │  │  ◆ AVE /tokens/ (全链代币) ~2s 轮询    │          │                │     │
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
│  │  │                ◆ AVE Chain Wallet                         │      │     │
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
│                                                                              │
│  ◆ = AVE Cloud Skill 调用点                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. API 调用明细表

### ave-data-rest (Base URL: `https://data.ave-api.xyz/v2`)

| # | 端点 | 方法 | 频率 | 请求参数 | 响应关键字段 | 调用模块 |
|---|------|------|------|----------|-------------|---------|
| 1 | `/tokens/trending` | GET | 每 10min, 每链 1 次 | `chain`, `limit=50` | `tokens[]`: current_price_usd, market_cap, tvl, holders, price_change_1h/4h/24h, buy_tx_count, sell_tx_count, appendix | HotCoinManager |
| 2 | `/tokens/{addr}-{chain}` | GET | 每 2s 轮询 | 路径参数 | `token`: current_price_usd, market_cap, tvl, token_tx_volume_usd_24h, holders | PriceFeed |
| 3 | `/contracts/{addr}-{chain}` | GET | 入榜时 + 交易前 | 路径参数 | is_honeypot, buy_tax, sell_tax, has_code, has_mint_method, has_black_method, can_take_back_ownership, risk_score, holders_detail[] | SecurityChecker |
| 4 | `/address/smart_wallet/list` | GET | 每 6h | `chain`, `limit=100` | list[]: address, pnl, win_rate | SmartMoneyTracker |
| 5 | `/tokens?keyword=` | GET | 按需 | `keyword` | tokens[]: address, name, symbol, chain | TokenSearch |

### ave-trade-chain-wallet (Base URL: `https://bot-api.ave.ai/v1/thirdParty`)

| # | 端点 | 方法 | 调用时机 | 请求参数 | 响应关键字段 | 调用模块 |
|---|------|------|---------|----------|-------------|---------|
| 6 | `chainWallet/getAmountOut` | POST | 每笔交易前 | chainIndex, inTokenAddress, outTokenAddress, amount, swapType | estimateOut, decimals | TradeExecutor |
| 7 | `chainWallet/createSolanaTx` | POST | SOL 买入/卖出 | inTokenAddress, outTokenAddress, amount, walletAddress, slippage, fee | rawTransaction, requestTxId | TradeExecutor |
| 8 | `chainWallet/createEvmTx` | POST | EVM 买入/卖出 | chainIndex, inTokenAddress, outTokenAddress, amount, walletAddress, slippage | rawTransaction, requestTxId | TradeExecutor |
| 9 | `chainWallet/sendSignedSolanaTx` | POST | SOL 签名后 | requestTxId, signedTransaction | txHash | TradeExecutor |
| 10 | `chainWallet/sendSignedEvmTx` | POST | EVM 签名后 | chainIndex, requestTxId, signedTransaction | txHash | TradeExecutor |

### 请求认证

| API 类型 | Header | 说明 |
|----------|--------|------|
| Data REST | `X-API-KEY: {AVE_API_KEY}` | 数据查询认证 |
| Trade Chain Wallet | `AVE-ACCESS-KEY: {AVE_API_KEY}` | 交易操作认证 |

---

## 10. 核心实现 ave_client.py

所有 AVE API 调用集中在 `ave_client.py` 单一模块中，实现统一的限速、重试、格式转换。

### AveClient 类结构

```python
class AveClient:
    """AVE Cloud API 统一客户端（1 RPS 限速）"""

    _session: aiohttp.ClientSession    # HTTP 会话复用
    _last_req_ts: float                # 上次请求时间戳
    _lock: asyncio.Lock                # 限速并发锁
```

### 公开方法

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `get_trending(chain, limit)` | 链名, 数量(默认50) | `List[dict]` | 获取链上热门代币 |
| `get_token_detail(address, chain)` | 代币地址, 链名 | `Optional[dict]` | 获取单个代币详情 |
| `get_batch_prices(pairs)` | `["addr-chain", ...]` | `Dict[str, float]` | 批量价格查询 |
| `check_risk(address, chain)` | 代币地址, 链名 | `Optional[dict]` | 合约安全检测 (goplus 格式) |
| `get_smart_wallets(chain, limit)` | 链名, 数量 | `List[dict]` | 获取聪明钱列表 |
| `get_quote(chain, in_token, out_token, amount, swap_type)` | 链/输入/输出/数量/类型 | `Optional[dict]` | 交易报价 |
| `create_solana_tx(...)` | 多参数 | `Optional[dict]` | 创建 Solana 交易 |
| `create_evm_tx(...)` | 多参数 | `Optional[dict]` | 创建 EVM 交易 |
| `send_signed_solana_tx(request_tx_id, signed_tx)` | 交易ID, 签名数据 | `Optional[dict]` | 发送 Solana 交易 |
| `send_signed_evm_tx(chain, request_tx_id, signed_tx)` | 链/交易ID/签名 | `Optional[dict]` | 发送 EVM 交易 |

### 限速机制

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

### 链名映射

```python
_CHAIN_MAP = {
    "solana": "solana",
    "bsc": "bsc",
    "base": "base",
    "eth": "eth",
    "ethereum": "eth",     # 兼容内部用 "ethereum" 的模块
}
```

### Session 复用

```python
def _get_session(self) -> aiohttp.ClientSession:
    if self._session is None or self._session.closed:
        self._session = aiohttp.ClientSession()
    return self._session
```

- 惰性创建 aiohttp.ClientSession
- 自动检测关闭状态并重建
- 全局单例 `ave = AveClient()` 保证进程内只有一个 HTTP 连接池

### Data REST 请求格式

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

### Trade REST 请求格式

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

### 格式转换层

`_convert_risk_to_goplus()` 静态方法将 AVE 安全检测结果转换为内部标准格式，使整个系统无需关心数据源差异：

- `is_honeypot`: int(-1/0/1) → bool
- `has_code`: int(0/1) → bool `is_open_source`
- `holders_detail`: array → `top10_holder_pct` + `top1_holder_pct`
- 保留 `_ave_raw` 原始数据，供调试使用

---

## 11. AI 决策引擎概览

AI 决策引擎建立在 AVE 数据基础设施之上，将结构化数据转化为交易决策。

### 三层决策架构

```
信号 (来自 AVE 数据)
    │
    ▼
L1 规则引擎 (毫秒级)
    过滤条件: 9 种运算符 (>, <, ==, !=, >=, <=, in, not_in, between)
    组合逻辑: AND / OR 嵌套树
    通过 L1 → 进入 L2
    │
    ▼
L2 快速评估 (Claude Opus 4.6, ~2秒)
    单次 LLM 调用，输入: 代币数据 + 信号上下文 + 记忆注入
    输出: {action: buy/sell/hold, confidence: 0-100, reasoning: "..."}
    confidence >= 70 → 进入 L3
    │
    ▼
L3 多角色辩论 (3-5 分钟)
    3 个分析师 (Haiku): 技术面 / 基本面 / 链上数据，并行分析
    牛方 (Sonnet): 综合看多论点
    熊方 (Sonnet): 综合看空论点
    仲裁者: 加权裁决 → 最终交易决策
```

### 三层记忆系统

| 层级 | 存储周期 | 内容 | 更新频率 |
|------|---------|------|---------|
| Working Memory | 24 小时 | 当前持仓、近期交易、活跃信号 | 实时 |
| Episodic Memory | 14-30 天 | 每笔交易的完整记录 + 每日反思 | 每笔交易后 |
| Semantic Memory | 长期 | 50 条经验规则 (如 "pump.fun BC>25% 需谨慎") | 反思周期 (每 6h) |

记忆注入到 L2 决策 Prompt 中，使 AI 能从过去的成功和失败中学习。

### Regime 市场状态检测 (7 状态)

| 状态 | 检测方法 | 仓位乘数 | 风控松紧 |
|------|---------|---------|---------|
| BULL | BTC 7d涨幅 > 5% | 较高 | 正常 |
| BEAR | BTC 7d跌幅 > 10% | 最低 | 最严 |
| SIDEWAYS | BTC 横盘 | 中等 | 正常 |
| VOLATILE | 高波动 | 降低 | 收紧 |
| CRISIS | BTC 24h跌幅 > 15% 或 VIX 极值 | 最低 | 紧急平仓 |
| RECOVERY | 从 CRISIS 恢复 | 逐步恢复 | 谨慎 |
| ACCUMULATION | 筹码吸纳阶段 | 中等 | 正常 |

### 风控系统 (15 项检查)

| # | 检查项 | 说明 |
|---|--------|------|
| 1 | 单笔仓位上限 | 不超过总资金 5% |
| 2 | 单链仓位上限 | 不超过总资金 25% |
| 3 | 总仓位上限 | 不超过总资金 80% |
| 4 | 单代币持仓上限 | 避免过度集中 |
| 5 | 日亏损限额 | 不超过总资金 10% |
| 6 | 连续亏损熔断 | 连亏 5 笔暂停 4h |
| 7 | 滑点检查 | 实际 vs 预期偏差 |
| 8 | 流动性检查 | 仓位 < 池子深度 2% |
| 9 | 安全检查 | AVE 合约审计结果 |
| 10 | 价格异常检查 | 5min 涨跌 > 50% |
| 11 | 持仓时间衰减 | 超 48h 降低继续持有信心 |
| 12 | 相关性检查 | 同类代币不超配 |
| 13 | BTC 大盘风险 | CRISIS 状态触发全局保护 |
| 14 | 同链集中度 | 单链信号过多时限流 |
| 15 | 最大回撤保护 | 回撤 > 20% 触发紧急审查 |

---

## 12. 效果指标与运营数据

### 数据覆盖

| 指标 | 数值 | 说明 |
|------|------|------|
| 热币覆盖 | 4 链 ~200 活跃代币 | 每链 50 个 Trending 候选，score >= 50 入榜 |
| 聪明钱地址 | 15,000+ 钱包 | SOL ~5,222 + EVM ~10,540，三层供给 |
| KOL 监控 | 212 个 | Twitter KOL 实时舆情 |
| 热币发现层 | ~542 候选/轮 | GeckoTerminal trending + new_pools，4 链 |
| Dune 地址导入 | 17,307 候选 | 4 链 Query，经五维度评估后入库 |
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

### AI 决策质量

| 指标 | 数值 | 说明 |
|------|------|------|
| 热币 D1 正收益 | 37.7% | 历史数据回测 |
| 热币 50%命中率 | 20.5% | D1 涨幅超 50% 的代币占比 |
| 热币平均最佳涨幅 | 38.8% | 入榜后 D0-D7 最佳涨幅均值 |
| 记忆系统 | 50 条语义规则 | 持续学习 |
| Regime 检测 | 7 种市场状态 | 动态适应大盘 |

---

## 13. 链支持矩阵

| 功能 | Solana | BSC | ETH | Base |
|------|--------|-----|-----|------|
| 热币发现 | AVE `/tokens/trending` | AVE `/tokens/trending` | AVE `/tokens/trending` | AVE `/tokens/trending` |
| 实时价格 | AVE `/tokens/{addr}` 2s | AVE `/tokens/{addr}` 2s | AVE `/tokens/{addr}` 2s | AVE `/tokens/{addr}` 2s |
| 安全检测 | AVE `/contracts/{addr}` | AVE `/contracts/{addr}` | AVE `/contracts/{addr}` | AVE `/contracts/{addr}` |
| 聪明钱 | AVE + Helius WS | AVE + EVM WS | AVE + EVM WS | AVE + EVM WS |
| 交易报价 | AVE `getAmountOut` | AVE `getAmountOut` | AVE `getAmountOut` | AVE `getAmountOut` |
| 创建交易 | `createSolanaTx` | `createEvmTx` | `createEvmTx` | `createEvmTx` |
| 发送交易 | `sendSignedSolanaTx` | `sendSignedEvmTx` | `sendSignedEvmTx` | `sendSignedEvmTx` |
| 签名库 | solders | eth_account | eth_account | eth_account |
| 出块时间 | ~400ms | ~3s | ~12s | ~2s |
| 原生代币 | SOL (wSOL) | BNB | ETH | ETH |
| chainIndex | 501 | 56 | 1 | 8453 |

---

## 14. 技术创新点

### 14.1 基于 AVE 的统一数据层

传统方案需要对接多个独立 API（DexScreener、GoPlus、OKX DEX 等），存在认证碎片化、格式不统一、限速各异等问题。AiTrading Pro 通过 AVE Cloud Skill 实现统一数据层：

- **单一 API Key**：一个 AVE Key 覆盖数据查询 + 安全检测 + 交易执行
- **统一格式**：`ave_client.py` 内部做一次格式转换，上层模块完全无感
- **统一限速**：1 RPS 限速器统管所有请求，不会因为某个模块超频导致封禁

### 14.2 AVE 数据驱动的毫秒级打分引擎

传统热币扫描依赖定时批量查询。AiTrading Pro 基于 AVE PriceFeed 实现了事件驱动的实时打分。每 2 秒的价格回调直接触发 HotCoinManager 重新计算 100 分，代币进出榜单延迟从分钟级降至秒级。退出机制（5 规则）同样由价格回调驱动，无需额外轮询。

### 14.3 PriceFeed 引用计数

创新的引用计数架构解决了代币追踪生命周期管理问题：

- 多个消费者（HotCoinManager / SimTrader / PerformanceTracker）可以独立注册和注销同一代币
- 只要有一个消费者还在关注，价格追踪就继续
- 全部消费者注销后，自动停止轮询，释放 API 配额
- 避免了"退榜后模拟盘无法止损"和"重复订阅浪费配额"两个常见问题

### 14.4 自托管交易的四步分离架构

AVE chain-wallet API 将交易拆分为 报价 → 构造 → 签名 → 广播 四个独立步骤，其中签名环节完全在本地完成。这种架构既享受了 AVE DEX 聚合的最优路由，又保证了私钥零泄露。CRISIS 模式下滑点自动放宽到 5%，优先保证清仓成交。

### 14.5 三层供给 + 五维度评估的聪明钱体系

聪明钱地址不是静态列表，而是一个动态生态。AVE 提供基础种子地址，内部 miner 从链上数据（毕业代币早期买家、热币 Top Holders）挖掘新地址，Dune 批量补充。所有地址经 v3 五维度（胜率/PNL/规模/活跃度/时效性）持续评估，实时 bot 检测 + 定期降级/移除，保证库的质量。

### 14.6 L1-L2-L3 渐进式 AI 决策 + 牛熊辩论

不是所有信号都需要 Claude Opus 级别的分析。L1 规则引擎以毫秒级过滤掉 80% 的低质量信号，L2 快评在 2 秒内给出初步判断，只有高置信度信号才进入 L3 多角色辩论。L3 引入 Bull Agent 和 Bear Agent 对抗式推理，强制考虑反面论据，避免单一模型的确认偏差。置信度评分决定仓位大小：高置信度 → 大仓位，低置信度 → 小仓位或放弃。

---

## 15. 环境配置

### 必需环境变量

```bash
# AVE Cloud Skill（系统数据与交易基础设施）
AVE_API_KEY=<your-ave-api-key>

# AVE 内置的基础 URL（无需手动配置）
# AVE_DATA_BASE=https://data.ave-api.xyz/v2
# AVE_TRADE_BASE=https://bot-api.ave.ai
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

### 辅助服务

```bash
# Helius（Solana DEX 实时监控）
HELIUS_API_KEY=<your-helius-key>

# Claude AI（决策引擎）
ANTHROPIC_API_KEY=<your-anthropic-key>

# Supabase（数据库）
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-supabase-key>

# Dune Analytics（聪明钱批量导入）
DUNE_API_KEY=<your-dune-key>
```

### 启动命令

```bash
cd services/pump-scanner
python main.py

# main.py 启动以下所有子系统:
#   - HotCoinManager     (AVE trending 发现 + 实时打分)
#   - PriceFeed          (AVE token detail 轮询)
#   - SecurityChecker    (AVE contracts 审计)
#   - SmartMoneyTracker  (AVE smart_wallet + 内部库)
#   - TradeExecutor      (AVE chainWallet 交易执行)
#   - AIDecisionEngine   (L1/L2/L3 决策)
#   - PumpScanner        (pump.fun 内盘扫描)
#   - KOLMonitor         (KOL 舆情监控)
#   - BTCETHAnalyzer     (大盘分析)
#   - AIOptimizer        (自动优化 Agent)
```

### 项目仓库结构

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
│       ├── trade_executor.py     # 交易执行（AVE chain-wallet）
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

---

## 16. License

MIT License

Copyright (c) 2026 AiTrading Pro

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
