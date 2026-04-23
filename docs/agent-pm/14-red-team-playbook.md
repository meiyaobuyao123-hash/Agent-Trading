# 14 Red Team Playbook 🟠 P1

> 主动攻击自己的 Agent，上线前把能发现的洞都发现。

| 字段 | 值 |
|------|---|
| Status | 🟡 Draft |
| Version | v0 |
| Owner | TBD |
| Priority | P1 |

---

## 1. Red Team 目标

_TODO：目标清单 / 不在 scope 内的攻击。_

---

## 2. Threat Model

### 2.1 攻击者画像

| 攻击者 | 动机 | 能力 | 典型手段 |
|-------|------|------|---------|
| Pump & Dump 操纵者 | _TODO_ | _TODO_ | _TODO_ |
| 恶意代币发行方 | _TODO_ | _TODO_ | _TODO_ |
| Prompt Injection 攻击者 | _TODO_ | _TODO_ | _TODO_ |
| 薅羊毛用户 | _TODO_ | _TODO_ | _TODO_ |
| 数据源污染 | _TODO_ | _TODO_ | _TODO_ |

### 2.2 攻击面

_TODO：API / Prompt / 数据源 / Memory / Tool / 用户输入。_

---

## 3. 攻击剧本（Attack Scenarios）

### 3.1 Prompt Injection

_TODO：构造含恶意指令的代币名 / 社交文本 / 用户输入，看 Agent 是否被劫持。_

### 3.2 信号污染

_TODO：伪造链上交易、刷量、伪 holder，让 Agent 误判。_

### 3.3 诱导违规

_TODO：用话术让 Agent 说出不应说的（承诺收益、违法建议）。_

### 3.4 极端市场

_TODO：闪崩 / 流动性蒸发 / 跨链桥故障下 Agent 的表现。_

### 3.5 成本攻击

_TODO：高频请求 / 长 prompt 耗尽 LLM 预算。_

### 3.6 Memory 污染

_TODO：通过长期反馈污染 Semantic Memory，引导后续决策偏差。_

### 3.7 越权

_TODO：尝试让 Agent 跳过 HITL / Safety 规则。_

---

## 4. 测试用例库

_TODO：每个剧本至少 20 条具体 payload。存储位置 `tests/redteam/`。_

---

## 5. 红队节奏

### 5.1 上线前

_TODO：全量剧本跑一遍 / 发现 Critical 必须修。_

### 5.2 上线后

_TODO：每月红队 1 次 / 重大改动触发红队。_

### 5.3 外部红队

_TODO：是否邀请外部红队 / Bug Bounty 计划。_

---

## 6. 发现 → 修复 → 回归

_TODO：红队发现的问题归属哪个文档（Safety Policy / Prompt / Tool）。_

---

## 7. 红队报告模板

```
## Red Team Report #_TODO_
- Date:
- Scope:
- Findings:
  - [CRITICAL] _TODO_
  - [HIGH] _TODO_
  - [MEDIUM] _TODO_
- Recommendations:
- Follow-up tickets:
```

---

## 8. 历史红队记录

_TODO：台账 / 复盘结论 / 已修复清单。_

---

## Change Log

- v0：初始骨架
