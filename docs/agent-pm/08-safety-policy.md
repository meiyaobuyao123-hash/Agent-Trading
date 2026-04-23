# 08 Safety & Risk Policy

> **文档即代码**：本文件的规则 Agent 运行时读取并强制执行。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |
| Machine-readable format | `safety_policy.yaml`（TODO 同步生成） |

---

## 1. Safety Levels

| Level | 含义 | 触发行为 |
|-------|------|---------|
| BLOCK | 硬禁止 | 直接拒绝，记录告警 |
| REVIEW | 需 HITL | 暂停等人工确认 |
| WARN | 软警告 | 执行但标记风险 |
| OK | 正常 | 直接执行 |

---

## 2. Hard Blocks（硬禁止）

### 2.1 交易执行层

| 规则 | 阈值 | 动作 |
|------|------|------|
| 单笔真实交易金额上限 | _TODO_ | BLOCK |
| 日累计交易上限 | _TODO_ | BLOCK |
| 新代币年龄下限 | _TODO_ | BLOCK |
| 流动性下限 | _TODO_ | BLOCK |
| goplus_risk = true | - | BLOCK |

### 2.2 市场状态层

| 规则 | 触发条件 | 动作 |
|------|---------|------|
| CRISIS 状态禁买 | _TODO_ | BLOCK |
| 异常波动熔断 | _TODO_ | BLOCK |

### 2.3 内容输出层

_TODO：禁止 Agent 说什么（例如承诺收益、诱导交易）。_

---

## 3. Soft Warnings（软警告）

| 规则 | 阈值 | UI 展示 |
|------|------|---------|
| Top10 持仓 > 70% | _TODO_ | _TODO_ |
| _TODO_ | _TODO_ | _TODO_ |

---

## 4. Circuit Breakers（熔断）

| 条件 | 动作 | 恢复方式 |
|------|------|---------|
| 24h 累计亏损 > 阈值 | _TODO_ | _TODO_ |
| 连续 N 次错误决策 | _TODO_ | _TODO_ |
| LLM 成本超限 | _TODO_ | _TODO_ |

---

## 5. Timeout & Fallback

| LLM 调用 | Timeout | Fallback |
|---------|---------|----------|
| technical_analyst | _TODO_ | _TODO_ |
| risk_reviewer | _TODO_ | _TODO_ |
| thesis_writer | _TODO_ | _TODO_ |

---

## 6. Security Boundaries

### 6.1 数据边界

_TODO：用户数据 / 内部数据 / 外部数据的读写权限。_

### 6.2 Tool 权限

_TODO：哪些 tool 可读、哪些可写、哪些涉及资金。_

### 6.3 Prompt Injection 防御

_TODO：用户输入清洗规则。_

---

## 7. Runtime Enforcement

### 7.1 规则加载机制

_TODO：Agent 启动时读 YAML → 每次决策前检查。_

### 7.2 违规日志

_TODO：violation log schema + 存储位置 + 告警通知。_

---

## 8. Deprecation Policy（内含）

_TODO：旧版本 tool / prompt 下线流程。_

---

## Change Log

- v0：初始骨架
