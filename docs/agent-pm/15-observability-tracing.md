# 15 Observability & Tracing Spec 🟠 P1

> 每次决策的完整 trace：prompt / tool_call / tool_result / latency / cost / outcome。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |
| Priority | P1 |

---

## 1. 设计原则

- **无 trace 无决策**：每个 LLM 调用必有 trace
- **可回放**：trace 足以重建决策上下文
- **低开销**：trace 采集 < 5% 原始请求时间
- **可审计**：90 天内任何决策都能调出

---

## 2. 技术选型

_TODO：OpenTelemetry / Langfuse / LangSmith / 自建 的对比和选择。_

---

## 3. Trace Schema

### 3.1 Decision Trace

```yaml
trace_id: _TODO_
agent_version: _TODO_
session_id: _TODO_
user_id: _TODO_
timestamp: _TODO_
loop: _TODO_         # scout / thesis / notify / reflect
status: _TODO_       # success / failed / blocked
duration_ms: _TODO_
total_cost_usd: _TODO_

spans:
  - span_id: _TODO_
    type: _TODO_     # tool_call / llm_call / db_query
    name: _TODO_
    duration_ms: _TODO_
    input: _TODO_
    output: _TODO_
    cost: _TODO_
    error: _TODO_
```

### 3.2 LLM Span

_TODO：prompt 版本 / token 数 / 模型 / temperature / 完整 I/O。_

### 3.3 Tool Span

_TODO：tool id / input / output / error / 重试。_

### 3.4 Safety Span

_TODO：触发的规则 / 决策 / 违规详情。_

---

## 4. 日志级别

| Level | 用途 | 保留时长 |
|-------|------|---------|
| DEBUG | _TODO_ | _TODO_ |
| INFO | _TODO_ | _TODO_ |
| WARN | _TODO_ | _TODO_ |
| ERROR | _TODO_ | _TODO_ |
| AUDIT | _TODO_ | _TODO_ |

---

## 5. Metrics（聚合指标）

| Metric | 粒度 | 告警阈值 |
|--------|------|---------|
| decision_latency_p95 | _TODO_ | _TODO_ |
| tool_error_rate | _TODO_ | _TODO_ |
| llm_cost_per_decision | _TODO_ | _TODO_ |
| safety_violation_count | _TODO_ | _TODO_ |
| hitl_pending_queue_size | _TODO_ | _TODO_ |

---

## 6. Dashboards

### 6.1 Realtime Dashboard

_TODO：实时监控页面，展示哪些指标。_

### 6.2 Decision Explorer

_TODO：按 trace_id / user_id 检索和展示决策链路。_

### 6.3 Cost Dashboard

_TODO：参考 13-cost-budget.md。_

---

## 7. 告警规则

| 告警 | 触发条件 | 严重度 | 通知 |
|------|---------|-------|------|
| LLM 超时飙升 | _TODO_ | _TODO_ | _TODO_ |
| Tool error > X% | _TODO_ | _TODO_ | _TODO_ |
| 成本异常 | _TODO_ | _TODO_ | _TODO_ |
| Safety 连续触发 | _TODO_ | _TODO_ | _TODO_ |

---

## 8. 隐私合规

_TODO：用户数据脱敏 / 保留期 / 删除请求处理。_

---

## 9. Trace 生命周期

_TODO：采集 → 传输 → 存储 → 查询 → 归档 → 删除。_

---

## Change Log

- v0：初始骨架
