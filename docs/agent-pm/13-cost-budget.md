# 13 Cost Budget 🔴 P0

> 每个 Loop / Tool / Prompt 的 token + API 预算，防止成本失控。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |
| Priority | P0 |

---

## 1. 总预算约束

### 1.1 月度预算

| 项目 | 预算上限 | 告警阈值 | 熔断阈值 |
|------|---------|---------|---------|
| Anthropic LLM | _TODO_ | 80% | 100% |
| OpenAI LLM | _TODO_ | 80% | 100% |
| DEX API (Jupiter/1inch) | _TODO_ | 80% | 100% |
| Data API (DexScreener/Gecko) | _TODO_ | 80% | 100% |
| 服务器 | _TODO_ | 80% | 100% |
| **总计** | _TODO_ | - | - |

### 1.2 单用户成本上限

_TODO：每活跃用户日均成本 / 月均成本上限。_

---

## 2. 分 Loop 预算

| Loop | 频率 | 单次成本 | 日调用数 | 日预算 |
|------|------|---------|---------|-------|
| Scout Loop | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| Thesis Loop | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| Notify Loop | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| Reflect Loop | _TODO_ | _TODO_ | _TODO_ | _TODO_ |

---

## 3. 分 Tool 预算

| Tool ID | 模型 | Input Tokens | Output Tokens | 单次成本 | 日调用上限 |
|---------|------|--------------|---------------|---------|-----------|
| T04 analyze_technical | _TODO_ | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| T05 analyze_sentiment | _TODO_ | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| T06 analyze_onchain | _TODO_ | _TODO_ | _TODO_ | _TODO_ | _TODO_ |

---

## 4. 模型选择原则

_TODO：什么场景用 Haiku、什么用 Sonnet、什么用 Opus；成本 vs 质量权衡。_

---

## 5. 成本熔断机制

### 5.1 熔断条件

| 条件 | 动作 |
|------|------|
| 小时成本 > $X | _TODO_ |
| 日成本 > 预算的 80% | _TODO_ |
| 单用户日成本 > $X | _TODO_ |

### 5.2 熔断后降级

_TODO：降级到规则引擎 / 减频率 / 停推送。_

### 5.3 恢复机制

_TODO_

---

## 6. 成本优化策略

### 6.1 Prompt 优化

_TODO：压缩 prompt / few-shot 精简 / 输出格式优化。_

### 6.2 缓存

_TODO：Prompt Caching / Response Caching。_

### 6.3 分级

_TODO：小请求小模型、大请求大模型。_

### 6.4 Batch

_TODO：Batch API 使用场景。_

---

## 7. 监控与报表

### 7.1 Dashboard

_TODO：实时成本看板 / 分维度展示。_

### 7.2 月度报表

_TODO_

### 7.3 异常告警

_TODO_

---

## 8. Cost Attribution（归因）

_TODO：分用户 / 分策略 / 分 Tool 的成本归因方法。_

---

## Change Log

- v0：初始骨架
