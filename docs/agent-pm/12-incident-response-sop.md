# 12 Incident Response SOP 🔴 P0

> Agent 出现异常决策 / 工具故障 / 成本失控时的响应手册。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |
| Priority | P0 |

---

## 1. 事故等级定义

| Severity | 定义 | 响应时间 | 通知渠道 |
|----------|------|---------|---------|
| SEV-1 | 资金损失 / 数据泄露 | _TODO_ | _TODO_ |
| SEV-2 | 服务中断 / 大面积误决策 | _TODO_ | _TODO_ |
| SEV-3 | 局部功能异常 | _TODO_ | _TODO_ |
| SEV-4 | 体验问题 | _TODO_ | _TODO_ |

---

## 2. On-Call 轮值

_TODO：排班机制、联系方式、备份 on-call。_

---

## 3. 响应流程

### 3.1 检测（Detect）

_TODO：自动告警规则 / 用户投诉入口 / 自检 hook。_

### 3.2 分级（Triage）

_TODO：分级判断流程图。_

### 3.3 止血（Mitigate）

| 场景 | 止血手段 | 执行人 |
|------|---------|-------|
| Agent 持续错误决策 | Kill Switch | _TODO_ |
| 单 Prompt 退化 | Rollback 到上一版 | _TODO_ |
| 单 Tool 故障 | 关闭该 Tool，走降级 | _TODO_ |
| LLM 成本飙升 | 触发成本熔断 | _TODO_ |
| 数据源异常 | 切到备用源 | _TODO_ |

### 3.4 调查（Investigate）

_TODO：怎么复现、怎么取 trace、需要什么日志。_

### 3.5 修复（Fix）

_TODO：热修 vs 正式 PR 的决策。_

### 3.6 复盘（Postmortem）

_TODO：无指责文化 / 模板 / 时间窗口。_

---

## 4. Postmortem 模板

```
## Incident: _TODO_
- Date / Duration:
- Severity:
- Impact: (用户数 / 金额 / 决策数)
- Root Cause:
- Timeline:
- What went well:
- What went wrong:
- Action items (with owner + due date):
```

---

## 5. Kill Switch 操作手册

### 5.1 触发场景

_TODO_

### 5.2 操作步骤

_TODO_

### 5.3 权限

_TODO：谁可以按 / 谁可以复位。_

### 5.4 影响范围

_TODO：按下后 Agent / 前端 / 通知 的表现。_

---

## 6. 用户沟通

### 6.1 透明度原则

_TODO：哪些事故必须告知用户、告知时间窗口。_

### 6.2 公告模板

_TODO_

---

## 7. Runbook（常见故障）

| 故障类型 | 症状 | 处理步骤 |
|---------|------|---------|
| LLM 超时飙升 | _TODO_ | _TODO_ |
| Tool 循环调用 | _TODO_ | _TODO_ |
| Memory 读取失败 | _TODO_ | _TODO_ |
| DEX 路由失败 | _TODO_ | _TODO_ |

---

## 8. 事故台账

_TODO：所有事故记录的位置 / 格式 / 访问权限。_

---

## Change Log

- v0：初始骨架
