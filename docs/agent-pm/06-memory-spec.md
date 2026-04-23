# 06 Memory Spec

> 定义 Agent 的 4 层记忆系统：写什么、留多久、谁读。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |

---

## 1. Memory Layers Overview

| Layer | 存什么 | TTL | 读取时机 | 存储介质 |
|-------|-------|-----|---------|---------|
| Working Memory | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| Episodic Memory | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| Semantic Memory | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| Reflection Log | _TODO_ | _TODO_ | _TODO_ | _TODO_ |

---

## 2. Working Memory

### 2.1 Purpose

_TODO_

### 2.2 Schema

_TODO_

### 2.3 Read/Write Rules

_TODO_

### 2.4 Eviction Policy

_TODO_

---

## 3. Episodic Memory

### 3.1 Purpose

_TODO_

### 3.2 Schema（事件 / 决策 / 结果）

_TODO_

### 3.3 Retrieval（相关性检索）

_TODO：embedding / keyword / hybrid；相关度阈值。_

### 3.4 索引策略

_TODO_

---

## 4. Semantic Memory

### 4.1 Purpose

_TODO_

### 4.2 规则学习机制

_TODO：何时从 Episodic 提炼到 Semantic；统计显著性门槛。_

### 4.3 Schema

_TODO_

### 4.4 冲突解决

_TODO：新旧规则冲突；人工审核；自动降权。_

---

## 5. Reflection Log

### 5.1 Purpose

_TODO_

### 5.2 反思节奏

_TODO：日反思 / 周反思 / 事件触发反思。_

### 5.3 输出格式

_TODO_

---

## 6. 跨层读写矩阵

| Tool | Working | Episodic | Semantic | Reflection |
|------|---------|----------|----------|------------|
| T04 analyze_technical | _TODO_ | _TODO_ | _TODO_ | _TODO_ |
| T12 recall_memory | _TODO_ | _TODO_ | _TODO_ | _TODO_ |

---

## 7. 隐私与合规

_TODO：用户数据保留期、删除请求、审计日志。_

---

## 8. 性能与扩展

_TODO：存储量估算、检索 latency 目标、多实例共享方案。_

---

## Change Log

- v0：初始骨架
