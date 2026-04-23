# 16 Trajectory Evaluation 🟡 P2

> 不只测单次调用，测**完整多步骤任务的轨迹质量**。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |
| Priority | P2 |

---

## 1. Trajectory Eval 是什么

_TODO：和 Unit / Integration Eval 的差异；为什么重要（Cognition Devin 的核心方法）。_

---

## 2. 典型 Trajectory

### 2.1 "从信号到模拟盘建仓"

_TODO：完整链路 + 每一步期望。_

### 2.2 "从用户提问到生成策略"

_TODO_

### 2.3 "从日复盘到 Semantic Memory 更新"

_TODO_

### 2.4 "从异常检测到 HITL 暂停"

_TODO_

---

## 3. Trajectory Dataset

### 3.1 Golden Trajectories

_TODO：每类场景 10-30 条完整轨迹 + 理想执行步骤。_

### 3.2 Dataset 格式

```yaml
trajectory_id: _TODO_
scenario: _TODO_
initial_state: _TODO_
ideal_steps:
  - step: _TODO_
    expected_tool: _TODO_
    expected_output_pattern: _TODO_
success_criteria:
  - _TODO_
```

### 3.3 对抗性 Trajectory

_TODO：包含噪音 / 干扰 / Prompt Injection 的轨迹。_

---

## 4. 评估维度

| 维度 | 描述 | 权重 |
|------|------|------|
| Correctness（最终结果对错） | _TODO_ | _TODO_ |
| Efficiency（步骤数 / 成本 / 时长） | _TODO_ | _TODO_ |
| Safety（是否触碰 Safety Policy） | _TODO_ | _TODO_ |
| Memory Usage（是否合理用记忆） | _TODO_ | _TODO_ |
| Tool Selection（选对了 tool 吗） | _TODO_ | _TODO_ |

---

## 5. 评分方法

### 5.1 LLM-as-Judge

_TODO：让 Claude Opus 当裁判，打分标准。_

### 5.2 规则校验

_TODO：确定性规则（比如必须调用 recall_memory）。_

### 5.3 人工抽检

_TODO_

---

## 6. 运行机制

### 6.1 CI 集成

_TODO：每次改 Agent 核心逻辑触发 trajectory eval。_

### 6.2 Weekly Full Run

_TODO_

### 6.3 Regression 门槛

_TODO_

---

## 7. 结果分析

### 7.1 失败模式归类

_TODO：tool 选错 / 参数错 / 顺序错 / 陷入循环 / 放弃_。

### 7.2 Pattern 挖掘

_TODO：系统性弱点识别。_

---

## 8. 扩展：Long-Horizon Task

_TODO：跨天 / 跨周的长期任务如何评估（例如"持仓 3 天观察加减仓决策"）。_

---

## Change Log

- v0：初始骨架
