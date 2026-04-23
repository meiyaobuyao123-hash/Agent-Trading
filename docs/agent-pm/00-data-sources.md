# 00 数据来源索引（Data Provenance）

> 本 PM 文档体系中**所有数据的出处**。一线 AI 团队必须有这份文档——不能用推测数据去做产品决策。

| 字段 | 值 |
|------|---|
| Status | 🟢 Live（每次更新数据时同步） |
| Version | v0.2 |
| Last Updated | 2026-04-23 |

---

## 0. 为什么需要这份文档

**问题**：产品文档里到处是数字（"50% 胜率目标"、"30 天留存 35%"、"资金 $5K-$50K"），但用户问一句"这数据哪来的"就傻眼。

**原则**：每个数据必标三要素——**来源 / 可信度 / 更新频率**。

**分类**：
- 🟢 **生产数据**：DB / 日志 / 系统埋点，每次查询实时
- 🔵 **公开数据**：行业报告（a16z / Chainalysis / Messari 等），引用即可
- 🟡 **推测数据**：基于经验 / 直觉，**必须标红 + 说明验证计划**
- ⚪ **待收集**：功能未上线，暂无数据

---

## 1. 生产数据清单（🟢 可信）

### 1.1 策略胜率与盈亏比（来自 `hot_sim_trades` 表）

| 指标 | 值（2026-04-23）| SQL 来源 |
|------|----------------|---------|
| Hot repeat 胜率 | **42.0%** | `hot_sim_trades WHERE source='hot' AND mode='repeat' AND status IN ('tp','sl')` |
| Hot unique 胜率 | **45.2%** | 同上 mode='unique' |
| Smart Money 胜率 | **44.0%** | source='smart_money' |
| Pump 胜率 | **无（0 闭仓 / 937 open）** | source='pump'，新上线 |
| Hot 平均盈利 | **+15.86%** | pnl_pct 平均，status='tp' |
| Hot 平均亏损 | **-14.48%** | pnl_pct 平均，status='sl' |
| Hot 盈亏比 | **1.10 : 1** | 15.86 / 14.48 |
| Smart Money 盈利 | **+24.87%** | 同上 |
| Smart Money 亏损 | **-11.74%** | 同上 |
| SM 盈亏比 | **2.12 : 1** | 24.87 / 11.74 |
| Hot 单笔期望值 | **-1.74%** | 0.42 × 15.86 - 0.58 × 14.48 |
| SM 单笔期望值 | **+4.37%** | 0.44 × 24.87 - 0.56 × 11.74 |

**更新频率**：实时（每 `hot_sim_trades` 新闭仓）。

**引用位置**：
- [01 Vision § 5.3 策略质量](./01-product-vision.md#53-策略质量strategy-quality-核心能力验证)
- [11 Launch Criteria](./11-launch-criteria-hitl.md)（待写）

### 1.2 用户规模（来自 `device_tokens` + `agent_strategies`）

| 指标 | 值（2026-04-23）| 说明 |
|------|----------------|------|
| device_tokens | **0** | 无真实用户 |
| agent_strategies 总数 | **13** | 开发者自测 |
| unique_users | **1** | 只有开发账号 |
| active strategies | **4** | status='active' 的 |

**引用位置**：[02 Persona § 0](./02-user-persona-journey.md)

### 1.3 代币覆盖（来自 `hot_coins`）

| 指标 | 值 |
|------|-----|
| Solana | 129 |
| Base | 68 |
| BSC | 64 |
| ETH（放宽过滤后）| 9 |
| 总计 | 270 |

### 1.4 聪明钱信号（来自 `smart_money_signals`）

| 指标 | 值（最近 30 天）|
|------|---------------|
| 信号总数 | 3,345 |
| **追踪数据**：D1/D3/D7 后涨幅 | **⚠️ 当前未追踪**，需 M1 埋点 |

### 1.5 交易覆盖（来自 `smart_money_txns`）

| 指标 | 值（14 天）|
|------|----------|
| 交易总数 | 8,933 |
| elite tier | 409 + 316 sell |
| verified | 6 + 11 |
| watching | 35 + 29 |

### 1.6 DEX 程序级事件流 ⭐ 核心实时源

> **这是本 Agent 最底层、最实时、最"链上原生"的数据源**。所有轮询式 API（OKX / GeckoTerminal / DexScreener）都只是**兜底或补充**。

#### 1.6.1 监听范围

| 链 | 监听对象 | 数据通道 | 实测延迟 | 覆盖率 |
|----|---------|---------|---------|--------|
| **SOL** | Raydium AMM V4 / CLMM / Orca Whirlpool / Meteora DLMM / Jupiter V6 / **Pump.fun** | Helius `logsSubscribe` WS | **~400ms**（1 slot）| 主流 DEX 100% |
| **ETH** | Uniswap V2 + V3（Swap Topic）| 公共 RPC WS + OKX 轮询 | ~12s（块时间）| V2/V3 |
| **BSC** | PancakeSwap V2/V3（同 Uniswap Topic）| 公共 RPC WS + OKX 轮询 | ~3s | V2/V3 |
| **Base** | Uniswap V3 / Aerodrome | 公共 RPC WS + OKX 轮询 | ~2s | 主流 |
| **Pump.fun 内盘** | pumpportal WS（newToken + trade）| 自建 WS | **<1s** | 100% |

#### 1.6.2 事件能抓到什么

✅ **已能解出**：
- `token_in / token_out` mint 地址
- `amount`（raw + USD 换算）
- `wallet`（SOL: feePayer + accountData；EVM: topics Sender/Recipient）
- `tx_hash / signature + timestamp`
- `price_usd`（后查 DexScreener 或缓存）
- `volume_usd`（SOL: nativeTransfers + WSOL/USDC tokenTransfers；EVM: topics 解析）
- `market_cap_at_tx`（近实时补全）
- `wallet_tier`（与 smart_wallets 表 join，得到 elite/verified/watching）

❌ **当前抓不到**（需额外订阅 / 独立源）：
- 池子 liquidity 深度（→ 用 OKX DEX API / DexScreener 补）
- Holder 变化（→ 需单独订 Transfer 事件或用 Helius enhanced TX）
- 多跳 swap 准确聚合（单 tx 多 swap 当前会记成多笔，去重用 signature 但会放大成交量 ~2%）

#### 1.6.3 直接落表

| 表 | 事件源 | 保留 |
|----|--------|------|
| `pump_tokens` | pumpportal newToken | 永久 |
| `token_trades` | pumpportal trade | 30 天 |
| `token_snapshots` | 1min 聚合快照（bc_progress / buy_sell_ratio / unique_buyers）| 90 天 |
| `smart_money_txns` | SOL/EVM DEX swap 解析 | 14 天 |
| `hot_coins` | （多源融合）| 实时 |

#### 1.6.4 已知局限与漏洞

| 局限 | 影响 | 处理方式 |
|------|------|---------|
| SOL 未监听 Phoenix（orderbook DEX）| ~2-3% SOL 成交漏数 | v1 接受，v2 补 |
| EVM 未监听 Curve（稳定币池 / stable swap topic）| 稳定币大额漏数 | v1 接受（不是我们主战场）|
| Helius 免费版 429 | 单 DEX 1 subscription，多触发易限流，触发后 10min 完全中断 | v1 必须付费升级，否则是 SEV-2 源 |
| Multi-hop swap 按 signature 去重但会放大量 | Volume 虚高 ~2% | v1 接受，回测时按 tx 级聚合 |
| 内部 tx（Jupiter router）| ~5% 漏数 | 大额交易改用 Helius enhanced TX API |
| EVM 块时间延迟 | ETH 12s、BSC 3s、Base 2s | 这是链的物理限制，无法优化 |

#### 1.6.5 "能替代什么 / 不能替代什么"

| 场景 | 用 DEX 事件流？ | 说明 |
|------|----------------|------|
| 实时成交监测 | ✅ **主源** | OKX / Gecko 降级为兜底 |
| 信号策略 evaluate（event-driven）| ✅ **主源** | 替代原 30s 轮询 |
| 聪明钱追踪 | ✅ **主源** | 已是现状 |
| Pump 早期发现 | ✅ **主源** | pumpportal WS |
| 历史 K 线 | ❌ | 用 GeckoTerminal API（WS 不适合回放）|
| 池子深度 / 滑点估算 | ❌ | OKX DEX API 必须 |
| 交易执行 quote | ❌ | Jupiter / OKX aggregator 必须 |
| Holder 分布 | ❌ | Helius enhanced / 独立源 |
| 跨链 bridge 追踪 | ❌ | v1 不做 |

**关键结论**：DEX 事件流是 **实时触发 / 实时感知** 的源；OKX / GeckoTerminal / Helius HTTP 是 **查询 / 深度 / 历史** 的源。**两者互补，不互斥**。

#### 1.6.6 引用位置

- [03 PRD § 8.7](./03-prd.md#87-event-driven-first-原则) — Event-Driven First 原则
- [03 PRD § 3](./03-prd.md#3-signal-strategy-builder自定义信号策略--核心) — 信号策略 evaluate 的数据通道
- [05 Tool Catalog](./05-tool-catalog.md) — T01/T04/T13 等 tool 的实现底层

---

## 2. 公开数据（🔵 可引用）

### 2.1 行业基准（需引用来源）

| 主题 | 数据 | 来源 |
|------|------|------|
| AI 产品 D30 留存均值 | 15-25% | Mixpanel 2024 消费者 app 基准 |
| Freemium → Pro 转化率 | 3-8% | ProductLed 2024 报告 |
| AI 推荐系统 CTR | 20-35% | Google/Meta 公开分享 |
| Web3 用户钱包分布 | ⚠️ 待查 | a16z State of Crypto 2024 |

**规则**：公开数据引用必须标来源年份。超过 2 年的数据需重新验证。

### 2.2 竞品数据（⚠️ 多数为猜测）

| 竞品 | 数据 | 可信度 |
|------|------|--------|
| Photon DAU | ⚠️ 未公开 | 低 |
| Nansen 付费用户 | ⚠️ 未公开 | 低 |
| DexScreener 月活 | 约 500 万（SimilarWeb 估算）| 中 |
| GMGN DAU | ⚠️ 未公开 | 低 |

**注意**：竞品数据多数是**行业猜测**，不作为我们的 KPI 依据，仅作定位参考。

---

## 3. 推测数据清单（🟡 需验证）

### 3.1 Vision 文档的推测

| 数据 | 当前假设 | 验证方式 | 截止时间 |
|------|---------|---------|---------|
| Thesis 采纳率目标 ≥ 30% | 推测 | M1 用户埋点 | M1 |
| 反馈率目标 ≥ 40% | 推测 | M1 | M1 |
| 7d 留存 ≥ 50% | 推测 | M1 | M1 |
| 30d 留存 ≥ 30% | 推测 | M1 | M2 |
| 3 月 100 用户 | 推测 | 上线后实际 | M3 |
| 1 年 1K-5K 用户 | 推测 | M6 趋势外推 | M6 |

### 3.2 Persona 文档的推测（全部）

| 数据类型 | 假设值 | 验证方式 |
|---------|-------|---------|
| 3 层用户占比 | 30 / 50 / 20 | 埋点 + M1 调研 |
| 资金规模分布 | $200-5K / $5K-50K / $50K+ | 钱包余额匿名抽样 |
| 工具栈 | Phantom / Rabby / DexScreener / TG | 用户访谈 20 人 |
| 典型一天时长 | 30-60min / 1-2h / 3-5h | 埋点 |
| 心声原话 | 虚构 | 访谈真实引用替换 |
| 成功标志 | M3/M6/M12 的具体描述 | 真实用户反馈 |

### 3.3 Competitive Landscape 的定性判断

- "Nansen 给原始数据，我们给 thesis" → ✅ **事实**（竞品公开定位）
- "Photon 强在快速执行" → ✅ **事实**
- "我们信号感知和 Photon 同级" → ⚠️ **待验证**（实测延迟对比）

---

## 4. 待收集数据（⚪ 功能未上线）

| 数据 | 依赖功能 | 计划上线 |
|------|---------|---------|
| 信号 D1/D3/D7 命中率 | 需新增 signal_outcomes 表 | v1 |
| 策略存活天数 | 需用户系统 + 策略 CRUD | v1 |
| 策略编辑迭代次数 | 同上 | v1 |
| 回测使用率 | 回测功能 | v1 |
| Thesis 采纳率 | Thesis UI + 采纳按钮 | v1 |
| 复盘阅读率 | 周报/月报 + 推送埋点 | v1 |
| 用户画像（钱包资产）| 钱包 connect 后 匿名聚合 | v1 |

---

## 5. 数据更新流程

### 5.1 每次查询生产数据时

1. 标明查询时间（年月日）
2. SQL / Script 可追溯
3. 结果更新至本文档对应章节

### 5.2 推测数据变真实数据时

1. 从 🟡 清单移到 🟢 清单
2. 更新相关文档（Vision / Persona / PRD）
3. 在 Change Log 注明"X 数据已用真实数据替换"

### 5.3 季度 review

每 3 个月必做：
- 推测数据清单 → 至少 50% 转为真实
- 公开数据引用 → 重新验证年份
- 新增埋点需求 → 同步到 15 Observability 文档

---

## 6. 反模式（我们不做）

| 反模式 | 危害 |
|-------|------|
| 把推测写成事实 | 误导决策 |
| 引用公开数据不标年份 | 可能已过时 |
| 用竞品猜测数据定 KPI | 基准错误 |
| 数据不更新 | 半年前的 baseline 继续用 |
| 查一次用半年 | 加密市场一周就变 |

---

## Change Log

- **v0.2 (2026-04-23)**：新增 § 1.6 DEX 程序级事件流
  - 基于代码盘点，把 DEX WS 事件流定性为 **P0 主源**（非 OKX API）
  - 明确监听范围（SOL 6 DEX + EVM Uniswap V2/V3 + pumpportal）
  - 盘点能抓到 / 抓不到的字段
  - 明确能替代什么 / 不能替代什么（DEX 事件流给实时 / API 给深度和历史）
  - 列出已知局限（Phoenix/Curve 未覆盖 / Helius 429 / multi-hop 重复计数）
- **v0.1 (2026-04-23)**：首版创建
  - 列出当前生产数据（策略胜率 / 盈亏比 / 用户数 / 代币覆盖）
  - 标明所有推测数据的验证路径
  - 建立数据更新流程
  - 产品反馈"数据必须真实"倒逼写成本文档
