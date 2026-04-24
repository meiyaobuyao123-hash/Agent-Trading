# 07 Prompt Library（Prompt-as-Code）

> 所有 Prompt **版本化管理**，改版必跑 eval，CHANGELOG 可追溯。
> 和 [05 Catalog](./05-tool-catalog.md) 的 Skills 配套使用：**Skill = SKILL.md（身份+能力描述）+ Prompt（具体 instruction）**

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.1 Draft |
| Version | v0.1 |
| Owner | 产品负责人 |
| Target Release | v1 MVP - 2026 Q3 |

---

## 0. 为什么要 Prompt-as-Code

### 0.1 传统 vs Prompt-as-Code

| 维度 | 传统做法 | Prompt-as-Code |
|------|---------|----------------|
| 存储 | 工程师代码里 hardcode | 版本化文件（Git）|
| 修改 | 随便改，无记录 | 改必提 PR + CHANGELOG |
| 测试 | 肉眼看输出 | Golden set + LLM-as-judge 自动 eval |
| 灰度 | 要么上要么不上 | A/B 分桶，按 device_id hash 切流 |
| 回滚 | 要重新部署 | 配置文件切换，秒级 |
| 知识沉淀 | 流失在工程师脑内 | 文档化 domain knowledge + few-shots |

### 0.2 和其他文档的关系

```
[04 Agent Spec]   定义 Agent 身份
     │
     ▼
[05 Skills Catalog] Skill 列表 + SKILL.md frontmatter
     │
     ▼
[07 Prompt Library] 每个 Skill 的具体 Prompt 内容 ← 本文档
     │
     ▼
[09 Eval Plan]    每个 Prompt 的 golden set + 门槛
```

**一个 Skill = SKILL.md（调度层）+ 若干 Prompt 文件（执行层）**

---

## 1. 目录结构约定

```
services/pump-scanner/agent/prompts/
  v1/                                    # v1 prompts（当前 production）
    skills/
      technical_analysis/
        SKILL.md                         # Skill frontmatter（见 05）
        prompt_main.md                   # 主 prompt（S01 LLM 调用）
        knowledge_rsi_guide.md           # RSI 解读指南（domain knowledge）
        knowledge_ma_cross.md            # 金叉死叉规则
        examples.md                      # Few-shot 示例
      sentiment_analysis/
        SKILL.md
        prompt_main.md
        ...
      onchain_analysis/
      signal_strategy_builder/
        SKILL.md
        prompt_clarifying.md             # S04 Stage ② 澄清 prompt
        prompt_draft_generation.md       # Stage ③ 生成 draft
        prompt_refinement.md             # Stage ⑤ 迭代反馈
        templates_library.md             # 5 类策略模板
        examples.md
      trade_strategy_builder/
      review_engine/
        prompt_daily.md
        prompt_weekly.md
        prompt_monthly.md
        knowledge_insight_quality.md     # 好 insight vs 坏 insight 示例
      thesis_writer/
    debate/                              # L3 辩论专用
      prompt_bull_round1.md
      prompt_bear_round1.md
      prompt_bull_round2.md
      prompt_bear_round2.md
      prompt_facilitator.md
    risk_reviewer/
      prompt_main.md
    nl_parser/                           # 用户 NL → 结构化
      prompt_strategy_nl_to_json.md
  v2/                                    # v2 prompts（canary 灰度中）
    skills/
      thesis_writer/
        prompt_main.md                   # 尝试更简洁的 tone
  CHANGELOG.md                           # 全局改动日志
  config.yaml                            # 版本 + A/B 分桶配置
```

### 1.1 version 目录规则

- `v1/` / `v2/` **并存**（便于 A/B test 和回滚）
- `config.yaml` 控制谁走 v1 谁走 v2：

```yaml
# prompts/config.yaml
skills:
  thesis_writer:
    current_stable: v1
    canary: v2
    canary_bucket_pct: 5           # 5% 流量走 canary
    bucket_hash_field: device_id   # 按 device_id hash 分桶
  technical_analysis:
    current_stable: v1
    canary: null                   # 无 canary
```

---

## 2. Prompt Inventory

### 2.1 Skills 相关 Prompts（核心）

| ID | Prompt | 对应 Skill | 模型 | Current Version | Last Eval | Pass Rate |
|----|--------|-----------|------|----------------|-----------|-----------|
| **P01** | `technical_analysis/prompt_main` | S01 | Opus | v0.1 | 🟡 待建 | - |
| **P02** | `sentiment_analysis/prompt_main` | S02 | Opus | v0.1 | 🟡 | - |
| **P03** | `onchain_analysis/prompt_main` | S03 | Opus | v0.1 | 🟡 | - |
| **P04** | `signal_strategy_builder/prompt_clarifying` | S04 | Opus | v0.1 | 🟡 | - |
| **P05** | `signal_strategy_builder/prompt_draft_generation` | S04 | Opus | v0.1 | 🟡 | - |
| **P06** | `signal_strategy_builder/prompt_refinement` | S04 | Opus | v0.1 | 🟡 | - |
| **P07** | `trade_strategy_builder/prompt_main` | S05 | Opus | v0.1 | 🟡 | - |
| **P08** | `review_engine/prompt_daily` | S07 | Opus | v0.1 | 🟡 | - |
| **P09** | `review_engine/prompt_weekly` | S07 | Opus | v0.1 | 🟡 | - |
| **P10** | `review_engine/prompt_monthly` | S07 | Opus | v0.1 | 🟡 | - |
| **P11** | `thesis_writer/prompt_main` | S08 | Opus | v0.1 | 🔴 重点 | - |

### 2.2 辩论相关 Prompts（L3 专用）

| ID | Prompt | 用途 | 模型 | Version |
|----|--------|------|------|---------|
| **P12** | `debate/prompt_bull_round1` | Bull 第 1 轮论点 | Opus | v0.1 |
| **P13** | `debate/prompt_bear_round1` | Bear 第 1 轮反驳 | Opus | v0.1 |
| **P14** | `debate/prompt_bull_round2` | Bull 第 2 轮 | Opus | v0.1 |
| **P15** | `debate/prompt_bear_round2` | Bear 第 2 轮 | Opus | v0.1 |
| **P16** | `debate/prompt_facilitator` | Facilitator 总结裁决 | Opus | v0.1 |

### 2.3 其他 Prompts

| ID | Prompt | 用途 | 模型 | Version |
|----|--------|------|------|---------|
| **P17** | `risk_reviewer/prompt_main` | L3 最后一道 LLM 风控审查 | Opus | v0.1 |
| **P18** | `nl_parser/prompt_strategy_nl_to_json` | 用户 NL → 策略 JSON（tool_use）| Opus | v0.1 |

**总计 18 个 Prompt**（v1 MVP 阶段）。

---

## 3. Prompt Spec 模板

> 每个 Prompt 一份 .md 文件，以下是标准模板。

### 模板示例：`technical_analysis/prompt_main.md`

```markdown
# Prompt: technical_analysis/prompt_main

## Meta

- **ID**: P01
- **Version**: 0.1
- **Created**: 2026-04-24
- **Last Eval**: TBD
- **Model**: claude-opus-latest
- **Skill Binding**: S01 technical-analysis
- **Input Token Budget**: ≤ 3000
- **Output Token Budget**: ≤ 800
- **Expected Latency**: P95 < 4s

## Input Variables

- `{{chain}}`: solana | eth | bsc | base
- `{{token_symbol}}`: string
- `{{token_address}}`: string
- `{{indicators}}`: JSON from T14 calc_technical_indicators
- `{{klines_summary}}`: recent 50 points 1h K-line summary (max 500 chars)
- `{{onchain_volume_24h}}`: number
- `{{user_persona}}`: 小白 | 中级 | 专业
- `{{semantic_rules}}`: [user's active Semantic Memory rules relevant to TA]

## System Prompt

你是一位严谨的加密货币技术分析师。基于给定的指标数据（**由 Tool 计算好的**，不要自己重算）和 K 线摘要，输出结构化的技术面判断。

**硬性规则**：
1. **永远不要自己计算 RSI/MA/ATR/BB** —— 这些由 T14 工具提供，你只解读
2. 置信度 < 0.5 时，`direction_bias` 必须为 `neutral`
3. 数据不足（klines < 50 根）时，返回 `data_gaps: ["insufficient_klines"]` + confidence 0
4. 不使用绝对化措辞（"一定"/"必然"/"百倍"）
5. 引用具体指标数值作为依据（e.g. "RSI 62.5 接近超买" ✅，"RSI 偏高" ❌）

**用户 Persona 适配**（{{user_persona}}）：
- 小白：用"价格高了/低了"替代"RSI 偏高/偏低"；隐藏 ATR / BB 数字
- 中级：标准术语 + 具体数值
- 专业：额外给出背离信号 / 多时间框架一致性判断

**用户已采纳的相关规则（优先遵守）**：
{{#each semantic_rules}}
- [{{this.source}}] {{this.content}}
{{/each}}

## User Prompt Template

代币：{{token_symbol}} ({{chain}} / {{token_address}})

技术指标（T14 Tool 计算）：
```json
{{indicators}}
```

近期 K 线摘要（1h 时间框架）：
{{klines_summary}}

24h 链上成交量：${{onchain_volume_24h}}

请输出结构化的技术面分析（见 output schema）。

## Expected Output Format

严格 JSON，符合 § 05 Catalog S01 的 Output Contract：

```json
{
  "direction_bias": "bullish | bearish | neutral",
  "trend": { "short_term": "...", "mid_term": "..." },
  "key_levels": { "support": [...], "resistance": [...] },
  "indicators_snapshot": { ...原样透传 T14 输入... },
  "entry_zone": { "low": ..., "high": ... },
  "stop_loss": ...,
  "confidence": 0.0-1.0,
  "reasoning": "简短说明（≤ 100 字）",
  "data_gaps": []
}
```

## Few-Shot Examples

### Example 1（BULL regime, 明确上升趋势）

Input:
- chain: solana, symbol: TRUMP
- indicators: { rsi_1h: 58, ma_20: 1.15, ma_50: 1.05, ma_cross: "golden", atr_14: 0.08, ... }
- klines_summary: "过去 24h 价格从 1.05 → 1.20，量能逐步放大"

Output:
```json
{
  "direction_bias": "bullish",
  "trend": { "short_term": "up", "mid_term": "up" },
  "key_levels": { "support": [1.10, 1.05], "resistance": [1.25, 1.40] },
  "indicators_snapshot": { ...原样... },
  "entry_zone": { "low": 1.10, "high": 1.15 },
  "stop_loss": 1.00,
  "confidence": 0.72,
  "reasoning": "MA20/50 金叉 + RSI 58 未超买 + 量价配合，短中期趋势偏多"
}
```

### Example 2（数据不足）

Input:
- klines_summary: "仅 12 根 K 线"（代币 < 12h）

Output:
```json
{
  "direction_bias": "neutral",
  "trend": { "short_term": "sideways", "mid_term": "sideways" },
  "indicators_snapshot": { ... },
  "confidence": 0.0,
  "data_gaps": ["insufficient_klines"],
  "reasoning": "K 线样本不足，暂无法判断趋势"
}
```

### Example 3（用户 Semantic Rule 介入）

semantic_rules:
- [user_approved] "TRUMP 类代币 RSI > 70 必须退出"

Input:
- indicators: { rsi_1h: 74, ... }

Output:
```json
{
  "direction_bias": "bearish",
  "trend": { "short_term": "up", "mid_term": "up" },
  "confidence": 0.55,
  "reasoning": "虽然趋势偏多，但按你已采纳规则 'RSI > 70 退出'，当前 RSI 74 触发退出信号"
}
```

## Failure Modes

- LLM 输出非 JSON → 重试 1 次 → 仍失败则返回 Skill fallback（S01 § 3.1 定义）
- 输出缺字段 → 验证失败 + 重试
- `reasoning` 超长（> 200 字）→ 截断 + 告警

## Eval

- **Golden**: `tests/evals/prompts/p01_technical_analysis.yaml`
- **Size**: 50 条
- **Metrics**:
  * Schema validity: ≥ 99%
  * Direction 与 ground truth 一致率: ≥ 75%
  * Confidence 合理性（LLM-as-judge）: ≥ 85%
  * 硬规则违反率（"永远不算 RSI"）: 0%

## CHANGELOG

- **v0.1 (2026-04-24)**: 初版创建
```

---

## 4. Versioning Rules

### 4.1 版本号规则（semver 简化）

`v{major}.{minor}`

| 变化类型 | 版本号 | 例子 |
|---------|-------|------|
| **patch**（错字、细节微调、改单个 few-shot）| minor +1 (内部) | v0.1 → v0.1-patch1 |
| **minor**（加字段 / 改表述 / 加 few-shot）| minor +1 | v0.1 → v0.2 |
| **major**（Output schema 变化 / 核心指令重写）| major +1 | v1 → v2（并存） |

### 4.2 何时出新版本（决策树）

```
改 prompt 之前问自己：
  └─ 只是改错字 / 加一个 few-shot？
     ├─ 是 → patch，同版本内改（走 CHANGELOG）
     └─ 否 ↓
        └─ 改后 Output schema 变了？
           ├─ 是 → major（新目录 v{N+1}/，canary 灰度）
           └─ 否 ↓
              └─ 改后预期行为显著变化（tone/重点/深度）？
                 ├─ 是 → minor，canary 灰度 1 周
                 └─ 否 → patch
```

### 4.3 Eval 通过门槛（改版必跑）

| 改动类型 | 门槛 |
|---------|------|
| patch | 老 golden set pass rate 不下降（≥ 原 rate - 2pp）|
| minor | 老 golden rate ≥ 原 - 2pp **AND** 新加字段的 golden pass ≥ 85% |
| major | 新旧并跑 7 天 canary，新版 pass rate **必须** ≥ 老版 + 3pp 才能全量 |

### 4.4 灰度机制（与 [03 PRD § 8.10](./03-prd.md#810-feature-flag--灰度策略) 统一）

| 阶段 | 流量 | 持续 | 判定 |
|------|------|------|------|
| Canary | 5% | 48h | 无 SEV-1 + 关键指标不退化 |
| Beta | 25% | 5d | Canary 通过 |
| GA | 100% | - | Beta 通过 |

分桶键：`hash(device_id) % 100`（同 device 稳定分桶）

### 4.5 回退机制

```yaml
# config.yaml 紧急回退示例（秒级生效）
skills:
  thesis_writer:
    current_stable: v1          # 回退：从 v2 → v1
    canary: null                 # 下线 canary
    rollback_reason: "v2 thesis 错误引用率 15% > 5pp 告警阈值"
    rolled_back_at: "2026-04-25T14:00Z"
```

- 配置热更新（无需重启服务，< 5s 全集群生效）
- Archive old version: `v1/` 继续保留（至少 2 个大版本的回溯能力）

---

## 5. Prompt Engineering Guidelines（团队约定）

### 5.1 通用约定

1. **System vs User message 分离**：
   - **System**: Role + Rules + Output format + Persona adaptation
   - **User**: 每次调用的 variable-filled data
   - Few-shots 放 System（稳定） 或 user/assistant turns（Anthropic tool_use mode 推荐后者）

2. **硬性规则前置**：
   - 最重要的规则放 System 最前面
   - 规则条目化（数字列表），不要堆文字

3. **不让 LLM 算数学**：
   - RSI/MA/ATR/Sharpe/MDD 等 → 必须由 Tool 计算后作为 input
   - 只允许 "加减 百分比对比" 这种最简单运算

4. **输出用结构化 JSON**：
   - 优先 tool_use 协议（Anthropic 原生）
   - 退而求其次：要求 JSON + 给 schema + 重试机制

5. **温度（temperature）策略**：
   - L1 类 nl_parser（需要确定性）→ 0.0-0.1
   - S01/S02/S03 分析（轻度多样性）→ 0.2-0.3
   - Debate（鼓励对抗性）→ 0.5-0.7
   - Thesis writer（有创造性语言）→ 0.3-0.4
   - Review insight → 0.3-0.4

6. **Max tokens**：
   - 严格声明上限，超出部分截断 + 告警

### 5.2 禁用表达（所有 Prompt 硬过滤）

对齐 [04 Agent Spec § 1.5 Personality](./04-agent-spec.md#15-personality说话风格)：

- ❌ "一定"/"必然"/"肯定"/"保证"
- ❌ "百倍"/"千倍"/"躺赚"/"稳的"/"稳赚不赔"
- ❌ "错过就亏了"/"FOMO"/"不买后悔"
- ❌ "内部消息"/"独家信号"/"大佬都在买"
- ❌ 任何预测具体价格的表述（"下周涨到 $X"）

**输出后过滤机制**：
- Prompt 末尾加 "严禁使用以下措辞：..."
- 输出侧 regex 过滤（见 [08 Safety Policy](./08-safety-policy.md)）
- 违反次数 > 1% → prompt 版本回退

### 5.3 引用数据硬规则（对齐 Vision）

**所有分析 / thesis 类 prompt 必须要求**：
- 📍 引用至少 **2 条具体数据**（e.g. "RSI 62.5" ✅）
- 📍 禁止空泛判断（"趋势向上" ❌ → "过去 24h 价格上涨 12% + MA20 上穿 MA50" ✅）

### 5.4 Persona 适配模板

所有面向用户的 prompt 都要支持 3 种 persona，统一用下述变量：

```
用户 Persona: {{user_persona}}
{{#if persona == "小白"}}
  - 使用白话和类比，避免术语
  - 隐藏：ATR / Sharpe / MDD / Kelly 等数字
  - 长度：100-150 字
{{else if persona == "中级"}}
  - 标准术语 + 具体数值
  - 长度：150-250 字
{{else if persona == "专业"}}
  - 技术参数 + 多维度交叉验证
  - 显示：所有指标原始值 + 置信度推导
  - 长度：250-400 字
{{/if}}
```

---

## 6. CHANGELOG 规范

### 6.1 全局 CHANGELOG.md 样式

```markdown
# Prompt CHANGELOG

## [2026-04-28] thesis_writer v1 → v2

- **Reason**: v1 在 L3 辩论后的 thesis 偶尔丢失 Bear 方观点，需加强融合度
- **Changes**:
  * System prompt 新增 "必须引用 Bull 和 Bear 各至少 1 条论点"
  * 加 3 条 few-shot（辩论后 thesis 示例）
- **Eval Delta**:
  * 结构完整率 95% → 98% (+3pp)
  * "Bear 观点引用率" 新指标 62% → 94%
  * LLM-as-judge 综合 0.82 → 0.89
- **Deployed**:
  * Canary 5% (2026-04-28 ~ 04-30)
  * Beta 25% (2026-04-30 ~ 05-05)
  * GA 100% (2026-05-05)
- **Bucket**: hash(device_id)
- **PR**: #342

---

## [2026-04-26] technical_analysis v0.1 → v0.2

- **Reason**: 小白 Persona 下 TA 结果太技术化，用户反馈看不懂
- **Changes**:
  * "小白" 分支新增类比模板库（"像去年的 X 代币")
  * 隐藏 ATR / BB 原始数值
- **Eval Delta**:
  * 小白 Persona 可读性（LLM-as-judge）63% → 87%
  * 中级 / 专业 Persona 不变（在控制组之外）
- **Deployed**: 无需 canary（仅改 persona 分支，不影响 schema）直接全量
```

### 6.2 CHANGELOG 必写字段

1. **Reason**：为什么改（业务原因 / 事故反馈 / eval 发现）
2. **Changes**：具体改动列表
3. **Eval Delta**：新旧 golden set 对比（至少 2 个关键指标）
4. **Deployed**：canary / beta / GA 时间线
5. **Bucket**：分桶键（如果 A/B）
6. **PR**：关联 GitHub PR

---

## 7. Prompt Library 与 Skill 的关系

### 7.1 One-to-Many

一个 **Skill** 可以包含**多个 Prompt**：

| Skill | Prompts |
|-------|---------|
| S01 technical-analysis | P01（主）|
| S04 signal-strategy-builder | P04（澄清）+ P05（生成 draft）+ P06（迭代反馈）|
| S07 review-engine | P08（日）+ P09（周）+ P10（月）|
| S08 thesis-writer | P11（主，L2/L3 共用但有分支）|

### 7.2 激活顺序

S04 signal-strategy-builder 的完整 7 阶段流程：

```
Stage ② 澄清        → P04 prompt_clarifying
Stage ③ 生成 draft   → P05 prompt_draft_generation
Stage ④ dry run      → T16 run_backtest（不涉及 prompt）
Stage ⑤ 反馈迭代      → P06 prompt_refinement
Stage ⑥ 确认保存      → P05 再次调用（或轻量确认 prompt）
```

### 7.3 Prompt 与 SKILL.md frontmatter 对照

- `SKILL.md` 的 `model:` 字段 → 决定 prompt 用什么模型
- `SKILL.md` 的 `tools_required:` → prompt 里必须声明 tool_use schema
- `SKILL.md` 的 `when_to_use:` → progressive disclosure matching 关键词（不在 prompt 里）
- `SKILL.md` 的 `failure_fallback:` → prompt 失败 retry 逻辑参考

---

## 8. 现状 vs 本 Spec 的 Gap

| Gap | 现状 | v1 目标 |
|-----|------|---------|
| G1 **Prompt 版本化缺失** | 代码里 hardcode 在 `*_analyst.py`/`debate.py`/`reflection.py` | 按 § 1 目录结构搬迁 |
| G2 **无 CHANGELOG** | 改 prompt 无记录 | 强制 PR 带 CHANGELOG 条目 |
| G3 **无 Golden set / eval** | 改完肉眼看输出 | 18 prompt × ≥ 30 golden / 个 |
| G4 **无 A/B 灰度机制** | prompt 改了就全量 | config.yaml 热切换 |
| G5 **Persona 适配不统一** | 分散在 analyst 代码 | § 5.4 模板统一 |
| G6 **禁用表达无过滤** | 依靠 prompt 约束 | 输出侧 regex 过滤兜底 |
| G7 **Prompt Token 预算无约束** | 任意长度 | 每 prompt 声明 input/output 上限 + 运行时截断 |
| G8 **Prompt 成本无 monitoring** | 靠账单倒查 | Trace 每次调用的 token + cost |

---

## 9. 与 Eval / Safety / Observability 的钩子

- **Eval** → [09 Eval Plan](./09-eval-plan.md)：每 Prompt 的 golden set / 指标 / 门槛
- **Safety 过滤** → [08 Safety Policy](./08-safety-policy.md)：输出侧禁用词 regex + 内容审核
- **Observability** → [15 Observability](./15-observability-tracing.md)：每次 prompt 调用的 trace（prompt version / input / output / cost / latency）

---

## 10. 术语对照表

| 本文档 | 等价概念 | 备注 |
|-------|---------|------|
| Prompt | System + User message（Anthropic 范式）| 单次 LLM 调用的 instruction |
| Prompt Library | Prompt 仓库 | 版本化集合 |
| Few-shot | In-context example | 给 LLM 学的示例 |
| Domain Knowledge | 领域知识文档 | RSI 解读表 / 好 insight 示例 等 |
| Canary / Beta / GA | 灰度阶段 | 5% / 25% / 100% |
| Golden Set | 人工标注的评测数据 | Prompt eval 的 ground truth |
| LLM-as-Judge | 用 LLM 评估 LLM 输出 | 自动化 eval 方法 |
| Shadow Mode | 影子模式 | 新 Prompt 只记录不生效 |
| Bucket Hash | 分桶哈希 | A/B test 的稳定分桶键 |

---

## Change Log

- **v0.1 (2026-04-24)**：首版完整填充
  - § 0 Prompt-as-Code 价值 + 与 Skill/Eval 关系
  - § 1 目录结构（prompts/v1/skills/ + debate/ + risk_reviewer/ + nl_parser/）
  - § 2 **18 个 Prompt Inventory**：
    * P01-P11 Skills 相关（S01/S02/S03/S04×3/S05/S07×3/S08）
    * P12-P16 辩论（5 轮）
    * P17 RiskReviewer / P18 NL Parser
  - § 3 **完整 Prompt Spec 模板**（以 P01 technical_analysis 为例）：Meta + Input Variables + System Prompt + User Prompt Template + Output Format + **3 条 Few-Shot 示例** + Failure Modes + Eval + CHANGELOG
  - § 4 Versioning：patch/minor/major 规则 + canary 灰度 + 秒级回退机制
  - § 5 **Engineering Guidelines**：
    * System/User 分离 / 硬规则前置 / **不让 LLM 算数学**
    * 温度策略 / Max tokens 约束
    * **禁用表达库**（"稳的"/"百倍"）+ 输出 regex 过滤
    * **Persona 适配模板**（3 分支）
  - § 6 CHANGELOG 规范（必写 6 字段）
  - § 7 Prompt 与 Skill 的 One-to-Many 关系
  - § 8 **8 条现状 Gap**（版本化 / CHANGELOG / Golden / A/B / Persona / 禁用词 / Token 预算 / Cost 监控）
  - § 9 与 Eval / Safety / Observability 的钩子
  - § 10 术语对照
- v0（2026-04-22）：初始骨架
