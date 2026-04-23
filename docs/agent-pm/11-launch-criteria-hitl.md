# 11 Launch Criteria + HITL Policy

> 上线硬门槛 + 人机协作规则。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |

---

## 1. Launch Gates（上线门槛）

### 1.1 Tech Gates

| 指标 | 门槛 | 当前 |
|------|------|------|
| Unit Eval pass rate | _TODO_ | _TODO_ |
| Integration Eval pass rate | _TODO_ | _TODO_ |
| Trajectory Eval pass rate | _TODO_ | _TODO_ |
| Latency p95 | _TODO_ | _TODO_ |
| Cost per decision | _TODO_ | _TODO_ |
| Safety Policy 覆盖 | 100% | _TODO_ |
| Observability tracing | 100% | _TODO_ |

### 1.2 Product Gates

| 指标 | 门槛 |
|------|------|
| 30 天模拟盘 Sharpe | _TODO_ |
| 30 天模拟盘最大回撤 | _TODO_ |
| 用户 thesis 满意度 | _TODO_ |

### 1.3 Safety Gates

_TODO：Red Team 报告通过 / Incident SOP 就绪 / Cost Budget 设定_

### 1.4 Legal & Compliance Gates

_TODO：免责声明 / 区域限制 / 审计日志_

---

## 2. HITL Policy（人机介入规则）

### 2.1 强制 HITL 场景

| 触发条件 | 阈值 | 处理 |
|---------|------|------|
| 单笔金额 | _TODO_ | _TODO_ |
| 低置信度 | _TODO_ | _TODO_ |
| 市场 CRISIS | - | _TODO_ |
| 新代币（年龄） | _TODO_ | _TODO_ |
| 策略首次执行 | - | _TODO_ |

### 2.2 HITL 流程

```
_TODO：请求 → 通知 → 等待 → 超时 → 记录
```

### 2.3 超时策略

_TODO：超时默认行为（保守拒绝 vs 保守批准）。_

### 2.4 HITL UI

_TODO：APP / Web / 通知推送的展示要求。_

### 2.5 反馈回流

_TODO：用户审批决策 → 存入 Episodic Memory → 影响未来决策。_

---

## 3. Rollout Strategy

### 3.1 灰度方案

_TODO：5% → 25% → 50% → 100% 节奏。_

### 3.2 Rollback

_TODO：触发条件 / 回退速度 / 数据一致性处理。_

### 3.3 Kill Switch

_TODO：一键停止整个 Agent 的机制与权限。_

---

## 4. Post-Launch Monitoring

### 4.1 核心指标

_TODO_

### 4.2 异常告警

_TODO：阈值 / 渠道 / on-call 轮值_

### 4.3 复盘节奏

_TODO：日 / 周 / 月复盘的议程_

---

## Change Log

- v0：初始骨架
