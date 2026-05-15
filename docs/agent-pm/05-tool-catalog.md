# 05 Skills & Tools Catalog（harness 核心）

> Agent 所有能力的**分层**清单：**Skills（能力 / 工作流）** + **Tools（原子操作）**。
> 每个都必有 **schema + eval + owner + version**。Skill 可以调用 Tool；Tool 不能调用 Skill 也不能调 LLM。

---

## 📖 PM 速读(给非技术读者 · 30 秒看完)

**什么是 Tool**:Agent 能做的**19 个最小原子动作**(像组装乐高的基础积木),每个都能单独调用 / 单独测试 / 单独评估成本。

**19 个 Tool 分 5 类**(R68 加 T19 — pump.fun 实时新币信号专属):

| 类别 | 数量 | 包含什么 |
|---|---|---|
| **查询类**(只读,免费,P95<500ms) | 7 | 查代币行情 / 查持币者 / 查链上活动 / 翻历史经验 / 查模拟盘表现 / 查热币榜(R39) / **查 pump.fun 早期信号**(R68 新增 — 暴露毕业曲线 % + 评分 + 检测时间) |
| **CRUD 类**(改数据库) | 4 | 列策略 / 改状态 / 存策略 / 审批新规则 |
| **执行类**(动钱) | 3 | 模拟盘下单 / 真金下单 / 申请审批(R62 后大多无审批) |
| **计算类**(纯算) | 3 | 算技术指标 / 算风险指标 / 跑回测 |
| **通知类** | 2 | 推送消息 / 算仓位 |

**每个 Tool 必标 4 项边界**(让组合时清楚后果):
- **是否幂等**(同样输入会不会有副作用累积)
- **有没有副作用**(动钱 / 改 DB / 只读)
- **P95 延迟**(95% 请求多久返)
- **单次成本**($,大多数 Tool 是 $0 — 没用 LLM)

**为什么这样设计**:LLM 出错时,我们能精确知道是"工具调错了"还是"工具结果误判了" — 单元化降低 debug 成本 + 让安全审计能逐 tool 做。

**v0.3 状态**(2026-05-15):18 个 Tool 全部实现,但有 3 个的"schema 字段命名"和"行为细节"跟文档有偏差(见 §13.2 偏差表),建议读 Tool 详情时**以代码 `agent/tools/T*.py` 为准**。

---

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.2 Draft |
| Version | v0.2 |
| Owner | 产品负责人 |
| Target Release | v1 MVP - 2026 Q3 |
| Total Skills / Tools | **7 Skills + 17 Tools** |

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
| **调用协议** | Anthropic `tool_use` API | prompt 方式激活 |
| **典型例子** | `SELECT FROM db` / `calc_RSI` | "技术面分析报告" / "做一次周复盘" |

### 0.2 判断框架（新增能力时走这个决策树）

```
新增能力 X
    ↓
X 是否需要 LLM 做判断 / 推理 / 文本生成？
    ├── 否 → X 是 Tool
    │      ├── 纯计算（数学公式）→ 必须 Tool
    │      ├── CRUD → 必须 Tool
    │      └── 外部 API 调用 → 必须 Tool
    └── 是 ↓
           X 是否包含领域知识（RSI 解读 / 好 insight 标准 / 策略模板）？
           ├── 否，只是 prompt 一次 LLM → 放 prompt library（§ 08）
           └── 是 ↓
                  X 是否多步骤 / 涉及文件 / 模板？
                  ├── 否 → 单次 prompt，放 prompt library
                  └── 是 → X 是 Skill
```

**反例警戒**：
- ❌ "让 Claude 算 RSI" → 错！RSI 是公式，必须 Tool
- ❌ "让 Claude 从 DB 查策略" → 错！SQL 查询必须 Tool
- ❌ "把 Tool 做成 Skill" → 错！纯函数不需要 LLM 推理

### 0.3 组合规则

**强约束**：
1. ✅ Skill **可以** 调用多个 Tool
2. ✅ Skill **可以** 调用其他 Skill（层级 ≤ 2，避免深嵌套）
3. ✅ Tool **可以** 内部调用其他 Tool（纯计算组合）
4. ❌ Tool **不得** 调用 Skill（Tool 是叶子）
5. ❌ Tool **不得** 调用 LLM（否则它应该是 Skill）
6. ✅ 每次 Skill 激活 = 一次或多次 LLM 调用，必须记录 trace
7. ✅ 每次 Tool 调用 = 一次函数执行，无 LLM 成本

### 0.4 与 03 PRD / 04 Agent Spec 的映射

- 本 doc 的 **Skills** = [04 Agent Spec § 1.3](./04-agent-spec.md#13-competencies核心能力--对齐-prd-6-大能力) 的 **C1-C7 核心能力**的具体实现
- 本 doc 的 **Tools** = [03 PRD v0.4](./03-prd.md) 中 "T01-T19" 原子映射的规范化展开
- v0.5 PRD 会同步将"T04 analyze_technical"等命名更新为 **S01 technical-analysis**

---

## 1. Skills Inventory（7 个能力级 Skill）

| ID | Skill Name | Category | Calls (Tools + Sub-Skills) | Status | Version |
|----|-----------|----------|---------------------------|--------|---------|
| **S01** | `technical-analysis` | Analysis | T01 + T02 + **T14** calc_indicators | 🟢 Spec 就绪 | v0.1 |
| **S02** | `sentiment-analysis` | Analysis | T01 + KOL 数据查询 | 🟢 | v0.1 |
| **S03** | `onchain-analysis` | Analysis | T01 + T02 + T03 | 🟢 | v0.1 |
| **S04** | `signal-strategy-builder` | Authoring | T04 (memory) + T16 (backtest) + T12 (save) | 🔴 核心 | v0.1 |
| **S05** | `trade-strategy-builder` | Authoring | T10 + **T15** calc_risk + T12 | 🟠 | v0.1 |
| **S07** | `review-engine` | Reflection | T04 + T10 + T05 + T16 + **T15** | 🟠 | v0.1 |
| **S08** | `thesis-writer` 🆕 | Synthesis | (纯 LLM，无 Tool) | 🔴 新增 | v0.1 |

**S06 已移除**（原 backtest-runner 重新定位为 **T16 run_backtest** 纯 Tool，详见 § 4.16）

**所有 Skill 均用 Claude Opus**（见 [03 PRD § 8.8.0](./03-prd.md#880-模型分层决策v1-采用质量优先方案)）
**Golden set 门槛**：≥ 50 案例 / Skill + Trajectory Eval ≥ 20 条
**SKILL.md 路径**：`services/pump-scanner/agent/skills/<skill_name>/SKILL.md`

---

## 2. Tools Inventory（19 个原子操作）

### 2.1 查询类（7）

| ID | Tool Name | I/O | Status | Version |
|----|-----------|-----|--------|---------|
| **T01** | `query_market` | read | 🟢 | v0.1 |
| **T02** | `query_holders` | read | 🟢 | v0.1 |
| **T03** | `query_onchain_activity` | read | 🟢 | v0.1 |
| **T04** | `recall_memory` | read | 🔴 新建 | v0.1 |
| **T10** | `get_paper_performance` | read | 🟢 | v0.1 |
| **T18** | `query_top_movers` 🆕 | read | 🟢 R39 | v0.1 |
| **T19** | `query_pump_tokens` 🆕 | read | 🟢 R68 | v0.1 |

### 2.2 CRUD 类（4）

| ID | Tool Name | I/O | Status | Version |
|----|-----------|-----|--------|---------|
| **T05** | `list_strategies` | read | 🟢 | v0.1 |
| **T06** | `update_strategy_status` | write | 🟢 | v0.1 |
| **T11** | `approve_rule` | write | 🔴 新建 | v0.1 |
| **T12** | `save_strategy` | write | 🟢 | v0.1 |

### 2.3 执行类（3）

| ID | Tool Name | I/O | Status | Version |
|----|-----------|-----|--------|---------|
| **T07** | `run_paper_trade` | write | 🟢 | v0.1 |
| **T08** | `execute_swap` | write + chain tx | 🟠 | v0.1 |
| **T09** | `create_approval_request` | write + push | 🔴 新建 | v0.1 |

### 2.4 计算类 🆕（3）

| ID | Tool Name | I/O | Status | Version |
|----|-----------|-----|--------|---------|
| **T14** | `calc_technical_indicators` | compute | 🔴 新建 | v0.1 |
| **T15** | `calc_risk_metrics` | compute | 🔴 新建 | v0.1 |
| **T16** | `run_backtest` | compute (heavy) | 🟠 | v0.1 |

### 2.5 通知 / 基础设施 🆕（2）

| ID | Tool Name | I/O | Status | Version |
|----|-----------|-----|--------|---------|
| **T13** | `send_push_notification` | external | 🟢 | v0.1 |
| **T17** | `calc_position_size` | compute | 🔴 新建 | v0.1 |

**Tools 性质**：无 LLM 成本（$0）；必须幂等（除明确标 `non_idempotent`）；严格 JSON Schema 校验。

---

## 3. Skills 详细 Spec

### 3.0 Skill 模板

每个 Skill 的 `SKILL.md` 必有以下 frontmatter：

```yaml
---
name: skill-name
description: |
  **强关键词** 描述（用于 progressive disclosure 自动 matching）
  when user ...（场景 1）
  when user ...（场景 2）
when_to_use: |
  - 场景 1（中文 + English keywords）
  - 场景 2
tools_required: [T01, T03, T14]       # 硬依赖 Tool
sub_skills_allowed: [S08]              # 可选嵌套（≤ 2 层）
model: claude-opus-latest              # v1 固定 Opus
version: 0.1
prompt_version_range: ">=0.1, <1.0"   # v0.2 新增：兼容的 prompt 版本范围
owner: TBD
failure_fallback: |
  当 Skill 失败时返回的 safe default（见各 Skill 具体定义）
---
```

**注意（v0.2）**：SKILL.md **只**装 metadata；具体 System Prompt / Few-shot / Domain Knowledge 全部在 [07 Prompt Library](./07-prompt-library.md) 的对应 prompt 文件中。边界严禁混淆。

### 3.1 S01: technical-analysis

**Description（强关键词）**:
> When user asks about **technical analysis / 技术面 / TA**, **RSI / MACD / moving average / 均线**, **support / resistance / 支撑 / 阻力**, **trend / 趋势**, **entry point / 入场点 / 止损位** for a specific token. Activates on chat messages like "TRUMP 技术面怎么样"/"看下 MA 和 RSI"/"what's the trend".

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
  "trend": { "short_term": "up|down|sideways", "mid_term": "..." },
  "key_levels": { "support": [1.10, 0.95], "resistance": [1.45, 1.80] },
  "indicators_snapshot": {                  // 来自 T14，不是 LLM 算的
    "rsi_1h": 62.5, "ma_cross": "golden", "atr_14": 0.08, "bb_position": "middle"
  },
  "entry_zone": { "low": 1.10, "high": 1.20 },
  "stop_loss": 0.95,
  "confidence": 0.72,
  "reasoning": "…简短说明（Opus 生成）",
  "data_gaps": []
}
```

**Domain Knowledge（`SKILL.md` 内嵌）**：
- RSI 解读表（< 30 超卖 / 30-70 中性 / > 70 超买 + 背离识别）
- 金叉 / 死叉判定规则
- 支撑阻力识别（swing high/low + volume 验证）
- Bollinger Bands 定位（挤压 / 突破 / 回归均线）
- **不含计算公式**（公式交给 T14）

**Tools Called**:
1. `T01 query_market`（拿代币基本信息 + K 线）
2. `T14 calc_technical_indicators`（**由 T14 算 RSI/MA/ATR/BB**，不让 Opus 算数学）
3. `T02 query_holders`（辅助判断集中度对支撑位影响）

**Cost**: ~$0.008（Opus ~1K in + 0.3K out）
**Latency P95**: < 4s
**Failure Fallback**（挂了时返回）:
```json
{ "direction_bias": "neutral", "confidence": 0, "data_gaps": ["skill_failed"], "reasoning": "技术面分析不可用" }
```

**Eval**: 50 条 golden（各链各走势 + 新币 / 老币混合）；trajectory 20 条
**Security**: 只读

---

### 3.2 S02: sentiment-analysis

**Description（强关键词）**:
> When user asks about **sentiment / 情绪 / 市场情绪**, **FOMO / panic / 恐慌 / 恐贪**, **KOL / social / 喊单 / 社交媒体**. Activates on "现在情绪怎么样" / "KOL 在说什么" / "Twitter 热度".

**Input Contract**:
```json
{ "chain": "solana", "address": "0x...", "period": "24h" }
```

**Output Contract**:
```json
{
  "sentiment": "euphoria | bullish | neutral | bearish | panic",
  "fomo_score": 0.35,
  "signals": {
    "kol_mentions_24h": 18, "kol_avg_score": 0.72,
    "social_growth_pct": 240, "fear_greed_index": 62
  },
  "red_flags": ["KOL 集中喊单", "Twitter 增粉 < 社交提及增长"],
  "confidence": 0.60,
  "reasoning": "..."
}
```

**Domain Knowledge**:
- 恐贪指数判读表（0-25 极恐 / 25-50 恐 / 50-75 贪 / 75-100 极贪）
- KOL 质量评估（历史命中率 ≥ 30% 可信）
- 假社交增长识别（机器人粉丝 / 突增归零）

**Tools Called**:
1. `T01 query_market`
2. 直接读 `kol_signals` / `social_metrics` 表（通过 DB schema 暴露为 read-only view，v1 可先 hard-code）

**Cost**: ~$0.008 | **Latency P95**: < 4s
**Failure Fallback**:
```json
{ "sentiment": "neutral", "fomo_score": 0.5, "confidence": 0, "reasoning": "情绪面分析不可用" }
```

**Eval**: 50 条 golden

---

### 3.3 S03: onchain-analysis

**Description（强关键词）**:
> When user asks about **onchain / 链上 / 链上数据**, **smart money / 聪明钱**, **holders / 持仓分布**, **liquidity / 流动性**, **dev wallet / 项目方钱包**, **concentration / 集中度**. Activates on "聪明钱在买吗"/"持仓分布"/"流动性健康吗".

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
  "holder_concentration": { "top10_pct": 58, "risk_level": "low|medium|high" },
  "liquidity": { "usd": 120000, "trend_24h": "+18%", "health": "healthy|thin|drained" },
  "dev_activity": { "dev_wallet_sold_pct_30d": 5, "risk": "low|medium|high" },
  "overall_signal": "bullish | neutral | bearish | rug_risk",
  "confidence": 0.80,
  "reasoning": "..."
}
```

**Domain Knowledge**:
- 聪明钱 tier 权重（elite ×3 / verified ×2 / watching ×1）
- Top10 集中度阈值（< 50% 健康 / 50-70% 警惕 / > 70% 高危）
- LP 健康度（> $100K 基本健康；trend 掉头 > 20% 告警）
- Dev 抛售识别规则

**Tools Called**: T01 + T02 + T03

**Cost**: ~$0.008 | **Latency P95**: < 4s
**Failure Fallback**:
```json
{ "overall_signal": "neutral", "confidence": 0, "reasoning": "链上分析不可用" }
```

---

### 3.4 S04: signal-strategy-builder ⭐ 核心

**Description（强关键词）**:
> When user wants to **build / create / 建 / 创建 / 做一个** a **strategy / 策略 / 信号**, or says **"帮我建个 X 策略"/"我想自动盯盘"/"turn my rule into a strategy"**, or clicks "New Strategy" / selects from template library. Handles the **7-stage co-creation flow**（see [03 PRD § 3.2.1](./03-prd.md#321-共创流程co-creation-flow)）.

**Input Contract**（每轮对话）:
```json
{
  "user_message": "我想做个聪明钱跟单",
  "conversation_id": "uuid",
  "existing_draft": null | { ...strategy JSON },
  "user_profile": { "persona": "中级", "preferred_chains": ["solana"] }
}
```

**Output Contract**:
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

**Domain Knowledge（`SKILL.md` 内嵌）**:
- 策略条件 schema 完整规范
- 5 类常见意图模板（聪明钱跟单 / BC 早鸟 / KOL 联动 / 涨幅突破 / 低位反弹）
- 澄清提问库（按意图 × 空白字段分类）
- 反例识别（矛盾条件 / 过于宽松 / 过于严格）
- 风险提示规则（EV < 0 主动警告 / 胜率 > 80% 疑似过拟合）
- **7 阶段流程状态机**（clarifying → refining → confirming → saved）

**Tools / Sub-Skills Called**:
1. `T04 recall_memory`（查用户历史偏好 + 类似策略的表现）
2. `T16 run_backtest`（第 ④ 阶段 dry run，**纯 Tool 调用**）
3. `T12 save_strategy`（第 ⑦ 阶段激活）

**Cost**: 平均一次完整共创会话 ~$0.06-$0.10
**Latency**: 每轮 < 6s
**Failure Fallback**:
- LLM 挂 → 返回"系统繁忙，请稍后重试，你的草稿已保存"，写 `conversation_states` 表保留 draft
- Tool 挂（如 T16）→ 跳过 dry run，提示用户"历史预估暂不可用，建议保存后观察 7 天模拟盘"

**Eval**: 100 条 golden 对话轨迹（trajectory eval，见 [16](./16-trajectory-eval.md)）
**Security**: 保存前强制 JSON Schema 校验 + 策略数 ≤ 20 硬限

---

### 3.5 S05: trade-strategy-builder

**Description（强关键词）**:
> When user wants to **add execution / 加交易执行 / 让策略自动下单** on top of a signal strategy, or says **"触发后买多少"/"止损设多少"/"paper mode"/"auto mode"**. Handles the trade strategy configuration with risk preview.

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
  "risk_preview": {                       // 来自 T15，不是 LLM 算的
    "max_drawdown_pct": 20,
    "per_trade_max_loss_usd": 15,
    "hitl_required": true,
    "reasons_for_hitl": ["单笔 > $500"]
  },
  "ready_to_save": false
}
```

**Domain Knowledge**:
- 止盈止损 3 套模板（保守 / 稳健 / 激进）+ 适用 Persona
- 追踪止损 / ATR 止损 适用场景
- 分批止盈策略（Kelly 近似）
- paper → notify_only → auto 晋升路径（§ 5.4 PRD）

**Tools Called**:
1. `T10 get_paper_performance`（同一 signal strategy 的已有表现）
2. `T15 calc_risk_metrics`（**纯 Tool 算 max_drawdown / per_trade_loss**）
3. `T12 save_strategy`

**Cost**: ~$0.05 / 会话 | **Latency**: < 6s / 轮
**Failure Fallback**: 返回模板化 draft（保守参数）+ 提示用户手动配置
**Eval**: 50 条 golden 对话

---

### 3.6 S06（已移除）

**原 S06 `backtest-runner`** 在 v0.2 中**降级为纯 Tool**：**T16 `run_backtest`**（见 § 4.16）。

**原因**：回测主体是**纯计算**（拉历史数据 + 跑策略 + 算 PnL / Sharpe / MDD）—— 不需要 LLM 推理。过拟合 warnings 用规则触发（胜率 > 80% + 样本 < 50 → "疑似过拟合"），也不需要 LLM。

**未来重新引入 S06 的条件**（v2 考虑）：
- 用户反馈"warnings 文案太机械，希望更个性化解读"
- 接入 LLM 做"策略对比分析"（A 策略 vs B 策略的自然语言优劣对比）

---

### 3.7 S07: review-engine

**Description（强关键词）**:
> When it's time for **daily / weekly / monthly review / 复盘 / 日报 / 周报 / 月报**, or user asks **"review my trades / 帮我复盘 / 这周表现"**, or Reflect Loop cron triggers at UTC 23:55 / Sunday / 1st of month, or emergency trigger on single trade < -25%.

**Input Contract**:
```json
{
  "device_id": "uuid",
  "period": "daily | weekly | monthly",
  "period_range": { "from": "2026-04-17", "to": "2026-04-23" },
  "trigger": "cron | threshold | user_request"
}
```

**Output Contract**：完整的 [§ 7.7 PRD Review Schema](./03-prd.md#77-review-报告完整-schema)

**Domain Knowledge**:
- 好 insight vs 坏 insight 示例库（§ 7.5 PRD 里的 few-shot）
- 规则提议格式规范
- 退化检测算法（近 N 笔 vs 前 N 笔 胜率对比）
- Persona 差异化 tone（小白 / 中级 / 专业）
- 冷启动处理（5 种状态 § 7.8 PRD）

**Tools / Sub-Skills Called**:
1. `T04 recall_memory`（查历史 episodic）
2. `T10 get_paper_performance`（查策略表现）
3. `T05 list_strategies`（当前活跃策略）
4. `T15 calc_risk_metrics`（MDD / Sharpe / EV）
5. `T16 run_backtest`（可选，发现策略退化时主动 walk-forward）

**Cost**: 日 ~$0.15 / 周 ~$0.40 / 月 ~$1.00
**Latency P95**: < 40s（后台任务，不阻塞用户）
**Failure Fallback**: 交易 < 5 笔走冷启动简化版；Insight LLM-as-judge 打分 < 0.5 丢弃；规则提议用户拒 > 3 次同类 → 该类 mute 7 天
**Eval**: 100 条 golden（各 Persona × 各交易表现）+ LLM-as-judge

---

### 3.8 S08: thesis-writer 🆕

**Description（强关键词）**:
> **Synthesize** 3 analyst reports (**technical + sentiment + onchain**) + historical similar cases (from memory) into a **final user-facing thesis** with direction / entry / stop / target / risks. Activates at the end of Thesis Loop (L2/L3).

**Input Contract**:
```json
{
  "token": { "chain": "solana", "address": "...", "symbol": "TRUMP" },
  "technical_report": { ...S01 output },
  "sentiment_report": { ...S02 output },
  "onchain_report": { ...S03 output },
  "similar_past_cases": [...],           // 来自 T04 recall_memory
  "regime": "BULL | SIDEWAYS | CRISIS",
  "user_persona": "小白 | 中级 | 专业",
  "level": "L2 | L3"                      // L3 会包含 debate result
}
```

**Output Contract**：完整的 [§ 2.7 PRD Thesis Schema](./03-prd.md#27-thesis-完整-schema)（direction / entry_zone / stop_loss / target / conviction / risks / summary_30w / evidence / similar_past_cases / ...）

**Domain Knowledge（`SKILL.md` 内嵌）**:
- **Thesis 结构硬规范**（§ 2.7 PRD 字段约束：risks 长度 ≥ 2 / conviction < 0.5 时 direction 必为 hold/avoid / evidence 必须引用真实数据）
- 3 面冲突融合规则（技术 bull + 情绪 bear + 链上 neutral → 如何加权）
- Persona tone 切换（小白白话 / 中级术语 / 专业技术参数）
- 禁用表达库（"稳的" / "百倍" / "错过就亏"—— 硬过滤）
- 置信度计算（三面 confidence 加权平均 × regime 调整）
- 历史案例引用规范（必须带日期 + outcome + similarity）

**Tools Called**: 无（纯 LLM synthesis Skill）
**Sub-Skills Called**: 无（被 orchestration 调用，不调别人）

**Cost**: ~$0.015（Opus ~2K in + 1K out）
**Latency P95**: < 5s
**Failure Fallback**（挂了）:
```json
{
  "direction": "hold",
  "conviction": 0.3,
  "risks": ["thesis 生成失败", "基础数据可用但未融合分析"],
  "summary_30w": "系统繁忙，请查看 3 面分析原始结果自行判断",
  "evidence": [...3 面原始报告...]
}
```

**Eval**: 100 条 golden（3 面输入 → thesis 输出 + LLM-as-judge 评分：结构正确性 / 事实准确性 / tone 一致性 / 风险标注率）

---

## 4. Tools 详细 Spec

### 4.0 Tool 模板

```json
{
  "name": "tool_name",
  "description": "一句话描述（用于 LLM tool_use 匹配）",
  "input_schema": { /* JSON Schema */ },
  "output_schema": { /* JSON Schema */ },
  "idempotent": true | false,
  "side_effects": "none | db_write | external_api | chain_tx | push",
  "p95_latency_ms": 200,
  "cost_usd": 0,
  "permission": "public | device_only | wallet_required",
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
  "idempotent": true, "side_effects": "none",
  "p95_latency_ms": 500, "cost_usd": 0,
  "permission": "public",
  "failure_modes": ["TOKEN_NOT_FOUND", "CHAIN_MISMATCH", "UPSTREAM_DEGRADED"],
  "data_sources": "P0 事件流聚合 + P2 DexScreener 兜底"
}
```

### 4.2 T02: query_holders

```json
{
  "name": "query_holders",
  "description": "查询代币 Top N 持仓钱包 + 集中度。",
  "input_schema": {
    "type": "object",
    "properties": {
      "chain": "...", "address": "...",
      "top_n": { "type": "integer", "default": 10, "maximum": 100 }
    },
    "required": ["chain", "address"]
  },
  "idempotent": true, "p95_latency_ms": 800, "cost_usd": 0,
  "permission": "public",
  "failure_modes": ["HOLDER_DATA_STALE (> 1h)", "RPC_ERROR"]
}
```

### 4.3 T03: query_onchain_activity

```json
{
  "name": "query_onchain_activity",
  "description": "查询代币近期链上活动（大额交易 / 聪明钱买卖 / 净流入流出）。",
  "input_schema": {
    "properties": {
      "chain": "...", "address": "...",
      "period": { "enum": ["1h", "24h", "7d"] },
      "min_usd": { "type": "number", "default": 1000 }
    },
    "required": ["chain", "address", "period"]
  },
  "idempotent": true, "p95_latency_ms": 400, "cost_usd": 0,
  "permission": "public",
  "data_sources": "smart_money_txns + token_trades (P0 事件流落表)"
}
```

### 4.4 T04: recall_memory 🔴 新建

```json
{
  "name": "recall_memory",
  "description": "按情境检索历史相似案例 / 语义规则（Episodic + Semantic）。",
  "input_schema": {
    "properties": {
      "device_id": "...",
      "situation": {
        "properties": { "chain": "...", "token_type": "...", "trigger_source": "...", "regime": "...", "mcap_bucket": "..." }
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
  "idempotent": true, "p95_latency_ms": 300, "cost_usd": 0,
  "permission": "device_only",
  "scoring_algorithm": "v1 启发式（trigger_source+3 / chain+2 / regime+2 / pnl+1，见 [06 Memory § 3.3](./06-memory-spec.md)）；v2 考虑 embedding",
  "cost_note": "v1 启发式 $0；v2 embedding 约 $0.0001/次"
}
```

### 4.5 T05: list_strategies

```json
{
  "name": "list_strategies",
  "description": "列出该 device 的策略（可按 status/mode 过滤）。",
  "input_schema": {
    "properties": {
      "device_id": "...",
      "status": { "enum": ["active", "paused", "archived", "all"], "default": "active" },
      "include_performance": { "type": "boolean", "default": false }
    },
    "required": ["device_id"]
  },
  "idempotent": true, "p95_latency_ms": 150, "cost_usd": 0,
  "permission": "device_only"
}
```

### 4.6 T06: update_strategy_status

```json
{
  "name": "update_strategy_status",
  "description": "更改策略状态（pause / resume / archive）。不做硬删除。",
  "input_schema": {
    "properties": {
      "device_id": "...", "strategy_id": "...",
      "new_status": { "enum": ["active", "paused", "archived"] },
      "reason": { "type": "string" }
    },
    "required": ["device_id", "strategy_id", "new_status"]
  },
  "idempotent": true, "side_effects": "db_write",
  "p95_latency_ms": 200, "cost_usd": 0,
  "permission": "device_only",
  "illegal_transitions": ["archived → active（必须 fork 新策略）"],
  "failure_modes": ["STRATEGY_NOT_OWNED", "ILLEGAL_TRANSITION"]
}
```

### 4.7 T07: run_paper_trade

```json
{
  "name": "run_paper_trade",
  "description": "策略触发时原子写入 hot_sim_trades + 更新 paper_accounts。",
  "input_schema": {
    "properties": {
      "device_id": "...", "trade_strategy_id": "...",
      "signal_context": { "...": "触发事件 payload" },
      "entry_price_usd": "...", "amount_usd": "...", "entry_at": "..."
    }
  },
  "idempotent": true, "idempotency_key": "signal_event_id",
  "side_effects": "db_write",
  "p95_latency_ms": 300, "cost_usd": 0,
  "permission": "device_only",
  "failure_modes": ["INSUFFICIENT_VIRTUAL_BALANCE", "DUPLICATE_EVENT（返回已有记录）"]
}
```

### 4.8 T08: execute_swap

```json
{
  "name": "execute_swap",
  "description": "真金 DEX swap。必须已通过风控 + HITL。",
  "input_schema": {
    "properties": {
      "device_id": "...", "wallet_address": "...", "chain": "...",
      "direction": { "enum": ["buy", "sell"] },
      "token_address": "...", "amount_usd": "...",
      "max_slippage_pct": "...", "signed_authorization": "..."
    }
  },
  "idempotent": false, "side_effects": "external_api + chain_tx",
  "p95_latency_ms": 8000, "cost_usd": 0,
  "external_costs": "用户 wallet gas 扣减",
  "permission": "wallet_required",
  "pre_conditions": [
    "authorization.expires_at > now",
    "amount <= § 4.2 PRD 硬限",
    "amount_usd <= active_authorization.single_trade_max（硬校验，对齐 08 HR10）",
    "agent_global_state.status != 'blocked'",
    "devices.credentials_revoked_at IS NULL（对齐 08 HR11）",
    "KMS key 可用（CB12 未触发）",
    "copy_trade 目标非黑名单（对齐 08 HR27/CB11）",
    "HITL approved（如需）"
  ],
  "failure_modes": ["QUOTE_FAILED", "SLIPPAGE_EXCEEDED", "WALLET_NOT_CONNECTED", "TX_REVERTED", "HITL_NOT_APPROVED"],
  "post_actions": "写入 agent_executions + 更新 pending_approvals.tx_hash"
}
```

### 4.9 T09: create_approval_request 🔴 新建

```json
{
  "name": "create_approval_request",
  "description": "创建待用户审批的请求（HITL）。写入 pending_approvals + 触发 T13 推送。",
  "input_schema": {
    "properties": {
      "device_id": "...", "strategy_id": "...",
      "trigger_conditions_matched": ["..."],
      "thesis_id": "...", "token": "...", "amount_usd": "...",
      "timeout_minutes": { "type": "integer", "default": 15 }
    }
  },
  "output_schema": {
    "approval_id": "...", "expires_at": "...", "push_sent": true
  },
  "idempotent": true,
  "idempotency_key": "strategy_id + signal_event_id + amount_usd",
  "side_effects": "db_write + trigger T13",
  "p95_latency_ms": 500, "cost_usd": 0,
  "permission": "device_only",
  "failure_modes": ["PUSH_FAILED (仍写入 DB)"]
}
```

### 4.10 T10: get_paper_performance

```json
{
  "name": "get_paper_performance",
  "description": "查询某策略（或全部）的模拟盘表现统计。",
  "input_schema": {
    "properties": {
      "device_id": "...",
      "strategy_id": { "type": "string", "description": "可选，缺省返回全部策略汇总" },
      "period_days": { "type": "integer", "default": 30 }
    }
  },
  "output_schema": "参见 03 PRD § 5.3 baseline 格式",
  "idempotent": true, "p95_latency_ms": 400, "cost_usd": 0,
  "permission": "device_only"
}
```

### 4.11 T11: approve_rule 🔴 新建

```json
{
  "name": "approve_rule",
  "description": "用户采纳规则提议，写入 Semantic Memory。",
  "input_schema": {
    "properties": {
      "device_id": "...", "rule_proposal_id": "...",
      "user_edits": { "type": "object", "description": "采纳前可微调文本/参数" }
    },
    "required": ["device_id", "rule_proposal_id"]
  },
  "output_schema": { "semantic_rule_id": "...", "activated_at": "..." },
  "idempotent": true, "idempotency_key": "rule_proposal_id",
  "side_effects": "db_write",
  "p95_latency_ms": 300, "cost_usd": 0,
  "permission": "device_only"
}
```

### 4.12 T12: save_strategy

```json
{
  "name": "save_strategy",
  "description": "原子保存（新建或更新）一条策略；由 S04 / S05 调用。",
  "input_schema": {
    "properties": {
      "device_id": "...",
      "strategy_type": { "enum": ["signal", "trade"] },
      "strategy_json": "...",  // § 3.3 / § 4.9 PRD Schema
      "mode": { "enum": ["new", "update"] }
    }
  },
  "output_schema": { "strategy_id": "...", "version": 3, "status": "active" },
  "idempotent": false,                  // update 模式会生成新 version
  "side_effects": "db_write",
  "p95_latency_ms": 400, "cost_usd": 0,
  "permission": "device_only",
  "validation": "完整 JSON Schema + 策略数 ≤ 20 + 条件矛盾检测"
}
```

### 4.13 T13: send_push_notification 🆕

```json
{
  "name": "send_push_notification",
  "description": "向指定 device 发送推送通知（HITL / 策略触发 / 降级告警 / 复盘提醒）。",
  "input_schema": {
    "properties": {
      "device_id": "...",
      "category": { "enum": ["hitl_approval", "strategy_triggered", "price_alert", "degradation_warning", "review_ready", "risk_alert"] },
      "title": "...",
      "body": "...",
      "deep_link": "agent-trading://...",
      "priority": { "enum": ["high", "normal", "low"], "default": "normal" },
      "ttl_seconds": { "type": "integer", "default": 3600 }
    },
    "required": ["device_id", "category", "title", "body"]
  },
  "output_schema": { "push_id": "...", "sent": true, "provider": "fcm | apns" },
  "idempotent": true,
  "idempotency_key": "device_id + category + hash(body) + 5min bucket",
  "side_effects": "external_api (FCM/APNs)",
  "p95_latency_ms": 1500, "cost_usd": 0,
  "permission": "device_only",
  "failure_modes": ["FCM_FAILED", "APNS_FAILED", "TOKEN_EXPIRED (标记 device_tokens.is_active=false)"]
}
```

### 4.14 T14: calc_technical_indicators 🆕

```json
{
  "name": "calc_technical_indicators",
  "description": "纯数学计算技术指标（RSI / MACD / MA / ATR / Bollinger Bands / 支撑阻力）。不调 LLM。",
  "input_schema": {
    "properties": {
      "klines": { "type": "array", "description": "K 线数组 [{ts, o, h, l, c, v}, ...]" },
      "indicators": {
        "type": "array",
        "items": { "enum": ["rsi_14", "ma_20", "ma_50", "ma_200", "macd", "atr_14", "bb_20_2", "support_resistance"] }
      }
    },
    "required": ["klines", "indicators"]
  },
  "output_schema": {
    "rsi_14": 62.5,
    "ma_20": 1.15, "ma_50": 1.08, "ma_200": 0.92,
    "macd": { "line": 0.015, "signal": 0.010, "histogram": 0.005 },
    "atr_14": 0.08,
    "bb_20_2": { "upper": 1.30, "middle": 1.15, "lower": 1.00 },
    "support": [1.10, 0.95], "resistance": [1.45, 1.80],
    "data_gaps": []                      // e.g. K 线 < 指标要求的最小窗口
  },
  "idempotent": true, "side_effects": "none",
  "p95_latency_ms": 50, "cost_usd": 0,
  "permission": "public",
  "failure_modes": ["INSUFFICIENT_KLINES (< 指标窗口)", "INVALID_KLINE_FORMAT"],
  "owner": "算法工程",
  "note": "**Skill S01 必须调本 Tool，不得让 LLM 自行计算 RSI/MA/ATR**"
}
```

### 4.15 T15: calc_risk_metrics 🆕

```json
{
  "name": "calc_risk_metrics",
  "description": "纯数学计算风控指标（最大回撤 / Sharpe / 每笔最大损失 / EV / Kelly）。",
  "input_schema": {
    "properties": {
      "trades": { "type": "array", "description": "交易数组 [{entry, exit, pnl_pct, ...}, ...]" },
      "metrics": {
        "type": "array",
        "items": { "enum": ["max_drawdown", "sharpe", "sortino", "ev_pct", "win_rate", "profit_factor", "kelly_fraction"] }
      },
      "baseline_equity": { "type": "number", "default": 10000 }
    },
    "required": ["trades", "metrics"]
  },
  "output_schema": {
    "max_drawdown_pct": -22.4, "sharpe": 0.82, "sortino": 1.05,
    "ev_pct": 3.5, "win_rate": 0.48, "profit_factor": 1.12,
    "kelly_fraction": 0.08, "sample_size": 42
  },
  "idempotent": true, "p95_latency_ms": 100, "cost_usd": 0,
  "permission": "public"
}
```

### 4.16 T16: run_backtest（原 S06）

```json
{
  "name": "run_backtest",
  "description": "在历史数据上跑一遍策略，产出完整报告（纯计算，不调 LLM）。",
  "input_schema": {
    "properties": {
      "strategy_snapshot": { "...": "完整 signal + trade strategy JSON" },
      "period_days": { "type": "integer", "default": 30 },
      "chains": { "type": "array", "items": "..." },
      "compare_to": { "type": "array", "items": { "enum": ["hold_sol", "hold_eth", "none"] } }
    }
  },
  "output_schema": "完整的 [§ 6.7 PRD Backtest Schema](./03-prd.md#67-backtest-结果完整-schema)",
  "idempotent": true, "side_effects": "none",
  "p95_latency_ms": 30000, "cost_usd": 0,
  "permission": "device_only",
  "internal_tool_calls": ["T01 query_market", "T02 query_holders", "T03 query_onchain_activity", "T15 calc_risk_metrics"],
  "warnings_generation": "规则触发（胜率 > 80% + 样本 < 50 → '疑似过拟合' / 样本 < 20 → '样本不足' / 窗口含 CRISIS regime > 40% → '极端行情窗口'）—— 不用 LLM",
  "failure_modes": ["INSUFFICIENT_HISTORY", "TIMEOUT (返回部分结果 + partial=true)"]
}
```

### 4.17 T17: calc_position_size 🆕

```json
{
  "name": "calc_position_size",
  "description": "纯计算仓位大小（按 fixed_usd / pct / Kelly 规则）。",
  "input_schema": {
    "properties": {
      "mode": { "enum": ["fixed_usd", "pct_of_balance", "kelly"] },
      "amount_value": { "type": "number" },
      "balance_usd": { "type": "number" },
      "hard_limits": { "per_trade_max": 500, "daily_max": 2000 },
      "strategy_historical_ev_pct": { "type": "number", "description": "Kelly 模式需要" }
    },
    "required": ["mode", "amount_value", "balance_usd", "hard_limits"]
  },
  "output_schema": {
    "recommended_amount_usd": 85.0,
    "applied_cap": "hard_limit | balance | requested",
    "skipped_reasons": []                 // e.g. balance < $10
  },
  "idempotent": true, "p95_latency_ms": 20, "cost_usd": 0,
  "permission": "public"
}
```

### 4.18 T18: query_top_movers 🆕 R39

```json
{
  "name": "query_top_movers",
  "description": "查询某窗口内涨幅 Top N 代币（支持 pump.fun BC 信号 / 多链热币 / 全部）。回答 '哪些币涨得好' / 'pump.fun top movers' / '近期表现优异的代币' 等问题。",
  "input_schema": {
    "type": "object",
    "properties": {
      "source": { "enum": ["pump", "hot", "all"], "default": "all" },
      "chain":  { "enum": ["solana", "eth", "bsc", "base", "all"], "default": "all" },
      "window": { "enum": ["5m", "1h", "6h", "24h"], "default": "24h" },
      "limit":  { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
      "min_volume_usd": { "type": "number", "minimum": 0, "default": 1000 },
      "sort_by": { "enum": ["pct_change", "volume", "score"], "default": "pct_change" }
    },
    "additionalProperties": false
  },
  "output_schema": {
    "ok": "boolean",
    "items": [
      {
        "rank": 1, "symbol": "TRUMP", "name": "...", "address": "...",
        "chain": "solana", "source": "pump | hot",
        "pct_change": 45.2, "volume_usd": 250000, "mcap_usd": 2000000,
        "liquidity_usd": 50000, "score": 80.5, "price_usd": 0.00012
      }
    ],
    "window": "24h", "total": 5, "source_used": "all"
  },
  "idempotent": true,
  "side_effects": "none",
  "p95_latency_ms": 400,
  "cost_usd": 0,
  "permission": "public",
  "data_sources": "hot_coins(多链 5m/1h/6h/24h) + pump_signals(SOL only, BC 3-35%)",
  "failure_modes": ["INPUT_SCHEMA_INVALID", "DB_ERROR", "EMPTY_RESULT"],
  "owner": "agent-team",
  "version": "0.1"
}
```

**关键设计**：
- `source=pump` 仅查 `pump_signals` 表（pump.fun BC 3-35% 信号，SOL only）
- `source=hot` 查 `hot_coins` 表（多链 + 多时间帧 price_change 字段）
- `source=all` union 两边 → 按 sort_by 全局排序
- 每链各取 top 30 后再合并（避免 SOL 高分淹没其他链）
- pump_signals 只 filter min_volume_usd（不应用 window，因为 BC 信号本身是分钟级时效）
- 字段格式：`hot_coins.price_change_24h` 是 percentage（45 = 45%），不是比例（0.45）

**调用方**：
- chat_loop 关键词预触发（R39 MVP 实施）
- 未来：S04 signal-strategy-builder（用户问"建监控"时先看 top movers）
- 未来：S07 review-engine（每周大涨 top 跟反思关联）

---

### 4.19 T19: query_pump_tokens 🆕 R68

> **跟 T18 区别**:T18 是综合 top movers(hot_coins + pump_signals union,**按涨幅排序为主**)。T19 是 **pump.fun 专属深度** — 暴露 pump 特有元数据(`bonding_curve_pct` / `score` / `detected_at` / `age_minutes`),只查 SOL 链 pump.fun 信号池,**按评分或 BC 进度排序**。

**purpose**:回答 "pump.fun 最新 / 毕业进度 X% / 刚冒头 score>N / BC 早期信号" 这类问题。让 chat agent 不再依赖 App "新币 Tab" 数据,自己有专属 tool 查 pump.fun。

**input_schema**:
```json
{
  "min_score": int 0-100,              // 默认 55(pump_scanner 早期信号阈值)
  "bc_min": float 0-100,                // 默认 3 (毕业曲线下界 %)
  "bc_max": float 0-100,                // 默认 35(毕业曲线上界 %)
  "min_volume_usd": number,             // 默认 1000
  "limit": int 1-50,                    // 默认 20
  "sort_by": "score" | "bc_pct" | "volume" | "detected_age"   // 默认 "score"
}
```

**output_schema**:
```json
{
  "ok": bool,
  "items": [{
    "rank": int,
    "symbol": str, "name": str, "address": str,
    "score": float,                     // 0-100,pump_scanner 综合评分
    "bonding_curve_pct": float,         // 3-35 = 早期;>50 = 接近毕业
    "price_usd": float,
    "mcap_usd": float,
    "volume_24h_usd": float,
    "price_change_24h_pct": float,
    "detected_at": str,
    "age_minutes": float                // 距 detected_at 多久(支持"刚出来 vs 老货")
  }],
  "total": int,
  "source_used": "scanner" | "redis" | "file" | "empty",   // 数据源透明
  "is_history": bool,                   // True = 实时池空,展示最近 1h 历史回顾
  "reason": str                         // 空池时给 friendly 解释
}
```

**数据源策略**(从 routes_pump.py 借鉴):
1. **scanner in-memory**(同进程,毫秒级,**最优**)
2. **Redis**`KEY_PUMP_SIGNAL_POOL`(独立 api 进程,5s 新鲜)
3. **文件**`/tmp/pump_signal_pool.json`(兜底,最差 60s)
4. 空池(所有都失败 / 无信号)

**字段**:
- `idempotent=True`,`side_effects=NONE`,`cost_usd=$0`,`permission=PUBLIC`
- `p95_latency_ms=200`(内存读 / Redis 都很快)
- `failure_modes`: `INPUT_SCHEMA_INVALID` / `DATA_SOURCE_UNAVAILABLE` / `EMPTY_RESULT`

**调用方**:
- chat_loop 关键词预触发(R68 实施)— `PUMP_TOKENS_KEYWORDS` 命中 → 调 T19 直接返表格
- 触发关键词:**"pump.fun" / "毕业" / "bonding curve" / "BC" / "新币" / "刚出" / "早期信号"**
- 优先级:**T19 优先于 T18**(更具体 → 先匹配)

**输出 chat 用 markdown 表格**(配合 R64 markdown 渲染):
```
| # | 代币 | 评分 | 毕业 % | 价格 | 市值 | 24h量 | 24h涨幅 | 检测 |
|---|------|----:|------:|-----:|-----:|------:|-------:|-----:|
| 1 | XYZ  | 87 | 18.3% | $0.000012 | $324K | $5K | +45% | 12m |
| ...
```

**未来扩展**:
- S04 signal-strategy-builder:用户问"建 pump.fun 监控"时先用 T19 看现状
- S08 thesis 合成:cite T19 结果("当前 pump.fun 平均评分 X / 池子里有 Y 个新币")
- S05 trade-strategy-builder:用 T19 的 `bonding_curve_pct` 范围做触发条件(如"BC 5-15% 自动跟单 $50")

---

## 5. Composition Rules（组合规则）

### 5.1 典型调用链

**场景 A：用户 Chat "分析 TRUMP"**

```
User Chat
  → Thesis Loop (L2/L3)
      → [并行] S01 technical-analysis
                   → T01 query_market
                   → T14 calc_technical_indicators (新：不让 LLM 算数学)
                   → T02 query_holders
      → [并行] S02 sentiment-analysis
                   → T01
      → [并行] S03 onchain-analysis
                   → T01 + T02 + T03
      → T04 recall_memory
      → [L3 仅] debate (Bull vs Bear Opus × 5 轮)
      → [L3 仅] RiskReviewer (Opus)
      → S08 thesis-writer (合成最终用户可读 thesis)
  → Response to User
```

**场景 B：用户共创新建信号策略**

```
User Chat
  → S04 signal-strategy-builder (多轮)
      ├─ T04 recall_memory (查历史偏好)
      ├─ [Round 1-3 澄清 / 对话]
      ├─ T16 run_backtest (第 ④ 阶段 dry run)
      │     └─ 内调 T01+T02+T03 + T15 calc_risk_metrics
      ├─ [Round 4-5 反馈迭代]
      └─ T12 save_strategy (第 ⑦ 阶段激活)
```

**场景 C：信号触发到真金执行（完整链）**

```
EventBus.smart_money_tx / hot_coin_update / pump_snapshot
  → Scout Loop (RuleEngine，纯规则 0 LLM)
  → [规则命中] → Thesis Loop L3
      → [并行] S01 + S02 + S03
      → debate + RiskReviewer
      → S08 thesis-writer
  → T17 calc_position_size (规则化算仓位)
  → RiskManager 9 项检查 (含 T15 calc_risk_metrics)
  → if HITL 需要:
       T09 create_approval_request
          └─ T13 send_push_notification
  → if paper:
       T07 run_paper_trade
  → if auto:
       T08 execute_swap
  → T13 send_push_notification (结果通知)
```

**场景 D：日复盘**

```
Cron UTC 23:55 或 累计 10 笔闭仓
  → Reflect Loop
  → S07 review-engine
      ├─ T05 list_strategies
      ├─ T10 get_paper_performance
      ├─ T15 calc_risk_metrics
      ├─ T04 recall_memory (last 30d episodic)
      └─ [optional] T16 run_backtest (发现策略退化时)
  → T13 send_push_notification ("复盘已生成，点此查看")
  → [用户打开 app 采纳某 insight]
      → T11 approve_rule → 写入 Semantic Memory
```

### 5.2 硬约束

1. **Tool 叶子原则**：Tool 不调 LLM、不调 Skill
2. **Skill 嵌套 ≤ 2 层**：S07 可调 T16，但 T16 不得再调 Skill
3. **并行优先**：S01 / S02 / S03 三个分析师必须 `asyncio.gather()` 并行
4. **事件驱动优先**：Scout Loop 不使用 LLM 类 Skill，只跑 RuleEngine
5. **真金前置条件硬校验**：T08 execute_swap 前**必须**通过 RiskManager + HITL（除授权额度内）
6. **数学归 Tool**：S01 / S07 里出现"算 RSI / Sharpe / MDD" → 必须调 T14/T15，**不得让 LLM 自算**
7. **推送归 Tool**：任何地方发推送 → 调 T13，**不得直接调 FCM/APNs**

### 5.3 禁止组合

- ❌ Scout Loop 调用任何 Skill（破坏毫秒级要求）
- ❌ 任何 Tool 内部调 LLM
- ❌ Skill 让 LLM 自己算数学 / 自己调 push API
- ❌ 同一次用户请求内嵌套 > 2 层 Skill

### 5.4 Progressive Disclosure 加载机制 🆕

> Anthropic Skill 的核心理念：**Claude 只在需要时才加载 Skill 的完整 SKILL.md**，避免 system prompt 膨胀。

#### 5.4.1 加载策略

| Skill | 加载方式 | 触发条件 |
|-------|---------|---------|
| **S08 thesis-writer** | **Always Loaded**（Thesis Loop 预加载）| 只要进入 Thesis Loop 必用 |
| **S01 / S02 / S03**（3 分析师）| **Always Loaded**（Thesis Loop L3 预加载）| L3 必用 |
| **S04 signal-strategy-builder** | **Lazy**（description matching）| Chat 提到 "建策略 / strategy / 策略"|
| **S05 trade-strategy-builder** | **Lazy** | Chat 提到 "加交易 / auto / 执行" 且有 signal_strategy 上下文 |
| **S07 review-engine** | **Always Loaded**（Reflect Loop 专用）| cron 或紧急触发 |

#### 5.4.2 加载实现

- **Always Loaded**：Skill 的 SKILL.md 全文 + tool schemas 直接拼入 system prompt
- **Lazy**：仅把 Skill 的 **name + description** 放入 system prompt（总计 < 1K tokens），Claude 触发时通过 `load_skill(S04)` 拿完整内容

#### 5.4.3 加载预算

| Loop | 预加载 Skills | System Prompt 预算 |
|------|-------------|------------------|
| Scout Loop | 无 | < 2K tokens（纯规则）|
| Thesis Loop L2 | S08 thesis-writer | ~5K tokens |
| Thesis Loop L3 | S01 + S02 + S03 + S08 + debate/review prompts | ~12K tokens |
| Notify Loop | 无 Skill（纯编排）| ~3K tokens |
| Reflect Loop | S07 review-engine | ~6K tokens |
| Chat（用户入口）| 所有 Skill 的 name+desc（lazy metadata）+ S08 | ~8K tokens |

#### 5.4.4 动态加载失败处理

- `load_skill(X)` 失败 → 返回 `SKILL_LOAD_FAILED` → orchestration 降级（按 Skill 的 `failure_fallback`）
- 加载超时（> 500ms）→ 同上

---

## 6. Lifecycle（生命周期）

### 6.1 新增

| 类型 | 提案人 | 必交付物 | 审核人 | 门槛 |
|------|-------|---------|-------|------|
| Tool | 工程师 | schema + 10 golden + owner | Agent 架构师 | 通过 CI |
| Skill | PM + 工程 | SKILL.md + 50 golden + trajectory eval 20 + cost 估算 + fallback | 产品 + 架构师 | 通过 CI + Dry-run 对比 |

### 6.2 修改

- **Tool schema breaking 改动** → 新 version（v1 并存 v2，≥ 2 周迁移期）
- **Skill instructions / domain knowledge 改动** → 新 version + A/B test 1 周（见 [08 Prompt Library](./08-prompt-library.md)）
- **Skill description 改动**（影响 progressive disclosure matching）→ 回测"加载命中率"不下降

### 6.3 废弃

- 标 `deprecated=true` + 日志 WARN
- 通知所有调用方（grep + audit）
- 2 周迁移期
- 移除时删除代码 + 保留 schema 历史在 `docs/agent-pm/05-archive.md`

---

## 7. Eval 要求

| 类型 | Golden 数量 | Eval 方式 | 通过门槛 | 责任人 |
|------|-----------|----------|---------|-------|
| **Tool**（每个）| ≥ 10 | Unit test + schema 校验 | 100% | 工程 |
| **Skill**（每个）| ≥ 50 | 结构化输出校验 + LLM-as-judge | ≥ 90% | PM + 工程 |
| **Skill trajectory**（S04 / S07 多轮）| ≥ 20 | 完整对话轨迹回放 | ≥ 85% | PM |
| **Composition**（§ 5.1 典型链）| 每条 ≥ 10 | E2E 集成 | ≥ 95% | 工程 |
| **Progressive disclosure matching** | 50 条 chat 样本 | 加载的 skill 是否正确 | ≥ 90% | PM |

详见 [09 Eval Plan](./09-eval-plan.md) + [16 Trajectory Eval](./16-trajectory-eval.md)。

---

## 8. 现状 vs 本 Catalog 的 Gap

| Gap | 影响对象 | 现状 | v1 目标 |
|-----|---------|------|---------|
| 所有 Skill 要改 Anthropic Tool Use + SKILL.md 格式 | S01-S08 | prompt + regex parse | SKILL.md + tool_use |
| T04 recall_memory 不存在 | T04 | - | 新建（基于 agent_memory + 启发式评分）|
| T09 create_approval_request + pending_approvals 表 | T09 | 无 HITL 队列 | 新建表 + 新建 tool |
| T11 approve_rule 不存在 | T11 | 无 Semantic Memory 采纳 | 新建 |
| T13 send_push_notification 未封装 | T13 | push 逻辑散在 FCM 直调 | 封装为 Tool |
| T14 calc_technical_indicators 未独立 | T14 | 算法混在 Skill prompt 里 | 独立 Tool，S01 必调 |
| T15 calc_risk_metrics 未独立 | T15 | 算法混在 RiskManager 代码 | 独立 Tool |
| T16 run_backtest 现状是 Skill 雏形 | T16 | `agent/backtest.py` 雏形 | 改为纯 Tool + 规则化 warnings |
| T17 calc_position_size 未独立 | T17 | 混在 RiskManager | 独立 Tool |
| S08 thesis-writer 不存在 | S08 | thesis 逻辑隐式 | 新建 Skill |
| 所有 Skill 缺 golden set | S01-S08 | 0 条 | ≥ 50 条 / Skill |
| Progressive disclosure 未实现 | - | 所有 prompt 硬拼 | Lazy loading 机制 |

---

## 9. 术语对照表

| 本文档 | 等价概念 | 出现位置 |
|-------|---------|---------|
| Skill | Claude Agent SDK "Skill" | Anthropic 文档 |
| Tool | Anthropic Messages API "tool_use" | - |
| SKILL.md | Skill 定义文件（Markdown + YAML frontmatter）| Anthropic 范式 |
| Composition | Skill → Tool / Skill → Skill 的依赖链 | § 5.1 |
| Trajectory | Skill 完整对话轨迹（多轮）| [16 Trajectory Eval](./16-trajectory-eval.md) |
| Progressive Disclosure | Skill 按需加载机制 | § 5.4 |
| Failure Fallback | Skill 挂了时的 safe default 返回 | 各 Skill § 3.x |
| Golden Set | 人工标注的测试数据 | [09 Eval Plan](./09-eval-plan.md) |
| CRUD | Create / Read / Update / Delete | - |

---

## Change Log

- **v0.2 (2026-04-24)**：Skill/Tool 边界修订（Review 反馈）
  - **S06 backtest-runner 移除 → 改为纯 Tool T16 run_backtest**（95% 纯计算不需 LLM）
  - **新增 S08 thesis-writer**（显式化 3 面分析融合为 thesis 的能力）
  - **新增 5 个计算 / 基础设施 Tool**：
    * T13 send_push_notification（推送独立化）
    * T14 calc_technical_indicators（**RSI/MA/ATR 不让 LLM 算**）
    * T15 calc_risk_metrics（MDD / Sharpe / EV）
    * T16 run_backtest（原 S06）
    * T17 calc_position_size（规则化算仓位）
  - **S01 依赖 T14**（domain knowledge 只讲"怎么解读"，计算交 Tool）
  - 所有 Skill **description 增加强关键词**（Anthropic progressive disclosure matching）
  - 所有 Skill 新增 **failure_fallback 字段**（挂了返回 safe default）
  - **新增 § 5.4 Progressive Disclosure 加载机制**（Always vs Lazy + 预算）
  - 每个 Tool 新增 `permission` 字段（public / device_only / wallet_required）
  - T04 recall_memory 明示"v1 启发式 $0，v2 embedding ~$0.0001"
  - § 8 Gap 更新（新增 5 个新 Tool + 1 个新 Skill）
- **v0.1 (2026-04-24)**：首版完整填充
  - § 0 Skill vs Tool 区分 + 组合规则
  - § 1 7 Skills Inventory
  - § 2 12 Tools Inventory
  - § 3 每 Skill 完整 spec
  - § 4 每 Tool 完整 spec
  - § 5 4 条典型组合链
- v0（2026-04-22）：初始骨架

### v0.3（2026-05-04 R39）增量
- **新增 T18 `query_top_movers`**（§ 2.1 + § 4.18）— 解决 chat agent 无法回答 "pump.fun 上近期表现优异的代币" 类问题
- Tools Inventory 数量从 17 → **18**
- 查询类从 5 → 6
- 配套：chat_loop.py 加关键词预触发（命中 → 调 T18 → 直接返 markdown 列表，不走 LLM）
- 实施代码：`services/pump-scanner/agent/tools/t18_query_top_movers.py`
- 单元测试：`tests/test_t18_query_top_movers.py`（13 case 全过）
