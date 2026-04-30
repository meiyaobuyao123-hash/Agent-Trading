# Agent PM 文档体系

> 按 **harness 工程规范**组织的加密交易 Agent 产品文档目录。对标 Anthropic / OpenAI / DeepMind / Cognition 等一线 AI 团队的文档体系。

---

## Agent 核心能力

1. 查询行情
2. 分析行情
3. 自定义信号策略
4. 自定义交易策略
5. 模拟盘
6. 策略回测
7. 策略复盘

---

## 文档矩阵（17 份）

### L1 战略层（定义做什么、给谁、为什么）

| # | 文档 | 状态 | Owner |
|---|------|------|-------|
| 01 | [Product Vision](./01-product-vision.md) | 🟡 TODO | - |
| 02 | [User Persona & Journey](./02-user-persona-journey.md) | 🟡 TODO | - |
| 03 | [PRD 总](./03-prd.md) | 🟡 TODO | - |

### L2 Agent 设计层（harness 规范核心）

| # | 文档 | 状态 | Owner |
|---|------|------|-------|
| 04 | [Agent Spec](./04-agent-spec.md) | 🟡 TODO | - |
| 05 | [Tool Catalog](./05-tool-catalog.md) | 🟡 TODO | - |
| 06 | [Memory Spec](./06-memory-spec.md) | 🟡 TODO | - |
| 07 | [Prompt Library](./07-prompt-library.md) | 🟡 TODO | - |
| 08 | [Safety & Risk Policy](./08-safety-policy.md) | 🟡 TODO | - |

### L3 质量层（eval-driven）

| # | 文档 | 状态 | Owner |
|---|------|------|-------|
| 09 | [Eval Plan](./09-eval-plan.md) | 🟡 TODO | - |
| 10 | [Quality Rubric](./10-quality-rubric.md) | 🟡 TODO | - |

### L4 交付层

| # | 文档 | 状态 | Owner |
|---|------|------|-------|
| 11 | [Launch Criteria + HITL Policy](./11-launch-criteria-hitl.md) | 🟡 TODO | - |

### L5 运营与风险（一线团队必备，初版缺失）

| # | 文档 | 优先级 | 状态 | Owner |
|---|------|-------|------|-------|
| 12 | [Incident Response SOP](./12-incident-response-sop.md) | 🔴 P0 | 🟡 TODO | - |
| 13 | [Cost Budget](./13-cost-budget.md) | 🔴 P0 | 🟡 TODO | - |
| 14 | [Red Team Playbook](./14-red-team-playbook.md) | 🟠 P1 | 🟡 TODO | - |
| 15 | [Observability & Tracing Spec](./15-observability-tracing.md) | 🟠 P1 | 🟡 TODO | - |
| 16 | [Trajectory Evaluation](./16-trajectory-eval.md) | 🟡 P2 | 🟡 TODO | - |

### L6 工程落地（PM 设计文档 → 代码的技术方案）

| # | 文档 | 状态 | Owner |
|---|------|------|-------|
| 17 | [Tech Plan v1](./17-tech-plan.md) | 🟢 v0.1 Draft | 工程负责人 |

---

## 文档关系图

```
         ┌─────────────────────────────────┐
         │   01 Vision  →  02 Persona      │   L1 战略
         │        ↓                         │
         │      03 PRD                      │
         └────────────┬────────────────────┘
                      │
         ┌────────────┴────────────────────┐
         │   04 Agent Spec                  │   L2 Agent 设计
         │   ├─ 05 Tool Catalog             │
         │   ├─ 06 Memory Spec              │
         │   ├─ 07 Prompt Library           │
         │   └─ 08 Safety Policy            │
         └────────────┬────────────────────┘
                      │
         ┌────────────┴────────────────────┐
         │   09 Eval Plan ←→ 10 Rubric      │   L3 质量
         │   16 Trajectory Eval             │
         └────────────┬────────────────────┘
                      │
         ┌────────────┴────────────────────┐
         │   11 Launch + HITL               │   L4 交付
         └────────────┬────────────────────┘
                      │
         ┌────────────┴────────────────────┐
         │   12 Incident SOP                │   L5 运营
         │   13 Cost Budget                 │
         │   14 Red Team                    │
         │   15 Observability               │
         └─────────────────────────────────┘
```

---

## 产出节奏建议

| Phase | 时长 | 产出 |
|-------|------|------|
| Phase A | 2 周 | 01-11 全部骨架填充 + 12/13 |
| Phase B | 1 月 | 14/15/16 落地 |
| Phase C | 持续迭代 | - |

---

## 文档活性要求（harness 规范）

- **Tool Catalog**：加 tool 必同步更新（CI 校验）
- **Prompt Library**：改 prompt 必跑 eval + 更新 CHANGELOG
- **Safety Policy**：Agent 运行时读取此文件（文档即代码）
- **Eval Plan**：weekly dashboard 自动跑

> 90 天无 commit 的文档视为**失活**。

---

## 版本

- v0（本次）：结构骨架，无具体内容
- v1（下一步）：填充 01-04 + 12/13 内容
