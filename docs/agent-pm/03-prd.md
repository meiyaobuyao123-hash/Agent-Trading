# 03 PRD（总）

> 按 **6 大核心能力**组织的 v1 MVP 需求。每个能力明确 tool 映射、数据源、验收标准、与现有代码的关系。

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.4 Draft |
| Version | v0.4 |
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

### 0.5 Persona 差异化（本 PRD 全局适用）

本 PRD 6 大能力默认服务 **中级用户（老王）**（见 [02 Persona](./02-user-persona-journey.md#3-中级-老王--核心用户)）。对小白 / 专业用户的差异化，在每章"X.N Persona 差异化"小节具体写。

| Persona | 占比假设 | 默认能力可见性 | UI 侧调整 |
|---------|---------|---------------|----------|
| **小白 小陈**（$200-5K）| 🟡 30% | C1-C3 + C5 + C7（禁 auto 执行）| 模板库优先；不显示 ATR / Sharpe；thesis 白话；默认 paper 模式 |
| **中级 老王**（$5K-50K）⭐ | 🟡 50% | 全量 C1-C7 | 默认视图；`notify_only` 为首选模式 |
| **专业 阿强**（$50K+）| 🟡 20% | 全量 + 高阶（批量分析 / walk-forward）| 显示技术参数；支持策略 JSON 导入导出；auto 模式优先 |

**Persona 识别方式（v1）**：
- 默认按中级视图
- 首启引导 3 问识别（资金规模 / 交易年限 / 自我定位）→ 写入本地 `user_profile` 表
- 用户可随时切换视图（Profile → 模式切换）
- 不做后台自动识别（隐私 + 准确性差）

### 0.6 Identity Model（身份模型 · 无注册账户）

> ⚠️ **关键产品决策**：本产品**没有注册账户能力，也不需要**。

| 身份类型 | 生成时机 | 用途 | 存储 |
|---------|---------|------|------|
| **device_id** | APP 首次启动生成 UUID | 默认主身份；策略/记忆/模拟盘/复盘所有权 | 本地 Keychain / SharedPreferences + 服务端 `devices` 表 |
| **wallet_address** | 用户主动 connect wallet | 真金交易**必需**；跨设备同步（同钱包下数据可迁移）| 本地 + 服务端关联 device_id |
| **session_id** | 每次 Chat 前端生成 | Chat 会话隔离 | 本地 + trace 日志 |

**关键规则**：
1. ❌ **无注册、无登录、无密码、无邮箱、无手机号**
2. ❌ **无"账号注销"概念**——用户卸载 APP 即失去本地 device_id；服务端数据依据下文保留策略清理
3. ✅ 所有策略 / 记忆 / 模拟盘记录**绑定 device_id**（可选绑定 wallet_address）
4. ✅ 真金操作：**必须 wallet connect + 签名授权**（无 wallet 则禁所有真金能力）
5. ✅ **跨设备同步**（可选）：用户可在新设备 connect 同一 wallet，按 wallet_address 拉取策略 / 记忆。**非强制**，不绑定新设备也能用
6. ✅ **数据所有权迁移**：APP 内可"导出本地数据 → 签 wallet → 上传绑定 wallet"，用于换机 / 多设备

**身份相关的数据保留**（见 [10 Data Privacy](./10-data-privacy-sheet.md) 待写）：
- device_id 30 天无活跃 → 标记 `inactive`（策略自动 pause，保留数据）
- device_id 180 天无活跃 + 未绑定 wallet → 清理关联策略 / 记忆 / 模拟盘
- wallet 绑定的数据 → 永久保留（用户可从 APP 内发起删除请求）
- 用户主动删除 → 7 天冷却期可恢复，之后永久删除

**引用位置**：§ 0.6 → [04 Agent Spec § 3.1](./04-agent-spec.md#31-对外-apiagent-接口)（API 鉴权方式）

### 0.7 核心数据源优先级（本 PRD 全局适用）

> 所有 Tool 的数据源栏必须按这份优先级填。轮询式 API 永远是**兜底**，不是主源。详见 [00 Data Sources § 1.6](./00-data-sources.md#16-dex-程序级事件流--核心实时源)。

| 等级 | 源 | 用途 | 延迟 |
|------|----|------|------|
| **P0（主源）** | **DEX 程序级事件流**（Helius WS / EVM RPC WS / pumpportal WS）| 实时成交 / 聪明钱 / Pump 早期 / 信号 evaluate 触发 | **SOL ~400ms / EVM 2-12s / Pump <1s** |
| **P0（主源）** | 落表的事件结果（`smart_money_txns` / `pump_tokens` / `token_trades` / `token_snapshots`）| 历史查询 / 信号条件引用 | 实时 |
| **P1（补充）** | `hot_coins` 聚合表 | 榜单 / 筛选 / 列表页 | 实时更新 |
| **P2（兜底 / 深度）** | OKX DEX API / Jupiter Aggregator | 交易执行 quote / 池子深度 / 滑点 | 秒级 |
| **P2（补充）** | GeckoTerminal API | 历史 K 线 / 代币元信息 | 秒级 |
| **P2（补充）** | DexScreener / GoPlus / Helius enhanced TX | 价格校验 / 安全检测 / Holder 分布 | 秒级 |

**原则**：
- ✅ 实时性优先用 **P0 事件流**；查询、深度、历史、执行报价用 **P2 API**
- ✅ P0 降级时（Helius 429 / RPC 断连）自动切 P2，**但产品必须显性降级提示**（UI 标"延迟模式"）
- ❌ 不允许 Tool 默认用 P2 轮询当主源（这是"假实时"，严禁）

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

### 1.3 数据源（按 § 0.7 优先级）

| 数据 | P0 主源 | P2 兜底 / 补充 | 说明 |
|------|---------|--------------|------|
| 当前价格 / 实时成交 | **DEX 事件流**（`smart_money_txns` + `token_snapshots` 实时聚合）| DexScreener | 事件流给秒内最新价，API 兜底 |
| MC / 24h 涨幅 / LP | `hot_coins` 表（P1，聚合表，事件流驱动更新）| OKX DEX / Gecko | 聚合层读 |
| 风险标记 | `hot_coins.goplus_risk` | GoPlus API | 独立源，事件流无法替代 |
| Holder 分布 | `hot_coin_top_holders` 表 | Helius enhanced TX / OKX | 当前 DEX 事件只订 Swap，holder 变化需独立源 |
| K 线 | GeckoTerminal API | DexScreener | **历史数据不用 WS**，这是 API 的强项 |
| 交易执行 quote / 滑点 | **OKX DEX / Jupiter**（P2 是主）| - | 现货报价必须用 aggregator |
| 社交数据 | LunarCrush | Twitter API | 🟡 数据不充分 |

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

### 1.7 失败场景与降级 UI（负面验收）

| 场景 | 触发条件 | UI 表现 | 文案示例 | 可重试 |
|------|---------|--------|---------|--------|
| 代币未被索引 | address 在 4 链均无匹配 | 返回 "未找到" + 提示用户核对地址 / 手动添加 | "未找到该代币。请确认合约地址正确，或该代币尚未进入我们的索引。"| 是（搜索） |
| 代币过新（< 1h）| `first_trade_at` 距现在 < 1h | 展示基础信息 + 灰框"数据尚不充分" | "⚠️ 该代币创建不足 1 小时，数据尚不充分，建议观察更久后再分析。"| 等待 |
| GoPlus 接口失败 | 503 / 超时 | 展示行情 + 风险标记区域显示"风险数据不可用" | "⚠️ 风险检测暂不可用，请谨慎判断。"| 后台自动重试 |
| Helius WS 断连（P0 降级）| heartbeat 超时 | 顶栏红标"🔴 延迟模式：数据可能延迟 30-60s" | 同左 | 自动尝试重连 |
| Holder 数据滞后 | 最近更新 > 1h | 卡片角标 "数据 X 分钟前" | - | 手动刷新 |
| 查询频率超限（用户）| > 60 次 / min | 429 + UI 禁用查询按钮 10s | "查询过于频繁，请稍后再试。"| 冷却 10s |
| 查询超时（> 3s）| 后端慢 | 骨架屏保持 3s → 降级展示缓存数据 + 角标"缓存" | "⚠️ 网络较慢，显示的是 X 秒前的数据。"| 手动刷新 |
| 跨链地址错误 | 用户输入 ETH 地址选了 SOL chain | 返回友好错误 + 自动建议正确链 | "这个地址看起来是 ETH 链地址，要切换到 ETH 链查询吗？"| 是 |

### 1.8 Success Metrics

| 指标 | 目标（v1）| 测量方式 | 失败下线条件 |
|------|----------|---------|------------|
| Chat 查行情 / DAU | ≥ 30% | Chat 中调用 T01 的独立设备数 / DAU | < 10% 持续 14 天 → 重做入口 |
| 查询后 60 min 内建策略转化率 | ≥ 8% | 查询 → 建信号策略漏斗 | < 3% → UX 重审 |
| 查询失败率（网络 + 后端）| < 2% | error log / 总请求 | > 5% 持续 3 天 → 告警 |
| P95 延迟 | < 500ms | 服务端 trace | > 1s 持续 1h → 告警 |
| 用户满意度（5 星评分）| ≥ 4.0 | 查询后的可选反馈 | < 3.5 → UX 重审 |

### 1.9 Persona 差异化

| Persona | 查询入口 | 默认展示 | 隐藏字段 |
|---------|---------|---------|---------|
| 小白 | Chat 自然语言为主 | 价格 + 涨跌 + 一句风险描述 | ATR / RSI / Sharpe / dev 钱包明细 |
| 中级 | Chat + 代币详情页 | 全量行情 + 风险卡 + 聪明钱动向 | walk-forward 指标 |
| 专业 | Chat + API（v2 考虑开放）| 全量 + 技术参数 + 原始链上数据 | - |

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

| 维度 | 数据源（P0 主 / P2 补）| 分析要点 |
|------|----------------------|---------|
| **技术面** | P2: GeckoTerminal K 线 / 本地计算 RSI/MA/ATR/支撑阻力 | 趋势 + 入场区 + 止损位 |
| **链上面** | **P0: DEX 事件流**（`smart_money_txns` 实时聚合买卖力量 / 流动性变化）+ P2: holder 独立源 | 主力方向 + 流动性健康度 |
| **情绪面** | P1: 社交提及 / KOL 喊单（`kol_signals`）+ 恐贪指数 API | FOMO 还是 fear |
| **风险面** | P2: GoPlus / `hot_coin_top_holders` / 代币年龄（来自 DEX 事件流的 first_trade_at）/ dev 钱包 | rugpull 概率 + 集中度风险 |

> **链上面必须用 P0 事件流聚合**，不许用 P2 API 轮询伪装（否则 thesis 里"最近 5 分钟聪明钱净买入"这种结论根本不成立）。

### 2.4 Tool 映射

> **模型策略（v1 质量优先）**：L2 / L3 全链用 **Claude Opus**。详见 [§ 8.8](#880-模型分层决策v1-采用质量优先方案)。

- `T04 analyze_technical(address, timeframes)` → 技术面分析（Opus，P95 < 4s）
- `T05 analyze_sentiment(address, period=24h)` → 情绪面分析（Opus，P95 < 4s）
- `T06 analyze_onchain(address)` → 链上面分析（Opus，P95 < 4s）
- `T12 recall_memory(situation)` → 历史类似案例检索（<500ms，无 LLM）
- **组合调用**：`analyze_token(address) = parallel(T04, T05, T06) + T12 → thesis_writer(Opus) prompt`

### 2.5 边界

- ❌ **不给"保证盈利"话术**（Vision Non-goal）
- ❌ **不诱导用户交易**（不写"错过就亏了"式话术）
- ⚠️ 低置信度必须显性标注，不伪装确信
- ⚠️ 数据不足（例如代币 <1h 新上线）时明确拒绝分析，引导用户等

### 2.6 与现有代码的关系

- ✅ `services/pump-scanner/agent/` 已有 analyst / debate / decision_agent
- ⚠️ 当前是 prompt 直接 call，需改造为 tool-use 协议（见 04 Agent Spec）
- ⚠️ `recall_memory` 不存在，需新建

### 2.7 Thesis 完整 Schema

```json
{
  "thesis_id": "uuid",
  "token": { "chain": "solana", "address": "...", "symbol": "TRUMP" },
  "generated_at": "2026-04-24T10:00:00Z",
  "level": "L2 | L3",                   // 分级，见 04 Agent Spec § 5
  "direction": "long | short | hold | avoid",
  "entry_zone": { "low_usd": 1.10, "high_usd": 1.25 },
  "stop_loss": { "price_usd": 0.95, "pct": -15.0 },
  "target": [
    { "price_usd": 1.80, "pct": 50, "description": "第一目标" },
    { "price_usd": 2.40, "pct": 100, "description": "第二目标" }
  ],
  "conviction": 0.72,                   // 0-1，< 0.6 UI 标"低置信度"
  "risks": [                            // 至少 2 条
    { "type": "liquidity", "severity": "medium", "description": "LP 仅 $80K，大额易滑点" },
    { "type": "concentration", "severity": "high", "description": "Top10 持有 68%" }
  ],
  "summary_30w": "30 字内纯中文摘要，供 push 用",
  "evidence": [                         // 必须引用具体数据
    { "source": "smart_money_txns", "detail": "过去 2h 3 个 elite 钱包净买入 $45K" },
    { "source": "token_snapshots", "detail": "BC 进度 15%，独立买家 42" }
  ],
  "similar_past_cases": [               // 来自 T12 recall_memory，1-3 条
    { "token": "PEPE", "date": "2024-05-10", "outcome": "+120% in 7d", "similarity": 0.78 }
  ],
  "used_tools": ["T04", "T05", "T06", "T12"],
  "trace_id": "uuid",
  "cost_usd": 0.015,
  "latency_ms": 4230,
  "disclaimer": "此为分析工具产出，不构成投资建议。",
  "regime_at_generation": "BULL | SIDEWAYS | CRISIS"
}
```

**字段硬约束**：
- `direction = avoid` 时，`entry_zone / stop_loss / target` 可为空
- `conviction < 0.5` 时，`direction` 必须为 `hold` 或 `avoid`
- `risks` 数组长度 ≥ 2（Vision 原则"用户看到具体风险"）
- `evidence` 必须引用真实数据源（不允许编造）
- `similar_past_cases` 为空（冷启动场景）→ UI 显示"暂无历史类似案例"

### 2.8 失败场景与降级 UI

| 场景 | 触发条件 | UI 表现 | 文案 | 降级行为 |
|------|---------|--------|------|---------|
| 数据不足（代币 <1h）| 预检查失败 | 不启动 LLM，返回引导 | "该代币数据尚不充分，建议 ≥ 1h 后再分析。"| 无 |
| 单分析师失败 | T04/T05/T06 任一异常 | 返回 thesis 但标注"X 面分析不可用" | "⚠️ 技术面数据暂不可用"| 其他 3 面继续 |
| LLM 超时（> 10s）| timeout | 返回低置信度默认 thesis | "⚠️ 分析超时，结果仅供参考，conviction 0.3 hold"| L3 → L2 / L2 → 直接默认 |
| Memory 读不到类似案例 | `similar_past_cases = []` | 正常返回但 UI 提示"暂无历史参考" | - | 继续 |
| Conviction < 0.6 | confidence 低 | UI 红框 + 图标 "⚠️ 低置信度" | "数据分歧较大，建议观察或等待"| 继续 |
| 成本预算紧 | 日预算 > 80% | L3 自动降级 L2 | UI 显示"🟡 分析降级" | L2 流程 |
| GoPlus 返回 honeypot | 风险面高危 | 直接拒绝分析，仅返回 risks | "⚠️ 该代币检测到蜜罐风险，不予分析"| 跳过所有分析 |
| 用户连续请求同代币 10 min | rate limit | 返回缓存 thesis | "这是 X 分钟前的分析结果，如需刷新请等待冷却。"| 冷却 10min |

### 2.9 Success Metrics

| 指标 | 目标（v1）| 测量方式 | 失败下线条件 |
|------|----------|---------|------------|
| Thesis 采纳率（点"有用"按钮）| ≥ 40% | 反馈按钮 / 生成总数 | < 20% 持续 14 天 |
| Thesis → 建策略转化率 | ≥ 15% | thesis 查看后 60min 内建策略 | < 5% |
| Thesis 错误引用率（人工抽检）| < 5% | 每周抽 20 条 thesis 核对 evidence | > 10% → prompt 修正 |
| 低置信度标注率 | 20-40% | conviction < 0.6 的比例 | > 50% 说明 agent 没自信 / 数据质量差 |
| P95 延迟 L2（Opus）| < 6s | trace | > 10s |
| P95 延迟 L3（全 Opus 辩论）| < 18s | trace | > 25s |
| 单 thesis 平均成本 | L2 ~$0.025 / L3 ~$0.35 | trace 聚合 | 翻倍告警 |

### 2.10 Persona 差异化

| Persona | thesis 语气 | 字段可见性 | 默认分析级别 |
|---------|-----------|----------|------------|
| 小白 | 白话 + 类比（"像去年的 XX 代币"）| 隐藏 entry_zone 的数字区间，改为"现价附近" | L2 |
| 中级 | 术语 + 数据 | 全量 | L2（大额自动升 L3）|
| 专业 | 技术参数 + evidence 原始数据 | 全量 + evidence 附详情 | L3 默认（可手动选 L2）|

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
| 🔴 | **共创式建策略（Co-creation，核心）** | Agent 与用户多轮对话，引导出条件、试算、预览，达成一致后保存。详见 § 3.2.1 |
| 🔴 | 自然语言建策略 | 用户输入"聪明钱 2+ 买入 + LP > $100K"，Agent 转换为结构化条件树。转换失败率 < 10% |
| 🔴 | 规则式建策略 | UI 提供条件树编辑器（AND/OR 嵌套，数据源下拉）|
| 🔴 | 策略 CRUD（增 / 查 / 改 / 删 / 暂停 / 启用）| 改完立即生效（无需重启）|
| 🔴 | 触发时通知 | 条件满足时 APP 内推 + 可选 push 通知，<1s 延迟 |
| 🔴 | 数据源支持 | 至少支持：hot_coins / smart_money_signals / token_snapshots / kol_signals |
| 🔴 | 触发去重 | 同代币同策略 30min 内不重复触发 |
| 🔴 | 冷却机制 | 每条策略可配置 cooldown（默认 5min）|
| 🟠 | 策略模板库 | 提供 5-10 条"热门模板"供快速创建 |
| 🟠 | 策略版本历史 | 每次修改保存 diff，可回滚 |
| 🟠 | 策略统计 | 显示最近 7/30 天触发次数 + 命中率 |
| 🟡 | 策略分享链接 | 生成可分享 URL（别人可复制到自己账号）|
| ⚫ v1 | 社区策略市场 | v2 再做 |

### 3.2.1 共创流程（Co-creation Flow）⭐

> **核心交互模型**：用户和 Agent **不是一问一答**，而是**多轮对话共同打磨出策略**，最终确认后才写入策略列表运行。

**完整 7 阶段流程**：

```
① 用户 → 描述意图（Chat）
   "我想做一个跟聪明钱的策略"
   or "我昨天看的那个 PEPE 很好，想做类似的"
   or 从模板库点"聪明钱跟单"进入
           ↓
② Agent → 澄清提问（多轮）
   • "你想跟哪一类聪明钱？elite / verified / watching？"
   • "最少几个钱包买入才算有效信号？"
   • "对链、流动性下限、代币年龄有要求吗？"
   • "预算多少、希望多久触发一次？"
   （用户的历史偏好 + Episodic Memory 会用来预填建议值）
           ↓
③ Agent → 生成策略 Draft
   { name, conditions: AND(...), filters, cooldown, limits }
   以 JSON preview + 人话翻译展示
           ↓
④ Agent → 历史表现预估（Dry Run）⭐
   "这个策略在过去 30 天会触发 X 次，胜率 Y%，EV Z%"
   （调用 T10 回测静默跑，给参考）
           ↓
⑤ 用户 → 调整 / 反馈
   • "触发太频繁，把冷却改成 1 小时"
   • "加上排除已归零代币的条件"
   • "不要 ETH 链"
   → Agent 更新 Draft（回到 ③）
           ↓
⑥ 用户 → 最终确认
   • 点"保存"按钮
   • 或对话中说"就这样，保存"
           ↓
⑦ 系统 → 写入策略列表 + 激活
   • 写入 agent_strategies 表 (status=active)
   • 立即订阅对应事件，开始 evaluate
   • 返回策略 ID 给用户
   • 推送 "策略 X 已激活，等待第一次触发"
```

**关键产品原则**：

| 原则 | 落地 |
|------|------|
| **Agent 先澄清再生成** | 不接受"给我建个策略"就直接生成——必须多轮对话降歧义 |
| **每步可见** | 每次用户反馈后，Agent 展示**更新后的完整 Draft**（不只 diff）|
| **默认带历史预估** | 第 ④ 步 dry run 是强制的，不让用户"盲建策略" |
| **不允许静默激活** | 必须用户明确 "保存" / "确认"，不会对话里说"好的"就自动激活 |
| **中断可恢复** | 对话中断（关 APP）可恢复到 ③ 的 Draft，不丢进度 |

**状态模型**：

| 阶段 | 策略 status | 对话状态 |
|------|-----------|---------|
| ① - ③ | `draft`（未保存）| `clarifying` |
| ④ - ⑤ | `draft` | `refining`（用户反馈中）|
| ⑥ | `draft` → `active` | `confirming` |
| ⑦ | `active` | `closed`（会话关闭，策略独立运行）|

**反例**（严禁）：

```
用户：帮我建个追涨策略
Agent：好的，已为你创建策略 "追涨 v1"，条件为 24h涨幅>50%。←  ❌ 未澄清、未预估、未确认
```

**正例**：

```
用户：帮我建个追涨策略
Agent：OK。先问几个问题帮你打磨：
       1. 追多大涨幅？（常见 30% / 50% / 100%）
       2. 时间窗口 1h / 24h / 7d？
       3. 有流动性底线要求吗？（避免小池子）
       4. 链的偏好？
用户：24h 涨 50%，LP 至少 $200K，就 SOL
Agent：明白。初稿如下：
       { name: "SOL 追涨", conditions: AND(
         chain==solana, 24h_change_pct>=50, liquidity_usd>=200000
       ), cooldown: 30min }
       📊 过去 30 天会触发 42 次，模拟胜率 38%，EV -1.2%。
          ⚠️ 负期望值，建议收紧条件（如加 Top10 持仓 < 70%）。
用户：加上 Top10 < 70%，再跑一次
Agent：[更新后] ... 触发 18 次，胜率 48%，EV +3.5%。好多了。
用户：这样挺好，保存
Agent：✅ 策略 "SOL 追涨" 已激活，等待第一次触发。
```

### 3.2.2 共创流程的 Tool 调用链

```
对话 → Chat API (使用 T07 build_signal_strategy)
  ├─ 澄清阶段：普通 LLM 调用（不调用 tool）
  ├─ 生成 Draft：T07 tool_use 生成结构化 JSON
  ├─ Dry Run：T10 run_backtest（静默 7-30 天）
  ├─ 反馈迭代：T07 tool_use 更新 Draft（同一个 conversation，不新建）
  └─ 最终激活：T07 持久化（status: draft → active）
```

**成本估算**（共创流程单次完成）：
- 平均 4-6 轮对话 × 每轮 LLM 调用
- 1 次 dry run（无 LLM 成本，纯计算）
- 单次完成成本 ~$0.04-$0.08（按 § 8.8 新模型）

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

### 3.4 数据源与触发通道

**策略持久层**：
- ✅ `agent_strategies` 表已有结构
- ✅ `StrategyEvaluator` + `RuleEngine`（`services/pump-scanner/agent/evaluator.py`）

**触发通道（必须全部是 P0 事件驱动，不是轮询）**：

| 数据源 | P0 事件通道 | 事件语义 |
|-------|------------|---------|
| `smart_money_signals` | `smart_money_txns` 新插入（DEX swap 解析后写入）| 聪明钱买 / 卖 |
| `hot_coins` 条件 | HotCoinManager 在 PriceFeed 回调里重算 score → 状态变更事件 | 进榜 / 涨幅突破 / 流动性变化 |
| `token_snapshots`（pump）| `token_trades` 1min 聚合写入 | BC 进度变化 / 独立买家增长 |
| `kol_signals` | KOL 抓取器 15min 轮询（P1，不是 P0）| KOL 喊单 |

**评估引擎**（关键架构决策）：
- ✅ **Event-Driven**：`EventListener` 订阅 EventBus，毫秒级触发策略 evaluate（现有 `event_listener.py`）
- ❌ **禁止 30s 轮询全表**（旧实现，已废弃，v1 不接受）
- ⚠️ KOL 类 P1 数据允许定时批量评估（不是 hot path）

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

### 3.8 生命周期与一致性（Lifecycle & Consistency）

**策略 status 与 lifecycle**：

| status | 含义 | 允许的动作 | 已触发仓位处理 |
|--------|------|----------|-------------|
| `draft` | 创建中（未保存）| 编辑 | - |
| `active` | 运行中 | pause / edit / delete | - |
| `paused` | 暂停（不触发新信号）| resume / edit / delete | 已开仓位继续按 trade_strategy 监控 |
| `archived` | 归档（用户删除）| 无（只能查看历史）| **已开仓位继续监控到闭仓**（止盈/止损/手动平仓）|
| `inactive` | device 30d 未活跃自动设置 | 系统自动 resume | 仓位保留 |

**关键一致性规则**：
1. **策略编辑**：修改条件树 / 冷却 / 过滤器 → 立即生效于**新信号评估**；**不影响已触发仓位**
2. **策略版本化**：每次编辑生成新 version（v1/v2/v3 ...），已触发仓位记录 `triggered_by_version`，避免后续混淆
3. **策略删除（软删）**：`status=archived`，**已开仓位不强平**，继续监控到闭仓；用户可在"历史策略"里看最终结果
4. **策略绑定变更**：解除 signal_strategy ↔ trade_strategy 绑定 → 新信号不再触发交易，旧仓位不受影响
5. **Device 失活**：device 30d 未活跃 → 所有策略 `inactive`，恢复活跃后自动 `resume`
6. **Device 删除（用户主动）**：7d 冷却期，之后永久删除策略 + 记忆；已开仓位要求用户先手动平仓或转移到 wallet 绑定下
7. **Wallet 切换**：同 device 换绑 wallet → 策略保留（按 device_id）；已开仓位属 old wallet，新 wallet 需重新授权才可继续

**不允许的转移**：
- `archived` → `active`（必须 fork 为新策略，避免用户误操作）
- `inactive` → `archived`（需先 resume）

### 3.9 失败场景与降级 UI

| 场景 | 触发条件 | UI 表现 | 文案 | 降级行为 |
|------|---------|--------|------|---------|
| NL 转换失败 | LLM 解析失败 / Schema 校验失败 | 返回部分解析 + 提示补全 | "没完全看懂，这是我猜的条件，请核对："| 用户手动修正 |
| 条件矛盾 | e.g. score>50 AND score<30 | 保存前阻止 | "条件互相矛盾，请检查"| 拒绝保存 |
| 策略数超上限（20）| count ≥ 20 | 禁用新建按钮 | "最多 20 条策略，请删除旧的再建"| - |
| 触发频率超限 | 日触发 > 100 | 自动 pause + 通知 | "策略触发过于频繁，已暂停。请调整条件或冷却"| 暂停 |
| 数据源字段无效 | field 在 schema 里不存在 | 保存前阻止 | "字段 X 不支持，可用字段：..."| 拒绝保存 |
| EventBus 积压 | queue > 80% | 标记为"数据延迟"但不丢失 | "数据处理较慢，可能延迟 10-30s"| 继续 |
| 触发但下游 notify 失败 | push 推送失败 | 内推仍写入，外部 push 重试 3 次 | - | 3 次失败后静默告警 |

### 3.10 Success Metrics

| 指标 | 目标（v1）| 测量方式 | 失败下线条件 |
|------|----------|---------|------------|
| 建策略的 DAU 比例 | ≥ 20% | 建策略独立 device / DAU | < 5% → UX 重审 |
| 平均策略存活天数 | ≥ 14 天 | 创建到 archived | < 5 天 → 策略无价值 |
| 每设备平均活跃策略数 | 3-8 条 | count(active) / device | > 15 → 过载；< 1 → 无粘性 |
| 策略触发命中率（30 天 paper 胜率）| ≥ 45% | paper trade 胜率 | 中位数 < 40% 说明策略质量差 |
| NL 转换成功率 | ≥ 90% | 转换成功 / 总尝试 | < 80% → 需优化 prompt |
| 模板策略使用率 | ≥ 40% 策略来自模板 | 模板 / 总策略 | 太高说明 UI 差；太低说明模板没用 |

### 3.11 Persona 差异化

| Persona | 建策略方式 | 模板可见 | 上限 |
|---------|----------|---------|-----|
| 小白 | **模板库优先**（自然语言编辑参数）| 全量 + "新手推荐"标签 | 5 条 |
| 中级 | 模板 + 条件树编辑器 | 全量 | 20 条 |
| 专业 | 条件树 + JSON 导入 / 导出 | 全量 + "高级参数"展开 | 20 条（v2 可申请扩容）|

---

## 4. Trade Strategy Builder（自定义交易策略）⭐ 核心

### 4.1 用户故事
> As 有风控意识的投资者, I want 定义触发后如何下单 + 止盈止损 + 仓位管理, so that 策略触发时自动执行（模拟盘默认，授权后可真金），不用手动操作。

### 4.2 功能需求

| 优先级 | 功能点 | 验收标准 |
|-------|-------|---------|
| 🔴 | 绑定信号策略 | 一条 Signal Strategy 可绑定一条 Trade Strategy |
| 🔴 | 入场金额设置 | 支持 **固定 USD** / **仓位百分比**（定义见 § 4.2.1）|
| 🔴 | 止损设置 | 固定百分比（-20% ~ -5%）|
| 🔴 | 止盈设置 | 固定百分比（+10% ~ +500%）|
| 🔴 | 执行模式 | paper（默认）/ notify_only / auto（需授权）|
| 🔴 | 单笔金额上限 | **硬限**：真金单笔 **$500** 上限 / 日累计 **$2000** / 月累计 **$20000**；模拟 **$10000** 单笔 |
| 🔴 | 同代币重复买入规则 | repeat（每次都买）/ unique（只买一次）|
| 🔴 | **余额不足降级** | 见 § 4.2.2，不允许静默跳过 |
| 🟠 | 分批止盈 | +50% 卖一半、+100% 全卖 |
| 🟠 | 追踪止损（Trailing Stop）| 高点回落 X% 止损 |
| 🟠 | ATR 动态止损 | 止损 = entry - k × ATR |
| 🟠 | 同链集中度限制 | 单链持仓上限（防 all-in 一条链）|
| 🟡 | DCA（分批建仓）| 第 1 次 -10% 加仓一半 |
| 🟡 | 加仓规则 | 盈利时主动加仓 |
| ⚫ v1 | 跨链组合策略 | v2 |

### 4.2.1 "仓位百分比" 的权威定义（Account Model）

> ⚠️ 历史歧义最大的点，必须写死。

| 执行模式 | "100% 仓位" 定义 | 读取方式 | 更新频率 |
|---------|----------------|---------|---------|
| `paper` | **虚拟账户余额**（初始 $10000，按模拟交易 PnL 累加） | `paper_accounts` 表 | 每次 paper trade 闭仓更新 |
| `notify_only` | 不涉及资金，无余额概念；百分比按 `paper` 计算仅作展示 | 同上 | 同上 |
| `auto` | **绑定 wallet 的单链可用余额**（WSOL/WETH/USDC 合计）| 链上 RPC 实时读（缓存 30s）| 每次触发前 refresh |

**关键规则**：
1. **百分比 × 余额 = 下单额**，四舍五入到 USDC/USDT 0.01 单位
2. **auto 模式且余额 < $10**：视为余额不足，走 § 4.2.2 降级
3. **多链混合持仓**：百分比**仅算当前链**（"SOL 策略的 10% = SOL 钱包余额的 10%"），不跨链折算
4. **账户余额实时读取**：调用 P2 RPC（不阻塞事件路径，fail 则用 30s 缓存，再 fail 则降级）
5. **用户手动设置 baseline**（专业用户）：可在 Profile 写死 `virtual_balance_for_percentage_calc`，覆盖上述规则

### 4.2.2 余额不足 / 读取失败的降级规则

| 场景 | 行为 | 通知用户 |
|------|------|---------|
| auto 余额 < 策略配置金额 | **不部分下单**，写入 `skipped_trades` 表并推送 | "策略 X 触发，但钱包余额仅 $Y，低于策略配置 $Z，已跳过"|
| auto 余额读取失败（RPC down）| 用 30s 缓存；缓存也失败 → 降级为 `notify_only`（本次）| "⚠️ 网络异常，本次未执行，已通知你手动确认"|
| 余额够但低于所有硬限下限（如策略配 $600 > 硬限 $500）| 按硬限 $500 下单，通知用户 | "策略配置 $600，已按硬限 $500 执行"|
| paper 虚拟余额 < 策略配置 | 直接跳过（不扩容虚拟账户）| "模拟盘余额不足，已跳过。可在 Profile 重置模拟盘"|

### 4.3 执行模式说明

| 模式 | 触发行为 | 适用场景 |
|------|---------|---------|
| `paper` | 自动写入 `hot_sim_trades` 模拟盘 | 默认，新策略先验证 3-4 周 |
| `notify_only` | 只推送通知，不自动下单 | 用户要手动控制 |
| `auto` | **真金自动执行**（需授权）| 已验证 3+ 周 + 用户 HITL 授权 + 额度限制 |

### 4.4 真金授权与 HITL 完整流程

#### 4.4.1 授权三要素

- **额度上限**：单笔（≤ $500 硬顶）/ 日累计（≤ $2000）/ 月累计（≤ $20000）
- **时效**：授权 7 天 / 30 天 / 永久（永久默认 90 天 reconfirm）
- **白名单**：只对特定代币 / 链 / 策略有效
- **随时可撤**：UI 一键 kill switch，< 10s 全局生效

#### 4.4.2 HITL 触发条件（任一满足即入队）

| 条件 | 原因 |
|------|------|
| 单笔 > $500 真金 | 硬顶保护 |
| 策略从 paper/notify → auto 首笔 | 真金首笔必审 |
| 策略最近 30 天胜率 < 40% | 质量告警 |
| 连续亏损 ≥ 3 笔 | 风控告警 |
| 同链持仓 > 50% 账户余额 | 集中度告警 |
| 代币最近 24h 跌 > 40%（准备抄底）| 逆势告警 |
| 代币 first_trade_at < 1h | 新币告警 |
| Regime = CRISIS 且尝试买入 | 大盘告警 |
| 授权额度即将用完（> 90%）| 额度告警 |
| Conviction < 0.5 | 低置信度 |

#### 4.4.3 HITL 请求流程

```
策略触发
  ↓
RiskManager 9 项检查通过
  ↓
检查 HITL 触发条件（§ 4.4.2）
  ↓
需 HITL → 写入 pending_approvals 表
  ↓
多渠道通知：
  1. APP 内推（即时，走 WS）
  2. Push notification（FCM / APNs）
  3. （v2）短信 / 邮件 兜底
  ↓
用户收到通知，点击进入 HITL 详情页
  ↓
详情页展示：
  - 策略名 / 触发条件 / 代币信息
  - Thesis（见 § 2.7 schema）
  - 风险卡片
  - 本次金额 / 剩余授权额度
  - "通过" / "拒绝" / "查看更多" 按钮
  ↓
用户 tap "通过" → 触发 wallet signature（本地 Face ID / Touch ID + wallet 私钥签名）
  ↓
签名 OK → 执行 DEX swap
  ↓
写入 audit log
```

#### 4.4.4 HITL 超时行为（必须明确）

| 超时时长 | 默认行为 | 可配置 |
|---------|---------|-------|
| 5 min 未响应 | 状态保持 `pending`，继续推送一次提醒 | - |
| 15 min 未响应 | **自动降级为 `notify_only`**（本次不执行，只通知）| 是，用户可改为 "保持 pending 60min" |
| 60 min 未响应 | **自动 reject**，写入 audit，标记为 `expired` | - |
| 任何时刻用户点 "拒绝" | 立即 reject + 记录原因（可选）| - |

**不允许**：无限期 pending（否则累积风险）。

#### 4.4.5 生物认证与签名

| 场景 | 认证要求 |
|------|---------|
| HITL approve（< $500 真金）| Face ID / Touch ID + wallet signature |
| HITL approve（≥ $500，触发 HITL）| Face ID / Touch ID + wallet signature + **短信 OTP**（v2）|
| 首次授权（申请 auto 模式）| Face ID + wallet signature + 阅读风险提示 ≥ 30s |
| 撤销授权 / kill switch | Face ID（无需 wallet signature，安全优先）|

**生物认证失败 3 次**：锁定 HITL 30 min，推送警告。

#### 4.4.6 审计字段（每次 HITL 必记）

`pending_approvals` + `agent_audit_log` 表：

| 字段 | 类型 | 说明 |
|------|------|------|
| approval_id | uuid | - |
| device_id | uuid | 来源设备 |
| wallet_address | text | 签名钱包 |
| strategy_id | uuid | 触发策略 |
| token / amount_usd | - | 执行详情 |
| trigger_conditions_matched | jsonb | 为什么触发 HITL（§ 4.4.2）|
| thesis_id | uuid | 关联 thesis |
| decision | enum | approve / reject / expired |
| decision_at | timestamp | 用户操作时间 |
| decision_latency_ms | int | 从推送到操作的耗时 |
| ip_address / user_agent / device_fingerprint | - | 合规 |
| signature | text | wallet 签名 hex |
| biometric_verified | bool | FaceID/TouchID 是否通过 |
| tx_hash | text | 执行后填入 |

保留 180 天（合规）。

### 4.5 数据源与执行通道

**数据层**：
- ✅ `agent_strategies` 表（添加 trade_strategy 字段）
- ✅ `hot_sim_trades` 表（模拟盘记录）
- ✅ `HotSimTrader` + `PaperEngine`（现有代码）

**执行层**：
- **信号触发**：P0 DEX 事件流 → EventBus → `event_listener.py` → 匹配 trade_strategy
- **成交价 / quote**：P2 主源——Jupiter / OKX DEX aggregator（事件流不能替代，现货必须走 aggregator 拿实时深度）
- **模拟盘价格基准**：P0 事件流（保证模拟与真金用同一价格源，避免失真）
- **真金执行**：`DexRouter`（已有，SOL + EVM 双路径）

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
- ⚠️ 把策略参数从"全局配置"改为"按 device + 按策略"（无 user_id）
- ⚠️ 加 HITL 授权流程 UI + API
- ⚠️ 加真金执行前的 dry-run 校验

### 4.9 Trade Strategy 完整 Schema

```json
{
  "id": "uuid",
  "device_id": "uuid",
  "wallet_address": "0x... | null",         // auto 模式必填
  "signal_strategy_id": "uuid",             // 绑定的信号策略
  "name": "聪明钱跟单 - SOL 激进",
  "version": 3,                             // 每次编辑 +1
  "status": "draft | active | paused | archived",
  "mode": "paper | notify_only | auto",
  "entry": {
    "amount_type": "fixed_usd | pct",
    "amount_value": 100,                    // $100 或 10（%）
    "slippage_pct": 2.0,
    "max_retry": 2
  },
  "stop_loss": {
    "type": "fixed_pct | atr",
    "value": -15,                           // -15% 或 k=2 (atr 倍数)
    "trailing": false,
    "trailing_pct": null
  },
  "take_profit": [
    { "pct": 50, "sell_ratio": 0.5 },       // 涨 50% 卖一半
    { "pct": 100, "sell_ratio": 1.0 }       // 涨 100% 全平
  ],
  "limits": {
    "max_position_per_trade_usd": 500,      // 硬限
    "max_daily_usd": 2000,
    "max_monthly_usd": 20000,
    "max_same_chain_pct": 50,
    "repeat_rule": "repeat | unique"
  },
  "authorization": {                         // auto 模式必填
    "granted_at": "2026-04-24T00:00:00Z",
    "expires_at": "2026-05-24T00:00:00Z",
    "scope": {
      "chains": ["solana"],
      "tokens": null,                       // null = 全部非黑名单
      "hitl_above_usd": 500
    },
    "signature": "0x...",
    "revoked_at": null
  },
  "created_at": "...",
  "updated_at": "..."
}
```

### 4.10 生命周期与一致性（Lifecycle & Consistency）

| 事件 | 影响 | 规则 |
|------|------|------|
| **策略编辑**（改 entry / stop / target）| 新版本 vN+1 | 新信号按 vN+1 执行；**已开仓位按建仓时的版本平仓**（止盈止损不变）|
| **策略从 auto 改 paper** | 立即生效 | **已开真金仓位保留**，继续按 trade_strategy 监控；新触发走 paper |
| **策略 archived（用户删除）** | 软删 | **已开仓位继续监控到闭仓**；不允许新信号触发 |
| **授权撤销 / kill switch** | 立即停止新执行 | **在途 swap tx**：已广播则不能撤（链上事实），已签名未广播则取消 |
| **wallet connect 变更** | 原 wallet 持仓与 device 脱钩 | 新 wallet 需重新授权；旧 wallet 持仓 UI 标"原钱包持仓"，用户可在原钱包 APP 自行管理 |
| **Device 删除** | 7d 冷却 | **必须先平仓或转移所有真金仓位**，否则删除请求被拒 |
| **Regime 突变到 CRISIS** | 全局 | 所有 auto 策略 **自动临时 pause**（持仓继续监控），恢复到 SIDEWAYS 后用户手动 resume |
| **连续亏损熔断** | RiskManager 触发 | 该策略 pause 60min + 推送；已开仓位不强平 |

### 4.11 失败场景与降级 UI

| 场景 | 触发条件 | UI 表现 | 文案 | 降级行为 |
|------|---------|--------|------|---------|
| DEX 报价失败 | Jupiter + OKX 均失败 | 本次跳过，推送 | "🔴 报价失败，本次未执行"| 尝试 1 次重试后放弃 |
| 滑点超限 | 预估滑点 > 策略配置 | 本次跳过 | "⚠️ 滑点过高，本次未执行，建议降低策略金额"| 跳过 |
| Gas 高于阈值 | EVM gas > 策略 max_gas | 本次跳过 | "⚠️ gas 过高，暂缓执行"| 重试 3 次 |
| 代币无流动性 | LP < $10K | 本次跳过，自动加入黑名单 | "该代币流动性过低，已跳过并加入黑名单"| 拉黑 |
| 蜜罐检测（事后）| GoPlus 实时检出 | 立即推送告警 | "⚠️ 该代币存在蜜罐风险，请尽快平仓"| 不自动平（风险过大）|
| wallet 断连 | 签名失败 | 本次跳过，提示重连 | "钱包未连接，本次未执行"| 用户手动重连 |
| 授权过期 | expires_at < now | 策略自动降级 notify_only | "授权已过期，策略已改为仅通知模式"| 用户手动续授权 |
| 熔断触发 | § 4.10 规则 | pause + 推送 | "连续亏 3 笔，策略已暂停 60min"| 60min 后自动 resume |
| 硬限超限 | amount > $500 | 触发 HITL（不是报错）| 走 § 4.4 流程 | HITL |
| paper 与 auto 价格源差 > 5% | 监控告警 | 日复盘列出 | - | 告警 |

### 4.12 Success Metrics

| 指标 | 目标（v1）| 测量方式 | 失败下线条件 |
|------|----------|---------|------------|
| 绑定交易策略的信号策略占比 | ≥ 60% | 有绑 / 总信号策略 | < 30% |
| paper → notify_only → auto 进阶率 | ≥ 15% | 走完三阶段 / 建了交易策略 | < 5% 说明门槛太高或信任不足 |
| auto 单笔 > $500 HITL 响应率 | ≥ 90% | approve/(approve+reject+expired) | < 70% 说明推送体验差 |
| HITL P50 响应时间 | < 3 min | decision_latency_ms 中位数 | > 10 min 说明不实用 |
| auto 执行成功率 | ≥ 95% | 成功 tx / 触发数（扣除合理跳过）| < 85% |
| 真金月累亏触发熔断的 device 比例 | < 5% | 熔断 device / auto device | > 20% 严重风控失效 |

### 4.13 Persona 差异化

| Persona | 默认 mode | auto 申请门槛 | 单笔上限 |
|---------|----------|-------------|---------|
| 小白 | paper（**禁 auto**）| 不开放，引导学习 | paper $100 |
| 中级 | paper → notify_only 30 天过渡 → auto | § 5.4 硬条件 + HITL 授权 | auto $500 硬顶 |
| 专业 | notify_only / auto 自由 | 同上但可跳过 30 天过渡（需签"理解风险"）| auto $500 硬顶（v2 考虑开放 $2000 for 白名单 wallet）|

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

### 5.7 Hot 策略期望值 -1.74% 修复路径（关键产品决策）

> Hot 策略当前单笔期望值 **-1.74%**（负期望值，见 § 5.3）。v1 launch 前**必须**处理。

**决策树**：

```
Week 1-2: 诊断阶段
  ├── 拉 hot_sim_trades 看亏损交易的共性
  │    - 是不是特定 chain 亏？（ETH 盈亏比更差？）
  │    - 是不是特定 score 段亏？（score 50-60 的亏？）
  │    - 是不是特定 regime 亏？（CRISIS 时亏？）
  └── 输出：亏损归因报告

Week 3-4: 修复阶段
  方案 A: 调参修复
    - 提高 score 阈值（e.g. score >= 65 才触发）
    - 增加过滤器（LP > $200K / age > 7d / Top10 < 60%）
    - 模拟盘重跑 30 天验证
  方案 B: 换数据源 / 权重
    - 接入 Top Holder D3 评估（聪明钱打分）
    - 引入技术面过滤（RSI / 布林带）
  方案 C: 调止盈止损
    - 当前 15% 止盈 / -15% 止损 → 尝试分批止盈 / 追踪止损
  方案 D: 接受现实 —— Hot 从 v1 删除
    - 保留 Smart Money + Pump 两个有正期望值的策略
    - Hot 退到 v2（等修好再上）

Week 5-6: 验证阶段
  - 修复后在 hot_sim 跑 14 天
  - EV 必须 ≥ +1%（v1 门槛）
  - 达标 → v1 上线
  - 不达标 → 方案 D（删 Hot）

v1 上线后 monitoring
  - 每周看 EV 是否保持
  - 连续 2 周 EV < 0 → 自动 pause Hot，触发重诊断
```

**上线硬门槛**（任何 hot 策略进 v1）：
1. 模拟盘回测 30 天 EV ≥ +1%
2. 胜率 ≥ 45%
3. 最大回撤 < 30%
4. 闭仓样本 ≥ 30 笔

**责任**：由 **AI Optimizer Agent**（已有，见记忆 MEMORY）每周跑一次 Hot 策略优化，PM Portal 人工审批。

### 5.8 失败场景与降级 UI

| 场景 | 触发条件 | UI 表现 | 文案 |
|------|---------|--------|------|
| paper 价格源失效 | P0 事件流断 + P2 也失败 | 标仓位"价格不可用" | "⚠️ 价格更新中断，未实现 PnL 暂停计算"|
| 模拟盘虚拟余额归零 | 亏光 | 推送 + 禁止新开仓 + 引导重置 | "模拟账户已归零，可在 Profile 重置为 $10000"|
| 未闭仓归档（30d）| 归档规则 | 从 active 挪到 archived | "仓位已持仓 30 天，已归档。可手动平仓"|
| 持仓同代币重复建 | 违反 unique 规则 | 拒绝新建 | "该代币已有持仓，策略规则为 unique，已跳过"|
| 滑点模拟与真实差 > 10% | 监控告警 | 日复盘列出 | - |
| 回测 / paper 结果矛盾 | 同策略 paper 胜率 55%，回测 35% | 警示用户可能过拟合 | "⚠️ 策略在历史数据表现较好，但实际模拟盘表现较差，建议 walk-forward 验证"|

### 5.9 Success Metrics

| 指标 | 目标（v1）| 测量方式 | 失败下线条件 |
|------|----------|---------|------------|
| 模拟盘 30 天闭仓数 / device | ≥ 20 笔 | count(closed) per device | < 5 笔说明策略不触发 |
| paper 整体胜率（所有 source 合并）| ≥ 45% | 加权胜率 | < 40% 持续 4 周 |
| paper 策略 EV 正的比例 | ≥ 60% | EV > 0 策略 / 总策略 | < 40% 说明策略池差 |
| 模拟盘 → notify_only 切换率（30d 内）| ≥ 30% | 切换 device / 有 paper | < 10% 说明用户不认可 |
| 模拟盘 bug 导致错账次数 | 0 | 对账工具 | > 0 立即修 |

### 5.10 Persona 差异化

| Persona | 默认虚拟余额 | 可重置 | 看到的指标 |
|---------|-----------|-------|----------|
| 小白 | $1000（降低金额直觉）| 是 | 胜率 + 总 PnL |
| 中级 | $10000 | 是 | + 盈亏比 + 单笔 EV |
| 专业 | 自定义（$1000-$100000）| 是 | + Sharpe + 回撤曲线 + 分策略归因 |

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

| 数据 | 粒度 | 来源 | 数据性质 | 已有 |
|------|------|------|---------|------|
| 代币价格 K 线 | 1h | `token_snapshots` 表（DEX 事件流 1min 聚合归档）| P0 事件落表 | ✅ 90 天 |
| 代币表现 | D1/D3/D7 best | `token_performance` 表 | P0 事件聚合 | ✅ 30 天 |
| 聪明钱交易历史 | 秒级 | `smart_money_txns` 表（DEX swap 事件落表）| **P0 事件原始数据** | ✅ 14 天 |
| 热币历史 | 30s 快照 | `hot_coins` 快照归档 | P1 聚合归档 | ⚠️ 当前只有当前状态，需加归档 |
| pump trade 流水 | 秒级 | `token_trades` 表（pumpportal WS 落表）| P0 事件原始数据 | ✅ 30 天 |

**关键优势**：**回测数据就是事件流原样落的**——模拟盘的触发条件和回测的历史触发用同一套数据结构，避免"回测环境 vs 生产环境价格源不一致"的经典坑。

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

### 6.7 Backtest 结果完整 Schema

```json
{
  "backtest_id": "uuid",
  "strategy_id": "uuid",
  "strategy_version": 3,
  "period": { "from": "2026-03-24", "to": "2026-04-23", "days": 30 },
  "chains": ["solana", "eth"],
  "params": { "score_threshold": 65, "liquidity_min_usd": 100000 },
  "summary": {
    "total_trades": 42,
    "win_count": 19,
    "loss_count": 23,
    "win_rate": 0.452,
    "avg_win_pct": 18.3,
    "avg_loss_pct": -14.1,
    "profit_factor": 1.12,            // sum(win) / sum(|loss|)
    "expected_value_pct": 0.89,
    "sharpe_ratio": 0.82,
    "max_drawdown_pct": -22.4,
    "final_equity_pct": 37.5
  },
  "trades": [                          // 每笔明细
    {
      "token": "TRUMP",
      "entry_at": "2026-03-25T10:00Z",
      "entry_price": 1.15,
      "exit_at": "2026-03-26T14:00Z",
      "exit_price": 1.72,
      "pnl_pct": 49.6,
      "exit_reason": "take_profit | stop_loss | trailing | manual | timeout"
    }
  ],
  "equity_curve": [                    // 图表数据
    { "date": "2026-03-24", "equity_pct": 100 },
    { "date": "2026-03-25", "equity_pct": 104.5 }
  ],
  "benchmark": {                       // 对照：持有 SOL 不动
    "total_return_pct": 8.3,
    "sharpe": 0.5
  },
  "warnings": [                        // 自动检测
    "疑似过拟合（胜率 > 80%）",
    "样本不足（< 20 笔）",
    "回测窗口涵盖极端行情（CRISIS regime 占 45%）"
  ],
  "data_quality": {
    "coverage_pct": 94,                // 数据完整度
    "missing_periods": ["2026-03-28 03:00-05:00"]
  },
  "cost_usd": 0,                       // 回测无 LLM 成本
  "duration_ms": 18450
}
```

### 6.8 失败场景与降级 UI

| 场景 | 触发条件 | UI 表现 | 文案 |
|------|---------|--------|------|
| 回测窗口超出数据范围 | period > 已有数据 | 自动截断 + 警告 | "⚠️ 实际回测窗口缩短至 45 天（我们只有 45 天数据）"|
| 回测样本 < 10 笔 | trade count 不足 | 显示结果 + 警告 | "⚠️ 样本不足，结果不具统计意义"|
| 回测发现疑似过拟合 | 胜率 > 80% | 警示 + 建议 walk-forward | "该策略回测表现极好，建议使用滚动窗口验证避免过拟合"|
| 回测超时（> 60s）| 超时 | 返回部分结果 | "回测超时，已返回前 N 天结果"|
| 回测过程中数据源变化 | 中途 smart_money_txns schema 变 | 警告 + 标记可疑时间段 | "⚠️ 某时间段数据不一致，已标注"|
| 并发回测过多 | 同 device 同时 > 3 个 | 排队 | "当前有 X 个回测在队列中"|

### 6.9 Success Metrics

| 指标 | 目标（v1）| 测量方式 | 失败下线条件 |
|------|----------|---------|------------|
| 建策略后 7 天内发起回测的比例 | ≥ 40% | 回测 device / 建策略 device | < 15% 说明入口难找 |
| 回测后 30 天内策略上线率（paper 以上）| ≥ 30% | 上线 / 回测 | < 10% 说明回测结果不被信任 |
| 回测 P95 延迟（30 天窗口）| < 30s | 服务端 | > 60s |
| 回测错账率 | 0 | 对账 | > 0 立即修 |

### 6.10 Persona 差异化

| Persona | 回测入口 | 默认窗口 | 高阶功能 |
|---------|---------|---------|---------|
| 小白 | 隐藏（策略详情页底部 collapsed）| 7d | 仅核心指标 |
| 中级 | 策略详情页主按钮 | 30d | + 对照基准 |
| 专业 | 独立回测实验室 Tab | 90d | + walk-forward + 蒙特卡洛 + 参数扫描 |

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

### 7.7 Review 报告完整 Schema

```json
{
  "review_id": "uuid",
  "device_id": "uuid",
  "wallet_address": "0x... | null",
  "period": "daily | weekly | monthly",
  "period_range": { "from": "2026-04-17", "to": "2026-04-23" },
  "generated_at": "2026-04-23T23:55Z",
  "summary": {
    "total_trades": 8,
    "paper_trades": 6,
    "auto_trades": 2,
    "win_rate": 0.50,
    "total_pnl_usd": 142.30,
    "best_trade": { "token": "TRUMP", "pnl_pct": 48.2 },
    "worst_trade": { "token": "FARTCOIN", "pnl_pct": -18.5 },
    "benchmark_sol_pct": 3.1,             // 同期 SOL 涨幅
    "relative_excess_pct": 5.2            // 超额收益
  },
  "strategy_rankings": [
    {
      "strategy_id": "uuid",
      "name": "聪明钱跟单 SOL",
      "trades": 4, "win_rate": 0.75, "pnl_pct": 22.1,
      "trend": "improving | stable | degrading"
    }
  ],
  "insights": [                           // 见 § 7.5 标准
    {
      "type": "timing | strategy_decay | over_exit | regime_mismatch | concentration",
      "severity": "low | medium | high",
      "text": "过去 7 天你在周五做了 4 笔交易，胜率 25%...",
      "evidence": ["trade_id_1", "trade_id_2"],
      "suggested_action": "周五暂停交易 3 周"
    }
  ],
  "rule_proposals": [                     // 供 T19 采纳
    {
      "proposal_id": "uuid",
      "rule_text": "周五不交易 SOL 链策略",
      "rationale": "基于过去 30 天数据，周五胜率显著低于其他日",
      "sample_size": 12,
      "win_rate_delta": -0.28
    }
  ],
  "degradation_events": [                 // 当日降级记录（对齐 § 8.10）
    { "type": "helius_disconnect", "duration_s": 145, "at": "2026-04-23T10:15Z" }
  ],
  "disclaimer": "此为数据复盘，不构成投资建议。"
}
```

### 7.8 新用户冷启动（Cold Start）

| 状态 | 复盘策略 |
|------|---------|
| Device 创建 < 7 天 / 无任何交易 | 不生成日复盘，改为"引导周报"（教 Agent 用法 / 推荐模板策略）|
| 有策略但无触发 | 生成"策略健康度报告"（分析策略条件太严 / 数据源问题）|
| 有触发但 < 5 笔 | 简化复盘（只 summary + 1-2 条 insight，不做规则提议）|
| ≥ 5 笔闭仓 | 完整复盘 |
| Episodic Memory 空 | thesis 不引用 "similar_past_cases"，UI 显示"学习中，暂无历史参考"|

### 7.9 失败场景与降级 UI

| 场景 | 触发条件 | UI 表现 | 文案 |
|------|---------|--------|------|
| Reflection LLM 超时 | > 30s | 跳过本次，下一周期重试 | "复盘生成失败，将在下次自动重试"|
| 数据不够（新用户）| 见 § 7.8 冷启动 | 显示"引导"版复盘 | "学习你的交易中，首次复盘将在 7 天或 5 笔交易后生成"|
| Insight 过于空泛 | LLM-as-judge 判为低质量 | 自动过滤 | 不展示，log 告警 |
| 规则提议用户拒绝超 3 次 | 类型同质 | 下次不再提议该类 | "你已多次拒绝此类建议，已调整推荐方向"|
| 月复盘数据缺失 | 某天数据断档 | 标注缺失天数 | "本月有 X 天数据不完整（Helius 降级），已排除"|

### 7.10 Success Metrics

| 指标 | 目标（v1）| 测量方式 | 失败下线条件 |
|------|----------|---------|------------|
| 日复盘阅读率（生成后 24h 内打开）| ≥ 50% | 打开 device / 生成 device | < 20% 说明价值低 |
| 周复盘阅读率（48h 内）| ≥ 60% | 同上 | < 30% |
| Insight "有用"反馈率 | ≥ 40% | 点"有用" / 展示数 | < 20% 说明 insight 空泛 |
| 规则提议采纳率（T19）| ≥ 20% | approve / 提议总数 | < 10% 说明建议不准 |
| 采纳后 30 天策略胜率提升 | ≥ +5pp | 采纳规则后 vs 之前的策略表现 | < 0（反而下降）严重问题 |

### 7.11 Persona 差异化

| Persona | 复盘频率 | Insight 重点 | 规则提议数 |
|---------|---------|-----------|----------|
| 小白 | 日 + 周 | 行为警示（"别连续追涨"）| 1-2 条 / 周 |
| 中级 | 日 + 周 + 月 | 策略归因 + 节奏分析 | 2-3 条 / 周 |
| 专业 | 日 + 周 + 月 + 季 | 策略退化检测 + regime 相关 + walk-forward 再验证建议 | 3-5 条 / 周 |

---

## 8. Cross-cutting Requirements（通用需求）

### 8.1 性能（延迟 / 吞吐 / 并发）

#### 8.1.1 延迟 SLA

| 场景 | P50 | P95 | P99 | 冷启动 P95 |
|------|-----|-----|-----|----------|
| 查询行情（T01）| 150ms | 500ms | 1s | 1.5s |
| 生成 thesis L2（Opus）| 3s | 6s | 10s | 8s |
| 生成 thesis L3（全 Opus 辩论）| 10s | 18s | 30s | 24s |
| 策略触发 → 事件进入评估 | 20ms | 200ms | 500ms | - |
| 策略触发 → 推送送达 | 300ms | 1s | 2s | - |
| 策略触发 → 模拟盘建仓 | 500ms | 2s | 4s | - |
| 策略触发 → 真金 swap 确认（SOL）| 3s | 8s | 20s | - |
| 策略触发 → 真金 swap 确认（EVM）| 15s | 45s | 120s | - |
| 复盘生成（后台）| 10s | 30s | 60s | - |
| 回测 30 天 | 12s | 30s | 60s | - |
| HITL 推送送达 | 500ms | 1.5s | 3s | - |

> **冷启动** 定义：该 device 首次请求 / 该 token 首次被查询 / 缓存全失效。

#### 8.1.2 吞吐（Throughput）

| 流 | 目标 | 过载阈值 | 过载行为 |
|----|------|---------|---------|
| EventBus 事件处理 | 1000 events/s | queue > 80%（8000）| 丢弃 P1 类数据事件，保留 P0 |
| 策略 evaluate（全平台）| 500 evals/s | queue > 70% | 降冷却时间 2×；告警 |
| Chat 并发 | 100 并发 | > 150 | 排队 + "当前分析较多，请稍候"|
| 回测并发 | 50 并发 | > 60 | 排队 |
| DEX swap 并发 | 20/s | > 30 | 排队 + 告警（超过 DEX rate limit）|

#### 8.1.3 规模假设（v1）

| 指标 | v1 上线 | v1 稳态（3 月）|
|------|--------|-------------|
| DAU | 20（种子用户）| 100 |
| 每 device 平均活跃策略数 | 3 | 5 |
| 每 device 日均 chat | 5 | 8 |
| 每 device 日均复盘阅读 | 0.5 | 1.0 |
| 总事件量 / 秒 | 200 | 800 |

### 8.2 可用性

- **SLA（核心能力）**：query / analyze / strategy_trigger ≥ **99.5%**（月停机 < 3.6h）
- **SLA（真金执行）**：≥ **99.9%**（月停机 < 45min）；失败事件必通知用户
- **Kill Switch**：1 键关闭所有真金执行，影响范围 < 10s
- **计划维护**：提前 48h 推送；选择低峰（UTC 09:00-11:00）
- **Chaos testing**：每月 1 次，主动模拟 Helius 断连 / DB 断连 / LLM 超时

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

### 8.7 Event-Driven First 原则 ⭐

> 本 Agent 的实时性底座。违反此原则的 PR 一律打回。详见 [00 Data Sources § 1.6](./00-data-sources.md#16-dex-程序级事件流--核心实时源)。

**硬规定**：
1. **实时路径必须走事件流**：信号策略 evaluate、聪明钱检测、pump 发现、价格更新推送——全部 P0（DEX 程序级 WS）驱动
2. **禁止 30s 轮询当主源**：已废弃的旧实现不得复活
3. **P2 API 只做三件事**：
   - 查询报价 / quote（交易执行）
   - 查询深度 / 滑点（交易前校验）
   - 查询历史（K 线 / 归档数据）
4. **P0 降级必须显性**：Helius 429 / RPC 断连时，UI 标红"延迟模式"，不静默切 P2 装正常

**对应 Tool 约束**：
| Tool | 实时性要求 | 强制数据源 |
|------|----------|-----------|
| T01 query_market | 秒内最新价 | DEX 事件 + 聚合表 |
| T03 query_onchain_activity | 秒内最新交易 | `smart_money_txns` / `token_trades`（事件流落表）|
| T04/T06 analyze_technical/onchain | 调用时刻最新状态 | 事件流聚合 |
| T13 策略 evaluate | **毫秒级** | EventBus 订阅（非轮询）|
| T15 execute_trade_strategy | 毫秒级触发 + 秒级成交 | 事件流触发 + P2 aggregator 执行 |

**工程落地要求**（对齐现有代码）：
- ✅ `event_listener.py` 的 EventBus 订阅模式必须保留
- ✅ 新增 tool 默认应**订阅事件**，不新增轮询任务
- ⚠️ 历史上的 30s 轮询代码需审计并废弃（技术债 § 10.3）

### 8.8 Cost Budget（成本预算每能力分摊）

#### 8.8.0 模型分层决策（v1 采用「质量优先」方案）

> ⚠️ **v0.4 关键决策**：产品优先保证**决策质量**，全链路采用当前最强模型。成本作为次要考量。

| 职责 | v1 采用 | 原理由 |
|------|---------|-------|
| L2 Thesis（常规分析）| **Claude Opus**（最强）| 单次决策影响用户真金，不因省钱牺牲 |
| L3 3 分析师（技术 / 情绪 / 链上）| **Claude Opus** × 3 并行 | 分析维度独立，不接受 Haiku 级别粗粒度 |
| L3 Bull vs Bear 辩论（5 轮）| **Claude Opus** | 辩论对抗性最高，需要最强推理 |
| L3 RiskReviewer | **Claude Opus** | 风控是最后一道防线 |
| C3 NL 建策略（tool-use）| **Claude Opus** | 策略生成错一个字段后果严重 |
| C7 日 / 周 / 月复盘 | **Claude Opus** | insight 质量 = 产品价值 |
| L1 规则 | 无 LLM | 不变 |
| Haiku 仅保留作降级用 | 仅当日预算 > 85% 时 | 降级不是常态 |

**架构一致性**：本节与 [04 Agent Spec § 5.3](./04-agent-spec.md#53-成本与延迟预算) 必须同步。

#### 8.8.1 单次调用成本（Opus 方案）

Claude Opus pricing（v1 基准）：**input $15 / M tokens，output $75 / M tokens**。

| 能力 | 模型 / 调用 | 单次成本 | 备注 |
|------|-----------|---------|------|
| C1 查行情 | 无 LLM | $0 | 纯 DB 查询 |
| **C2 生成 thesis L2** | 1× Opus | **~$0.025** | 约 1.5K in + 0.5K out |
| **C2 生成 thesis L3** | 3× Opus（分析师并行）+ 5× Opus（辩论）+ 1× Opus（review）| **~$0.35** | 完整辩论流，8-12s |
| **C3 NL 建策略（共创一次完整会话）** | 4-6× Opus 调用 + 1× T10 回测 | **~$0.06-$0.10** | 多轮共创 |
| C3 策略 evaluate | 无 LLM（RuleEngine）| $0 | |
| C5 paper 建仓 / 监控 | 无 LLM | $0 | |
| C6 回测 30 天 | 无 LLM | $0 | 纯计算 |
| **C7 日复盘** | 1× Opus | **~$0.15** | 5K in + 2K out |
| **C7 周复盘** | 1× Opus + recall_memory | **~$0.40** | 10K in + 4K out |
| **C7 月复盘** | 1× Opus + 大量 memory | **~$1.00** | 20K in + 8K out |

#### 8.8.2 每 device 日/月预算上限

| Persona | 日预算 | 月预算 | 超限行为 |
|---------|-------|-------|---------|
| 免费（v1 所有用户）| **$1.50** | **$30** | L3 降 L2 Opus；L2 降 L2 Sonnet；超过再触发→拒绝 |
| 付费（v2 计划）| $5 | $100 | 同上但阈值放宽 |

**冲突处理（降级顺序）**：
- **第 1 级降级**（预算 > 70%）：L3 分析师 Opus → Sonnet，辩论仍 Opus
- **第 2 级降级**（预算 > 85%）：L3 全链降 Sonnet；L2 降 Sonnet
- **第 3 级降级**（预算 > 95%）：C2 L3 改为 L2，C7 日复盘改简化版
- **硬停**（预算 100%）：拒绝新请求 + 提示"今日 AI 分析额度已用完，明日恢复"
- **永远保护**：C1 / C3 evaluate / C5 / C6（无 LLM 成本的能力不受影响）

#### 8.8.3 月度平台总预算（v1 上线 3 月，Opus 方案）

假设 DAU 100，中级用户日均 3 次 thesis（80% L2 + 20% L3）+ 1 次日复盘 + 共创 1 次 / 周：

| 项 | 计算 | 月成本 |
|----|------|--------|
| C2 L2 Opus | 100 × 30 × 3 × 0.8 × $0.025 | **$180** |
| C2 L3 Opus | 100 × 30 × 3 × 0.2 × $0.35 | **$630** |
| C3 NL 共创 | 100 × 4（每周 1 次）× $0.08 | **$32** |
| C7 日复盘 Opus | 100 × 30 × $0.15 | **$450** |
| C7 周复盘 Opus | 100 × 4 × $0.40 | **$160** |
| LLM 合计 | | **~$1452** |
| Helius 付费 | | **$50** |
| 其他 API | | **$100** |
| **合计** | | **~$1602 / 月** |

**v1 阶段评估**：
- ✅ 在 100 DAU 规模可承受（$16 / DAU / 月）
- ⚠️ 到 1K DAU 需考虑 Sonnet fallback 分层 / 付费模式
- ⚠️ 到 10K DAU Opus 全链不可持续，必须差异化（免费用户 Sonnet / 付费用户 Opus）

#### 8.8.4 v2 预备方案（不在 v1 启用）

| 方案 | 说明 | 触发条件 |
|------|------|---------|
| A. Tier 分级 | 免费 Sonnet 主 / 付费 Opus 主 | DAU > 500 |
| B. 智能路由 | 简单 token 用 Sonnet，复杂 / 陌生 token 用 Opus | DAU > 1K |
| C. Opus 仅留给"大额真金"| Opus 仅 auto > $100 真金才用 | DAU > 5K |

详见 [13 Cost Budget](./13-cost-budget.md)（待写）。

### 8.9 数据一致性原则（Data Consistency）

#### 8.9.1 时间戳权威（Time Source of Truth）

| 数据 | 权威时间戳 | 原因 |
|------|----------|------|
| DEX swap | **链上 block_time** | 事件真实发生时间 |
| 策略触发 | **服务端 EventBus 接收 ts** | 与 swap 有 ~400ms 差（延迟正常）|
| Thesis 生成 | **服务端生成完成 ts** | 不回写为 "token 当前时间" |
| 用户操作（HITL 等）| **服务端接收 ts**，客户端 ts 仅参考 | 防客户端时钟伪造 |
| 复盘 | **UTC 23:55 为日期切线** | 固定不随用户时区变 |

**显示时**：UI 可按用户时区转换，但**存储一律 UTC timestamp**。

#### 8.9.2 价格权威（Price Source of Truth）

| 场景 | 价格源 | 原因 |
|------|-------|------|
| thesis 里的"当前价" | DEX 事件流最新（缓存 ≤ 3s）| 一致性 |
| 策略触发条件评估 | 事件 payload 里的 price_usd | 触发判断凭据 |
| 模拟盘建仓价 | 同触发事件的 price_usd | 避免"触发价 ≠ 建仓价" |
| 模拟盘 PnL 实时计算 | 最新事件流价格（≤ 5s 延迟）| 用户感知 |
| 真金 swap 实际成交价 | DEX aggregator 返回的 executed_price | 真相 |
| 回测建仓价 | `token_snapshots` 表最近点的 close | 历史数据 |

**矛盾原则**：当同时刻事件流 $1.00 vs OKX API $1.02 → **事件流为准**（更实时），但差 > 5% 时触发告警（可能事件流漏数据）。

#### 8.9.3 数据虚高 2% 已知问题的透明度

- multi-hop swap 导致成交量虚高 ~2% → **模拟盘 / 回测 / 复盘**展示的"策略胜率"也都受影响
- 产品侧**透明披露**：在回测页底部显示"⚠️ 历史成交量数据存在 ~2% 虚高，实际表现可能略差于展示值"
- v2 按 tx 级聚合修复

### 8.10 Feature Flag & 灰度策略

#### 8.10.1 能力级 Feature Flag

每个能力独立 flag，可单独开/关（即使整体正常，也能快速回滚单个能力）：

| Flag | 默认 | 控制范围 |
|------|------|---------|
| `feature.query_market` | ON | C1 查行情 |
| `feature.thesis_l2` | ON | C2 thesis L2 |
| `feature.thesis_l3` | OFF → canary → beta → GA | C2 thesis L3（辩论）|
| `feature.signal_strategy` | ON | C3 |
| `feature.trade_strategy_paper` | ON | C4 paper |
| `feature.trade_strategy_notify` | canary | C4 notify |
| `feature.trade_strategy_auto` | **OFF（v1 上线 14 天后分批开启）** | C4 auto |
| `feature.backtest` | ON | C6 |
| `feature.review_daily` | canary | C7 日复盘 |
| `feature.review_weekly` | canary → ON after 14d | C7 周复盘 |
| `feature.hot_strategy` | **OFF until EV > +1%** | Hot 策略 |
| `feature.pump_strategy` | canary | Pump 策略 |
| `feature.smart_money_strategy` | ON | SM 策略（EV 最好）|

#### 8.10.2 灰度分桶

| 阶段 | 流量 | 判定条件 | 持续时间 |
|------|------|---------|---------|
| **Canary** | 5%（内部 + opt-in 种子用户）| 无 SEV-1，关键指标不退化 | 48h |
| **Beta** | 25% | 48h canary OK | 5 天 |
| **GA** | 100% | 5d beta OK | - |

#### 8.10.3 按身份分桶（无注册的替代方案）

- **分桶键**：`hash(device_id)` → 稳定分桶（同 device 永远在同桶）
- **opt-in 种子用户**：APP 内"加入内测"开关，写入本地 `opt_in_canary=true` → 下次请求头带 `X-Beta: 1`
- **紧急回滚**：直接把 feature flag 置 OFF，影响范围 < 5s

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
| **Helius WS（SOL 事件流 P0）** | **实时成交 / 聪明钱 / pump（Agent 实时性底座）** | 🔴 **致命** | **必须付费升级**；失败时 UI 显性降级，不静默切 API |
| **pumpportal WS** | pump.fun 内盘事件 | 🔴 高 | 无兜底，失败即 pump 能力离线 |
| **EVM 公共 RPC WS** | ETH/BSC/Base 事件流 P0 | 🟠 中 | 多个 RPC 源冗余，OKX 轮询补 |
| Jupiter / OKX DEX | DEX 路由（P2，交易执行必须）| 🔴 高 | Jupiter 失败降级 OKX DEX |
| DexScreener | 行情兜底（P2）| 🟡 低 | 多源（GeckoTerminal）备份 |
| GeckoTerminal | K 线 / 历史（P2）| 🟠 中 | 历史查询无兜底，失败时回测不可用 |
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
| 历史 30s 轮询代码尚未完全废弃 | 违反 § 8.7 Event-Driven First | v1 审计 + 迁移到 EventBus 订阅 |
| Helius 免费版 429 限流 | P0 事件流 10min 全断，SEV-2 | v1 前必须付费升级 |
| Multi-hop swap 重复计数 | 成交量虚高 ~2% | v1 接受，v2 按 tx 级聚合 |

---

## 11. E2E 端到端闭环验收（North Star 落地）

> Vision North Star 是"每周完成 ≥ 1 次闭环的用户比例"。闭环 = 从建策略到复盘的完整主干。本章定义主干路径 + 每个节点的验收。

### 11.1 闭环主干路径

```
① Device 安装 + 首启
     ↓
② 引导（3 问 Persona 识别）
     ↓
③ 浏览官方 Tab（热币/聪明钱/新币）← APP 已有，Agent 不改
     ↓
④ Chat 分析 1-3 个代币 (C1+C2)
     ↓
⑤ 基于分析建 Signal Strategy（NL 或模板）(C3)
     ↓
⑥ 绑定 Trade Strategy - paper 模式 (C4)
     ↓
⑦ 30 天 paper 跟踪 + 实时 PnL (C5)
     ↓
⑧ 期间可选：回测看历史表现 (C6)
     ↓
⑨ 满足 § 5.4 硬条件 → 切 notify_only（首阶段）
     ↓
⑩ 用户手动按 notify 操作 ≥ 3 次（建立信任）
     ↓
⑪ Connect wallet → 申请 auto 授权 (C4 + HITL)
     ↓
⑫ auto 第 1 笔（必 HITL）
     ↓
⑬ 日复盘 + 周复盘阅读 (C7)
     ↓
⑭ 规则提议采纳（写入 Semantic Memory）(T19)
     ↓
⑮ Semantic 规则生效 → 新 thesis 更精准
     ↓
  ──→ 回到 ④，形成持续闭环
```

### 11.2 每节点验收（E2E 测试用例）

| # | 节点 | 验收标准 | 失败下线条件 |
|---|------|---------|------------|
| ① | 首启 | APP 启动 < 3s；device_id 生成成功 | > 5s / 失败率 > 1% |
| ② | Persona 识别 | 3 问完成率 ≥ 80% | < 50% 说明步骤太重 |
| ④ | Chat 分析 | thesis 生成 P95 < 5s；evidence 引用 ≥ 2 条 | § 2.9 |
| ⑤ | 建 Signal Strategy | NL 转换成功率 ≥ 90%；首次建策略时长 < 3 min | > 10 min 说明 UX 差 |
| ⑥ | 绑定 Trade Strategy | 默认 paper；首次绑定 < 1 min | - |
| ⑦ | paper 跟踪 | 30 天内触发 ≥ 5 笔；PnL 实时更新（≤ 5s 延迟）| 触发 < 1 笔说明策略无效 |
| ⑧ | 回测 | P95 < 30s；样本 ≥ 10 笔 | - |
| ⑨ | 切 notify_only | 硬条件校验通过率 ≥ 90%（真符合的）；拒绝率 < 20% | - |
| ⑩ | 手动操作 ≥ 3 次 | 推送后 60min 内操作 ≥ 60% | < 30% 说明推送无效 |
| ⑪ | wallet connect + auto 授权 | Connect 成功率 ≥ 95%；授权完成率 ≥ 80%（启动 flow 的）| - |
| ⑫ | auto 首笔 HITL | § 4.12 指标 | - |
| ⑬ | 日复盘阅读 | § 7.10 指标 | - |
| ⑭ | 规则采纳 | § 7.10 指标 | - |
| ⑮ | 闭环形成 | 采纳后 7 天内用 Semantic Memory 生成新 thesis ≥ 1 次 | < 30% device 达成 |

### 11.3 North Star 验收

- **每周完成 ≥ 1 次 "④→⑦"** 的 device 比例 ≥ **30%**（中间阶段目标）
- **每月完成 ≥ 1 次 "④→⑭"** 的 device 比例 ≥ **10%**（完整闭环 KPI）
- **进入 auto（⑫）** 的 device 比例 ≥ **5%**（3 个月稳态）

### 11.4 闭环中断告警

监控以下"断链点"，持续 7d 超过阈值触发 PM 告警：

| 断链点 | 告警阈值 |
|--------|---------|
| ④ → ⑤ 转化 | < 8% |
| ⑤ → ⑥ 转化 | < 60%（建了信号不绑交易）|
| ⑥ → ⑦ 触发率 | < 50%（绑了策略但从不触发）|
| ⑦ → ⑨ 切换率 | < 15% |
| ⑨ → ⑪ 授权率 | < 20% |
| ⑬ 阅读率 | < 30% |

---

## 12. 验收总 Gate（上线前必达）

引用 [11 Launch Criteria](./11-launch-criteria-hitl.md)，本 PRD 相关硬门槛：

**功能完整度**：
- ✅ 6 大能力全部 MUST 项验收通过（§ 1-7 每章 🔴 项 100%）
- ✅ 每能力对应 tool 有 golden dataset（≥ 50 案例，见 [09 Eval Plan](./09-eval-plan.md)）
- ✅ 每能力"负面验收"场景 UI 测试通过（§ 1.7/2.8/3.9/4.11/5.8/6.8/7.9）

**质量红线**：
- ✅ Hot 期望值 ≥ +1%（或 Hot 功能从 v1 暂下线）
- ✅ Smart Money 期望值保持 ≥ +4%（已达标）
- ✅ 策略 NL 转换成功率 ≥ 90%

**安全与合规**：
- ✅ Safety Policy 100% 覆盖（[08 Safety Policy](./08-safety-policy.md)）
- ✅ HITL 流程所有分支测试通过（§ 4.4）
- ✅ Kill Switch 实测 < 10s
- ✅ 审计字段完整（§ 4.4.6）
- ✅ CN IP 屏蔽 + 免责声明

**运营就绪**：
- ✅ [12 Incident Response SOP](./12-incident-response.md) 就绪 + on-call 排班
- ✅ [15 Observability](./15-observability-tracing.md) 覆盖所有 Loop + Tool
- ✅ Cost Budget 硬约束生效（§ 8.8）
- ✅ Feature Flag 分级就绪（§ 8.10）

**E2E 验收**：
- ✅ § 11.2 每节点验收通过
- ✅ 首批 **20 种子用户 1 周试用**：
  - 无 SEV-1 / SEV-2 事故
  - 至少 10 人完成到 ⑦（paper 跟踪）
  - 至少 3 人完成到 ⑬（复盘阅读）
  - NPS ≥ 30

---

## Change Log

- **v0.4 (2026-04-24)**：模型策略升级 + 共创流程明确
  - § 3.2.1 新增 **共创流程 Co-creation Flow**（7 阶段 + 关键原则 + 反例/正例 + Tool 调用链）
  - § 3.2 功能需求首行新增"共创式建策略"为核心
  - § 8.8.0 新增 **模型分层决策**：v1 全链 **Claude Opus（质量优先）**
  - § 8.8.1 / 8.8.2 / 8.8.3 成本按 Opus 重算：月度预算 $264 → **$1602**（5.5× 当前）
  - § 8.8.4 新增 v2 预备方案（Tier 分级 / 智能路由 / 大额专用 Opus）
  - § 2.4 T04/T05/T06 模型标注 Opus；§ 2.9 指标/成本表更新
  - § 8.1 L2 / L3 延迟调整（Opus 更慢但更准）
  - 同步 [04 Agent Spec § 2.2 D3 / § 5.3 / § 架构图 / § 8.1 failure mode](./04-agent-spec.md)
  - 术语表：CRUD = Create / Read / Update / Delete（增 / 查 / 改 / 删）
- **v0.3 (2026-04-24)**：关键产品决策 + P0/P1 硬伤补齐
  - **产品决策**：§ 0.6 新增 **Identity Model**——**本产品无注册账户**；身份 = device_id + 可选 wallet_address
  - § 0.5 新增 **Persona 差异化全局原则** + 每章补 "X.N Persona 差异化" 小节
  - § 0.5 → § 0.7（数据源优先级下移编号）
  - 每章补 "X.N 失败场景与降级 UI"（§ 1.7 / 2.8 / 3.9 / 4.11 / 5.8 / 6.8 / 7.9）—— **负面验收硬伤修复**
  - 每章补 "X.N Success Metrics"（§ 1.8 / 2.9 / 3.10 / 4.12 / 5.9 / 6.9 / 7.10）
  - § 2.7 新增 **Thesis 完整 Schema**
  - § 3.8 新增 **策略生命周期与一致性**（status 转移 / 软删 / 版本化）
  - § 4.2.1 **"仓位百分比" 权威定义**（paper / notify / auto 三种 account model）
  - § 4.2.2 **余额不足 / 读取失败降级规则**
  - § 4.4 **HITL 完整流程展开**：触发条件 10 条 / 推送流程 / 超时行为 / 生物认证 / 审计字段
  - § 4.9 **Trade Strategy 完整 Schema**
  - § 4.10 **Trade Strategy 生命周期**（编辑 / 删除 / 撤授权 / wallet 切换 对持仓的影响）
  - § 5.7 **Hot 期望值 -1.74% 修复决策树**（4 方案 + 上线硬门槛）
  - § 6.7 **Backtest 结果完整 Schema**
  - § 7.7 **Review 报告完整 Schema**
  - § 7.8 **新用户冷启动**（5 种状态的 Review 策略）
  - § 8.1 **性能表扩展**：P50/P95/P99 + 冷启动 + 吞吐 + 并发 + 规模假设
  - § 8.8 **Cost Budget 每能力分摊** + 每 device 预算 + 月度总预算
  - § 8.9 **数据一致性原则**：时间戳权威 / 价格权威 / 虚高 2% 披露
  - § 8.10 **Feature Flag 每能力独立**（Hot OFF / auto OFF 14d / canary 分桶）
  - § 11 新增 **E2E 端到端闭环验收**（15 节点主干 + North Star 指标 + 断链告警）
  - § 12 Launch Gate 细化（功能/质量/安全/运营/E2E 5 维度硬门槛）
  - 同步更新 [04 Agent Spec § 2.1 架构图双语 + § 3.1 API 去 user_id](./04-agent-spec.md)
- **v0.2 (2026-04-23)**：引入 DEX 程序级事件流作为 P0 数据源
  - § 0.5 新增 核心数据源优先级表（P0 事件流 / P1 聚合表 / P2 API 兜底）
  - § 1.3 / 2.3 / 3.4 / 4.5 / 6.3 各 Tool 数据源栏按新优先级重写
  - § 8.7 新增 **Event-Driven First 原则**（硬规定：实时路径必走事件流，禁止轮询当主源）
  - § 10.1 依赖表：Helius WS / pumpportal WS 升级为 🔴 致命级依赖
  - § 10.3 技术债新增 3 项：废弃轮询代码 / Helius 付费 / multi-hop 聚合
  - 同步更新 [00 Data Sources § 1.6](./00-data-sources.md#16-dex-程序级事件流--核心实时源)
- **v0.1 (2026-04-23)**：首版完整填充
  - 6 大能力按 MoSCoW 展开功能需求
  - 每能力对应 tool 映射（T01-T19）
  - 明确与 APP 其他 Tab + 现有代码的关系
  - 引用真实生产 baseline（Hot 期望值 -1.74% 作为 v1 必修项）
  - Cross-cutting 性能/合规/可观测要求
  - Out of Scope 10 项 + Risks 清单 + 技术债清单
- v0（2026-04-22）：骨架创建
