# 04 Agent Spec（harness 核心）

> 定义 Agent 本体：身份、能力、边界、Loop、状态机、失败模式、版本。
> 本 Spec 是 [01 Vision](./01-product-vision.md) + [03 PRD](./03-prd.md) 的**工程实现契约**。

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.1 Draft |
| Version | v0.1 |
| Owner | 产品负责人 |
| Target Release | v1 MVP - 2026 Q3 |

---

## 0. 文档导读

### 0.1 阅读顺序

- 从未看过 Agent 代码 → 先读 § 1（身份）+ § 2（架构图）+ § 6（Loop）
- 工程实现 → § 3 输入输出契约 + § 7 状态机 + § 8 失败模式
- 产品 review → § 1 身份 + § 4 能力矩阵 + § 9 边界
- QA → § 7 状态机 + § 8 失败模式 + § 10 evaluation hooks

### 0.2 和其他文档的关系

```
[01 Vision]  产品原则 + Non-goals
    ↓
[02 Persona] 用户 + 场景
    ↓
[03 PRD]     6 大能力 + T01-T19 Tool 映射
    ↓
[04 Agent Spec] ← 本文档：Agent 本体 / Loop / 状态 / 失败
    ↓
[05 Tool Catalog]    每个 Tool 的 schema
[07 Memory]          三层记忆详细
[08 Prompt Library]  prompt 版本管理
[09 Eval Plan]       golden set
```

### 0.3 术语

- **Loop**：Agent 的主循环，本 Agent 有 4 条（Scout / Thesis / Notify / Reflect）
- **L1 / L2 / L3**：决策分级（规则 / Opus 单次 / Opus 多分析师+辩论）
- **HITL**：Human-In-The-Loop，用户当次拍板
- **Event-Driven First**：实时路径必走事件流，详见 [03 PRD § 8.7](./03-prd.md#87-event-driven-first-原则)

---

## 1. Agent Identity

### 1.1 Mission（使命句 · 一行）

> **做一个懂用户、记得住、能陪完整交易周期的加密链上现货 Copilot——把用户自己的判断框架沉淀为可自动执行的策略。**

### 1.2 Role Definition（角色定义）

| 维度 | 定义 |
|------|------|
| **是什么** | 用户的交易助手（Copilot），**不是信号分发者** |
| **服务谁** | APP 已注册用户（Persona 主打中级用户）|
| **服务边界** | 加密**链上现货**（SOL/ETH/BSC/Base 4 链）|
| **对齐目标** | 用户的**长期投资回报 + 风控守纪**，不是短期 engagement |

> ⚠️ **核心边界**：Agent **不做官方信号推送**——APP 的热币/聪明钱/新币 Tab 已承担该职责。Agent 的价值是让用户**把这三个 Tab 的信号 + 自己的判断**组合为策略。详见 [01 Vision § 6.5](./01-product-vision.md#65-agent-与-app-其他模块的边界)。

### 1.3 Competencies（核心能力 · 对齐 PRD 6 大能力）

| # | 能力 | Tool | 对应 PRD |
|---|------|------|---------|
| C1 | **查行情**：按 address/symbol 查询代币实时状态 | T01-T03 | [§1](./03-prd.md#1-market-query查询行情) |
| C2 | **分析行情**：多维融合 + 引用历史类似案例 + 置信度 | T04-T06, T12 | [§2](./03-prd.md#2-market-analysis分析行情) |
| C3 | **建信号策略**：用户自然语言 / 规则构造 → 可触发条件树 | T07, T13-T14 | [§3](./03-prd.md#3-signal-strategy-builder自定义信号策略--核心) |
| C4 | **建交易策略**：绑定信号策略 → paper/notify/auto 执行 | T08, T15-T16 | [§4](./03-prd.md#4-trade-strategy-builder自定义交易策略--核心) |
| C5 | **模拟盘**：先 paper 验证再真金 | T09, T17 | [§5](./03-prd.md#5-paper-trading模拟盘) |
| C6 | **回测**：在历史数据跑一遍 | T10 | [§6](./03-prd.md#6-backtest策略回测) |
| C7 | **复盘**：日/周/月复盘 + 规则提议 | T11, T18-T19 | [§7](./03-prd.md#7-review策略复盘) |

### 1.4 Limits（硬性边界 · 绝不做）

来自 [03 PRD § 9](./03-prd.md#9-out-of-scopev1-明确不做) + Safety Policy：

- ❌ 不做合约 / 期货 / 杠杆 / CEX 交易 / NFT / DeFi LP / 借贷 / 跟单 / 税务
- ❌ 不推送官方信号（用户需自建策略）
- ❌ 不给"保证盈利"话术
- ❌ 不预测具体价格
- ❌ 单笔真金 > $500 **必须**用户当次 HITL，即使已授权
- ❌ 不做未经用户明确授权的真金执行
- ❌ 不访问、保存、传输用户私钥 / 助记词 / CEX 账号密码

### 1.5 Personality（说话风格）

| 维度 | 设定 |
|------|------|
| **语气** | 严谨务实，不卖弄术语，不贩卖焦虑 |
| **立场** | **说不知道不丢人**。数据不足 → 拒绝分析；置信度低 → 明示 |
| **术语** | 按用户 Persona 自适应（小白用白话 / 中级用行话 / 专业用技术参数）|
| **Emoji** | 最多 1 个 / 段（✅ ⚠️ 🔴 功能性表达可），禁止装饰性 emoji |
| **长度** | Thesis ≤ 200 字；每日复盘 ≤ 500 字；insight ≤ 50 字 |
| **禁用表达** | "错过就亏了" / "躺赚" / "稳的" / "百倍机会" / "一定涨" |

---

## 2. Architecture

### 2.1 分层架构（Layered Architecture）

```
┌───────────────────────────────────────────────────────────────────────┐
│  用户层 / User Surface                                                │
│  Flutter APP（对话 Chat / 策略 Strategy / 复盘 Review / 授权 HITL）   │
└────────────────────────────┬──────────────────────────────────────────┘
                             │  REST / WebSocket
┌────────────────────────────┴──────────────────────────────────────────┐
│  编排层 / Agent Orchestration Layer                                   │
│                                                                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │  Scout Loop  │ │ Thesis Loop  │ │ Notify Loop  │ │ Reflect Loop │  │
│  │  扫描 / 触发 │ │ 分析 / 决策  │ │ 推送 / 执行  │ │ 复盘 / 反思  │  │
│  │ (事件驱动)   │ │  (按需)      │ │ (事件驱动)   │ │  (定时)      │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────────────┘  │
│         │                │                │                           │
│         └────────────────┼────────────────┘                           │
│                          ▼                                            │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  分级决策 / Decision Grading                                  │    │
│  │  L1 规则 Rule  /  L2 Opus 单次  /  L3 多角色 Multi-role Opus  │    │
│  └──────┬──────────────────────────┬─────────────────────────────┘    │
│         │                          │                                  │
│     ┌───▼───────┐          ┌───────▼──────────┐                       │
│     │ 规则引擎  │          │ 多角色编排器     │ 3 Opus 分析师（技术/  │
│     │ Rule Eng. │          │ Multi-Role Orch. │ 情绪/链上 并行）+     │
│     └───┬───────┘          └───────┬──────────┘ 牛熊 Bull vs Bear     │
│         └────────────┬─────────────┘            Opus + 风控审查       │
│                      ▼                          RiskReviewer Opus     │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  风控 Risk Manager（9 项检查）                                │    │
│  │  + HITL 人审门 HITL Gate  + 决策 Agent Decision Agent         │    │
│  └──────┬─────────────────────────────────────┬──────────────────┘    │
│         │                                     │                       │
│    ┌────▼────────┐                    ┌───────▼─────────┐             │
│    │ 模拟盘引擎  │                    │ 真金执行器      │             │
│    │ Paper Eng.  │                    │ Trade Executor  │             │
│    └─────────────┘                    └───────┬─────────┘             │
└────────────────────────────────────────────────┼──────────────────────┘
                                                 │
┌────────────────────────────────────────────────┴──────────────────────┐
│  工具与数据层 / Tool & Data Layer                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │ Tool 目录   │ │ 记忆 Memory │ │ 市场状态    │ │ DEX 路由    │      │
│  │ T01-T19     │ │ 情景/语义/  │ │ Regime      │ │ Router      │      │
│  │ Tool Cat.   │ │ 反思        │ │ Detector    │ │ (Jup/OKX)   │      │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘      │
└─────────┼───────────────┼───────────────┼───────────────┼─────────────┘
          │               │               │               │
┌─────────┴───────────────┴───────────────┴───────────────┴─────────────┐
│  事件与数据基础设施 / Event & Data Infrastructure                     │
│  EventBus (asyncio)  │ Postgres (local) │ Redis (v1+) │ PostgREST     │
│                                                                       │
│  P0 主源 / Primary Sources（实时事件流 Real-time Event Streams）      │
│    Helius WS (SOL)  ─▶ smart_money_txns / pump_tokens / token_trades  │
│    EVM RPC WS       ─▶ token_snapshots / hot_coins                    │
│    pumpportal WS    ─▶ agent_memory / agent_executions / ...          │
│                                                                       │
│  P2 兜底 / Fallback（查询式 API，仅用于深度/历史/报价）               │
│    OKX DEX / GeckoTerminal / DexScreener / GoPlus / Helius Enhanced   │
└───────────────────────────────────────────────────────────────────────┘
```

### 2.2 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| D1 | **Event-Driven First** | 实时路径必走事件流（[PRD §8.7](./03-prd.md#87-event-driven-first-原则)）|
| D2 | **三级决策分级 L1/L2/L3** | 成本 $0 / ~$0.025 / ~$0.35，绝大多数走 L1，复杂/大额才升级 |
| D3 | **v1 全链 Claude Opus（质量优先）** | 分析师 / 辩论 / 风控 / 复盘 / NL 建策略全部 Opus；Sonnet / Haiku 仅作**预算降级**兜底；详见 [03 PRD § 8.8.0](./03-prd.md#880-模型分层决策v1-采用质量优先方案) |
| D4 | **本地 Postgres + PostgREST** | 已从 Supabase 迁移，减少依赖 |
| D5 | **Memory 分三层** | Episodic(14d) / Semantic(30d) / Reflection（promotion）|
| D6 | **Paper 默认，Auto 需授权** | 策略 ≥ 30d + ≥ 30 闭仓 + EV ≥ +1% 才能切 auto |
| D7 | **HITL 队列（v1 新建）** | 大额 / 低置信度 / 新策略首笔 必入队 |

---

## 3. Input / Output Contract

> **身份模型（Identity Model）**：本产品**无注册账户**。身份 = **device_id（匿名设备标识，APP 首启生成，本地保存）** + 可选 **wallet_address（用户 connect wallet 后绑定，真金交易必需）**。详见 [03 PRD § 0.6](./03-prd.md#06-identity-model身份模型--无注册账户)。

### 3.1 对外 API（Agent 接口）

所有 API 使用 HTTP header `X-Device-Id`（必需）+ `X-Wallet-Address`（真金场景必需）鉴权，不用 session cookie / user_id。

**入口 1：Chat 对话**
```http
POST /api/agent/chat
Headers: X-Device-Id: <uuid>
{
  "session_id": "uuid",           # 本次会话 ID（前端生成）
  "message": "帮我分析 TRUMP",
  "context": { "chain": "solana", "address": "..." }
}
→ 200 OK
{
  "reply": "...",
  "used_tools": ["T01", "T04", "T12"],
  "thesis": { direction, entry_zone, stop_loss, target, conviction, risks[], summary },
  "trace_id": "uuid"
}
```

**入口 2：策略 CRUD**
```http
POST   /api/agent/strategies         # 建策略（自然语言 or 结构化）
GET    /api/agent/strategies         # 该 device 的策略列表
PATCH  /api/agent/strategies/:id     # 改
DELETE /api/agent/strategies/:id     # 软删（保留已触发仓位）
POST   /api/agent/strategies/:id/pause
POST   /api/agent/strategies/:id/resume
Headers: X-Device-Id: <uuid>
```

**入口 3：HITL 审批**（v1 新增）
```http
GET    /api/agent/approvals/pending         # 待审列表
POST   /api/agent/approvals/:id/approve     # 需 wallet signature
POST   /api/agent/approvals/:id/reject
Headers: X-Device-Id: <uuid>, X-Wallet-Address: <addr>, X-Signature: <sig>
```

**入口 4：复盘**
```http
GET    /api/agent/reviews/daily?date=
GET    /api/agent/reviews/weekly?week=
POST   /api/agent/reviews/rules/:id/approve  # 采纳规则提议
Headers: X-Device-Id: <uuid>
```

### 3.2 Error Model（统一错误码）

| Code | 含义 | HTTP | 可重试 |
|------|------|------|-------|
| `DATA_INSUFFICIENT` | 数据不足无法分析（如代币 <1h）| 200 | 是，等数据 |
| `CONFIDENCE_TOO_LOW` | 分析完成但置信度 < 阈值 | 200 | 否（显示 UI 警示）|
| `LLM_TIMEOUT` | LLM 超时 | 504 | 是，退避重试 |
| `TOOL_FAILED` | Tool 执行失败 | 502 | 视具体 Tool |
| `SAFETY_REJECTED` | Safety Policy 否决 | 403 | 否 |
| `HITL_REQUIRED` | 需用户当次拍板 | 202 | 用户审批后继续 |
| `QUOTA_EXCEEDED` | 成本 / rate limit 超限 | 429 | 是，退避 |

### 3.3 事件规范（Agent 订阅 / 发布）

**订阅（EventBus 入）**：

| 事件类型 | 来源 | 用途 |
|---------|------|------|
| `data.hot_coin_update` | HotCoinManager | 触发信号策略 evaluate |
| `data.hot_coin_entered` | 同上 | 新进榜推送 |
| `data.hot_coin_exited` | 同上 | 退榜通知 |
| `data.pump_snapshot` | PumpCollector | pump 策略 evaluate |
| `data.kol_signal` | KOLTracker | KOL 策略 evaluate |
| `data.smart_money_tx` | SmartMoneyTracker | 聪明钱策略 evaluate |
| `market.regime_change` | RegimeDetector | 调整仓位 / 风控倍数 |
| `position.price_tick` | PriceFeed | 止盈止损评估 |

**发布（EventBus 出）**：

| 事件类型 | 订阅者 | 负载 |
|---------|-------|------|
| `agent.thesis_generated` | UI / audit log | thesis + trace_id |
| `agent.strategy_triggered` | ActionDispatcher | strategy_id + signal_context |
| `agent.trade_decision` | RiskManager → Executor | decision + amount + risks |
| `agent.hitl_requested` | Notification → UI | pending_approval_id |
| `agent.reflection_done` | UI | rules_proposed[] |

---

## 4. Loops（4 条核心循环）

### 4.1 Scout Loop（扫描 / 信号触发）

**目的**：用户策略的条件评估 —— "这条策略该不该触发？"

| 项 | 值 |
|----|---|
| 触发方式 | **Event-Driven**（EventBus 订阅）|
| 频率 | 无固定，随事件即时触发，毫秒级 |
| 输入 | EventBus event（hot_coin_update / pump_snapshot / ...）|
| 输出 | 是否触发某条 signal_strategy → 若触发，发布 `agent.strategy_triggered` |
| 涉及组件 | EventListener → RuleEngine → StrategyManager |
| 延迟目标 | P95 < 200ms（事件进入到条件评估完成）|

**伪代码**：
```python
async def on_event(event):
    for strategy in active_strategies_matching(event.type):
        if in_cooldown(strategy): continue
        if rule_engine.evaluate(strategy.conditions, event.payload):
            if daily_trigger_count(strategy) >= strategy.limit: continue
            publish("agent.strategy_triggered", strategy, event)
            record_cooldown(strategy)
```

**L1 规则引擎即可满足**（无 LLM），成本 $0。

### 4.2 Thesis Loop（分析 / 生成决策）

**目的**：用户 chat 问"分析 XXX" 或 strategy_triggered 需决策时

| 项 | 值 |
|----|---|
| 触发方式 | 用户请求 OR `agent.strategy_triggered` |
| 频率 | 按需 |
| 输入 | token + chain + 用户意图 |
| 输出 | Thesis（direction / entry / stop / target / conviction / risks / summary）|
| 延迟目标 | L2 < 5s（P95），L3 < 15s（P95）|

**分级（来自现有 multi_role_orchestrator）**：

| 级别 | 触发条件 | 流程 | 模型 | 成本 |
|------|---------|------|------|------|
| **L1** | 简单查询 / 已决定 | RuleEngine | 无 LLM | $0 |
| **L2** | 常规分析 | 单 prompt + tool-use | **Opus** | **~$0.025** |
| **L3** | 大额（>$200）/ 低置信度（<0.6）/ CRISIS regime / 新策略首笔 | 3 分析师并行 + Bull vs Bear 3 轮辩论 + RiskReviewer | **3×Opus + 5×Opus + 1×Opus** | **~$0.35** |

**L3 伪代码**：
```python
async def thesis_l3(token, context):
    reports = await asyncio.gather(
        technical_analyst(token),
        sentiment_analyst(token),
        onchain_analyst(token),
    )  # ~3s Opus 并行（3 个分析师）
    past = recall_memory(situation=context)  # T12
    debate = await run_debate(reports, past)  # 5 × Opus 串行 ~12s
    decision = decision_agent.decide(debate, past, regime)  # 规则
    review = await risk_reviewer.review(decision)  # Opus ~3s
    return thesis_from(debate, decision, review)
```

### 4.3 Notify Loop（执行 / 推送）

**目的**：策略触发后实际执行（paper / notify / auto）

| 项 | 值 |
|----|---|
| 触发方式 | `agent.strategy_triggered` 事件 |
| 频率 | 随事件 |
| 输入 | trade_strategy + signal_context + thesis |
| 输出 | 写入 `hot_sim_trades`（paper）/ push 通知 / 真金 DEX swap |
| 延迟目标 | 推送 < 1s；paper 建仓 < 2s；真金 quote < 3s |

**决策链路**：
```
strategy_triggered
  → RiskManager（9 项检查）
  → is_auto_authorized? + amount_within_limits?
  → HITL required? ──yes──▶ 写入 pending_approvals → 推送用户
  │                 │
  │                 no
  ▼
mode:
  paper       → PaperEngine.open_position
  notify_only → 只推送通知
  auto        → DexRouter.swap
```

### 4.4 Reflect Loop（反思 / 复盘）

**目的**：生成 insight + 规则提议，写入 Semantic Memory

| 项 | 值 |
|----|---|
| 触发方式 | 每日 UTC 20:00 cron + 累计 10 笔闭仓 + 紧急（单笔 < -25%）|
| 频率 | 1-3 次 / 天 |
| 输入 | 当日交易 + episodic memory + 策略统计 |
| 输出 | 复盘报告 + 2-3 条 rule_proposals（待用户采纳）|
| 延迟目标 | 后台 < 30s |

**伪代码**：
```python
async def reflect(period="daily"):
    trades = query_closed_trades(period)
    episodes = episodic_memory.top_relevant(trades)
    report = sonnet_call(reflection_prompt, trades, episodes)
    rules = parse_rule_proposals(report)
    save(report, pending=rules)
    publish("agent.reflection_done", report_id)
```

---

## 5. Decision Grading（L1 / L2 / L3 分级规则）

### 5.1 升级条件（任一满足即升级）

| 当前级别 | 升级到 | 触发条件 |
|---------|-------|---------|
| L1 → L2 | | 需要文本 thesis（chat / thesis UI）|
| L2 → L3 | | 任一：amount > $200 / conviction < 0.6 / regime == CRISIS / 新策略首 3 笔 / 陌生代币（< 24h 且无 memory） |
| 任何 → HITL | | amount > $500 真金 / 同链集中度 > 50% / 连续亏损 ≥ 3 笔 |

### 5.2 降级条件（提前结束）

- 数据不足 → 直接返回 `DATA_INSUFFICIENT`，不升级
- Safety 否决 → 直接返回 `SAFETY_REJECTED`
- 成本预算紧张 → L3 降级为 L2（发 warning）

### 5.3 成本与延迟预算

| 级别 | 延迟 P95 | 成本 / 次 | 日预算占比 |
|-----|---------|----------|----------|
| L1  | < 200ms | $0       | - |
| L2  | < 6s    | ~$0.025  | ≤ 20% |
| L3  | < 18s   | ~$0.35   | ≤ 60% |
| Reflect | < 40s | ~$0.15 / 日 · $0.40 / 周  | ≤ 20% |

详见 [13 Cost Budget](./13-cost-budget.md)。

---

## 6. Memory Architecture

### 6.1 三层记忆

| 层 | 存储 | TTL | 写入者 | 读取者 | 条数上限 |
|----|------|-----|-------|-------|---------|
| **Working** | 进程内（session）| 单次会话 | 所有 | 所有 | 无（但压上下文）|
| **Episodic** | `agent_memory` (type=episodic) | 14-30 天 | 每次 thesis/trade | T12 recall_memory | 相关性 Top-N |
| **Semantic** | `agent_memory` (type=semantic) | 30 天未匹配则废弃 | ReflectionEngine + 用户 | L2/L3 prompt 注入 | ≤ 50 条活跃 |

### 6.2 Semantic 规则晋升

反思产生的 rule_proposal **不直接生效**，需满足：
1. 用户点"采纳"（T19 approve_rule）
2. 或连续 3 次反思提出同条规则 + ≥ 5 笔样本 + 胜率领先 15%（自动晋升）

### 6.3 Memory 的 Tool 接口

- `T12 recall_memory(situation, top_k=3)` → 相关 episodic / semantic 条目
- 写入在 Loop 内部，不暴露为 Tool

详见 [07 Memory & Learning](./07-memory-learning.md)。

---

## 7. State Machine

### 7.1 Agent 全局状态

**现状**：状态分散在多张表（agent_strategies.status / agent_executions.status / ...）。
**v1 要做**：显式化为统一 state enum。

```
       ┌─────────────┐
       │  IDLE       │
       │  空闲       │◀───────────────────────────────────┐
       └──────┬──────┘                                    │
              │ event / user_request                      │
              │ 事件 / 用户请求                           │
              ▼                                           │
       ┌─────────────┐                                    │
       │  SCANNING   │  rule no match                     │
       │  扫描       │── 规则未命中 ──────────────────────┤
       └──────┬──────┘                                    │
              │ rule match OR user ask analysis           │
              │ 规则命中 或 用户请求分析                  │
              ▼                                           │
       ┌─────────────┐                                    │
       │  ANALYZING  │  data insufficient                 │
       │  分析        │── 数据不足 ────────────────────────┤
       └──────┬──────┘                                    │
              │ thesis ready / 分析完成                   │
              ▼                                           │
       ┌─────────────┐                                    │
       │  RISK_CHECK │  rejected                          │
       │  风控       │── 风控拒绝 ────────────────────────┤
       └──────┬──────┘                                    │
              │                                           │
      ┌───────┴────────┐                                  │
      ▼                ▼                                  │
 ┌─────────────┐  ┌───────────────────┐                   │
 │  EXECUTING  │  │ AWAITING_APPROVAL │  timeout / 超时   │
 │  执行       │  │ 待授权 (HITL)     │── reject / 拒绝 ──┤
 │ (paper/auto)│  └─────┬─────────────┘                   │
 └──────┬──────┘        │ user approve                    │
        │               │ 用户通过                        │
        │               ▼                                 │
        │        ┌─────────────┐                          │
        │        │  EXECUTING  │                          │
        │        │  执行       │                          │
        │        └──────┬──────┘                          │
        │               │                                 │
        └───────────────┴───────────────┐                 │
                                        ▼                 │
                              ┌─────────────┐             │
                              │ MONITORING  │             │
                              │ 持仓监控    │             │
                              └──────┬──────┘             │
                                     │ closed / 平仓      │
                                     ▼                    │
                              ┌─────────────┐             │
                              │ REFLECTING  │─────────────┘
                              │ 反思        │
                              └─────────────┘

       横切状态 / Cross-cutting state：
       BLOCKED 熔断（Kill Switch）可从任何状态进入
       Can be entered from any state.
```

### 7.2 状态列表（State List）

| State 状态 | 含义 Meaning | 允许行为 Allowed Actions | 表达位置 Persisted At |
|-----------|-------------|------------------------|---------------------|
| `IDLE` 空闲 | 等待事件 / 请求 | 订阅事件 Subscribe events | 默认 Default |
| `SCANNING` 扫描 | 规则评估中 Rule eval | RuleEngine | 极短 ms 级 Ephemeral |
| `ANALYZING` 分析 | LLM 分析中 LLM in flight | Tool 调用 Tool calls | `agent_executions.state='analyzing'` |
| `RISK_CHECK` 风控 | 9 项风控检查 9 risk checks | RiskManager | 同上 Same as above |
| `AWAITING_APPROVAL` 待授权 | 等待 HITL Waiting for HITL | 用户决策 User decision | `pending_approvals` 表（v1 新建 new in v1）|
| `EXECUTING` 执行 | 下单中 Placing order | swap / paper_open | `agent_executions.status='pending'` |
| `MONITORING` 持仓监控 | 持仓跟踪 Position tracking | 止盈止损 TP/SL check | `agent_paper_trades.status='open'` / `agent_executions.status='confirmed'` |
| `REFLECTING` 反思 | 反思生成中 Reflection in flight | LLM call + memory write | `reflection_jobs` 表（v1 新建 new in v1）|
| `BLOCKED` 熔断 | Kill Switch / 熔断器 Circuit breaker | 只响应解除命令 Unblock only | `agent_global_state.status='blocked'`（v1 新建 new in v1）|

### 7.3 非法转移（必须报错 / Illegal Transitions · Must Reject）

- `IDLE` → `EXECUTING`（跳过 ANALYZING / skipping ANALYZING）❌
- `EXECUTING` → `AWAITING_APPROVAL`（执行中不能再审批 / cannot approve mid-execution）❌
- `BLOCKED` → 任何状态（除 admin 手动解除 / admin manual unblock only）❌

---

## 8. Failure Modes（失败模式）

### 8.1 故障矩阵

| 失败类型 | 检测方式 | 降级行为 | 告警级别 | 状态转移 |
|---------|---------|---------|---------|---------|
| **LLM 超时**（>10s）| timeout 捕获 | 退避重试 1 次 → 失败则返回默认 thesis（conviction=0.3 hold）| P2 | → IDLE |
| **LLM rate limit** | 429 响应 | 退避 + fallback 降级链（Opus → Sonnet → Haiku，UI 显性标"降级模式"）| P2 | 继续 |
| **Tool 执行失败** | 异常 / 非 2xx | 重试 1 次 → 返回 TOOL_FAILED | P1 | → IDLE |
| **数据不可用**（代币 < 1h / 数据缺失）| 预检查 | 返回 DATA_INSUFFICIENT，不启动 LLM | P3 | → IDLE |
| **Memory 读取失败** | DB 异常 | 降级为无 memory 的分析（记 P2 告警）| P2 | 继续 |
| **Safety 否决** | SafetyPolicy.evaluate() | 终止决策，写入 audit | P1 | → IDLE |
| **DEX swap 失败** | tx 失败 / 签名失败 | 重试 1 次 → 推送用户 + 记录 | **P0** | → IDLE（不回滚已花 gas）|
| **Helius WS 断连** | heartbeat | 切 P2 API（OKX/Gecko）+ UI 显性降级提示 | **P0** | 继续但标 degraded |
| **EventBus 积压**（queue > 80%）| 监控 | 丢弃 P1 数据类事件，保留 market.regime_change | P1 | 继续 |
| **成本超日预算** | 成本累加器 | L3 自动降为 L2，新 L2 排队 | P1 | 继续 |
| **熔断触发**（连续亏 3 笔 / 日累亏 > 阈值）| RiskManager | 全局 BLOCKED 60min | **P0** | → BLOCKED |

### 8.2 降级不可静默原则

**所有降级必须可见**：
- UI 显示 "🔴 延迟模式"（Helius 断连时）
- UI 显示 "⚠️ 分析降级"（L3→L2）
- UI 显示 "🛑 Agent 已暂停"（BLOCKED）
- 日复盘中列出当天所有降级事件

### 8.3 Kill Switch

- UI 一键关闭所有真金执行（影响范围 < 10s）
- Admin 可全局 BLOCK（调用 `/api/admin/agent/block`）
- 所有 DEX swap 前检查 `agent_global_state.status`，BLOCKED 则终止

---

## 9. Tool Integration Contract

### 9.1 Tool 调用协议

**v1 硬规定**：所有 LLM 的外部动作**必须**走 Anthropic Tool Use 协议。
- ❌ 不允许 "prompt 里让模型输出 JSON + regex 解析" （当前 llm_parser 以外的调用方式，属技术债）
- ✅ 所有 tool 定义集中在 [05 Tool Catalog](./05-tool-catalog.md)

### 9.2 Tool 分类（来自 03 PRD）

| 类别 | Tool | 调用 Loop |
|------|------|---------|
| 查询类 | T01-T03 | Thesis / Chat |
| 分析类 | T04-T06 | Thesis Loop |
| 记忆类 | T12 | Thesis Loop / Reflect Loop |
| 策略类 | T07, T08, T13-T16 | Chat / Scout |
| 执行类 | T09 (paper), T15-T16 (trade) | Notify Loop |
| 回测类 | T10 | 用户按需 |
| 复盘类 | T11, T17-T19 | Reflect Loop |

### 9.3 Tool 成本 / 延迟 SLA

每个 Tool 在 [05 Tool Catalog](./05-tool-catalog.md) 必须声明：`p95_latency_ms` / `cost_per_call` / `failure_mode` / `idempotent?`。

---

## 10. Evaluation Hooks

### 10.1 每个 Loop 的 Eval 要求

| Loop | Eval 类型 | 门槛 |
|------|----------|------|
| Scout Loop | Unit: RuleEngine + Integration: 策略触发 golden 50 条 | 100% 命中 |
| Thesis Loop | Agentic Eval: 100 代币 golden + Trajectory Eval 20 条 | 结构完整度 ≥ 95% / 事实准确度 ≥ 90% |
| Notify Loop | Integration: 模拟触发 → 执行 → 记账 | 0 错账 |
| Reflect Loop | Unit: 规则 dedupe + LLM-as-judge 100 条 | 有效建议比 ≥ 60% |

### 10.2 Regression 门槛

PR 改动 agent/ 下代码 → 自动触发对应 Eval。失败不得合入。详见 [09 Eval Plan](./09-eval-plan.md)。

---

## 11. Agent 与其他系统的边界

| 外部系统 | 关系 | Agent 不做什么 |
|---------|------|--------------|
| **APP 热币 Tab** | 作为 Agent 数据源 | 不替代它做官方推送 |
| **APP 聪明钱 Tab** | 作为 Agent 数据源 | 不篡改聪明钱榜单 |
| **APP 新币 Tab（pump）** | 作为 Agent 数据源 | 不替代 pump 扫描器 |
| **Signal Collector / SmartMoneyTracker / HotCoinManager** | 上游，发布事件 | Agent 只消费，不改其逻辑 |
| **DexRouter** | 下游，执行真金 | 所有真金路由走它，Agent 不直连 RPC 下单 |
| **PaperEngine** | 下游，执行模拟盘 | 同上 |
| **AI Optimizer Agent**（已有的策略优化器）| 姐妹系统 | Agent 交易 Loop 与策略优化 Loop 独立；优化器只读 Agent 数据做回测 |
| **KOL Tracker** | 上游数据 | Agent 不评估 KOL 可信度（用 kol_signals 现有 score）|

---

## 12. Versioning

### 12.1 版本号规则

`agent-v{major}.{minor}.{patch}`

- **major**：改动 Loop 结构 / 状态机 / 公开 API 契约
- **minor**：新增能力 / Tool / Memory 类型
- **patch**：bug fix / prompt 微调 / 参数调整

### 12.2 灰度机制

| 流量 | 适用 |
|------|------|
| Canary（5%）| 内部账号 + 种子用户 opt-in |
| Beta（25%）| 无 SEV-1 持续 48h 后 |
| GA（100%）| Beta 7d 无 SEV-2 + 关键指标不退化 |

### 12.3 版本并存

- **Prompt 级**：A/B 分桶（详见 [08 Prompt Library](./08-prompt-library.md)）
- **Agent 级**：同一时间只允许 1 个 active major + 1 个 canary major
- **Tool 级**：允许 tool v1 / v2 并存，每次调用声明版本（[05 Tool Catalog](./05-tool-catalog.md)）

### 12.4 回滚机制

- 每次 deploy 保留前 3 版 Agent 镜像
- 关键指标退化（思考成本翻倍 / 胜率跌 10pct / P95 延迟翻倍）自动告警 + 一键回滚
- 详见 [11 Launch Criteria & HITL](./11-launch-criteria-hitl.md)

---

## 13. 现状 vs 本 Spec 的 Gap（v1 要补齐的）

基于代码现状盘点（见 Change Log），当前实现与本 Spec 的 gap：

| # | Gap | 影响 | 解决方式 |
|---|-----|------|---------|
| G1 | **Tool Use 未统一** | 除 llm_parser 外仍用 prompt + regex | v1 重构所有 LLM 调用为 Anthropic Tool Use |
| G2 | **HITL 队列缺失** | 大额/低置信度直接拒绝，无 pending | v1 新建 `pending_approvals` 表 + UI |
| G3 | **State Machine 分散** | 状态散在 4+ 表，无全局视图 | v1 新建 `agent_global_state` + 统一 state enum |
| G4 | **Memory 内存缓存** | 进程重启丢活跃规则 | v1 改为 Redis 缓存 + DB 持久化 |
| G5 | **Observability 基础** | 只有 logger，无 trace | v1 接 Langfuse / OpenTelemetry（[15 Observability](./15-observability-tracing.md)）|
| G6 | **Eval 套件未建** | prompt 改完无数据反馈 | v1 跑通 Agentic Eval + Regression ([09 Eval Plan](./09-eval-plan.md)) |
| G7 | **Cost Budget 未硬约束** | 成本累加器无熔断 | v1 加日预算硬上限 + L3→L2 自动降级 |
| G8 | **HITL 默认策略** | 真金首笔 / >$500 无 HITL 门槛 | v1 写入 Safety Policy |
| G9 | **降级不可见** | Helius 断连用户无感 | v1 UI "延迟模式" 标识 |
| G10 | **旧 30s 轮询代码未废弃** | 违反 Event-Driven First | v1 审计并删除 monitor_job 部分职能 |

---

## 14. 验收 Gate（本 Spec 对应的 Launch Criteria）

本 Spec v1 ready 的硬门槛：

- ✅ 13 个 gap 全部关闭
- ✅ 4 条 Loop 都有 golden eval 通过（[09](./09-eval-plan.md)）
- ✅ 状态机所有非法转移 100% rejected（[09 Eval](./09-eval-plan.md)）
- ✅ 所有失败模式有对应 runbook（[12 Incident Response](./12-incident-response.md)）
- ✅ Kill Switch 1 键关闭 < 10s
- ✅ 成本预算 + HITL 阈值写入 [06 Safety](./06-safety-alignment.md)
- ✅ 观测覆盖所有 Tool 调用 + Loop 入口

---

## Change Log

- **v0.1 (2026-04-23)**：首版完整填充
  - § 1 Identity：Mission / Role / 7 大 Competencies（C1-C7）/ Limits / Personality
  - § 2 架构图：User Surface → Orchestration → Tool/Data → Event Infrastructure 4 层
  - § 3 API & Error Model：Chat / Strategy CRUD / HITL / Review 4 类入口
  - § 4 4 条 Loop（Scout event-drv / Thesis on-demand / Notify event-drv / Reflect cron）
  - § 5 L1/L2/L3 Decision Grading + 成本/延迟预算
  - § 6 Memory 三层 + 晋升规则
  - § 7 **显式 State Machine**（9 状态 + 非法转移）—— 针对现状分散做的规范化
  - § 8 失败模式矩阵 11 项 + 降级不可静默原则 + Kill Switch
  - § 9 Tool Use 协议 v1 硬规定
  - § 10 每 Loop 对应 Eval
  - § 11 与外部系统 8 条边界
  - § 12 Versioning + 灰度 + 并存 + 回滚
  - § 13 **13 条 Gap**（v1 要补齐的）
  - § 14 Launch Gate
- v0（2026-04-22）：骨架创建
