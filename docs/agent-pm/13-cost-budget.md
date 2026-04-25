# 13 Cost Budget

> 每个 Loop / Skill / Tool / Prompt 的成本预算，防止失控。
> **运行时熔断**：超预算自动降级（Opus → Sonnet → 拒绝），不允许"先花再说"。

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.1 Draft |
| Version | v0.1 |
| Owner | 工程 + PM |
| Target Release | v1 MVP - 2026 Q3 |
| Priority | P0（v1 必备）|

---

## 0. 文档导读

### 0.1 为什么 Cost Budget 是 v1 必备

加密交易 Agent 的成本结构与传统 SaaS 不同：
- **LLM 调用密集**：每次 thesis 多 Skill + 多轮调用
- **真金交易触发自动**：用户休息时仍可能触发 → 成本可能凌晨爆表
- **数据 API 持续订阅**：Helius / OKX / Gecko 等
- **失控代价**：1 个 bug 让 LLM 死循环 → 24h 烧 $10K+

**没 Cost Budget**：靠月底账单倒查 → "一觉醒来钱没了"
**有 Cost Budget**：实时监控 + 自动熔断 + Cost Attribution 到用户/策略/Tool

### 0.2 和其他文档的关系

| 文档 | 关系 |
|------|-----|
| [03 PRD § 8.8 Cost Budget](./03-prd.md#88-cost-budget成本预算每能力分摊) | 单次调用成本 + 月度预算 来源 |
| [05 Catalog § 1-4](./05-tool-catalog.md) | 每 Tool / Skill 的 cost_per_call |
| [07 Prompt § 4](./07-prompt-library.md) | Prompt token 预算 |
| [08 Safety § 10 CB04](./08-safety-policy.md#10-circuit-breakers熔断器) | Cost 熔断器（CB04 LLM 成本超预算）|
| [11 Launch § 5 C01-C04](./11-launch-criteria-hitl.md#5-cost--operational-gates) | Launch Cost Gates |
| [09 Eval § 11.4](./09-eval-plan.md#114-llm-调用的录像--回放v02-强化) | Eval 自身成本 |
| [15 Observability](./15-observability-tracing.md) | 提供 cost trace 数据 |

---

## 1. 总预算（v1 100 DAU 阶段）

### 1.1 月度预算（对齐 03 PRD § 8.8.3）

| 项目 | 月预算 | 告警 | 熔断（CB04）| Hard Cap |
|------|--------|------|-----------|---------|
| **Anthropic LLM**（Opus 主）| **$1500** | $1200（80%）| $1500（100%）| **$2250**（150%）|
| OpenAI LLM（备 / Judge 校准）| $50 | - | - | - |
| **Helius 付费**（SOL P0 源）| $50 | - | - | - |
| OKX DEX / Jupiter / 1inch | $50 | - | - | - |
| DexScreener / GeckoTerminal | $30 | - | - | - |
| GoPlus（安全检测）| $20 | - | - | - |
| 服务器（Postgres + Redis + Compute）| $200 | - | - | - |
| 其他（监控 / 告警 / 备份）| $100 | - | - | - |
| **总计** | **~$2000** | $1500（75%）| $1700（85%）| $3000（150%）|

### 1.2 v1 → v2 规模演进

| DAU | LLM 成本 / 月 | 总成本 / 月 | 每 DAU 月成本 |
|-----|------------|-----------|------------|
| 20（种子）| $400 | $700 | $35 |
| 100（v1 目标）| $1500 | $2000 | $20 |
| 500（v1.5）| $7500 | $9000 | $18 |
| 1K（v2 切分层）| **降至 $5K**（Tier 分级）| $7000 | $7 |
| 10K（v2 后期）| $30K（智能路由 + 付费用户 Opus）| $40K | $4 |

> v2 必须有 Tier / 智能路由（[03 PRD § 8.8.4](./03-prd.md#884-v2-预备方案不在-v1-启用)），否则 10K DAU $300K/月不可持续。

### 1.3 单 Device 预算上限

| Persona | 日预算 | 月预算 | 超限行为 |
|---------|-------|-------|---------|
| **免费**（v1 所有用户）| **$1.50** | **$30** | 3 级降级（§ 5.2）|
| 付费（v2 计划）| $5 | $100 | 阈值放宽 |
| **滥用 device 检测** | 单 device 单日 > $3 | 立即限流 + audit | 防 bot / 攻击 |

---

## 2. 分 Loop 成本

| Loop | 触发频率 | 单次成本 | 日均次/device | 日成本/device |
|------|---------|---------|-------------|--------------|
| **Scout Loop** | 事件驱动（无 LLM）| **$0** | 高频 | $0 |
| **Thesis Loop L2** | 用户 chat / 策略触发 | $0.025 | 2-4 次 | $0.05-0.10 |
| **Thesis Loop L3** | 大额 / 低置信度 / CRISIS | $0.35 | 0.5-1 次 | $0.18-0.35 |
| **Notify Loop** | 策略触发后 | ~$0（无 LLM）| 5-10 次 | $0 |
| **Reflect Loop（日复盘）** | 每日 1 次 | $0.15 | 1 | $0.15 |
| **Reflect Loop（周复盘）** | 每周日 1 次 | $0.40 | 1/7 ≈ 0.14 | $0.06 / 日均 |

**单 device 日成本预估**：$0.44 - $0.66（典型中级用户）→ 月约 $13-20，落在 $30 预算内。

---

## 3. 分 Skill 成本（对齐 [03 PRD § 8.8.1](./03-prd.md#881-单次调用成本opus-方案)）

| Skill | 模型 / 调用 | 单次 cost | 月 / DAU 调用 | 月 / DAU 成本 |
|-------|-----------|----------|-------------|------------|
| **S01** technical-analysis | 1× Opus | ~$0.008 | 60 | $0.48 |
| **S02** sentiment-analysis | 1× Opus | ~$0.008 | 60 | $0.48 |
| **S03** onchain-analysis | 1× Opus | ~$0.008 | 60 | $0.48 |
| **S04** signal-strategy-builder（一次完整共创）| 4-6× Opus | ~$0.06-$0.10 | 4 / 月 | $0.32 |
| **S05** trade-strategy-builder | ~3× Opus | ~$0.05 | 2 / 月 | $0.10 |
| **S07** review-engine 日 | 1× Opus | $0.15 | 30 | $4.50 |
| **S07** review-engine 周 | 1× Opus | $0.40 | 4 | $1.60 |
| **S07** review-engine 月 | 1× Opus | $1.00 | 1 | $1.00 |
| **S08** thesis-writer | 1× Opus | ~$0.015 | 60 | $0.90 |
| L3 辩论（含 RiskReviewer）| 5× Opus + 1× Opus | ~$0.345 | 12（20% L3）| $4.14 |

**月 / DAU 总 Skill cost**: ~$14-15
**100 DAU 月**: ~$1450（与 § 1.1 $1500 月预算 ✅ 吻合）

---

## 4. 分 Tool 成本

绝大多数 Tool 无 LLM 成本（$0）。少数有外部 API 成本：

| Tool | 单次 cost | 备注 |
|------|---------|------|
| T01 query_market | $0（DB）| 偶尔触发 P2 API（已含月费）|
| T02 query_holders | $0 | - |
| T03 query_onchain_activity | $0 | - |
| T04 recall_memory | **$0**（v1 启发式）/ $0.0001（v2 embedding）| 升级 v2 才有成本 |
| T05-T07 | $0 | DB CRUD |
| T08 execute_swap | $0 LLM / **链上 gas 由用户钱包出** | 我方不承担 gas |
| T09 create_approval_request | $0 LLM / **$0.0001 push notification**（FCM/APNs 免费层内）| - |
| T10-T12 | $0 | - |
| T13 send_push_notification | $0（FCM/APNs 免费层内）| 超 100 万次 / 月才付费 |
| T14 calc_technical_indicators | $0 | 纯数学 |
| T15 calc_risk_metrics | $0 | 纯数学 |
| T16 run_backtest | **$0.01**（warnings 解读用 Opus）| - |
| T17 calc_position_size | $0 | 纯数学 |

**Tool 总成本占比**：< 5%（Skill 是大头）。

---

## 5. 模型选型原则

### 5.1 v1 选型决策（对齐 [03 PRD § 8.8.0](./03-prd.md#880-模型分层决策v1-采用质量优先方案)）

**v1 全链 Opus**（质量优先，月预算 $1500 @ 100 DAU 可承受）：

| 职责 | 模型 |
|------|------|
| 所有 Skill（S01-S08）| Claude Opus |
| 辩论 5 轮 + RiskReviewer | Claude Opus |
| 复盘 / NL 建策略 | Claude Opus |
| Judge（Eval）| Claude Opus 主 + GPT-4 月度校准 |
| Embedding（v2 Memory）| Voyage AI / OpenAI text-embedding-3-small |

### 5.2 模型成本对比（参考）

| 模型 | Input $ / 1M tokens | Output $ / 1M tokens | 速度 | 适合 |
|------|------------------|--------------------|------|------|
| Claude Haiku 4.x | $0.25 | $1.25 | 最快 | v2 降级用 |
| Claude Sonnet 4.x | $3 | $15 | 快 | v2 Tier 1 用户 |
| **Claude Opus 4.x** | **$15** | **$75** | 中 | **v1 全链** |
| GPT-4 Turbo | $10 | $30 | 快 | Judge 校准用 |
| GPT-4o | $2.5 | $10 | 极快 | v2 智能路由考虑 |

### 5.3 v2 Tier 分级方案（不在 v1 启用）

| Tier | 用户类型 | 模型 | 单次成本 | 月成本 / DAU |
|------|---------|------|---------|------------|
| Free | 普通注册（v2 才开放注册）| Sonnet | $0.005 | ~$3 |
| Pro | 付费 $9.99/月 | Opus | $0.025 | ~$15 |
| Premium | 付费 $49/月 | Opus + Priority | $0.025 | ~$30 |

---

## 6. 成本熔断机制（运行时）

### 6.1 熔断器 CB04（对齐 [08 § 10](./08-safety-policy.md#10-circuit-breakers熔断器)）

| 熔断点 | 触发条件 | 动作 | 自动恢复 |
|--------|---------|------|---------|
| **第 1 级**（70% 预算）| 月度 LLM > $1050（70% 月预算）| L3 分析师 Opus → Sonnet（辩论仍 Opus）| 次月自动 |
| **第 2 级**（85%）| 月度 LLM > $1275 | L3 全链 Sonnet；L2 降 Sonnet | 次月自动 |
| **第 3 级**（95%）| 月度 LLM > $1425 | C2 L3 改 L2；C7 日复盘改简化 | 次月自动 |
| **硬停**（100%）| 月度 LLM ≥ $1500 | 拒绝新请求 + UI"今日 AI 分析额度已用完"| 次月自动 |
| **超预算紧急**（150%）| 月度 LLM > $2250 | **全局 BLOCKED**（仅留 query / paper）+ SEV-1 告警 | 人工解除 |

### 6.2 单 device 熔断

| 触发 | 动作 |
|------|------|
| device 日成本 > $1.50 | L3 自动降 L2，仍超 → L2 降 Sonnet |
| device 日成本 > $3 | **限流**（thesis 间隔 ≥ 5min）+ 标 `cost_anomaly=true` |
| device 日成本 > $10（异常） | **临时 BLOCK** + 告警审查（可能是 bot 攻击）|

### 6.3 异常 Pattern 检测

| Pattern | 处理 |
|---------|------|
| 单 device 1 小时调用 thesis > 100 次 | 限流（< 1/min）+ Slack 告警 |
| 单 IP 多 device 调用激增 | 同 IP 限流 |
| Eval 自身成本 > $300 / 周 | 检查录像回放是否失效 |
| 单 Skill cost 周环比涨 > 50% | 排查 prompt 是否变长 |

### 6.4 永远保护的能力（即使硬停）

- ✅ T01-T03 query（无 LLM）
- ✅ T05-T07/T10-T12 CRUD
- ✅ T14/T15/T17 计算类
- ✅ T16 backtest（无 LLM 主体）
- ✅ Scout Loop 事件驱动（纯规则）

**硬停只影响**：Thesis Loop / Reflect Loop / S04 共创对话（这些是 LLM 重的）。

---

## 7. 成本优化策略（运行时省钱）

### 7.1 Prompt Caching（最重要）

Anthropic Prompt Caching 节省**最多 90%**（缓存 input token $1.5/M vs 普通 $15/M）：

| 用途 | 缓存内容 | 命中率 |
|------|---------|--------|
| Skill Prompt 头部 | System prompt + Domain knowledge + Few-shots | > 90%（同 Skill 几乎不变）|
| Semantic Memory 注入 | 用户活跃规则（5 min 内不变）| 80% |
| Persona 模板 | 3 套 persona block | 100%（强制缓存）|
| Output schema | JSON 格式定义 | 100% |

**集成方式**：
- 所有 Anthropic SDK 调用启用 `cache_control: {type: "ephemeral"}`
- Cache breakpoint 放在 System prompt 末尾 / 用户输入前
- 命中率监控（Dashboard 单独面板）

**节省估算**：
- 同 Skill 每次 Prompt 头部 ~1.5K tokens
- 100 DAU × 60 调用 / 月 / DAU × Skill 头部缓存
- 月节省 input cost：约 $300-500（30-40% LLM 总成本）

### 7.2 Eval Recording / Replay（[09 § 11.4](./09-eval-plan.md#114-llm-调用的录像--回放v02-强化)）

- 不重复跑相同 input 的 LLM 调用
- 月度抽 20% 真调（防 drift）
- 节省 Eval 成本：每周全量 $20-30 → $5-10

### 7.3 Skill 分级触发

只在需要时调用 L3：
- 简单查询（query_market）→ 不调任何 Skill
- 已有 thesis < 10 min → 直接复用，不重生成
- 用户拒绝过的 thesis → 不重生成

### 7.4 Output Token 优化

- Thesis 严格限 ≤ 200 字（Persona 中级）/ ≤ 100 字（小白）
- Insight 严格限 ≤ 50 字
- 复盘报告先生成 summary，详情按需展开

### 7.5 Batch API（Anthropic）

复盘类**非实时**任务用 Batch API（**50% 折扣**）：
- 日复盘（次日凌晨批量跑）
- 月复盘（月初批量跑）
- Eval re-record（月度批量跑）
- **不能用 Batch**：实时 thesis / 实时 chat

### 7.6 Memory 缓存

- Semantic 规则进程内 LRU 5 min
- Episodic 30s 缓存
- 命中率 > 90% 时几乎零成本检索

---

## 8. Cost Attribution（归因）

### 8.1 归因维度

每次 LLM 调用必带：
- `device_id`（device 维度）
- `skill_id`（Skill 维度）
- `prompt_id` + `prompt_version`
- `loop_type`（Scout / Thesis / Notify / Reflect）
- `regime`（市场状态）
- `is_paper / is_auto`
- `trace_id`（完整调用链）

写入 `llm_cost_log` 表（保留 90d）：
```sql
CREATE TABLE llm_cost_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID,
  skill_id TEXT,
  prompt_id TEXT,
  prompt_version TEXT,
  loop_type TEXT,
  regime TEXT,
  trace_id UUID,
  model TEXT NOT NULL,
  input_tokens INT,
  output_tokens INT,
  cache_hit_tokens INT,
  cost_usd NUMERIC(10, 6),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_cost_device_time ON llm_cost_log(device_id, created_at DESC);
CREATE INDEX idx_cost_skill_time ON llm_cost_log(skill_id, created_at DESC);
```

### 8.2 Dashboard 视图

| 视图 | 用途 |
|------|------|
| **总览**：日 / 周 / 月成本曲线 + 预算占比 | 整体监控 |
| **按 Skill** Top 10 | 哪个 Skill 烧钱多 |
| **按 device** Top 20（cost > $1.50/day）| 异常 device 排查 |
| **Cache 命中率** by Skill | Caching 效果 |
| **预测**（基于近 7 天）下月预估 | 提前 budget |
| **Eval 成本** | Eval 占总成本比例 |

### 8.3 用户透明度（v1.5+）

考虑给用户看自己的 cost（"今日 AI 分析消耗 $0.32 / 预算 $1.50"），增加感知。

---

## 9. 月度报表（Cost Review）

每月 1 日 PM + 工程出 Cost Review：

```markdown
# Monthly Cost Review - 2026-04

## 总览
- 总成本: $1850（预算 $2000）
- LLM cost: $1380
- 数据 / API: $200
- 服务器: $270
- 月环比: +12%（上月 $1650）

## Top 5 Cost Drivers
1. S07 review-engine 日复盘: $480 / 月
2. L3 辩论: $420 / 月
3. S04 共创建策略: $180 / 月
4. ...

## 异常
- 4/12 当日 cost spike $120（正常 $65）→ 1 个 device 异常 1 小时调用 200 次 thesis（已限流）

## Cache 命中率
- S01: 94% ✅
- S07: 76% ⚠️ 需优化（System prompt 频繁更新）

## 预测
下月预估: $1900-$2050（DAU 增长 10%）

## Action Items
1. S07 prompt cache breakpoint 调整（提升命中率到 85%+）
2. 考虑日复盘改 Batch API（节省 $240 / 月）
3. ...
```

### 9.1 季度 review

- 是否需要切 v2 Tier 分级？
- DAU 增长趋势 → 预算调整
- 模型 side 涨价 / 降价 → 成本影响

---

## 10. Eval 成本（独立 budget）

对齐 [09 § 11.4](./09-eval-plan.md#114-llm-调用的录像--回放v02-强化)：

| 项 | 月成本 |
|----|-------|
| 日常 PR CI（回放为主）| $50-100 |
| 周 full regression（含部分真调）| $150-300 |
| 月度 re-record + drift check | $100-200 |
| Prompt 改版 re-record | $50-150 |
| Judge 校准（GPT-4 交叉）| $20-40 |
| **合计** | **$500-1500 / 月** |

**Eval 预算独立**（不挤占生产 LLM 预算），月度报表分开。

---

## 11. Hard Limits（硬上限）

无论什么场景，以下永不可超：

| 限制 | 值 | 后果 |
|------|---|------|
| 月度 LLM 总预算 Hard Cap | **$2250**（150%）| 全局 BLOCKED + 创始人通知 |
| 单 device 月成本 Hard Cap | $50 | 该 device 暂停 |
| 单次 LLM 调用 input tokens | 50K | 拒绝（超 prompt budget）|
| 单次 LLM 调用 output tokens | 8K | 截断 + warning |
| Eval 月度成本 Hard Cap | $2000 | 暂停 nightly full run |
| 单 PR 触发的 Eval cost | $50 | 拒绝 merge（要求优化）|

---

## 12. 现状 Gap

| # | Gap | 影响 | v1 目标 |
|---|-----|------|--------|
| G1 | Anthropic Prompt Caching 未集成 | 多 30-40% 成本 | v1 必接入 |
| G2 | `llm_cost_log` 表 + Dashboard 未建 | 无成本归因 | v1 启动前 |
| G3 | CB04 第 1/2/3 级降级未实现 | 无运行时熔断 | v1 必备 |
| G4 | 单 device 限流（cost > $3/day）未实现 | bot 攻击风险 | v1 必备 |
| G5 | 月度 Cost Review 流程未跑过 | 趋势盲区 | v1 上线后立即开始 |
| G6 | Batch API 未集成（日复盘）| 多 50% 复盘成本 | v1.5 |
| G7 | v2 Tier 分级方案未细化 | DAU 增长后无路径 | v1.5 设计 |
| G8 | Cost 与 SLO 联动（Error Budget）未建 | 不能"超预算暂停发布" | v1.5 |

---

## 13. 术语表

| 术语 | 含义 |
|------|------|
| Prompt Caching | Anthropic 提供的 input tokens 缓存（90% off）|
| Batch API | 非实时批量调用（50% off）|
| Cost Attribution | 成本归因（device / Skill / Prompt 维度）|
| Hard Cap | 硬上限，永不可超 |
| Tier 分级 | 按用户付费等级提供不同模型 |
| Cache Hit Rate | 缓存命中率（key metric）|

---

## Change Log

- **v0.1 (2026-04-24)**：首版完整填充
  - § 1 总预算（$2000 / 月 @ 100 DAU）+ v1→v2 规模演进表
  - § 2 4 条 Loop 成本（Scout $0 / Thesis L2 $0.025 / L3 $0.35 / Reflect $0.15-1.0）
  - § 3 7 个 Skill 月 / DAU 成本（合计 ~$14 / DAU）
  - § 4 17 个 Tool 成本（绝大多数 $0）
  - § 5 v1 全 Opus 选型 + v2 Tier 分级方案
  - § 6 **Cost 熔断器 CB04 4 级降级 + 单 device 熔断 + 异常 Pattern 检测**
  - § 7 **6 类成本优化策略**：
    * Prompt Caching（30-40% off，最重要）
    * Eval Recording / Replay
    * Skill 分级触发 + Output token 限制
    * Batch API（复盘 50% off）
    * Memory 缓存
  - § 8 **Cost Attribution**：`llm_cost_log` 表 schema + Dashboard 6 视图
  - § 9 月度 Cost Review 模板 + 季度 review
  - § 10 Eval 独立预算 $500-1500
  - § 11 **Hard Limits 6 项**（永不可超）
  - § 12 8 条现状 Gap
- v0（2026-04-22）：初始骨架
