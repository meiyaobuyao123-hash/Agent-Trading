# 03 PRD（总）

> 按 **6 大核心能力**组织的 v1 MVP 需求。每个能力明确 tool 映射、数据源、验收标准、与现有代码的关系。

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.1 Draft |
| Version | v0.1 |
| Owner | 产品负责人 |
| Target Release | v1 MVP - 2026 Q3 |

---

## 0. 文档导读

### 0.1 谁要看这份 PRD
- **工程**：照着开发，每个能力的验收标准是合约
- **设计**：每个功能的用户场景和边界
- **PM**：Vision → 功能 → Tool → Eval 的映射
- **QA**：验收标准直接翻译成测试用例

### 0.2 MoSCoW 图例
- 🔴 **MUST** — v1 MVP 必须，不做不上线
- 🟠 **SHOULD** — 应该有，可延后 1-2 周
- 🟡 **COULD** — 有余力再做
- ⚫ **WON'T** — v1 明确不做（可能 v2）

### 0.3 术语对齐
- **信号策略（Signal Strategy）**：用户定义的"什么条件触发通知/分析"
- **交易策略（Trade Strategy）**：用户定义的"触发后如何下单 + 止盈止损 + 仓位"
- **Thesis**：Agent 产出的投资建议文本（方向 + 理由 + 风险 + 入场区）
- **Tool**：Agent 可调用的能力单元（harness 规范，见 [05 Tool Catalog](./05-tool-catalog.md)）

### 0.4 与 Vision / Persona 的映射
本 PRD 是 [01 Vision](./01-product-vision.md) 的落地。所有功能必须服务：
- Vision 的 5 条产品原则
- Vision 的 6.5 节"Agent 与 APP 其他模块的边界"——**Agent 不做官方信号推送**
- [02 Persona](./02-user-persona-journey.md) 主打中级用户的工作流

---

## 1. Market Query（查询行情）

### 1.1 用户故事
> As 加密链上投资者, I want 通过 Agent 用一句话查询任意代币的实时行情 + 风险数据, so that 不用切到 DexScreener / GoPlus 等 3 个工具。

### 1.2 功能需求

| 优先级 | 功能点 | 验收标准 |
|-------|-------|---------|
| 🔴 | 按代币地址查询 | 输入 `chain + address` 返回完整数据（价格/MC/LP/24h 涨幅/holder 分布/风险标记），延迟 < 500ms |
| 🔴 | 按 symbol 模糊查询 | 输入 "TRUMP" 返回全 4 链匹配的代币列表 |
| 🔴 | 4 链支持 | SOL / ETH / BSC / Base 全部覆盖 |
| 🔴 | 风险标记 | GoPlus 检查（rugpull 风险、honeypot、持仓集中度）|
| 🟠 | 历史 K 线 | 5m / 1h / 4h / 1d 粒度，至少 90 天历史 |
| 🟠 | Top Holders | Top 10 钱包持仓分布 |
| 🟠 | 近期大额交易 | 最近 20 笔大额买卖记录（> $1K）|
| 🟡 | 社交数据 | Twitter / Telegram 关注数、最近 24h 提及量 |

### 1.3 数据源

| 数据 | 来源 | 是否已有 |
|------|------|---------|
| 行情（价格/MC/LP/涨幅）| `hot_coins` 表 + DexScreener API | ✅ 已有 |
| 风险标记 | `hot_coins.goplus_risk` + GoPlus API | ✅ 已有 |
| Holder 分布 | `hot_coin_top_holders` 表 + Helius/OKX | ✅ 已有 |
| K 线 | DexScreener + GeckoTerminal | ⚠️ API 接入已有，未聚合到单一端点 |
| 社交数据 | LunarCrush / Twitter API | 🟡 有 LunarCrush 但不充分 |

### 1.4 Tool 映射（harness 规范）

- `T01 query_market(chain, address, [include=holders,klines])` → 单代币完整数据
- `T02 query_holders(chain, address)` → 持仓分布
- `T03 query_onchain_activity(chain, address, period=24h)` → 近期交易活动

### 1.5 边界

- ❌ 不支持 CEX 行情（只做链上 DEX）
- ❌ 不做 limit order book（DEX 没有）
- ❌ 不做跨链资产（一次查询只涉及一条链）

### 1.6 与 APP 现有功能的关系

| APP 现有 | 本功能与之关系 |
|---------|--------------|
| 热币 Tab | 展示官方扫描结果。**本功能是"按需深查"**，用户点进去看详情时触发 |
| 聪明钱 Tab | 展示官方信号。Agent 对单代币查询时会带上"最近聪明钱动向" |
| 代币详情页 | 已有。Agent 查询 API 复用其数据源 |

---

## 2. Market Analysis（分析行情）

### 2.1 用户故事
> As 投资者, I want 让 Agent 分析一个代币的投资价值, so that 我得到可解释的 thesis（方向/入场/止损/止盈/风险），不用自己在 5 个工具间拼数据。

### 2.2 功能需求

| 优先级 | 功能点 | 验收标准 |
|-------|-------|---------|
| 🔴 | 生成 Thesis | 输入 `chain + address`，返回结构化 thesis：{direction, entry_zone, stop_loss, target, conviction, risks[], 30_word_summary}。**P95 延迟 < 5s** |
| 🔴 | 引用数据源 | Thesis 必须引用具体数据（价格变化、聪明钱买卖次数、holder 变化）|
| 🔴 | 引用历史类似案例 | 必须调用 `recall_memory` 工具，在 thesis 里带 1-3 条"过去类似情况"|
| 🔴 | 风险标注 | 每条 thesis 必须列 ≥ 2 个具体风险 |
| 🔴 | Confidence Score | 0-1 连续值，< 0.6 必须在 UI 标注"低置信度"|
| 🟠 | 多角色辩论（L3）| 大额（>$200）/ 低置信度（<0.6）/ CRISIS regime 自动触发 Bull vs Bear Sonnet 辩论 |
| 🟠 | 分析风格切换 | 按 Persona（小白/中级/专业）切换 thesis 语言风格 |
| 🟡 | 批量分析 | 同时分析 3-5 个代币的对比表 |

### 2.3 分析维度

每条 thesis 必须融合以下 4 维（缺任一标注"数据不足"）：

| 维度 | 数据源 | 分析要点 |
|------|--------|---------|
| **技术面** | K 线 / RSI / MA / ATR / 支撑阻力 | 趋势 + 入场区 + 止损位 |
| **链上面** | 聪明钱买卖 / holder 变化 / 流动性 | 主力方向 + 流动性健康度 |
| **情绪面** | 社交提及 / KOL 喊单 / 恐贪指数 | FOMO 还是 fear |
| **风险面** | GoPlus / Top10 持仓 / 代币年龄 / dev 钱包 | rugpull 概率 + 集中度风险 |

### 2.4 Tool 映射

- `T04 analyze_technical(address, timeframes)` → 技术面分析（Haiku，<2s）
- `T05 analyze_sentiment(address, period=24h)` → 情绪面分析（Haiku，<2s）
- `T06 analyze_onchain(address)` → 链上面分析（Haiku，<2s）
- `T12 recall_memory(situation)` → 历史类似案例检索（<500ms）
- **组合调用**：`analyze_token(address) = parallel(T04, T05, T06) + T12 → thesis_writer prompt`

### 2.5 边界

- ❌ **不给"保证盈利"话术**（Vision Non-goal）
- ❌ **不诱导用户交易**（不写"错过就亏了"式话术）
- ⚠️ 低置信度必须显性标注，不伪装确信
- ⚠️ 数据不足（例如代币 <1h 新上线）时明确拒绝分析，引导用户等

### 2.6 与现有代码的关系

- ✅ `services/pump-scanner/agent/` 已有 analyst / debate / decision_agent
- ⚠️ 当前是 prompt 直接 call，需改造为 tool-use 协议（见 04 Agent Spec）
- ⚠️ `recall_memory` 不存在，需新建

---

## 3. Signal Strategy Builder（自定义信号策略）⭐ 核心

> 🔑 **本功能是 Agent 的核心价值**：让用户把自己的判断框架**沉淀为会自动触发的策略**，而不是被动消费官方信号。

### 3.1 用户故事

> As 有判断框架的投资者, I want 用自然语言或规则式描述"什么条件触发通知"，so that Agent 替我 24×7 盯盘。

**典型案例**：
- "聪明钱 2+ 钱包在 2h 内买入 + 流动性 > $100K"
- "pump.fun 内盘 BC 进度 5-20% + 独立买家 >= 3"
- "24h 涨幅 > 50% + Top10 持仓 < 60%"
- "KOL 喊单 3+ + score > 70"

### 3.2 功能需求

| 优先级 | 功能点 | 验收标准 |
|-------|-------|---------|
| 🔴 | 自然语言建策略 | 用户输入"聪明钱 2+ 买入 + LP > $100K"，Agent 转换为结构化条件树。转换失败率 < 10% |
| 🔴 | 规则式建策略 | UI 提供条件树编辑器（AND/OR 嵌套，数据源下拉）|
| 🔴 | 策略 CRUD | 增/删/改/查/暂停/启用。改完立即生效（无需重启）|
| 🔴 | 触发时通知 | 条件满足时 APP 内推 + 可选 push 通知，<1s 延迟 |
| 🔴 | 数据源支持 | 至少支持：hot_coins / smart_money_signals / token_snapshots / kol_signals |
| 🔴 | 触发去重 | 同代币同策略 30min 内不重复触发 |
| 🔴 | 冷却机制 | 每条策略可配置 cooldown（默认 5min）|
| 🟠 | 策略模板库 | 提供 5-10 条"热门模板"供快速创建 |
| 🟠 | 策略版本历史 | 每次修改保存 diff，可回滚 |
| 🟠 | 策略统计 | 显示最近 7/30 天触发次数 + 命中率 |
| 🟡 | 策略分享链接 | 生成可分享 URL（别人可复制到自己账号）|
| ⚫ v1 | 社区策略市场 | v2 再做 |

### 3.3 策略 Schema（JSON）

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "聪明钱跟单 SOL",
  "description": "用户自定义描述",
  "status": "active | paused",
  "conditions": {
    "operator": "AND",
    "rules": [
      {"data_source": "smart_money_signals", "field": "unique_buyers", "operator": ">=", "value": 2},
      {"data_source": "hot_coins", "field": "liquidity_usd", "operator": ">", "value": 100000},
      {"data_source": "hot_coins", "field": "chain", "operator": "==", "value": "solana"}
    ]
  },
  "filters": {
    "chains": ["solana", "bsc"],
    "token_blacklist": []
  },
  "cooldown_minutes": 30,
  "daily_trigger_limit": 20,
  "actions": [
    {"type": "notify", "channel": "push"},
    {"type": "bind_trade_strategy", "strategy_id": "..."}
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

### 3.4 数据源（已有）

- ✅ `agent_strategies` 表已有结构
- ✅ `StrategyEvaluator` + `RuleEngine`（`services/pump-scanner/agent/evaluator.py`）
- ✅ `EventListener` 已监听 4 类数据事件

### 3.5 Tool 映射

- `T07 build_signal_strategy(nl_description | structured_rules)` → 创建/更新策略
- `T13 list_user_strategies(user_id)` → 列出用户策略
- `T14 pause_strategy(strategy_id) / resume_strategy(strategy_id)`

### 3.6 边界

- ❌ Agent **不替用户建策略**（Agent 是助手，不主动想）。**除非用户主动让 Agent 建议**
- ❌ v1 不做"策略相关性检测"（两条策略互相冲突时不报警）
- ⚠️ 单用户策略数量上限 20 条（防滥用）
- ⚠️ 单策略触发频率上限 100 次/天

### 3.7 与 APP 其他 Tab 的关系

| APP Tab | 关系 |
|---------|------|
| 热币 Tab | 可作为策略的数据源（条件引用 hot_coins）|
| 聪明钱 Tab | 可作为策略的数据源（条件引用 smart_money_signals）|
| 新币 Tab | 可作为策略的数据源 |
| **Agent 信号策略** | **用户自己组合 3 个 Tab 的信号 + 额外条件**，沉淀为可复用策略 |

---

## 4. Trade Strategy Builder（自定义交易策略）⭐ 核心

### 4.1 用户故事
> As 有风控意识的投资者, I want 定义触发后如何下单 + 止盈止损 + 仓位管理, so that 策略触发时自动执行（模拟盘默认，授权后可真金），不用手动操作。

### 4.2 功能需求

| 优先级 | 功能点 | 验收标准 |
|-------|-------|---------|
| 🔴 | 绑定信号策略 | 一条 Signal Strategy 可绑定一条 Trade Strategy |
| 🔴 | 入场金额设置 | 支持固定 USD 金额 / 账户百分比 |
| 🔴 | 止损设置 | 固定百分比（-20% ~ -5%）|
| 🔴 | 止盈设置 | 固定百分比（+10% ~ +500%）|
| 🔴 | 执行模式 | paper（默认）/ notify_only / auto（需授权）|
| 🔴 | 单笔金额上限 | 硬限 $500 真金 / $10000 模拟 |
| 🔴 | 同代币重复买入规则 | repeat（每次都买）/ unique（只买一次）|
| 🟠 | 分批止盈 | +50% 卖一半、+100% 全卖 |
| 🟠 | 追踪止损（Trailing Stop）| 高点回落 X% 止损 |
| 🟠 | ATR 动态止损 | 止损 = entry - k × ATR |
| 🟠 | 同链集中度限制 | 单链持仓上限（防all-in 一条链）|
| 🟡 | DCA（分批建仓）| 第 1 次 -10% 加仓一半 |
| 🟡 | 加仓规则 | 盈利时主动加仓 |
| ⚫ v1 | 跨链组合策略 | v2 |

### 4.3 执行模式说明

| 模式 | 触发行为 | 适用场景 |
|------|---------|---------|
| `paper` | 自动写入 `hot_sim_trades` 模拟盘 | 默认，新策略先验证 3-4 周 |
| `notify_only` | 只推送通知，不自动下单 | 用户要手动控制 |
| `auto` | **真金自动执行**（需授权）| 已验证 3+ 周 + 用户 HITL 授权 + 额度限制 |

### 4.4 真金自动执行授权三要素

- **额度上限**：单笔 / 日累计 / 月累计
- **时效**：授权 7 天 / 30 天 / 永久
- **白名单**：只对特定代币 / 链 / 策略有效
- **随时可撤**：UI 一键 kill switch

### 4.5 数据源（已有）

- ✅ `agent_strategies` 表（添加 trade_strategy 字段）
- ✅ `hot_sim_trades` 表（模拟盘记录）
- ✅ `HotSimTrader` + `PaperEngine`（现有代码）
- ✅ `DexRouter`（真金执行已有）

### 4.6 Tool 映射

- `T08 build_trade_strategy(signal_strategy_id, trade_params)` → 创建/更新交易策略
- `T15 execute_trade_strategy(strategy_id, token, amount)` → 触发执行
- `T16 request_trade_authorization(amount, duration, whitelist)` → HITL 授权流程

### 4.7 边界

- ❌ **不做杠杆**
- ❌ **不做合约 / 期货**
- ❌ **不做挂限价单**（DEX 现货 AMM 没有 order book）
- ❌ **单笔真金 > $500 必须用户当次 HITL 确认**（即使已授权）
- ⚠️ 所有真金执行触发 `15 Observability` 的完整 trace

### 4.8 与现有代码的关系

基本能力已有（`hot_sim_trader.py` / `dex_router.py`），需要：
- ⚠️ 把策略参数从"全局配置"改为"按用户 + 按策略"
- ⚠️ 加 HITL 授权流程 UI + API
- ⚠️ 加真金执行前的 dry-run 校验

---

## 5. Paper Trading（模拟盘）

### 5.1 用户故事
> As 谨慎投资者, I want 用虚拟资金跟踪策略表现, so that 30 天验证后再决定是否开真金。

### 5.2 功能需求

| 优先级 | 功能点 | 验收标准 |
|-------|-------|---------|
| 🔴 | 自动建仓 | 策略触发后自动写 `hot_sim_trades`（当前已有）|
| 🔴 | 实时 PnL | 价格更新时实时计算未实现盈亏 |
| 🔴 | 自动止盈止损 | 按 trade_strategy 配置自动平仓 |
| 🔴 | 归档周期 | 30 天后未闭仓自动归档（不占 active）|
| 🔴 | 胜率 / 盈亏比统计 | 按策略 / 来源分组展示 |
| 🟠 | 多组合 | 用户可同时跑 3-5 个策略组合 |
| 🟠 | 滑点模拟 | 模拟真实交易 1-3% 滑点 |
| 🟠 | Gas 模拟 | 按链扣除模拟 gas 费 |
| 🟡 | Shadow Mode | 不执行只记录"如果执行了会怎样" |

### 5.3 当前生产 baseline（来自 [00 Data Sources](./00-data-sources.md)）

| source | 胜率 | 盈亏比 | 单笔期望值 |
|--------|------|--------|-----------|
| hot repeat | 42% | 1.10:1 | **-1.74%** 🔴 |
| hot unique | 45% | 1.10:1 | -0.86% 🔴 |
| smart_money | 44% | 2.12:1 | **+4.37%** ✅ |
| pump | 无闭仓 | - | - |

### 5.4 真金切换硬条件

只有同时满足以下条件，才允许策略从 paper 切到 auto：
1. 该策略模拟盘 ≥ 30 天
2. 闭仓次数 ≥ 30 次
3. 单笔期望值 ≥ +1%
4. 最大回撤 < 30%
5. 用户明确 HITL 授权 + 额度

**任一不满足 → API 拒绝切换**。

### 5.5 Tool 映射

- `T09 run_paper_trade(trade_strategy_id, signal_context)` → 自动在策略触发时调用
- `T17 get_paper_performance(strategy_id, period)` → 查询策略表现

### 5.6 边界

- ❌ 不模拟跨链路由（DEX 路由复杂度高，v1 只模拟主 pair）
- ❌ 不模拟 MEV 夹击（v1 先忽略）
- ⚠️ 模拟价格必须用和真金一致的价格源（避免失真）

---

## 6. Backtest（策略回测）

### 6.1 用户故事
> As 策略设计者, I want 把策略在历史数据上跑一遍, so that 我知道它过去表现如何（不是只看未来模拟盘）。

### 6.2 功能需求

| 优先级 | 功能点 | 验收标准 |
|-------|-------|---------|
| 🔴 | 时间窗口选择 | 7 天 / 30 天 / 90 天 |
| 🔴 | 策略选择 | 选择用户自建的信号策略 + 交易策略 |
| 🔴 | 代币池 | 按链筛（SOL / ETH / BSC / Base / all）|
| 🔴 | 核心指标输出 | 胜率 / 盈亏比 / 单笔期望值 / 最大回撤 / Sharpe |
| 🔴 | 交易明细 | 每笔"入场-出场"的时间、价格、PnL |
| 🔴 | 可视化图表 | 权益曲线 + 每笔 PnL 散点图 |
| 🟠 | 参数扫描 | score 阈值从 50-80 扫，对比表现 |
| 🟠 | 对比模式 | 策略 A vs 策略 B vs 基准（持有 SOL）|
| 🟠 | 对比基准 | 自动加 "持有 SOL / ETH 不动"作为对照 |
| 🟡 | Walk-forward analysis | 滚动窗口验证，防过拟合 |
| 🟡 | 蒙特卡洛模拟 | 回测结果的置信区间 |

### 6.3 历史数据来源

| 数据 | 粒度 | 来源 | 已有 |
|------|------|------|------|
| 代币价格 K 线 | 1h | `token_snapshots` 表（已有）| ✅ 90 天 |
| 代币表现 | D1/D3/D7 best | `token_performance` 表 | ✅ 30 天 |
| 聪明钱交易历史 | 秒级 | `smart_money_txns` 表 | ✅ 14 天 |
| 热币历史 | 30s 快照 | `hot_coins` 快照归档 | ⚠️ 当前只有当前状态，需加归档 |

**v1 MVP 限制**：回测窗口最长 30 天（数据够），90 天窗口依赖数据归档改造。

### 6.4 Tool 映射

- `T10 run_backtest(strategy_id, period, chains, [compare_to])` → 同步返回结果
- 执行时间：<30s（不需要实时，可接受后台跑）

### 6.5 边界

- ❌ v1 不做 tick 级精确模拟（gas / 滑点用估算值）
- ❌ v1 不做 orderbook 回放
- ⚠️ 回测结果明确标注"历史不代表未来"
- ⚠️ 过拟合风险提示（若某策略回测胜率 > 80%，系统自动提示"疑似过拟合，建议 walk-forward 验证"）

### 6.6 与现有代码的关系

- ⚠️ `services/pump-scanner/agent/backtest.py` 有初步框架，需扩展
- ⚠️ 需补充历史数据归档机制

---

## 7. Review（策略复盘）

### 7.1 用户故事
> As 想持续进步的投资者, I want 每周看到我的策略表现 + Agent 基于我的数据给出的改进建议, so that 下周决策更聪明。

### 7.2 功能需求

| 优先级 | 功能点 | 验收标准 |
|-------|-------|---------|
| 🔴 | 日复盘 | 每日 23:55 UTC 生成，覆盖当日交易/触发 |
| 🔴 | 周复盘 | 每周日 23:55 UTC，覆盖过去 7 天 + 策略排名 |
| 🔴 | 核心指标 | 本周总交易数 / 胜率 / 总 PnL / 最佳交易 / 最差交易 |
| 🔴 | 策略维度排名 | 按策略分组，显示各策略胜率 / 盈亏比 |
| 🔴 | Agent insights | 基于数据的 Insight（"你周五的决策胜率偏低"、"策略 X 近期退化"）|
| 🔴 | 规则提议（写入 Semantic Memory）| Agent 提出 2-3 条建议，用户点"采纳"后写入个人规则库 |
| 🟠 | 月复盘 | 每月 1 日生成，含趋势分析 |
| 🟠 | 导出 PDF | 复盘可导出分享 |
| 🟡 | 同期行情基准对比 | "你本周 +8%，同期 SOL +3%，相对超额 +5%" |
| 🟡 | 同类用户对比 | 匿名排位（同资金档位中 top X%）|

### 7.3 数据源

- ✅ `hot_sim_trades` 表（交易记录）
- ✅ `agent_strategies` 表（策略元数据）
- ✅ Episodic Memory（决策记录）
- ⚠️ Reflection Log（需新建）
- ⚠️ Semantic Memory（需新建）

### 7.4 Tool 映射

- `T11 review_performance(user_id, period=daily/weekly/monthly)` → 生成复盘
- `T18 propose_rules(period=weekly)` → 从复盘中提炼规则建议
- `T19 approve_rule(rule_id)` → 用户采纳规则，写入 Semantic Memory

### 7.5 Agent insights 示例（要求具体，不空泛）

✅ **好的 insight**：
- "过去 7 天你在周五做了 4 笔交易，胜率 25%（其他日 55%），建议周五暂停交易"
- "策略 X 近 30 天胜率从 60% 降到 40%，疑似市场 regime 变化，建议重新回测"
- "你 3 次止盈位都设在 +50%，但模拟盘显示 60% 的 trade 达到 +80%。可考虑分批止盈"

❌ **坏的 insight**（空泛不可执行）：
- "继续努力！"
- "市场有风险，注意风控"
- "建议多关注链上数据"

### 7.6 边界

- ❌ 不做"投资建议报告"（合规风险，用 insights 而非 recommendations）
- ❌ 不包含其他用户的具体交易
- ⚠️ 规则提议必须用户主动采纳才生效（Agent 不自动写入 Semantic）

---

## 8. Cross-cutting Requirements（通用需求）

### 8.1 性能

| 场景 | P95 延迟目标 |
|------|-------------|
| 查询行情 | < 500ms |
| 生成 thesis（L2）| < 5s |
| 生成 thesis（L3 辩论）| < 15s |
| 策略触发到推送 | < 1s |
| 策略触发到模拟盘建仓 | < 2s |
| 复盘生成 | < 30s（后台可接受）|
| 回测 30 天 | < 30s |

### 8.2 可用性

- SLA：核心能力（query / analyze / strategy trigger）≥ 99.5%
- Kill Switch：1 键关闭所有真金执行，影响范围 < 10s

### 8.3 国际化

- v1：中文、英文（基于 Persona 分布）
- v2：日文、韩文

### 8.4 合规与风控

- 所有 thesis 底部必带免责声明（"此为分析工具产出，不构成投资建议"）
- CN IP + 钱包双重检测 → 限制真金执行
- 用户行为审计日志保留 ≥ 180 天（合规诉求）

### 8.5 隐私

- 用户的策略、交易数据不对其他用户可见
- 用户数据可导出、可删除（GDPR-like）
- LLM 调用不直接传用户身份 ID（用 hash）

### 8.6 可观测性

引用 [15 Observability Spec](./15-observability-tracing.md)：所有 tool 调用必有 trace。

---

## 9. Out of Scope（v1 明确不做）

- ⚫ Agent 主动推送官方信号（APP 其他 Tab 已做）
- ⚫ 社交复制交易（social copy）
- ⚫ 多账户 / 子账户
- ⚫ Agent 代表用户与其他 on-chain agent 交互（v3 愿景）
- ⚫ 合约 / 期货 / 杠杆
- ⚫ CEX 交易
- ⚫ NFT / GameFi / DeFi LP
- ⚫ 税务报告
- ⚫ 自动升级策略（参数自动优化，Agent 先只给提议）
- ⚫ 自然语言回测（"帮我回测聪明钱跟单策略" - 需 build + run 分两步）

---

## 10. Dependencies & Risks

### 10.1 关键外部依赖

| 依赖 | 用途 | 风险等级 | 兜底方案 |
|------|------|---------|---------|
| Anthropic API | 分析师 / 辩论 / 决策 / 复盘 | 🔴 高 | 降级到规则引擎 + 历史 thesis |
| OpenAI API | 部分备用 | 🟠 中 | 同上 |
| Jupiter / 1inch | DEX 路由 | 🔴 高 | 失败降级 OKX DEX |
| Helius（SOL） | 实时 txns | 🟠 中 | 免费额度已紧张，需付费升级 |
| DexScreener | 行情 | 🟡 低 | 多源（GeckoTerminal）备份 |
| GoPlus | 安全检测 | 🟠 中 | 无兜底，失败直接标"未知风险" |

### 10.2 已识别风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| Hot 策略期望值为负（-1.74%）| 产品核心能力亏钱 | v1 前必须修复，否则 Hot 不上线真金 |
| LLM 成本失控 | 免费模式烧钱 | 严格执行 [13 Cost Budget](./13-cost-budget.md) |
| 用户混淆"官方信号 vs 我的策略" | 信任崩塌 | 所有 Agent 推送必标注"你的策略 X 触发" |
| 模拟盘过拟合 | 真金上线后不符预期 | 强制 30 天 + 30 笔最小闭仓 |
| Prompt Injection | 用户输入代币名带恶意指令 | [14 Red Team Playbook](./14-red-team-playbook.md)覆盖 |
| 监管 | AI 给投资建议可能在某些地区违法 | CN / 某些州屏蔽 |

### 10.3 技术债（继承自现有代码）

| 项 | 影响 | 计划 |
|---|------|------|
| prompt → regex parse（非 tool-use 协议）| 脆弱、难迭代 | v1 迁移至 Anthropic tool-use |
| 无 prompt eval 套件 | 改 prompt 后无数据反馈 | [09 Eval Plan](./09-eval-plan.md)落地 |
| Memory 只在进程内内存 | 重启丢规则 | v1 接 Redis / DB |
| 无 HITL 队列 | 大额只能 block 不能 pending | v1 新建 `pending_approvals` 表 |

---

## 11. 验收总 Gate（上线前必达）

引用 [11 Launch Criteria](./11-launch-criteria-hitl.md)，本 PRD 相关硬门槛：

- ✅ 6 大能力全部 MUST 项验收通过
- ✅ 每能力对应 tool 有 golden dataset（≥ 50 案例）
- ✅ 策略质量红线不触发（Hot 期望值转正）
- ✅ Safety Policy 100% 覆盖
- ✅ Incident SOP 就绪
- ✅ 首批 20 种子用户 1 周试用无 SEV-1/SEV-2 事故

---

## Change Log

- **v0.1 (2026-04-23)**：首版完整填充
  - 6 大能力按 MoSCoW 展开功能需求
  - 每能力对应 tool 映射（T01-T19）
  - 明确与 APP 其他 Tab + 现有代码的关系
  - 引用真实生产 baseline（Hot 期望值 -1.74% 作为 v1 必修项）
  - Cross-cutting 性能/合规/可观测要求
  - Out of Scope 10 项 + Risks 清单 + 技术债清单
- v0（2026-04-22）：骨架创建
