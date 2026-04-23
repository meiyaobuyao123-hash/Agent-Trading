# 05 Tool Catalog（harness 核心，持续维护）

> Agent 所有能力的 tool 化清单。每个 tool 必有 **schema + eval + owner + version**。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |
| Total Tools | 0 / TBD |

---

## 0. 使用约定

- 每新增 tool 必须提交 **tool doc + input/output schema + 至少 10 条 golden case**
- CI 校验：新 PR 若加 tool 但无 schema/eval，自动 block
- Tool 废弃走 [08 Deprecation Policy](./08-safety-policy.md#deprecation)（待补）

---

## 1. Tool Inventory

| ID | Tool Name | Category | Status | Owner | Version |
|----|-----------|----------|--------|-------|---------|
| T01 | query_market | Market Data | 🟡 TODO | - | - |
| T02 | query_holders | Market Data | 🟡 TODO | - | - |
| T03 | query_onchain_activity | Market Data | 🟡 TODO | - | - |
| T04 | analyze_technical | Analysis | 🟡 TODO | - | - |
| T05 | analyze_sentiment | Analysis | 🟡 TODO | - | - |
| T06 | analyze_onchain | Analysis | 🟡 TODO | - | - |
| T07 | build_signal_strategy | Strategy | 🟡 TODO | - | - |
| T08 | build_trade_strategy | Strategy | 🟡 TODO | - | - |
| T09 | run_paper_trade | Execution | 🟡 TODO | - | - |
| T10 | run_backtest | Eval | 🟡 TODO | - | - |
| T11 | review_performance | Reflection | 🟡 TODO | - | - |
| T12 | recall_memory | Memory | 🟡 TODO | - | - |

---

## 2. Tool Specification Template

> 新增 tool 时 copy 此模板。

### T_XX: tool_name

**Purpose**: _TODO_

**Category**: _TODO_

**Input Schema** (JSON Schema):
```json
{
  "type": "object",
  "properties": {
    "TODO": "TODO"
  },
  "required": []
}
```

**Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "TODO": "TODO"
  }
}
```

**Error Cases**:
- _TODO_

**Cost / Latency Budget**:
- Latency: _TODO_
- Cost: _TODO_

**Dependencies**:
- _TODO（调用哪些外部 API / 内部表）_

**Eval**:
- Golden dataset: `tests/evals/TODO.yaml`
- Current pass rate: _TODO_

**Security**:
- _TODO（是否需要权限 / HITL）_

**Owner**: _TODO_
**Version**: _TODO_
**Created**: _TODO_
**Last Eval**: _TODO_

---

## 3. Tool Composition Rules

_TODO：哪些 tool 组合调用、顺序约束（例如：决策前必须先 recall_memory）。_

---

## 4. Tool Lifecycle

### 4.1 新增

_TODO：提案 → schema 审核 → eval 准备 → merge_

### 4.2 废弃

_TODO：标 deprecated → 通知依赖方 → 2 周迁移期 → 移除_

---

## Change Log

- v0：初始骨架
