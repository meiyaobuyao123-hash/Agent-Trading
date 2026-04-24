# 05 Skills & Tools Catalog（harness 核心）

> Agent 所有能力的**分层**清单：**Skills（能力 / 工作流）** + **Tools（原子操作）**。
> 每个都必有 **schema + eval + owner + version**。Skill 可以调用 Tool；Tool 不能调用 Skill。

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.1 Draft |
| Version | v0.1 |
| Owner | 产品负责人 |
| Target Release | v1 MVP - 2026 Q3 |
| Total Skills / Tools | **7 Skills + 12 Tools** |

---

## 0. 为什么要区分 Skill 和 Tool

### 0.1 概念区分（Anthropic 范式）

| 维度 | **Tool** | **Skill** |
|------|---------|----------|
| **本质** | 单次函数调用 | 能力 / 工作流 封装 |
| **LLM 参与** | ❌ 不需要 LLM | ✅ LLM 是执行引擎 |
| **确定性** | 确定（同输入 → 同输出）| 不确定（含推理）|
| **范围** | 原子操作 | 多步骤 / 领域知识 |
| **加载方式** | 始终在 system prompt | 按需加载（progressive disclosure）|
| **编码形式** | 代码函数 + JSON Schema | `SKILL.md` + prompts + 资源 |
| **调用协议** | Anthropic `tool_use` API | prompt 方式激活（或 `skill_use`）|
| **典型例子** | `SELECT FROM db` / HTTP GET | "写一份技术面分析报告" / "做一次周复盘" |

### 0.2 判断框架（新增能力时走这个决策树）

```
新增能力 X
    ↓
X 是否需要 LLM 做判断 / 推理 / 文本生成？
    ├── 否 → X 是 Tool
    └── 是 ↓
           X 是否包含领域知识（如 "RSI 怎么算" / "什么是好 insight"）？
           ├── 否，只是 prompt 一次 LLM → 可以用 Tool + prompt 参数
           └── 是 ↓
                  X 是否多步骤 / 涉及文件 / 模板？
                  ├── 否 → 放在 prompt library（§ 08），不是独立 Skill
                  └── 是 → X 是 Skill
```

### 0.3 组合规则

**强约束**：
1. ✅ Skill **可以** 调用多个 Tool
2. ✅ Skill **可以** 调用其他 Skill（层级 ≤ 2，避免深嵌套）
3. ❌ Tool **不得** 调用 Skill（Tool 是叶子）
4. ❌ Tool **不得** 调用 LLM（否则它应该是 Skill）
5. ✅ 每次 Skill 激活 = 一次 LLM 调用（或多次），必须记录 trace
6. ✅ 每次 Tool 调用 = 一次函数执行，无 LLM 成本

### 0.4 与 03 PRD / 04 Agent Spec 的映射

- 本 doc 的 **Skills** = [04 Agent Spec § 1.3](./04-agent-spec.md#13-competencies核心能力--对齐-prd-6-大能力) 的 **C1-C7 核心能力**的具体实现
- 本 doc 的 **Tools** = 原 [03 PRD v0.3](./03-prd.md) "T01-T19 Tool 映射"中的**原子部分**
- v0.4 起，PRD 里的"T04 analyze_technical" → 正式改写为 **S01 technical-analysis**（Skill）
- PRD v0.5 同步更新编号映射

---

## 1. Skills Inventory（7 个能力级 Skill）

| ID | Skill Name | Category | Calls (Tools + Sub-Skills) | Status | Owner | Version |
|----|-----------|----------|---------------------------|--------|-------|---------|
| **S01** | `technical-analysis` | Analysis | T01 + T03 | 🟢 Spec 就绪 | - | v0.1 |
| **S02** | `sentiment-analysis` | Analysis | T01 + KOL 数据 | 🟢 | - | v0.1 |
| **S03** | `onchain-analysis` | Analysis | T01 + T02 + T03 | 🟢 | - | v0.1 |
| **S04** | `signal-strategy-builder` | Authoring | S06 (dry-run) + T04 (memory) + T12 (save) | 🔴 核心 | - | v0.1 |
| **S05** | `trade-strategy-builder` | Authoring | T10 + T12 | 🟠 | - | v0.1 |
| **S06** | `backtest-runner` | Evaluation | T01 + T02 + T03（纯数据查询）| 🟠 | - | v0.1 |
| **S07** | `review-engine` | Reflection | T04 + T10 + T05 | 🟠 | - | v0.1 |

**Skills 的性质**：
- 均用 **Claude Opus** 作为推理引擎（v1 质量优先，见 [03 PRD § 8.8.0](./03-prd.md#880-模型分层决策v1-采用质量优先方案)）
- 均需 golden dataset（≥ 50 案例）
- Skill 的 `SKILL.md` 文件路径：`services/pump-scanner/agent/skills/<skill_name>/SKILL.md`

---

## 2. Tools Inventory（12 个原子操作）

| ID | Tool Name | Category | I/O Type | Status | Owner | Version |
|----|-----------|----------|----------|--------|-------|---------|
| **T01** | `query_market` | Query | read | 🟢 | - | v0.1 |
| **T02** | `query_holders` | Query | read | 🟢 | - | v0.1 |
| **T03** | `query_onchain_activity` | Query | read | 🟢 | - | v0.1 |
| **T04** | `recall_memory` | Memory | read | 🔴 新建 | - | v0.1 |
| **T05** | `list_strategies` | Strategy CRUD | read | 🟢 | - | v0.1 |
| **T06** | `update_strategy_status` | Strategy CRUD | write | 🟢 | - | v0.1 |
| **T07** | `run_paper_trade` | Execution | write | 🟢 | - | v0.1 |
| **T08** | `execute_swap` | Execution | write | 🟠 | - | v0.1 |
| **T09** | `create_approval_request` | HITL | write | 🔴 新建 | - | v0.1 |
| **T10** | `get_paper_performance` | Query | read | 🟢 | - | v0.1 |
| **T11** | `approve_rule` | Memory | write | 🔴 新建 | - | v0.1 |
| **T12** | `save_strategy` | Strategy CRUD | write | 🟢 | - | v0.1 |

**Tools 的性质**：
- 无 LLM 成本（$0）
- 必须幂等（除非明确标 `non_idempotent`）
- 严格 JSON Schema 校验

---

## 3. Skills 详细 Spec

### 3.0 Skill 模板

每个 Skill 的 `SKILL.md` 必有以下 frontmatter：

```yaml
---
name: skill-name
description: 一句话说明 Claude 什么时候应该激活（用于自动匹配）
when_to_use: |
  - 场景 1
  - 场景 2
tools_required: [T01, T03]           # 硬依赖 Tool
sub_skills_allowed: [S06]             # 可选嵌套（≤ 2 层）
model: claude-opus-latest             # v1 固定 Opus
version: 0.1
owner: TBD
---
```

后接正文（含 Role Prompt / Domain Knowledge / Input Contract / Output Contract / Examples / Failure Modes）。

---

### 3.1 S01: technical-analysis

**目的**：对单个代币产出技术面判断（趋势 / 入场区 / 止损位 / 置信度）。

**When to use**：Thesis Loop L2/L3 需要技术面输入；用户 Chat 问"XX 代币技术面怎么样"。

**Input Contract**:
```json
{
  "chain": "solana",
  "address": "0x...",
  "timeframes": ["5m", "1h", "4h", "1d"],
  "context": { "user_persona": "中级" }
}
```

**Output Contract**:
```json
{
  "direction_bias": "bullish | bearish | neutral",
  "trend": {
    "short_term": "up | down | sideways",
    "mid_term": "up | down | sideways"
  },
  "key_levels": {
    "support": [1.10, 0.95],
    "resistance": [1.45, 1.80]
  },
  "indicators": {
    "rsi_1h": 62.5,
    "ma_cross": "golden | death | none",
    "atr_14": 0.08,
    "bb_position": "upper | middle | lower"
  },
  "entry_zone": { "low": 1.10, "high": 1.20 },
  "stop_loss": 0.95,
  "confidence": 0.72,
  "data_gaps": []
}
```

**Domain Knowledge（在 SKILL.md 里封装）**：
- RSI 计算方法 + 超买超卖阈值
- 金叉 / 死叉定义
- ATR 动态止损公式（stop = entry - k × ATR，默认 k=2）
- 支撑阻力识别规则（swing high/low + volume 验证）
- Bollinger Bands 解读

**Tools Called**: `T01 query_market`（拿价格 + K 线）, `T03 query_onchain_activity`（成交量参考）

**Cost**: ~$0.008（Opus ~1K in + 0.3K out）
**Latency P95**: < 4s
**Failure Modes**:
- K 线数据 < 50 根 → 返回 `{data_gaps: ["insufficient_klines"]}`, confidence 0
- 代币 <1h → 拒绝，返回 `DATA_INSUFFICIENT`

**Eval**: 50 条 golden（各链各走势 + 新币 / 老币混合）
**Security**: 只读，无权限需求

---

### 3.2 S02: sentiment-analysis

**目的**：情绪面判断（FOMO / Fear / 中性），含 KOL / 社交 / 恐贪指数。

**Input Contract**:
```json
{ "chain": "solana", "address": "0x...", "period": "24h" }
```

**Output Contract**:
```json
{
  "sentiment": "euphoria | bullish | neutral | bearish | panic",
  "fomo_score": 0.35,                     // 0-1
  "signals": {
    "kol_mentions_24h": 18,
    "kol_avg_score": 0.72,
    "social_growth_pct": 240,
    "fear_greed_index": 62
  },
  "red_flags": ["KOL 集中喊单", "Twitter 增粉 < 社交提及增长"],
  "confidence": 0.60
}
```

**Domain Knowledge**:
- 恐贪指数判读表
- KOL 喊单质量评估（历史命中率 ≥ 30% 可信）
- "假社交增长"识别（机器人粉丝特征）

**Tools Called**: `T01 query_market`（代币信息）+ 直接读 `kol_signals` / `social_metrics` 表

**Cost**: ~$0.008
**Latency P95**: < 4s

---

### 3.3 S03: onchain-analysis

**目的**：链上行为解读（聪明钱 / 持仓集中度 / 流动性 / 资金流向）。

**Input Contract**:
```json
{ "chain": "solana", "address": "0x..." }
```

**Output Contract**:
```json
{
  "smart_money": {
    "net_flow_usd_24h": 45000,
    "buyer_count_24h": 3,
    "tier_distribution": { "elite": 2, "verified": 1, "watching": 0 }
  },
  "holder_concentration": {
    "top10_pct": 58,
    "risk_level": "low | medium | high"
  },
  "liquidity": {
    "usd": 120000,
    "trend_24h": "+18%",
    "health": "healthy | thin | drained"
  },
  "dev_activity": {
    "dev_wallet_sold_pct_30d": 5,
    "risk": "low | medium | high"
  },
  "overall_signal": "bullish | neutral | bearish | rug_risk",
  "confidence": 0.80
}
```

**Domain Knowledge**:
- 聪明钱 tier 权重
- Top10 持仓集中度阈值（< 50% 健康 / 50-70% 警惕 / > 70% 高危）
- LP 健康度（> $100K 基本健康；trend 掉头 > 20% 告警）
- dev 钱包抛售识别

**Tools Called**: `T01 query_market` + `T02 query_holders` + `T03 query_onchain_activity`

**Cost**: ~$0.008
**Latency P95**: < 4s

---

### 3.4 S04: signal-strategy-builder ⭐ 核心

**目的**：和用户共创一条 Signal Strategy（对话式，非一问一答）。对应 [03 PRD § 3.2.1](./03-prd.md#321-共创流程co-creation-flow)。

**When to use**：用户说"建个策略" / 从模板库点"编辑"进入 / Chat 中提到"我想自动盯盘 X"。

**Input Contract**:
```json
{
  "user_message": "我想做个聪明钱跟单",
  "conversation_id": "uuid",
  "existing_draft": null | { ...strategy JSON },
  "user_profile": { "persona": "中级", "preferred_chains": ["solana"] }
}
```

**Output Contract**（每轮返回）:
```json
{
  "conversation_state": "clarifying | refining | confirming | closed",
  "reply_text": "…（给用户看的自然语言）",
  "draft_strategy": { ...完整 strategy JSON（§ 3.3 PRD Schema）},
  "dry_run_result": {
    "triggers_in_past_30d": 18,
    "simulated_win_rate": 0.48,
    "simulated_ev_pct": 3.5
  } | null,
  "awaiting_user_action": "answer_question | review_draft | confirm_save",
  "ready_to_save": false
}
```

**Domain Knowledge**（`SKILL.md` 包含）:
- 策略条件 schema 完整规范
- 常见意图模板（聪明钱跟单 / BC 早鸟 / KOL 联动 / 涨幅突破 / 低位反弹）
- 澄清提问库（按意图类型分）
- 反例识别（矛盾条件 / 过于宽松 / 过于严格）
- 风险提示（EV 负 / 过拟合疑似）

**Tools / Sub-Skills Called**:
- `T04 recall_memory`（查用户历史偏好）
- **`S06 backtest-runner`**（第 ④ 阶段 dry run）
- `T12 save_strategy`（第 ⑦ 阶段激活）

**Cost**: 平均一次完整共创会话 ~$0.06-$0.10（4-6 次 Opus 调用 + 1 次 backtest）
**Latency**: 每轮 < 6s
**Failure Modes**:
- NL 无法解析意图 → 进入澄清模式，反复追问
- dry run EV < 0 → **主动警告** + 建议调参，不允许静默保存
- 用户超 20 条策略 → 阻止保存 + 提示

**Eval**: 100 条 golden 对话轨迹（见 [16 Trajectory Eval](./16-trajectory-eval.md)）
**Security**: 保存前强制 § 4.2 schema 校验

---

### 3.5 S05: trade-strategy-builder

**目的**：和用户共创一条 Trade Strategy（在 S04 基础上，绑定执行参数）。

**When to use**：用户建完 Signal Strategy 后选"加交易执行" / Chat 里说"让 X 策略自动下单"。

**Input Contract**:
```json
{
  "signal_strategy_id": "uuid",
  "user_message": "触发后买 $100，-15% 止损，+50%+100% 分批止盈",
  "conversation_id": "uuid",
  "existing_draft": null
}
```

**Output Contract**:
```json
{
  "conversation_state": "clarifying | refining | confirming",
  "reply_text": "…",
  "draft_trade_strategy": { ...§ 4.9 PRD Schema },
  "risk_preview": {
    "max_drawdown_pct": 20,
    "per_trade_max_loss_usd": 15,
    "hitl_required": true,
    "reasons_for_hitl": ["单笔 > $500"]
  },
  "ready_to_save": false
}
```

**Domain Knowledge**:
- 止盈止损模板（保守 / 稳健 / 激进）
- 追踪止损 / ATR 止损适用场景
- 分批止盈策略（Kelly 近似）
- paper → notify → auto 晋升路径（§ 5.4 PRD）

**Tools Called**: `T10 get_paper_performance` + `T12 save_strategy`

**Cost**: ~$0.05 / 会话
**Latency**: < 6s / 轮

---

### 3.6 S06: backtest-runner

**目的**：在历史数据上跑一遍策略，产出完整报告。

**When to use**：
- 用户点"回测"按钮
- S04/S05 在策略创建流程中调用（dry run）
- Reflect Loop 检测策略退化时自动触发

**Input Contract**:
```json
{
  "strategy_snapshot": { ...完整 signal + trade strategy JSON },
  "period_days": 30,
  "chains": ["solana"],
  "compare_to": ["hold_sol"] | null
}
```

**Output Contract**：完整的 [§ 6.7 PRD Backtest Schema](./03-prd.md#67-backtest-结果完整-schema)

**Domain Knowledge**:
- 过拟合检测规则（胜率 > 80% + 样本 < 50 → 告警）
- 样本不足判定（< 20 笔 → 降信心度）
- Walk-forward 触发条件
- Benchmark 选择（SOL / ETH / 同 category 代币）

**Tools Called**: `T01` / `T02` / `T03`（历史数据） —— 注意**只读 DB，无 LLM**，除了最后生成 "warnings" 文本用 Opus

**Cost**: ~$0.01（只有最后解读阶段用 Opus，主体是纯计算）
**Latency P95**: < 30s（30 天窗口）
**Failure Modes**:
- 数据 < 7 天 → 拒绝，返回 `INSUFFICIENT_HISTORY`
- 超时 → 返回部分结果 + 标记 `partial=true`

**Eval**: 30 条 golden（各类策略 × 各类行情）

---

### 3.7 S07: review-engine

**目的**：生成日 / 周 / 月复盘 + insight + 规则提议。对应 [03 PRD § 7](./03-prd.md#7-review策略复盘)。

**When to use**：Reflect Loop cron 触发（日 UTC 23:55 / 周日 / 月 1）+ 紧急触发（单笔 < -25%）+ 累计 10 笔闭仓。

**Input Contract**:
```json
{
  "device_id": "uuid",
  "period": "daily | weekly | monthly",
  "period_range": { "from": "2026-04-17", "to": "2026-04-23" },
  "trigger": "cron | threshold | user_request"
}
```

**Output Contract**：完整的 [§ 7.7 PRD Review Schema](./03-prd.md#77-review-报告完整-schema)（含 summary / strategy_rankings / insights / rule_proposals / degradation_events）

**Domain Knowledge**:
- 好 insight vs 坏 insight 示例库（§ 7.5 PRD 里的示例 = Few-shot）
- 规则提议格式规范
- 退化检测算法（近 N 笔 vs 前 N 笔 胜率对比）
- Persona 差异化 tone（小白 / 中级 / 专业）
- 冷启动处理（5 种状态 § 7.8 PRD）

**Tools / Sub-Skills Called**:
- `T04 recall_memory`（查历史 episodic）
- `T10 get_paper_performance`（查策略表现）
- `T05 list_strategies`（当前活跃策略）
- 可选调用 **S06 backtest-runner**（发现策略退化时主动 walk-forward）

**Cost**: 日 ~$0.15 / 周 ~$0.40 / 月 ~$1.00
**Latency P95**: < 40s（后台任务，不阻塞用户）
**Failure Modes**:
- 交易数据 < 5 笔 → 走"冷启动简化版"
- Insight LLM-as-judge 打分 < 0.5 → 丢弃该 insight
- 规则提议用户连续拒绝 > 3 次同类 → 下次不再提议该类

**Eval**: 100 条 golden（各 Persona × 各交易表现）+ LLM-as-judge（每条 insight 打分）

---

## 4. Tools 详细 Spec

### 4.0 Tool 模板

```json
{
  "name": "tool_name",
  "description": "一句话描述用途（用于 LLM tool_use 匹配）",
  "input_schema": { /* JSON Schema */ },
  "output_schema": { /* JSON Schema */ },
  "idempotent": true | false,
  "side_effects": "none | db_write | external_api",
  "p95_latency_ms": 200,
  "cost_usd": 0,
  "failure_modes": [...],
  "owner": "...",
  "version": "0.1"
}
```

---

### 4.1 T01: query_market

```json
{
  "name": "query_market",
  "description": "查询单个代币的完整实时行情（价格/MC/LP/涨幅/风险/社交）。",
  "input_schema": {
    "type": "object",
    "properties": {
      "chain": { "enum": ["solana", "eth", "bsc", "base"] },
      "address": { "type": "string", "pattern": "^(0x[a-fA-F0-9]{40}|[1-9A-HJ-NP-Za-km-z]{32,44})$" },
      "include": { "type": "array", "items": { "enum": ["klines", "holders_top10", "recent_txs"] } }
    },
    "required": ["chain", "address"]
  },
  "output_schema": "参见 03 PRD § 1.2 功能需求 + Thesis evidence 格式",
  "idempotent": true,
  "side_effects": "none",
  "p95_latency_ms": 500,
  "cost_usd": 0,
  "failure_modes": [
    "TOKEN_NOT_FOUND（4 链均无）",
    "CHAIN_MISMATCH（地址与链不符）",
    "UPSTREAM_DEGRADED（Helius 断连 / OKX 超时，返回缓存 + `degraded: true`）"
  ],
  "data_sources": "P0 事件流聚合 + P2 DexScreener 兜底（按 § 0.7 PRD 优先级）"
}
```

---

### 4.2 T02: query_holders

```json
{
  "name": "query_holders",
  "description": "查询代币 Top N 持仓钱包 + 集中度。",
  "input_schema": {
    "type": "object",
    "properties": {
      "chain": { "enum": ["solana", "eth", "bsc", "base"] },
      "address": { "type": "string" },
      "top_n": { "type": "integer", "default": 10, "maximum": 100 }
    },
    "required": ["chain", "address"]
  },
  "idempotent": true,
  "p95_latency_ms": 800,
  "cost_usd": 0,
  "data_sources": "hot_coin_top_holders 表 + Helius enhanced TX 兜底",
  "failure_modes": ["HOLDER_DATA_STALE（> 1h 标 stale）", "RPC_ERROR"]
}
```

---

### 4.3 T03: query_onchain_activity

```json
{
  "name": "query_onchain_activity",
  "description": "查询代币近期链上活动（大额交易 / 聪明钱买卖 / 净流入流出）。",
  "input_schema": {
    "type": "object",
    "properties": {
      "chain": "...",
      "address": "...",
      "period": { "enum": ["1h", "24h", "7d"] },
      "min_usd": { "type": "number", "default": 1000 }
    },
    "required": ["chain", "address", "period"]
  },
  "idempotent": true,
  "p95_latency_ms": 400,
  "cost_usd": 0,
  "data_sources": "smart_money_txns + token_trades（P0 事件流落表）"
}
```

---

### 4.4 T04: recall_memory 🔴 新建

```json
{
  "name": "recall_memory",
  "description": "按情境检索历史相似案例 / 语义规则（Episodic + Semantic）。",
  "input_schema": {
    "type": "object",
    "properties": {
      "device_id": { "type": "string" },
      "situation": {
        "type": "object",
        "properties": {
          "chain": "...",
          "token_type": "...",
          "trigger_source": "...",
          "regime": "...",
          "mcap_bucket": "..."
        }
      },
      "types": { "type": "array", "items": { "enum": ["episodic", "semantic"] } },
      "top_k": { "type": "integer", "default": 3, "maximum": 10 }
    },
    "required": ["device_id", "situation"]
  },
  "output_schema": {
    "memories": [
      { "id": "...", "type": "episodic | semantic", "content": "...", "relevance_score": 0.78, "created_at": "..." }
    ]
  },
  "idempotent": true,
  "p95_latency_ms": 300,
  "cost_usd": 0,
  "data_sources": "agent_memory 表（已有）+ 相关性评分（见 04 Agent Spec § 6.1）"
}
```

---

### 4.5 T05: list_strategies

```json
{
  "name": "list_strategies",
  "description": "列出该 device 的策略（可按 status/mode 过滤）。",
  "input_schema": {
    "type": "object",
    "properties": {
      "device_id": "...",
      "status": { "enum": ["active", "paused", "archived", "all"], "default": "active" },
      "include_performance": { "type": "boolean", "default": false }
    },
    "required": ["device_id"]
  },
  "idempotent": true,
  "p95_latency_ms": 150,
  "cost_usd": 0
}
```

---

### 4.6 T06: update_strategy_status

```json
{
  "name": "update_strategy_status",
  "description": "更改策略状态（pause / resume / archive）。不做软删以外的物理删除。",
  "input_schema": {
    "type": "object",
    "properties": {
      "device_id": "...",
      "strategy_id": "...",
      "new_status": { "enum": ["active", "paused", "archived"] },
      "reason": { "type": "string" }
    },
    "required": ["device_id", "strategy_id", "new_status"]
  },
  "idempotent": true,
  "side_effects": "db_write",
  "p95_latency_ms": 200,
  "cost_usd": 0,
  "non_idempotent_exceptions": "archived 不可 resume（见 § 3.8 PRD）",
  "failure_modes": ["STRATEGY_NOT_OWNED（device 不是主）", "ILLEGAL_TRANSITION"]
}
```

---

### 4.7 T07: run_paper_trade

```json
{
  "name": "run_paper_trade",
  "description": "在策略触发时原子写入 hot_sim_trades + 更新 paper_accounts。",
  "input_schema": {
    "type": "object",
    "properties": {
      "device_id": "...",
      "trade_strategy_id": "...",
      "signal_context": { "...": "触发时的事件 payload" },
      "entry_price_usd": "...",
      "amount_usd": "...",
      "entry_at": "..."
    }
  },
  "idempotent": true,
  "side_effects": "db_write",
  "idempotency_key": "signal_event_id",
  "p95_latency_ms": 300,
  "cost_usd": 0,
  "failure_modes": ["INSUFFICIENT_VIRTUAL_BALANCE", "DUPLICATE_EVENT（幂等已触发，返回已有记录）"]
}
```

---

### 4.8 T08: execute_swap

```json
{
  "name": "execute_swap",
  "description": "真金 DEX swap（Jupiter / OKX aggregator），必须已通过风控 + HITL。",
  "input_schema": {
    "type": "object",
    "properties": {
      "device_id": "...",
      "wallet_address": "...",
      "chain": "...",
      "direction": { "enum": ["buy", "sell"] },
      "token_address": "...",
      "amount_usd": "...",
      "max_slippage_pct": "...",
      "signed_authorization": "..."
    }
  },
  "idempotent": false,
  "side_effects": "external_api + blockchain_tx",
  "p95_latency_ms": 8000,
  "cost_usd": 0,
  "failure_modes": [
    "QUOTE_FAILED",
    "SLIPPAGE_EXCEEDED",
    "WALLET_NOT_CONNECTED",
    "TX_REVERTED（链上失败）",
    "HITL_NOT_APPROVED（尝试绕过）"
  ],
  "pre_conditions": ["authorization.expires_at > now", "amount <= § 4.2 PRD 硬限", "device 在 BLOCKED 状态则拒绝"],
  "post_actions": "写入 agent_executions + 更新 pending_approvals.tx_hash"
}
```

---

### 4.9 T09: create_approval_request 🔴 新建

```json
{
  "name": "create_approval_request",
  "description": "创建一条待用户审批的请求（HITL）。写入 pending_approvals 表 + 触发推送。",
  "input_schema": {
    "type": "object",
    "properties": {
      "device_id": "...",
      "strategy_id": "...",
      "trigger_conditions_matched": ["..."],
      "thesis_id": "...",
      "token": "...",
      "amount_usd": "...",
      "timeout_minutes": { "type": "integer", "default": 15 }
    }
  },
  "output_schema": {
    "approval_id": "...",
    "expires_at": "...",
    "push_sent": true
  },
  "idempotent": true,
  "idempotency_key": "strategy_id + signal_event_id + amount_usd（防重复审批）",
  "side_effects": "db_write + push_notification",
  "p95_latency_ms": 500,
  "cost_usd": 0,
  "failure_modes": ["PUSH_FAILED（仍然写入 DB，依赖用户打开 APP 看到）"]
}
```

---

### 4.10 T10: get_paper_performance

```json
{
  "name": "get_paper_performance",
  "description": "查询某策略（或全部）的模拟盘表现统计。",
  "input_schema": {
    "type": "object",
    "properties": {
      "device_id": "...",
      "strategy_id": { "type": "string", "description": "可选，缺省返回全部策略汇总" },
      "period_days": { "type": "integer", "default": 30 }
    }
  },
  "output_schema": "参见 03 PRD § 5.3 当前 baseline 格式",
  "idempotent": true,
  "p95_latency_ms": 400,
  "cost_usd": 0
}
```

---

### 4.11 T11: approve_rule 🔴 新建

```json
{
  "name": "approve_rule",
  "description": "用户采纳一条规则提议，写入 Semantic Memory。",
  "input_schema": {
    "type": "object",
    "properties": {
      "device_id": "...",
      "rule_proposal_id": "...",
      "user_edits": { "type": "object", "description": "用户可能在采纳前微调文本/参数" }
    },
    "required": ["device_id", "rule_proposal_id"]
  },
  "output_schema": {
    "semantic_rule_id": "...",
    "activated_at": "..."
  },
  "idempotent": true,
  "idempotency_key": "rule_proposal_id",
  "side_effects": "db_write",
  "p95_latency_ms": 300,
  "cost_usd": 0
}
```

---

### 4.12 T12: save_strategy

```json
{
  "name": "save_strategy",
  "description": "原子保存（新建或更新）一条策略；由 S04 / S05 调用。",
  "input_schema": {
    "type": "object",
    "properties": {
      "device_id": "...",
      "strategy_type": { "enum": ["signal", "trade"] },
      "strategy_json": "...",  // § 3.3 / § 4.9 PRD Schema
      "mode": { "enum": ["new", "update"] }
    }
  },
  "output_schema": {
    "strategy_id": "...",
    "version": 3,
    "status": "active"
  },
  "idempotent": false,                  // update 模式生成新 version
  "side_effects": "db_write",
  "p95_latency_ms": 400,
  "cost_usd": 0,
  "validation": "完整 JSON Schema 校验 + 策略数 ≤ 20 硬限 + 条件矛盾检测"
}
```

---

## 5. Composition Rules（组合规则）

### 5.1 典型调用链

**场景 A：用户 Chat "分析 TRUMP"**

```
User Chat
  → Thesis Loop (L2/L3)
      → S01 technical-analysis
            → T01 query_market
            → T03 query_onchain_activity
      → S02 sentiment-analysis
            → T01 query_market
      → S03 onchain-analysis
            → T01 + T02 + T03
      → T04 recall_memory
  → Thesis Writer (Opus)
  → Response to User
```

**场景 B：用户共创新建信号策略**

```
User Chat
  → S04 signal-strategy-builder
      ├─ T04 recall_memory (查历史偏好)
      ├─ [多轮对话澄清]
      ├─ S06 backtest-runner (dry run)
      │     └─ T01 + T02 + T03
      ├─ [用户反馈迭代]
      └─ T12 save_strategy (确认后激活)
```

**场景 C：策略触发执行**

```
EventBus.hot_coin_update
  → Scout Loop (RuleEngine，无 Skill/Tool)
  → Thesis Loop L3 (触发分析)
      → [S01, S02, S03 并行]
      → debate + review
  → RiskManager (9 checks)
  → if HITL needed: T09 create_approval_request
  → else if paper: T07 run_paper_trade
  → else auto: T08 execute_swap
```

**场景 D：日复盘**

```
Cron UTC 23:55
  → Reflect Loop
  → S07 review-engine
      ├─ T05 list_strategies
      ├─ T10 get_paper_performance
      ├─ T04 recall_memory (last 30d episodic)
      └─ [optional] S06 backtest-runner (发现策略退化时)
  → 用户采纳 insight → T11 approve_rule
```

### 5.2 硬约束

1. **Tool 叶子原则**：Tool 不调 LLM、不调 Skill
2. **Skill 嵌套 ≤ 2 层**：S07 可调 S06，但 S06 不应再调 S05
3. **并行优先**：S01 / S02 / S03 三个分析师必须 `asyncio.gather()` 并行
4. **事件驱动优先**：Scout Loop 不使用 LLM 类 Skill，只跑 RuleEngine
5. **真金前置条件硬校验**：T08 execute_swap 前**必须**有对应的 T09 approval_id（除非该策略 authorization 允许免 HITL 的额度区间）

### 5.3 禁止组合

- ❌ Scout Loop 调用任何 Skill（破坏 event-driven 毫秒级要求）
- ❌ 任何 Tool 内部调 LLM
- ❌ S06 backtest 里用 Opus 分析每笔交易（成本爆炸，只在 warnings 文本阶段用）
- ❌ 同一次用户请求内嵌套 > 2 层 Skill

---

## 6. Lifecycle（生命周期）

### 6.1 新增

| 类型 | 提案人 | 必交付物 | 审核人 | 门槛 |
|------|-------|---------|-------|------|
| Tool | 工程师 | schema + 10 golden + owner | Agent 架构师 | 通过 CI |
| Skill | PM + 工程 | SKILL.md + 50 golden + trajectory eval + cost 估算 | 产品 + 架构师 | 通过 CI + Dry-run 对比 |

### 6.2 修改

- **Tool schema breaking 改动** → 新 version（v1 并存 v2，≥ 2 周迁移期）
- **Skill instructions 改动** → 新 version + A/B test 1 周（见 [08 Prompt Library](./08-prompt-library.md)）
- **Skill domain knowledge 改动** → 回跑 golden set，pass rate 不降才可 merge

### 6.3 废弃

- 标 `deprecated=true` + 日志 WARN
- 通知所有调用方（grep + audit）
- 2 周迁移期
- 移除时删除代码 + 保留 schema 历史在 `docs/agent-pm/05-tool-catalog-archive.md`

---

## 7. Eval 要求

| 类型 | Golden 数量 | Eval 方式 | 通过门槛 | 责任人 |
|------|-----------|----------|---------|-------|
| **Tool**（每个）| ≥ 10 | Unit test + schema 校验 | 100% | 工程 |
| **Skill**（每个）| ≥ 50 | 结构化输出校验 + LLM-as-judge | ≥ 90% | PM + 工程 |
| **Skill trajectory** | ≥ 20 | 完整对话轨迹回放 | ≥ 85% | PM |
| **Composition**（5.1 典型链）| 每条 ≥ 10 | E2E 集成 | ≥ 95% | 工程 |

详见 [09 Eval Plan](./09-eval-plan.md) + [16 Trajectory Eval](./16-trajectory-eval.md)。

---

## 8. 现状 vs 本 Catalog 的 Gap

基于 [04 Agent Spec § 13](./04-agent-spec.md#13-现状-vs-本-spec-的-gap) 的 gap 清单，落到 Skills/Tools 层面：

| Gap | 影响对象 | 现状 | v1 目标 |
|-----|---------|------|---------|
| 所有 Skill 要改为 Anthropic Tool Use 协议 | S01-S07 | prompt + regex parse | SKILL.md + tool_use |
| T04 recall_memory 不存在 | T04 | - | 新建（基于 agent_memory 表 + 相关性评分）|
| T09 create_approval_request 不存在 | T09 | 无 HITL 队列 | 新建 `pending_approvals` 表 |
| T11 approve_rule 不存在 | T11 | 无 Semantic Memory 采纳 | 新建 |
| S06 backtest-runner 有初步框架 | S06 | `agent/backtest.py` 雏形 | 扩展 + warnings LLM 模块 |
| 所有 Skill 缺 golden set | S01-S07 | 0 条 | ≥ 50 条 / Skill |

---

## 9. 术语对照表（给工程）

| 本文档 | 等价概念 | 出现位置 |
|-------|---------|---------|
| Skill | Claude Agent SDK "Skill" / 旧命名的 "复合能力" | Anthropic 文档 |
| Tool | Anthropic Messages API "tool_use" | - |
| SKILL.md | Skill 定义文件（Markdown + YAML frontmatter）| Anthropic 范式 |
| Composition | Skill 调 Tool 的依赖链 | § 5.1 |
| Trajectory | Skill 完整对话 / 任务轨迹（多轮）| [16 Trajectory Eval](./16-trajectory-eval.md) |
| Progressive Disclosure | Skill 按需加载（不占 system prompt）| Anthropic 范式 |
| Golden Set | 人工标注的测试数据 | [09 Eval Plan](./09-eval-plan.md) |
| CRUD | Create / Read / Update / Delete（增 / 查 / 改 / 删）| - |

---

## Change Log

- **v0.1 (2026-04-24)**：首版完整填充
  - § 0 概念区分：Skill vs Tool 判断框架 + 组合规则
  - § 1 **7 个 Skills Inventory**（S01-S07）：analysis 3 + authoring 2 + evaluation 1 + reflection 1
  - § 2 **12 个 Tools Inventory**（T01-T12）：query 4 + CRUD 4 + execution 3 + HITL 1
  - § 3 每个 Skill 完整 spec：input/output contract + domain knowledge + tools called + cost + failure + eval
  - § 4 每个 Tool 完整 spec：JSON Schema + idempotent + side_effects + failure_modes
  - § 5 典型组合链 4 场景（chat analysis / 共创策略 / 策略触发执行 / 日复盘）+ 硬约束 + 禁止组合
  - § 6 Lifecycle：新增 / 修改 / 废弃
  - § 7 Eval 要求：Tool 10 / Skill 50 / Trajectory 20
  - § 8 现状 Gap：v1 要补齐
  - § 9 术语对照表
- v0（2026-04-22）：初始骨架
