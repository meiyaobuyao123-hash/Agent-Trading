# 04 Agent Spec（harness 核心）

> 定义 Agent 本体：身份、能力、边界、状态机、失败模式。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |

---

## 1. Agent Identity

### 1.1 Mission（使命句）

_TODO_

### 1.2 Competencies（能做的）

_TODO：列出核心能力，与 PRD 的 6 大能力对齐但更抽象。_

### 1.3 Limits（不做的）

_TODO：硬性边界，不可跨越。_

### 1.4 Personality（性格 / 说话风格）

_TODO：严谨 vs 亲和、使用术语密度、emoji 用量、是否给建议、是否讲故事。_

---

## 2. Architecture

### 2.1 分层架构（ASCII 图）

```
_TODO：绘制分层图
```

### 2.2 四条 Loop

| Loop | 频率 | 职责 | 触发方式 |
|------|------|------|---------|
| Scout Loop | _TODO_ | _TODO_ | _TODO_ |
| Thesis Loop | _TODO_ | _TODO_ | _TODO_ |
| Notify Loop | _TODO_ | _TODO_ | _TODO_ |
| Reflect Loop | _TODO_ | _TODO_ | _TODO_ |

### 2.3 各 Loop 的数据输入/输出

_TODO：每条 Loop 详述。_

---

## 3. Input / Output Contract

### 3.1 Agent 的对外 API

_TODO：输入格式、输出格式、error code。_

### 3.2 事件规范

_TODO：Agent 监听哪些事件、产生哪些事件。_

---

## 4. State Machine

### 4.1 状态列表

_TODO：idle / scanning / analyzing / awaiting_approval / executing / reflecting / blocked / 等。_

### 4.2 状态转移图

```
_TODO：状态转移图
```

### 4.3 每个状态允许的行为

_TODO：表格化。_

---

## 5. Failure Modes（失败模式）

| 失败类型 | 检测方式 | 降级行为 | 告警级别 |
|---------|---------|---------|---------|
| LLM 超时 | _TODO_ | _TODO_ | _TODO_ |
| Tool 失败 | _TODO_ | _TODO_ | _TODO_ |
| 数据不可用 | _TODO_ | _TODO_ | _TODO_ |
| Memory 读取失败 | _TODO_ | _TODO_ | _TODO_ |
| Safety 否决 | _TODO_ | _TODO_ | _TODO_ |

---

## 6. Agent 与其他系统的关系

_TODO：和信号采集 / 聪明钱追踪 / 模拟盘 / DEX 执行 的边界。_

---

## 7. Versioning

### 7.1 Agent 版本号规则

_TODO：semver / rolling / 其他。_

### 7.2 版本切换机制

_TODO：灰度 / 全量 / A/B。_

---

## Change Log

- v0：初始骨架
