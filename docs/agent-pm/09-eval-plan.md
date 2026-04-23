# 09 Eval Plan

> 回答："Agent 靠谱吗？每次改动让它更好还是更坏？"

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |

---

## 1. Eval 三层金字塔

```
         ┌───────────────────┐
         │  Trajectory Eval  │   端到端任务（见 16-trajectory-eval.md）
         └────────┬──────────┘
                  │
         ┌────────┴──────────┐
         │  Integration Eval │   多 tool 组合
         └────────┬──────────┘
                  │
         ┌────────┴──────────┐
         │    Unit Eval      │   单 tool / 单 prompt
         └───────────────────┘
```

---

## 2. Unit Eval（单 tool / 单 prompt）

### 2.1 覆盖范围

_TODO：每个 tool 最少 50 个 golden case。_

### 2.2 Golden Dataset 结构

_TODO：YAML schema + 存储位置。_

### 2.3 Pass Rate 目标

_TODO：每类 tool 的最低 pass rate。_

### 2.4 数据来源

_TODO：真实数据抽样 / 人工构造 / 历史 bug 复现。_

---

## 3. Integration Eval（多 tool 组合）

### 3.1 典型场景

_TODO：列出 10-20 个端到端场景（例如"给代币 X 生成完整 thesis"）。_

### 3.2 评估维度

_TODO：与 Unit Eval 的差异（关注 tool 间传递是否正确）。_

---

## 4. Human Eval

### 4.1 人工抽检

_TODO：每周抽 N 条样本 / 评估人员 / 打分标准引用 [10 Quality Rubric](./10-quality-rubric.md)。_

### 4.2 用户反馈

_TODO：APP 内点赞/点踩怎么回流到 eval。_

---

## 5. Regression Policy

### 5.1 PR 门槛

_TODO：改动必跑 eval / pass rate 下降 X% block。_

### 5.2 Weekly Regression

_TODO：周五跑全量 / Dashboard 记录趋势。_

### 5.3 Champion-Challenger

_TODO：新 prompt vs 旧 prompt 自动 A/B。_

---

## 6. Eval Infrastructure

_TODO：工具选型（pytest / promptfoo / langsmith / 自建）、CI 集成、存储。_

---

## 7. Golden Dataset 维护

### 7.1 扩充流程

_TODO_

### 7.2 过时数据清理

_TODO_

### 7.3 数据权属

_TODO_

---

## 8. Eval Dashboard

_TODO：展示维度、访问权限、告警规则。_

---

## Change Log

- v0：初始骨架
