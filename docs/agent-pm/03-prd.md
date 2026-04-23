# 03 PRD（总）

> 按 **6 大核心能力**组织的 v1 MVP 需求。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |
| Target Release | TBD |

---

## 0. 文档导读

_TODO：谁要看这份 PRD、看完要做什么决策。_

## 0.1 MoSCoW 图例

- **MUST** 🔴：MVP 必须
- **SHOULD** 🟠：应该有，可延后 1-2 周
- **COULD** 🟡：有余力再做
- **WON'T** ⚫：v1 明确不做

---

## 1. Market Query（查询行情）

### 1.1 用户故事

_TODO：As a ..., I want ..., so that ..._

### 1.2 功能需求

| 优先级 | 功能点 | 验收标准 |
|-------|-------|---------|
| 🔴 | _TODO_ | _TODO_ |

### 1.3 数据源

_TODO：用哪些 API、成本、延迟。_

### 1.4 边界

_TODO：不支持的查询类型。_

---

## 2. Market Analysis（分析行情）

### 2.1 用户故事

_TODO_

### 2.2 功能需求

_TODO_

### 2.3 分析维度

_TODO：技术面 / 基本面 / 情绪面 / 链上面 各自包含什么。_

---

## 3. Signal Strategy Builder（自定义信号策略）

### 3.1 用户故事

_TODO_

### 3.2 功能需求

_TODO：规则式 vs 自然语言式；可组合性；冷却；版本管理。_

### 3.3 Strategy Schema

_TODO：JSON schema 示例。_

---

## 4. Trade Strategy Builder（自定义交易策略）

### 4.1 用户故事

_TODO_

### 4.2 功能需求

_TODO：入场/出场/加仓/止损；仓位管理；多标的组合。_

### 4.3 与 Signal Strategy 的关系

_TODO：信号 → 交易的触发链路。_

---

## 5. Paper Trading（模拟盘）

### 5.1 用户故事

_TODO_

### 5.2 功能需求

_TODO：多组合、实时 PnL、滑点模拟、gas 模拟、到期归档。_

### 5.3 真实盘切换条件

_TODO：满足哪些条件才允许从模拟盘切真实盘。_

---

## 6. Backtest（策略回测）

### 6.1 用户故事

_TODO_

### 6.2 功能需求

_TODO：时间窗口、数据源、结果指标、可视化。_

### 6.3 回测结果指标

_TODO：列出必须展示的指标（胜率/收益/最大回撤/Sharpe/Calmar ...）。_

---

## 7. Review（策略复盘）

### 7.1 用户故事

_TODO_

### 7.2 功能需求

_TODO：日复盘 / 周复盘 / 策略维度复盘。_

### 7.3 复盘产出

_TODO：自动 insights / 规则提议 / 策略调优建议。_

---

## 8. Cross-cutting Requirements（通用需求）

### 8.1 性能

_TODO：每个能力的 latency 目标。_

### 8.2 可用性

_TODO：SLA 目标。_

### 8.3 国际化 / 合规

_TODO：多语言 / CN 限制 / 免责声明。_

---

## 9. Out of Scope（v1 不做）

_TODO：明确列出 v1 不做的功能（可能 v2 做）。_

---

## 10. Dependencies & Risks

_TODO：外部依赖（API / 监管 / 模型）、已识别风险。_

---

## Change Log

- v0：初始骨架
