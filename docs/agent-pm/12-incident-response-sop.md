# 12 Incident Response SOP

> Agent 出现异常决策 / 工具故障 / 成本失控 / 安全事件时的**响应手册**。
> on-call 工程师遇到任何告警**第一时间打开本文档**。

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.1 Draft |
| Version | v0.1 |
| Owner | 运维 + PM |
| Target Release | v1 MVP - 2026 Q3 |
| Priority | P0（v1 必备）|

---

## 0. 文档导读

### 0.1 为什么 Incident SOP 是 v1 必备

**没 SOP 的事故响应**：
- on-call 凌晨被叫起来，手忙脚乱，不知道先做什么
- 关键时刻找不到 Kill Switch 的命令
- 修完后没人记录原因，下次同样事故再来
- 用户被冷处理，信任崩塌

**有 SOP 的事故响应**：
- 5 min 内分级 → 15 min 内止血 → 1h 内修复 → 24h 内复盘
- 标准化 Runbook，新人也能值班
- Postmortem 沉淀为 Memory，下次自动 detect

### 0.2 和其他文档的关系

| 文档 | 关系 |
|------|-----|
| [08 Safety § 9.1 SEV 分级](./08-safety-policy.md#91-sev-分级违规事件分级) | SEV-0/1/2/3 定义来源 |
| [08 Safety § 13](./08-safety-policy.md#13-事故响应钩子引用-12) | Safety 事件 → 触发 Incident |
| [11 Launch § 9 Kill Switch](./11-launch-criteria-hitl.md#9-kill-switch紧急停止) | L1/L2/L3 Kill Switch 实施 |
| [11 Launch § 10.3 SLI/SLO](./11-launch-criteria-hitl.md#103-sli--slo-量化v02-新增) | Error Budget 触发响应 |
| [15 Observability](./15-observability-tracing.md) | 提供 trace + metrics |
| [14 Red Team](./14-red-team-playbook.md) | 主动制造 incident 演练 |

### 0.3 谁读本文档

- **on-call 工程师**：值班期间常驻
- **Sec Lead**：Safety 事件主责
- **PM**：用户沟通 + Postmortem 主持
- **CEO / Founders**：SEV-0 通报

---

## 1. 事故等级定义（对齐 [08 § 9.1](./08-safety-policy.md#91-sev-分级违规事件分级)）

| SEV | 定义 | 响应时间 | 通知渠道 | 谁能 close |
|-----|------|---------|---------|-----------|
| **SEV-0** 灾难 | 真金损失 > $1K 或大规模影响（> 10 用户）| **< 15 min** | PagerDuty + 短信 + 创始人电话 | 创始人 + Sec Lead |
| **SEV-1** 严重 | 单次严重违规 / HITL 失效 / 真金 < $1K | **< 1h** | PagerDuty + Slack | Sec Lead 或 PM |
| **SEV-2** 一般 | 频繁 WARN / 降级异常 / 单 Prompt 退化 | **< 4h** | Slack #alerts | on-call 工程师 |
| **SEV-3** 轻微 | 偶发告警 / 边缘 case fail | 24h 内 | Dashboard | 任何工程师 |

**升级规则**：
- SEV-2 持续 1h 未止血 → 升 SEV-1
- SEV-1 持续 2h 未止血 → 升 SEV-0
- 用户社交媒体公开投诉 SEV-2 → 升 SEV-1（声誉风险）

---

## 2. On-Call 轮值

### 2.1 轮值设计

| 角色 | 数量 | 轮值周期 | 职责 |
|------|-----|---------|------|
| **Primary on-call**（工程）| 1 人 | 1 周轮换 | 一线响应所有告警 |
| **Secondary**（工程，备份）| 1 人 | 1 周（与 Primary 错峰）| Primary 5min 不响应自动接力 |
| **Escalation**（Lead）| Sec Lead / PM Lead | 24/7 待命 | SEV-0/1 升级 |
| **Founder / CEO** | 创始人 | 24/7 | SEV-0 必须通知 |

### 2.2 轮值规则

- 单人最长连班 **7 天**
- 周末连班需 +1 天 comp 假
- 出差 / 度假**禁止**做 Primary
- 实际响应 1 次 SEV-0 计 0.5 天 comp
- 实际响应 1 次 SEV-1 计 0.25 天 comp

### 2.3 联系方式

`oncall.json`（私有 repo，不入 git，存 Vault）：
```json
{
  "primary": { "name": "...", "phone": "+86...", "tg": "@...", "pagerduty_id": "..." },
  "secondary": {...},
  "sec_lead": {...},
  "pm_lead": {...},
  "founder": {...}
}
```

### 2.4 Hand-off（交接）

每周一 09:00 UTC：
- 上周 Primary → 本周 Primary 30 min 交接
- 同步：未关 ticket / 待观察的指标 / 上周 Postmortem 结论
- 写入 `oncall_handoff_log`

---

## 3. 响应流程（5 阶段）

```
告警触发
   │
   ▼
┌──────────────┐
│ 1. Detect 检测 │  自动告警 / 用户投诉 / Eval 失败
└──────┬───────┘
       ▼
┌──────────────┐
│ 2. Triage 分级 │  5 min 内：SEV-0/1/2/3
└──────┬───────┘
       ▼
┌──────────────┐
│ 3. Mitigate  │  15 min 内：Kill Switch / Rollback / 降级
│   止血       │
└──────┬───────┘
       ▼
┌──────────────┐
│ 4. Investigate│  Mitigate 后 1h：找 Root Cause
│   调查       │
└──────┬───────┘
       ▼
┌──────────────┐
│ 5. Fix 修复   │  正式 PR / 热修
└──────┬───────┘
       ▼
┌──────────────┐
│ 6. Postmortem│  24h 内（SEV-0/1）/ 1 周（SEV-2/3）
│   复盘       │
└──────────────┘
```

### 3.1 Detect（检测）

**自动告警源**：
| 来源 | 触发示例 |
|------|---------|
| **PagerDuty** | SLO 烧穿 / Cost > 1.5× / Safety violation |
| **Slack #alerts** | 单 Prompt pass rate 跌 / 降级频发 |
| **Sentry / Error tracking** | 异常率 > 阈值 |
| **DB Cron 监控** | WAL 积压 / RPC 失败率高 |
| **用户反馈** | thumbs_down 集中 / Twitter 投诉（标签监控）|
| **Eval CI** | Regression block 持续 24h 未解 |

**人工 detect**：用户邮件 / 投诉 → 客服转 Slack `#user-issues` → on-call 评估。

### 3.2 Triage（5 min 内分级）

**SEV-0 立即识别条件**（任一命中）：
- 真金错误执行 > $500 / 单笔
- 多用户钱包余额异常变动
- KMS 密钥泄漏迹象
- safety_policy.yaml 加载失败 → 全局 BLOCKED 触发
- 系统对外 0% 可用 > 5 min

**SEV-1 识别**：
- 单笔真金错误 < $500
- HITL 流程失效（pending 不响应 / 跨过 HITL 直接执行）
- Prompt Injection 突破防御（漏到输出）
- Audit log 写入失败

**SEV-2/3 识别**：
- 单 Skill 局部失败 / 降级
- 用户体验 bug（不影响安全）
- 边缘 eval case fail

**Triage 操作**：
- on-call 5 min 内 ack（PagerDuty acknowledge）
- 创建 Slack 频道 `#incident-YYYYMMDD-NN`
- 邀请：on-call + Sec Lead（SEV-0/1）+ PM（用户影响）
- 创建 Ticket：`incidents/INC-YYYY-NNNN.md`

### 3.3 Mitigate（15 min 内止血）

**优先级：止血 > 调查**。先停损，原因后查。

| 场景 | 止血手段 | 命令 |
|------|---------|------|
| Agent 持续错误决策 | **Kill Switch L3**（全局真金停）| `scripts/kill_switch.py --level l3 --reason="..."` |
| 单 Prompt 退化 | Rollback 到上一版 | 改 `config.yaml` + 热推 |
| 单 Tool 故障 | Feature flag 关闭该 Tool | `flag_set feature.tool_X=false` |
| 单 Skill 退化 | Feature flag 关 Skill | `flag_set feature.skill_X=false` |
| LLM 成本飙升 | 触发 CB04 / 强制降级 Sonnet | `cost_throttle on` |
| 数据源异常 | 切备用源 + UI 标延迟 | `datasource switch helius->okx` |
| Memory 写入失败 | 进入只读模式（不写 Memory）| `memory readonly on` |
| Specific user / device 异常 | L2 单 device Kill Switch | `kill_switch.py --level l2 --device=...` |
| KMS / Audit 故障 | **Fail-safe 自动 BLOCKED**（policy_loader 触发）| 系统自动，等恢复 |

**Kill Switch 实操**：详见 § 5。

**Mitigate 后必做**：
- 在 `#incident-YYYYMMDD-NN` 频道 post 状态："Mitigated. Investigating root cause."
- 通知用户（按 § 6 公告模板）
- Update Status Page（v1.5+ 上线）

### 3.4 Investigate（找根因）

**Mitigate 后 1h 内开始调查**（不抢救火期）。

#### 3.4.1 调查手册

| 现象 | 调查路径 |
|------|---------|
| Agent 错误决策 | trace_id → Langfuse → 完整 LLM 调用链（prompt + response + tools）|
| 真金执行错误 | `agent_executions.trace_id` → 对应 thesis + RiskManager 决策 + KMS access log |
| Cost 飙升 | trace 聚合 → 哪个 Skill / Prompt 触发量异常 |
| Eval Regression | git bisect → 找到引入 PR |
| Injection 突破 | `security_audit_log` → 找漏的 input → 复现 |
| Memory 异常 | `memory_write_wal` retry queue + WAL 内容 |

#### 3.4.2 必收集证据

- 完整 trace_id 列表（受影响请求）
- 时间窗口（开始/结束）
- 受影响 device 数量
- 实际损失（金额 / 数据 / 用户体验）
- 触发原因（hypothesis）

#### 3.4.3 调查工具

- **Langfuse**：trace + LLM 调用详情
- **Postgres + Grafana**：DB 查询 + 指标趋势
- **Sentry**：异常堆栈
- **GitHub**：commit history + PR diff
- **`scripts/incident_helper.py`**：综合查询脚本（trace + audit + DB）

### 3.5 Fix（修复）

| 修复类型 | 流程 | 适用 |
|---------|------|-----|
| **Hot-fix**（紧急）| 直接 PR + 1 人 review + 跳过 Canary 直接 Beta | SEV-0/1 持续中 |
| **Standard PR** | 正常 PR 流程 + Canary 灰度 | SEV-2/3 |
| **Config 改动** | 改 `config.yaml` + 热推 | 阈值调整等 |
| **Rollback** | 配置切换前一版 | Prompt / Skill / Tool |

**Hot-fix 硬规定**：
- 必须双人 sign-off（不跳 review）
- Hot-fix merge 后 24h 内**必须**补完整测试 + Postmortem
- Hot-fix 后**禁止再 Hot-fix 同一模块** 7 天（防 cascading 错误）

### 3.6 Postmortem（复盘）

| SEV | 复盘时限 | 模板见 § 4 |
|-----|---------|----------|
| SEV-0 | **24h 内** | 完整 |
| SEV-1 | **3d 内** | 完整 |
| SEV-2 | **1 周内** | 简化（可省 stakeholder review）|
| SEV-3 | 不强制（可批量 review）| 可选 |

**Blameless 文化**（无指责）：
- 重点是"系统怎么变得更鲁棒"，不是"谁的错"
- Postmortem 不能写"X 的失误"（写"我们的检测/防护未覆盖此场景"）
- 工程师参加 Postmortem 不影响绩效

---

## 4. Postmortem 模板

存放于 `docs/postmortems/INC-YYYY-NNNN.md`。

```markdown
# Postmortem: [事件简要标题]

## Meta
- Incident ID: INC-2026-0042
- Date / Duration: 2026-04-25 14:00 - 15:30 UTC (1h 30min)
- SEV: 1
- Author: [PM / Sec Lead]
- Status: Draft | Reviewed | Closed

## Impact

- 受影响 device 数: 14
- 受影响金额: $0（paper） / $342（auto，已退款规划）
- 用户感知: 14 个 device 看到 thesis 错误引用 KOL 数据
- SLA 影响: 真金 swap SLO Error Budget 消耗 12 min

## Timeline（UTC）

| 时间 | 事件 |
|------|------|
| 13:55 | 部署 P02 sentiment_analysis Prompt v0.3 → Beta 25% |
| 14:08 | Slack 告警：sentiment_analysis pass rate 跌 12pp |
| 14:09 | on-call ack（< 5 min ✅）|
| 14:11 | Triage 判定 SEV-1 |
| 14:13 | Rollback：P02 切回 v0.2 |
| 14:15 | 受影响请求停止增长 |
| 14:30 | 用户公告发出 |
| 15:30 | 全部受影响 trace 排查完毕，确认 14 device |

## Root Cause

P02 v0.3 在 system prompt 加了"引用至少 3 个 KOL"的硬要求，但 KOL 数据为 0 时 LLM 编造了 KOL 名字。

具体：
- v0.3 改动: prompt L42-L48
- 触发条件: kol_signals 表 24h 无数据（哪些 token？）
- LLM 行为: 因硬要求 + 无数据 → 幻觉

## What Went Well

- ✅ 自动告警在 8 min 内触发（pass rate drop detection）
- ✅ on-call 响应 5 min 内
- ✅ Rollback 5 min 内完成
- ✅ Eval Regression 测试覆盖了部分情况但未覆盖"KOL 数据为 0"

## What Went Wrong

- ❌ Prompt 改版**未测**"KOL 数据为 0"边界
- ❌ Beta 25% 流量未发现，依赖 pass rate 阈值告警
- ❌ Eval Golden 没有"KOL 数据为 0"的 case

## Action Items

| # | Action | Owner | Due Date | Done |
|---|--------|-------|---------|------|
| 1 | P02 加"KOL 数据为 0 时不强求引用"的容错 | @工程 | 2026-04-26 | ☐ |
| 2 | Eval Golden 补 5 条"KOL 数据为 0"边界 case | @PM | 2026-04-28 | ☐ |
| 3 | Prompt 改版 PR 模板加"边界 case 列表" | @PM | 2026-04-30 | ☐ |
| 4 | 受影响 14 device 推送说明 + auto 仓位审查 | @PM | 2026-04-26 | ☐ |
| 5 | Canary 5% 流量监控加"幻觉率"指标 | @工程 | 2026-05-05 | ☐ |

## Lessons Learned（写入 06 Memory）

- 涉及 LLM "硬要求引用" 类 prompt → 必须配 "数据缺失容错" 分支
- Eval Golden 必须覆盖"输入字段为 0 / null / 空数组"边界

## Follow-up

- Action items 跟踪：JIRA-INC-42
- 关联 PR：#789（rollback）+ #790-794（Action items）
- 后续监控：14 天内 P02 pass rate 趋势
```

---

## 5. Kill Switch 操作手册

详细实现见 [11 Launch § 9](./11-launch-criteria-hitl.md#9-kill-switch紧急停止)。

### 5.1 触发场景

| 级别 | 触发场景 | 谁能按 |
|------|---------|-------|
| **L3 全局** | 系统级真金错误 / KMS 失效 / 大规模 Injection 突破 | Sec Lead + 创始人 |
| **L2 Device** | 单 device 异常（被盗 / 异常交易模式）| on-call 工程 + Sec Lead |
| **L1 用户** | 用户自己 APP 内一键 | 用户 |

### 5.2 操作步骤（L3 全局）

```bash
# 1. SSH 到任一生产节点（或本地 admin tool）
ssh ops@prod-1

# 2. 执行 kill_switch
python scripts/kill_switch.py \
    --level l3 \
    --reason "kms_key_leak_suspected" \
    --duration unlimited \
    --notify-all

# 3. 验证（< 5s 内全集群感知）
curl https://api.agent-trading.com/admin/agent_global_state
# 期望返回 status: "blocked"

# 4. 确认 T08 execute_swap 全部拒绝
tail -f /var/log/agent/t08.log
# 期望大量 "SAFETY_REJECTED reason: kill_switch"
```

### 5.3 解除步骤

L3 解除**必须**双人复核：

```bash
# 1. 创始人 / Sec Lead 发起解除
python scripts/kill_switch.py --level l3 --action release \
    --request-id REL-2026-001

# 2. 第二人复核（不同人）
python scripts/kill_switch.py --confirm-release REL-2026-001

# 3. 写 audit log + 全员通知
```

### 5.4 影响范围（用户感知）

| 级别 | UI 表现 |
|------|---------|
| L3 触发后 | 顶栏红色横幅"🛑 Agent 真金执行已暂停（系统维护）"|
| L2 Device | 该 device 红色横幅 + 暂停按钮变灰 |
| L1 User | 设置页"已暂停"标识 |

**已开仓位**：不强平，继续按 trade_strategy 监控止盈止损（避免 cascading 失败）。

---

## 6. 用户沟通

### 6.1 透明度原则

| 事故级别 | 必须告知 | 告知时间窗口 |
|---------|---------|------------|
| SEV-0 | 全平台用户 + Twitter / 官方公告 | 1h 内 |
| SEV-1 | 受影响 device + Status Page | 4h 内 |
| SEV-2 | 受影响 device | 24h 内 |
| SEV-3 | 不强制（可计入月度报告）| - |

**透明度硬原则**：
- ✅ 不隐瞒事故（即使无人发现也告知）
- ✅ 不甩锅（不归咎于"模型供应商" / "网络")
- ✅ 写明 root cause（即使是我们的失误）
- ❌ 不发"已修复请放心"式空话（必须说"修复了什么 / 不会再发生的措施")

### 6.2 公告模板

#### 6.2.1 SEV-0 全平台公告（Twitter + APP 内推 + Email）

```
[Service Update] 2026-04-25

我们于 14:00 UTC 检测到 Agent 在某些情况下错误执行真金交易。
检测后 12 分钟内已触发全局 Kill Switch，停止所有真金执行。

受影响:
- 14 个 device 的 auto 模式被错误触发，总金额 $342
- 我们已识别全部受影响交易并启动赔偿流程

我们做了什么:
1. 立即停止所有 auto 执行（已恢复 paper / notify_only 服务）
2. 受影响用户将收到 1:1 赔偿（24h 内到账钱包）
3. 修复后增加边界 case Eval 防止再发生

时间线:
- 14:00 部署新版本
- 14:08 自动告警触发
- 14:13 Rollback 完成
- 14:30 全部受影响交易识别完毕

详细 Postmortem 将于 24h 内发布。

如有疑问，回复本邮件 / Telegram @support
```

#### 6.2.2 SEV-1/2 受影响 device 推送

```
检测到您的策略 X 在 [时间窗口] 触发了异常。
我们已修复，您的资金未受影响。
具体细节: [链接]
```

### 6.3 不发的话（黑名单）

- ❌ "We apologize for the inconvenience"（无具体内容的道歉）
- ❌ "issue has been resolved"（不说怎么 resolve 的）
- ❌ "no impact to user funds"（无证据时不说，要先核实）
- ❌ 责怪上游（"due to our LLM provider"——用户不在乎）

---

## 7. Runbook（常见故障 SOP）

### 7.1 LLM 超时飙升

| 症状 | Latency P95 > 30s 持续 5 min |
| 立即操作 | 1) 检查 Anthropic Status Page; 2) 切 Sonnet fallback; 3) 通知用户延迟 |
| 调查 | 是模型 side（Anthropic incident）还是我方 prompt 改版？ |
| 联系 | Anthropic support if their issue |

### 7.2 Tool 循环调用 / 死循环

| 症状 | 单 trace 内同 Tool 调用 > 10 次 / 单 device 总调用 > 1000/min |
| 立即操作 | 1) 该 device kill switch L2; 2) 关闭 feature flag; 3) 排查 Skill 编排 bug |
| 调查 | trace_id → 找到 loop pattern |

### 7.3 Memory 读取失败

| 症状 | T04 recall_memory 失败率 > 5% |
| 立即操作 | 1) 切 Memory 只读模式（不写）；2) DB 连接池排查 |
| 调查 | DB query 是否慢？索引正常？|

### 7.4 DEX 路由失败

| 症状 | T08 execute_swap 失败率 > 10% |
| 立即操作 | 1) 切 OKX / Jupiter 备用源；2) 通知用户延迟；3) 不要重试已 broadcast 的 tx |
| 调查 | RPC 节点状态 / aggregator API 健康 |

### 7.5 KMS 失效

| 症状 | KMS API 失败率 > 1% / 5min（CB12 触发）|
| 立即操作 | 1) 自动进入 fail-safe BLOCKED；2) 通知 AWS / KMS provider |
| 调查 | KMS quota / 凭证过期 / 网络隔离 |

### 7.6 Cost 失控

| 症状 | 日 LLM cost > $50（CB04 触发）|
| 立即操作 | 1) 自动 L3→L2 降级；2) 排查异常 device（malicious user？）；3) 限流 |
| 调查 | 哪个 Skill 调用激增？是 bug 还是攻击？|

### 7.7 Helius WS 断连

| 症状 | heartbeat > 30s 无回应 |
| 立即操作 | 1) UI 标延迟模式；2) 切 OKX 轮询 P2；3) 重连 Helius |
| 调查 | Helius incident / 我方 IP 被 ban / 限流 |

### 7.8 Eval Regression

| 症状 | PR 后 pass rate 跌 ≥ 5pp（统计显著）|
| 立即操作 | 1) Block PR; 2) 看 McNemar test result; 3) 重跑 3 次确认 |
| 调查 | git bisect → 哪行改动 |

### 7.9 Injection Attack 突破

| 症状 | AE 对抗场景任一 fail / 用户输入"成功"绕过 Blocklist |
| 立即操作 | 1) 立即升级 input filter; 2) 限流该 device; 3) 检查是否漏到输出（用户看到？）|
| 调查 | 14 Red Team Playbook 再跑一轮 |

### 7.10 用户报"钱被偷"

| 症状 | 用户投诉钱包余额异常 |
| 立即操作 | 1) **立即** L2 该 device kill switch；2) 拉取 audit log + agent_executions；3) 不要立即承诺赔偿 |
| 调查 | 是 Agent 错误？还是用户钱包外部被盗？还是用户错记？ |

---

## 8. 事故台账

### 8.1 存放位置

- **公开 Postmortems**: `docs/postmortems/INC-YYYY-NNNN.md`（公开 Repo）
- **内部细节**: 私有 Confluence（含调查内幕 / 用户具体数据）
- **Audit log**: `incident_response_audit` 表（每次操作）

### 8.2 月度报告

每月 1 日 PM 整理上月 Incident Report：
- 总事件数（按 SEV 分布）
- MTTR（Mean Time To Resolution）
- Top 3 事故归因
- Action Items 完成率
- 趋势分析（是否事故率上升 → 触发系统性 review）

### 8.3 季度 review

- 整理累计 Postmortem 中的 lessons learned
- 看哪些类似事故重复发生 → 系统性问题
- Update 本 SOP

---

## 9. 演练（Fire Drill）

### 9.1 节奏

| 频率 | 类型 |
|------|------|
| **每月** | Kill Switch L1/L2/L3 演练 |
| **每月** | 模拟 SEV-1 走完整流程（不真停 production）|
| **每季** | 模拟 SEV-0 + 全员参与演习 |
| **新人入职** | 1 周内必参与一次 SEV-2 模拟 |

### 9.2 演练评估

- 响应时间 vs SLA
- 流程偏差点
- 工具是否就绪
- on-call 信心评分（1-5）

### 9.3 演练结果应用

- 演练结果**写入** Postmortem（Type: drill）
- 不达标 → Update SOP / 增加培训
- 月度演练通过率 < 80% → 升级 review

---

## 10. 现状 Gap

| # | Gap | 影响 | v1 目标 |
|---|-----|------|--------|
| G1 | PagerDuty 未集成 | 告警靠 Slack | v1 必接入 |
| G2 | on-call rotation 未设定 | 没人值班 | v1 启动前确定 4 人轮值 |
| G3 | Runbook 未沉淀代码 | scripts/kill_switch.py 等待写 | v1 上线前 |
| G4 | Postmortem 流程未跑过 | 未实践 | v1 前先做 1-2 次 dry run |
| G5 | Kill Switch 未演练 | 实际 SLA 未知 | v1 前每级各演练 1 次 |
| G6 | Status Page 未建 | 用户无实时状态获知 | v1.5 上线 |
| G7 | 用户公告模板未法务 review | 措辞 risk | v1 前 sign-off |
| G8 | 事故归类标签 / 分析未自动化 | Postmortem 难量化 | v1.5 dashboard |

---

## 11. 术语表

| 术语 | 含义 |
|------|------|
| MTTR | Mean Time To Resolution 平均修复时间 |
| MTTA | Mean Time To Acknowledge 平均认领时间 |
| Hot-fix | 紧急绕过常规流程的修复 |
| Blameless | 不指责文化 |
| Fire Drill | 故障演练 |
| Status Page | 系统状态公开页（如 status.openai.com）|
| Action Item | Postmortem 产出的待办（必须有 owner + due）|

---

## Change Log

- **v0.1 (2026-04-24)**：首版完整填充
  - § 1 SEV-0/1/2/3 分级 + 升级规则（对齐 08 § 9.1）
  - § 2 On-Call 4 角色轮值（Primary / Secondary / Lead / Founder）+ 联系方式 + 交接
  - § 3 **5 阶段响应流程**：Detect → Triage(5min) → Mitigate(15min) → Investigate → Fix → Postmortem
  - § 3.3 **9 类止血手段**（Kill Switch / Rollback / Feature Flag / 数据源切换 / Memory 只读 / Cost 限流 ...）
  - § 4 **完整 Postmortem 模板**（含真实示例：P02 sentiment v0.3 KOL 幻觉事件）
  - § 5 **Kill Switch L1/L2/L3 操作手册**（含命令 / 解除流程 / 用户感知）
  - § 6 用户沟通 透明度原则 + 3 套公告模板 + **黑名单话语**
  - § 7 **Runbook 10 类常见故障**（LLM 超时 / Tool 循环 / Memory / DEX / KMS / Cost / WS / Eval / Injection / 用户被盗）
  - § 8 事故台账 + 月度 + 季度 review
  - § 9 Fire Drill 演练（月度 / 季度 / 新人）
  - § 10 8 条现状 Gap
- v0（2026-04-22）：初始骨架
