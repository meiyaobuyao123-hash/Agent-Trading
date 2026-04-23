# 07 Prompt Library（Prompt-as-Code）

> 所有 Prompt **版本化管理**，改版必跑 eval，CHANGELOG 可追溯。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |

---

## 0. 目录结构约定

```
prompts/
  v1/
    technical_analyst.md
    sentiment_analyst.md
    onchain_analyst.md
    debate_bull.md
    debate_bear.md
    debate_facilitator.md
    decision_agent.md
    risk_reviewer.md
    thesis_writer.md
    reflection.md
    strategy_builder.md
  v2/
    ...
  CHANGELOG.md
```

---

## 1. Prompt Inventory

| ID | Prompt | Tool Binding | Current Version | Last Eval | Pass Rate |
|----|--------|--------------|-----------------|-----------|-----------|
| P01 | technical_analyst | T04 | _TODO_ | _TODO_ | _TODO_ |
| P02 | sentiment_analyst | T05 | _TODO_ | _TODO_ | _TODO_ |
| P03 | onchain_analyst | T06 | _TODO_ | _TODO_ | _TODO_ |
| P04 | thesis_writer | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| P05 | strategy_builder | T07/T08 | _TODO_ | _TODO_ | _TODO_ |
| P06 | risk_reviewer | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| P07 | reflection | _TODO_ | _TODO_ | _TODO_ | _TODO_ |

---

## 2. Prompt Spec Template

> 每个 prompt 单独一份 .md 文件。

### Prompt: _TODO_

**Version**: v_TODO_
**Model**: _TODO_（e.g. claude-sonnet-4, haiku-3.5）
**Tool Binding**: _TODO_
**Expected Output Format**: _TODO_（JSON schema）

**System Prompt**:
```
_TODO_
```

**Input Variables**:
- `{{var_name}}`: _TODO_

**Few-Shot Examples**:

Example 1:
- Input: _TODO_
- Expected Output: _TODO_

**Eval**:
- Golden dataset: `tests/evals/prompt_TODO.yaml`
- Current pass rate: _TODO_

---

## 3. Versioning Rules

### 3.1 何时出新版本

_TODO：bugfix 递增 patch / 语义变化递增 minor / 结构大改递增 major。_

### 3.2 Eval 通过门槛

_TODO：新版本 vs 旧版本 pass rate 变化要求。_

### 3.3 回退机制

_TODO_

---

## 4. Prompt Engineering Guidelines

_TODO：团队内部约定（system vs user / 思维链 / JSON 输出 / 温度等）。_

---

## 5. CHANGELOG 样式

每次改 prompt 必写：
```
## [YYYY-MM-DD] prompt_name v1 → v2
- Reason: _TODO_
- Eval delta: _TODO_
- Deployed to: _TODO_（灰度 / 全量）
```

---

## Change Log

- v0：初始骨架
