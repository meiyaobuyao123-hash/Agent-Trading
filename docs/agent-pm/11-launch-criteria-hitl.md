# 11 Launch Criteria + HITL Policy

> **v1 上线决策单一事实源**：整合 03-10 所有文档的上线门槛，一份清单说清"什么时候能 ship"。
> 每条门槛必可验证、必有责任人、必有结论。

> ⚠️ **R42 修订（2026-05-05）— HITL 全废,改为完全全自动化**
>
> 用户对齐 2026-05-05:
> - **不要分层 auto/semi/manual**,所有交易直接执行
> - **不要紧急停止开关**(用户单笔/单日上限 + 策略级 pause 已足够)
> - **单日 cap = $50,000**(全 App 合计,明天 0 点重置)
>
> **7 条兜底防线**(任一触发拒,见 [08-safety-policy.md HR35](./08-safety-policy.md)):
> 1. paper mode → 直接通过(不消耗 daily cap)
> 2. status archived/paused → 拒
> 3. 单笔 > strategy.max_position_usd(默认 $5,000) → 拒
> 4. sell 不受 daily cap / 连亏 / 回撤限制(让止损能正常出货)
> 5. 全 App 单日累计 > $50,000 → 拒
> 6. 该策略连续亏损 ≥ 3 笔 → 拒
> 7. 该策略 30 天最大回撤 > 30% → 拒(锁回 paper)
>
> 详见 [18-trade-execution-spec.md §3](./18-trade-execution-spec.md)

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.2 Draft |
| Version | v0.2 |
| Owner | 产品负责人 |
| Target Release | v1 MVP - 2026 Q3 |

---

## 0. 文档导读

### 0.1 本文档的作用

**前提**：03-10 每份文档里都有自己的"Gap" 和"上线要求"清单，但散落各处 → 决策时难以汇总 → Ship/No-Ship 决定靠拍脑袋。

**解决**：本文档是**唯一的 Launch Gate 汇总**，所有前序文档的硬门槛在这里**重新汇集 + 责任人分配 + 当前状态追踪**。

### 0.2 内容结构

- **§ 1-5**：Launch Gates（5 类硬门槛：Tech / Product / Safety / Compliance / Cost & Ops）
- **§ 6**：HITL Policy（引用 03 PRD § 4.4 + 08 Safety § 6.2，补充 Launch 视角）
- **§ 7-8**：Rollout + Rollback（灰度 + 回退）
- **§ 9**：Kill Switch
- **§ 10**：Post-Launch Monitoring
- **§ 11**：Launch Day Checklist（上线当天 SOP）
- **§ 12**：**Deprecation Policy**（承接 08 v0.2 移出的内容）
- **§ 13**：Gate Status 追踪表
- **§ 14**：现状 Gap

### 0.3 硬门槛原则

1. **可机器验证**：每条门槛必须能用脚本 / 查询 / 查表验证（不接受"感觉 OK"）
2. **责任人明确**：每条门槛必有 owner
3. **缺一不可**：任一门槛未达 → 不允许上线（除非 exit criteria 覆盖）
4. **公示透明**：Dashboard 实时显示 Gate Status
5. **回溯可审计**：Launch 决策记录到 `launch_audit_log`

---

## 1. Tech Gates（技术硬门槛）

对齐 [09 Eval § 13 Launch Criteria Gate](./09-eval-plan.md#13-launch-criteria-gate引用-11) + [04 Agent Spec § 14 Launch Gate](./04-agent-spec.md#14-验收-gate本-spec-对应的-launch-criteria)。

| # | 门槛 | 标准 | 当前 | Owner | 验证方式 |
|---|------|------|-----|-------|---------|
| T01 | L1 Tool Unit Eval | **100%** pass (17 Tools) | 🔴 0% | 工程 | CI green |
| T02 | L1 Prompt Unit Eval | **≥ 90%** pass + Safety 100% (18 Prompts) | 🔴 0% | 工程 + PM | CI + 抽检 |
| T03 | L2 Skill Integration Eval | **≥ 90%** pass (7 Skills) | 🔴 0% | 工程 | CI |
| T04 | L3 Agentic Eval | **≥ 85%** pass (4 Composition chains) | 🔴 0% | 工程 | CI |
| T05 | L4 Trajectory Eval（核心场景）| **≥ 85%** pass（S04 共创 + S07 复盘）| 🔴 0% | PM | CI |
| T06 | Memory Eval | P@3 ≥ 0.7 / 规则有用性 ≥ +3pp | 🔴 未测 | 工程 | [06 § 10](./06-memory-spec.md#10-eval记忆系统的质量测试) |
| T07 | Judge vs 人工 Pearson | **≥ 0.7**（首批 100 条双打）| 🔴 未做 | PM | [09 § 5.5](./09-eval-plan.md#55-judge-冷启动信任流程v02-新增) |
| T08 | Latency P95 | query < 500ms / thesis L2 < 6s / L3 < 18s | 🔴 未压测 | 工程 | 压测脚本 |
| T09 | Cost per decision | L2 ≤ $0.025 / L3 ≤ $0.35 / 日复盘 ≤ $0.15 | 🔴 未验证 | 工程 | trace 聚合 |
| T10 | Observability tracing | **100%** Tool/Skill 调用有 trace | 🔴 未接入 | 工程 | [15 Observability](./15-observability-tracing.md) 待建 |
| T11 | State Machine 非法转移 | 100% reject (9 states × 非法组合)| 🔴 未测 | 工程 | eval |
| T12 | Golden 总量 | **≥ 1660 条**（配置 A）或 ≥ 700 条（最小可行）| 🔴 0 条 | PM+工程 | [09 § 10.5](./09-eval-plan.md#105-v1-冷启动策略v02-重算--人力--tool-优先级修订) |

**Gate 整体通过条件**：T01-T12 **全部绿**（不达标不允许进 Product / Safety Gate 评审）。

---

## 2. Product Gates（产品硬门槛）

对齐 [03 PRD § 12 验收总 Gate](./03-prd.md#12-验收总-gate上线前必达) + 每能力 Success Metrics。

| # | 门槛 | 标准 | Owner |
|---|------|------|-------|
| P01 | 6 大能力 MUST 项 | 全部 🔴 功能 100% 验收（§ 1-7 PRD 表格）| PM |
| P02 | 每能力负面场景 UI 测试 | 全部通过（§ 1.7 / 2.8 / 3.9 / 4.11 / 5.8 / 6.8 / 7.9）| QA + 设计 |
| P03 | **Hot 策略期望值** | EV ≥ **+1%**（或 Hot 从 v1 下线）| 产品 + AI Optimizer |
| P04 | Smart Money 策略 EV | ≥ +4%（当前已达）| - |
| P05 | Signal Strategy NL 转换 | 成功率 ≥ **90%** | PM |
| P06 | **E2E 闭环验收** | [03 PRD § 11.2](./03-prd.md#112-每节点验收e2e-测试用例) 15 节点通过 | PM + QA |
| P07 | **种子用户试用**（首批 20 用户 1 周）| 无 SEV-1/2 / ≥ 10 人完成到 paper 跟踪 / ≥ 3 人复盘阅读 / NPS ≥ 30 | 产品 |

### 2.2 种子用户招募流程（v0.2 详细化）⭐

**问题**：v0.1 只说"20 种子用户"但没说从哪招、怎么招。

#### 2.2.1 招募来源（按优先级）

| 来源 | 数量 | 渠道 | 优势 |
|------|-----|------|------|
| 内部团队 + 朋友圈 Web3 玩家 | 5-8 | Telegram / 微信直邀 | 高质量反馈，包容 bug |
| 早期社群（产品 Twitter / Discord）| 5-8 | 官方公告 + 报名表 | 真实用户场景 |
| KOL 朋友（有真金交易经验）| 3-5 | 1v1 邀约 | 专业反馈 |
| Allowlist 候选（事先收集邮箱）| 3-5 | 官网注册 | 留存意愿强 |

**招募节奏**：T-30 启动收集 → T-14 完成筛选 → T-3 全部就位。

#### 2.2.2 用户筛选标准

**必备条件**：
- ✅ 有 ≥ 6 月加密交易经验（避免完全小白）
- ✅ 有 SOL 或 EVM 链 wallet 操作经验
- ✅ 自声明非中国大陆居民（合规）
- ✅ 18 岁以上

**优先选**：
- 中级用户 Persona 匹配（资金 $5K-50K）
- 至少 1 项已有交易策略（用过 Photon / DexScreener / Phantom）
- 愿意配合 1 周内 ≥ 3 次反馈

**排除**：
- 高频做市 / 套利 bot 用户（场景不符）
- 完全合约 / 杠杆用户（场景不符）

#### 2.2.3 知情同意 + NDA

种子用户必签 3 份：

| 协议 | 内容 | 签署时点 |
|------|------|---------|
| **风险知情书** | 加密投资风险 / 托管模式声明 / 真金可能亏损 | 入选时 |
| **数据使用协议** | 同意匿名行为数据用于改进产品 / 不卖第三方 | 入选时 |
| **NDA**（可选）| v1 上线前不公开内测内容 / 不截图传播 bug | 入选时 |

**电子签**：DocuSign / 微信扫码签 / Telegram bot 引导（v1 阶段成本最低）。

#### 2.2.4 试用支持

- 专属 Telegram / Discord 反馈群
- 每日 1 次 PM 主动收反馈
- Critical bug 4h 响应
- 试用结束送小额激励（如 $50 USDC 模拟盘体验金 / 周边）

#### 2.2.5 试用通过门槛

| 指标 | 门槛 |
|------|------|
| **完成至 paper 跟踪**（E2E ⑦）| ≥ 10 / 20 |
| **完成至复盘阅读**（E2E ⑬）| ≥ 3 / 20 |
| 试用期 SEV-1 / SEV-2 事件 | **0** |
| NPS 评分 | ≥ 30 |
| 1 周后留存 | ≥ 60% |

**任一不达标 → 推迟 v1 上线 1-2 周修复**。

### 2.1 能力具体 Metrics 门槛（引用）

| 能力 | 关键指标 | 门槛（引用）|
|------|---------|------------|
| C1 查行情 | 失败率 / P95 延迟 / DAU 比例 | [§ 1.8](./03-prd.md#18-success-metrics) |
| C2 分析行情 | Thesis 采纳率 ≥ 40% / 错误引用率 < 5% | [§ 2.9](./03-prd.md#29-success-metrics) |
| C3 信号策略 | 建策略 DAU ≥ 20% / 平均存活 ≥ 14d | [§ 3.10](./03-prd.md#310-success-metrics) |
| C4 交易策略 | HITL 响应率 ≥ 90% / P50 < 3min | [§ 4.12](./03-prd.md#412-success-metrics) |
| C5 模拟盘 | 胜率 ≥ 45% / 错账率 0 | [§ 5.9](./03-prd.md#59-success-metrics) |
| C6 回测 | 回测后上线率 ≥ 30% / 错账 0 | [§ 6.9](./03-prd.md#69-success-metrics) |
| C7 复盘 | 日复盘阅读率 ≥ 50% / 规则采纳 ≥ 20% | [§ 7.10](./03-prd.md#710-success-metrics) |

---

## 3. Safety Gates（安全硬门槛）

对齐 [08 Safety § 12.2 Safety Gate](./08-safety-policy.md#122-通过门槛v1-上线-safety-gate) + [09 Eval § 8 Safety Eval](./09-eval-plan.md#8-safety-eval引用-08--12)。

| # | 门槛 | 标准 |
|---|------|------|
| **S01** | **灾难级漏洞 L1/L2/L3** | **必须 100% 修复** |
| S02 | Alignment Eval AE01-AE10 SEV-0 场景 | **0 漏**（AE03 金额绕过 / AE05 私钥钓鱼 / AE08 Kill Switch / AE09 HITL 超时）|
| S03 | Alignment Eval SEV-1 场景 | **≥ 99%** 拦截（AE01/AE02/AE06/AE07/AE10）|
| S04 | Alignment Eval SEV-2 场景 | **≥ 95%** 避开（AE04 禁用表达）|
| S05 | `safety_policy.yaml` + `policy_loader.py` | ✅ 上线 + Fail-safe default 通过测试 |
| S06 | `security_audit_log` 表 + Query API | ✅ 180d 保留就绪 + [08 § 11.5](./08-safety-policy.md#115-audit-log-query-apiv02-新增) API 实现 |
| S07 | Output filter（禁用表达 regex）| ✅ 集成所有 LLM 调用后过滤 |
| S08 | Input filter（Injection Blocklist）| ✅ 所有用户输入入口拦截 |
| S09 | Circuit Breakers CB01-CB13 | ✅ 全部实现 + 压测通过 |
| S10 | HITL 超时流程 | 5/15/60 min 三级生效（03 PRD § 4.4.4 对齐）|
| S11 | Kill Switch L1/L2/L3 | 实测 L1 < 10s / L3 < 5s |
| S12 | 用户凭证擦除 SLA | **< 60s** 生效 + 压测 |
| S13 | Constitutional Rules C1-C5 | Judge 可测 + pass rate ≥ 95% |
| S14 | Red Team（持续）| v1 前至少 1 轮完整 red team pass（[14 Red Team Playbook](./14-red-team-playbook.md) 待建）|

**灾难级 L1/L2/L3 状态**（引用 [08 § 6A.2](./08-safety-policy.md#6a2-v1-必修的-3-个灾难级漏洞-上线前必须修复)）：

| # | 漏洞 | 修复 | 状态 |
|---|------|------|------|
| **L1** | `TRADE_WALLET_PRIVATE_KEY` .env 明文 | 迁 AWS Secrets Manager | 🔴 待修 |
| **L2** | `agent_executions.private_key` DB 明文 | 删列 + KMS 映射 | 🔴 待修 |
| **L3** | 授权额度 vs 签名金额无硬校验 | T08 pre_condition 硬校验 | 🔴 待修 |

**不修 L1/L2/L3 → v1 auto 模式禁上线**（只允许 paper + notify_only）。

---

## 4. Legal & Compliance Gates（合规硬门槛）

对齐 [08 Safety § 8 Multi-jurisdiction](./08-safety-policy.md#8-multi-jurisdiction-compliance多地区合规)。

| # | 门槛 | 标准 | Owner |
|---|------|------|-------|
| L01 | 免责声明 | 所有 thesis / insight 底部必带（中英）| 产品 + 法务 |
| L02 | CN IP 地理检测 | Cloudflare + MaxMind 双源，VPN 保守判定 | 工程 |
| L03 | CN IP 观察模式 | 禁真金 + 禁助记词导入 + 只 query/paper/review | 工程 |
| L04 | CN 自声明 v0.2 | **仅解锁 paper 模式**，真金走综合评分 | 产品 + 法务 |
| L05 | 托管模式用户声明 | 首启弹窗 + `custodial_consent_at` 记录 | 产品 + 法务 |
| L06 | 美国 SEC | 全文用 "analysis/insight" 非 "recommendation"；NY/TX 等严格州 auto 禁 | 法务 |
| L07 | 欧盟 MiCA 披露 | 代币详情页风险分级 + 非证券声明 | 法务 |
| L08 | GDPR | 用户 6 项数据权利（查看 / 编辑 / 禁用 / 删除 / 清空 / 导出）全部上线 | 工程 + 法务 |
| L09 | 香港 SFC | VASP 警示 UI + 零售保护 | 法务 |
| L10 | 审计日志 | 180 天保留 + Query API + 导出合规报告 | 工程 |
| L11 | 跟单交易合规 | 被跟方 opt-in + US SEC "非推荐" 声明 | 产品 + 法务 |
| L12 | Legal Review sign-off | v1 上线前法务最终签字 | **法务** |

**L12 是最终闸门**：技术和产品都过了但法务不 sign → 不允许上线。

---

## 5. Cost & Operational Gates

对齐 [03 PRD § 8.8 Cost Budget](./03-prd.md#88-cost-budget成本预算每能力分摊) + [13 Cost Budget](./13-cost-budget.md)（待建）。

| # | 门槛 | 标准 | Owner |
|---|------|------|-------|
| **C01** | 月度 LLM 预算上限 | **$1600 / 月** @ 100 DAU（含 20% buffer）| 工程 |
| C02 | 每 device 日预算 | $1.50 / day | 工程 |
| C03 | Cost Budget 熔断器 | 3 级降级（Opus→Sonnet→拒绝）压测通过 | 工程 |
| C04 | Eval 月度成本 | $500-1500 / 月（预算内）| 工程 |
| **O01** | **Incident Response SOP** | [12 Incident](./12-incident-response-sop.md) ready + on-call 轮值 | 运维 |
| O02 | Observability Tracing | [15](./15-observability-tracing.md) 覆盖所有 Loop + Tool | 工程 |
| O03 | Dashboard 上线 | Eval + Safety + Cost 实时监控 | 工程 |
| O04 | 备份 / DR | DB 备份每日 + 30 天保留 + DR 演练 | 工程 |
| O05 | Deprecation Policy | § 12 生效（Prompt / Tool 下线流程）| PM + 工程 |
| O06 | 灰度配置 | Canary/Beta/GA feature flag 机制 ready | 工程 |
| O07 | Kill Switch 演练 | L1/L2/L3 三级实际演练 pass | 工程 + on-call |
| O08 | Runbook | on-call 手册覆盖 top 10 故障场景 | 运维 |

---

## 6. HITL Launch Gates（v0.2 精简）

> **完整 HITL 流程定义在 [03 PRD § 4.4](./03-prd.md#44-真金授权与-hitl-完整流程)**。本节**只列 Launch 必达硬要求**，不重复细节。

### 6.1 五项 Launch 硬要求

| # | 要求 | 验证方式 |
|---|------|---------|
| **H01** | HITL 10 条触发条件**全部实现 + 测试**（03 PRD § 4.4.2）| 09 Eval AE09 + 单元测试 |
| **H02** | 超时三级（5/15/60 min）**全部生效**，超 60min 必 expire | cron 实测 + audit log 抽查 |
| **H03** | `pending_approvals` 表 + 16 字段 audit 全部就绪 | DB schema review |
| **H04** | 生物认证集成（iOS Face ID / Android BiometricPrompt）+ 失败 3 次锁定 30 min | UI 实测 |
| **H05** | HITL Golden Set ≥ 50 条（含 AE09 超时场景）| Eval CI |

### 6.2 反馈回流（Launch 后启用）

- 用户 HITL reject → 写 Episodic Memory（[06 § 3.3](./06-memory-spec.md#33-episodic-memory情景记忆)）
- 连续 reject 同类 ≥ 3 次 → S07 主动提议用户废弃对应策略
- reject > 5 次 / day → CB10 熔断该 device（08 § 10）

**v1 Launch 不阻塞**：Launch 时反馈回流可以是 manual review 模式，自动化在 v1.1 上线。

---

## 7. Rollout Strategy（灰度节奏）

对齐 [03 PRD § 8.10 Feature Flag](./03-prd.md#810-feature-flag--灰度策略)。

### 7.1 三级灰度

| 阶段 | 流量 | 持续 | 进入下一阶段条件 | 退回条件 |
|------|------|------|----------------|---------|
| **Canary** | 5%（内部 + opt-in 种子用户）| 48h | 无 SEV-1 / 关键指标不退化 | 任一 SEV-0/1 / Pass rate 跌 5pp |
| **Beta** | 25% | 5 天 | Canary OK + 关键指标 delta < 2pp | 同上 |
| **GA** | 100% | - | Beta OK + NPS ≥ 30 + 无显著 drift | 同上 |

### 7.2 分桶键

`hash(device_id) % 100`（同 device 稳定分桶，避免用户体验跳变）

### 7.3 Feature Flag 能力级

**每个能力独立 flag**（即使整体正常也能单独关闭）：

| Flag | v1 启动状态 | 特殊要求 |
|------|-----------|---------|
| `feature.query_market` | ✅ ON | - |
| `feature.thesis_l2` | ✅ ON | - |
| `feature.thesis_l3` | 🟡 OFF → Canary | 成本观察 48h |
| `feature.signal_strategy` | ✅ ON | - |
| `feature.trade_strategy_paper` | ✅ ON | - |
| `feature.trade_strategy_notify` | 🟡 Canary | - |
| **`feature.trade_strategy_auto`** | **🔴 OFF 14d 后分批开启** | 灾难 L1/L2/L3 修复 + HITL 验证 |
| `feature.backtest` | ✅ ON | - |
| `feature.review_daily` | 🟡 Canary | Judge 校准后转 GA |
| `feature.review_weekly` | 🟡 Canary → ON after 14d | - |
| `feature.hot_strategy` | **🔴 OFF until EV > +1%** | P03 门槛 |
| `feature.pump_strategy` | 🟡 Canary | - |
| `feature.smart_money_strategy` | ✅ ON | EV 已达标 |
| `feature.copy_trading` | 🟡 OFF → Canary（v1 后期）| HR26-HR31 全部上线 |

---

## 8. Rollback（回退机制）

### 8.1 自动 Rollback 触发（v0.2 统计判定明确）

| 条件 | 判定方法 | 行动 | 生效时间 |
|------|---------|------|---------|
| Safety violation（任何 AE fail）| 直接判 fail（无统计）| 立即回退 + SEV-1 | < 5s |
| Pass rate 跌（**McNemar's test**）| `p < 0.05 且 下降 ≥ 5pp`（对齐 [09 § 9.5](./09-eval-plan.md#95-flakiness-handlingv02-新增)）| 自动回退 | < 5s |
| Pass rate borderline 下降 | 重跑 3 次取中位数判定 | 人工 review 决定 | < 1h |
| Cost 超预算 1.5× | 持续 ≥ 1h 平均 | 告警 + 24h 内强制回退 | 24h |
| NPS 周环比跌 ≥ 10 | bootstrap CI 95% 下界 | 产品 review + 可能回退 | 人工决策 |

**v0.2 强制规定**：
- 不允许"一次性测得 pass rate 跌 5pp 就 rollback"（可能是 flaky）
- McNemar 配对检验是 **唯一** 自动判定方法
- 实施脚本 `scripts/rollback_decision.py` 调 09 § 9.5 的同一逻辑

### 8.2 回退机制

**配置级**（Prompt / Skill version / feature flag）：
- config.yaml 切换 → 热推 < 5s 全集群生效
- 回退版本可回溯至少 3 版

**代码级**（Bug 修复）：
- git revert → CI → 灰度重新走 Canary（不跳级）
- 高危修复可走 hot-fix 通道（跳 Canary 直接 Beta，风险告警）

### 8.3 数据一致性处理

- Rollback 不影响已完成 trade / paper 记录
- 已触发但未执行的 pending HITL → 保留（按新 rollback 版本继续处理）
- Memory 写入 rollback 期间可能丢失（依赖 WAL 兜底，[06 § 3.8](./06-memory-spec.md#38-write-reliability写入可靠性v02-新增)）

### 8.4 Rollback 审计

所有 rollback 必写 `launch_audit_log`：
- 触发原因 / 回退的版本 / 恢复时间 / 受影响用户数 / 决策人

---

## 9. Kill Switch（紧急停止）

详见 [08 Safety § 6.4](./08-safety-policy.md#64-kill-switch一键关闭)。

| 级别 | 谁能触发 | 范围 | 生效 |
|------|---------|-----|------|
| **L1 用户级** | 用户 APP 内一键 | 自己所有真金 | < 10s |
| **L2 Device 级** | Admin API | 单 device | < 10s |
| **L3 全局级** | Admin 紧急 | 所有用户真金 | < 5s |

### 9.0 实现选型（v0.2 明确）

| 级别 | 实现 | 验证 SLA |
|------|------|---------|
| **L1 用户级**（< 10s）| Flutter 一键 → API `/api/agent/kill_switch/user` → DB `user_kill_switch_active=true` → T08 调用前检查（< 30s 内全集群感知）| 压测：模拟 100 device 并发 |
| **L2 Device 级**（< 10s）| Admin API → 同上字段（device 级）| 压测同上 |
| **L3 全局级**（< 5s）| Admin → **Redis pub/sub broadcast** → 各 Python 进程订阅 → 进程内 `agent_global_state.status='blocked'` 标志位置 1 → T08 全部立即拒绝 | 实测从命令到全集群（≥ 5 进程）感知 |

**v0.2 实现要点**：
- 选 **Redis pub/sub**（不用 Kafka，避免引入新基础设施 + Redis 已用作缓存）
- 进程内 polling fallback：每 1s 查 Redis state（防 pub/sub 漏 message）
- DB 持久化兜底：Redis 重启后从 DB 恢复 state
- 演练脚本：`scripts/kill_switch_drill.py` 测全程时延

### 9.1 Launch 要求

- L1/L2/L3 三级**实际演练 pass**（不是"应该能 work"）
- L3 演练：从决定到全集群真金停止全程 **< 5s**（验证）
- L1 / L2 演练：< 10s（压测 100 并发）
- 演练流程写入 Runbook
- 每月 1 次 fire drill（对齐 02 SOP）

### 9.2 Kill Switch 后的用户体验

- 用户 UI 显示"🛑 Agent 真金执行已暂停"（高级别红色顶栏）
- 已开仓位**不自动平仓**（继续监控止盈止损）
- paper 模式仍可用
- Kill Switch 解除需**二次确认 + audit log**

---

## 10. Post-Launch Monitoring（上线后监控）

### 10.1 核心指标（Dashboard 实时）

| 维度 | 指标 |
|------|------|
| **Safety** | SEV-0/1/2/3 分布 / Injection 尝试数 / CB 触发次数 |
| **Eval** | L1-L4 pass rate / Judge drift / Cost per call |
| **Product** | DAU / 6 能力使用 / E2E 闭环转化 / NPS |
| **Financial** | 真金成交量 / 胜率 / EV / 最大回撤 |
| **Operational** | P95 延迟 / Error rate / LLM cost 实际 vs 预算 |

### 10.2 告警阈值与响应

| 阈值 | 渠道 | 响应 |
|------|------|------|
| SEV-0 | PagerDuty + 短信 | **< 15 min 响应** |
| SEV-1 | PagerDuty | < 1h 响应 |
| SEV-2 | Slack | < 4h 响应 |
| SEV-3 | Dashboard | 24h 内处理 |
| 关键指标 drift > 10% | Slack | PM 24h review |

### 10.3 SLI / SLO 量化（v0.2 新增）

> v0.1 用"P95 延迟" 模糊；v0.2 给具体 SLI 定义 + SLO 阈值 + Error Budget。

| SLI（指标） | SLO（目标） | Error Budget | 告警阈值 |
|-----------|----------|--------------|---------|
| **可用性 - Chat API** | 99.9% / 月（成功响应率）| 月 43 min 容许 | 1h 错误率 > 1% |
| **可用性 - 真金 swap (T08)** | 99.95% / 月 | 月 22 min 容许 | 5min 错误率 > 5% |
| **延迟 - query_market** | P95 < 500ms / 95%时段 | 5% 时段超标 | 1h 时段 P95 > 1000ms |
| **延迟 - thesis L2** | P95 < 6s / 95%时段 | 5% | 1h P95 > 10s |
| **延迟 - thesis L3** | P95 < 18s / 95%时段 | 5% | 1h P95 > 30s |
| **延迟 - HITL push 送达** | P95 < 1.5s / 95%时段 | 5% | - |
| **Eval pass rate L1 Tool** | 100% | 0% | 任一 fail |
| **Eval pass rate L1 Prompt** | ≥ 90% | 10% | < 85% |
| **Safety - Injection 拦截** | 100% (AE01-AE10 SEV-0) | 0% | 任一漏 |
| **Cost - LLM 月度** | ≤ $1600 @ 100 DAU | 50% buffer | 月度 $2000 |
| **Cost - 单 device 日预算** | ≤ $1.50 / day | 0% (硬限)| 单 device > $2 |
| **NPS** | ≥ 30 | - | < 20 触发 review |
| **Error rate - Tool** | < 1% | - | > 3% |
| **Error rate - LLM API** | < 0.5% | - | > 2% |

**Error Budget 政策**：
- Budget 烧尽（如月度真金 swap 22 min 用完）→ **暂停所有非紧急发布**直到下月
- 鼓励工程在 Budget 内迭代（不达标但有 Budget 可用）
- 月度 review SLI 实际 vs SLO（写入 [12 Incident](./12-incident-response-sop.md)）

### 10.3 复盘节奏

| 节奏 | 议程 |
|------|------|
| **日**（on-call 短 standup）| 昨日事件 / 未解决 ticket / 今日关注 |
| **周**（产品 review）| 关键指标周报 / 用户反馈 top 5 / Rubric 打分趋势 |
| **月**（全员）| 月度 KPI / Safety 事件总结 / Gap 清理进度 |
| **季**（leadership）| 季度 OKR / 战略调整 / v2 规划 |

---

## 11. Launch 时间轴 + Day Checklist（v0.2 反推 T-90）

### 11.0 Gate 依赖关系图（v0.2 新增）⭐

62 项 Gate 不是 flat 列表。**依赖关系决定执行顺序**——做错顺序整个上线计划崩。

```
Phase 0: Foundation（T-90 ~ T-60，灾难漏洞 + 基础设施）
   ┌─────────────────────────────────────────────┐
   │  S01 灾难级 L1/L2/L3 修复（4-6 周）           │
   │  S05 safety_policy.yaml + policy_loader      │
   │  S06 security_audit_log + Query API          │
   │  O02 Observability Tracing                   │
   │  C01 Cost Budget 硬约束 + 熔断器             │
   └─────────────────────────────────────────────┘
                    │
                    ▼
Phase 1: Eval 建设（T-60 ~ T-30，Golden 1660 条）
   ┌─────────────────────────────────────────────┐
   │  T01 Tool Unit Eval（Week 1-2）              │
   │  T02 Prompt Unit Eval（Week 2-3）            │
   │  T03 Skill Integration Eval（Week 3-4）      │
   │  T07 Judge 校准 100 条双打（伴随）           │
   │  T06 Memory Eval                             │
   └─────────────────────────────────────────────┘
                    │
                    ▼
Phase 2: 上层 Eval + Safety（T-30 ~ T-14）
   ┌─────────────────────────────────────────────┐
   │  T04 Agentic Eval（4 chains）                │
   │  T05 Trajectory Eval（核心场景）             │
   │  S02-S04 AE01-AE10 对抗（依赖 S05/T01-T03）  │
   │  S07-S09 Filter 上线（依赖 S05）             │
   │  S14 Red Team 首轮                           │
   │  S11 Kill Switch 演练                        │
   │  S12 凭证擦除 < 60s 压测                     │
   └─────────────────────────────────────────────┘
                    │
                    ▼
Phase 3: Compliance + Final（T-14 ~ T-3）
   ┌─────────────────────────────────────────────┐
   │  L01-L11 多地区合规（前期同步推进，此时收尾）│
   │  P01-P07 产品 Gate 验收                      │
   │  T08-T11 性能 / 状态机                       │
   │  O01 Incident Response SOP                   │
   │  O03-O08 Dashboard / Backup / Runbook        │
   └─────────────────────────────────────────────┘
                    │
                    ▼
Phase 4: Launch Day（T-3 ~ T-0）
   ┌─────────────────────────────────────────────┐
   │  L12 法务 Final Sign-off ⭐ 最终闸门         │
   │  P07 种子用户招募完成                        │
   │  O07 Kill Switch 实际演练                    │
   │  Launch Day Checklist（§ 11.4）              │
   └─────────────────────────────────────────────┘
```

### 11.1 关键依赖（必须先做后做）

| 后置 Gate | 依赖 |
|---------|------|
| T05 Trajectory | T03 Skill 全 pass |
| T04 Agentic | T01 + T02 + T03 全 pass |
| S02-S04 AE 对抗 | S05 safety_policy + T01-T03 |
| S07/S08 Filter | S05 policy_loader |
| L12 法务 sign-off | 所有其他 Gate（最末闸）|
| O01 Incident SOP | S06 audit_log + O02 trace |
| Canary 启动 | 62 Gate 全绿 |
| Beta | Canary 48h 无 SEV-0/1 |
| GA | Beta 5d 无 SEV-0/1/2 + NPS ≥ 30 |

### 11.2 时间轴反推（v0.2 详细，从 T-90 起）

| 节点 | 周数 | 关键里程碑 | Gate 进度目标 |
|------|-----|-----------|-------------|
| **T-90** | -13w | Phase 0 启动：灾难漏洞 / 基础设施 | 0% |
| T-75 | -11w | L1/L2/L3 灾难漏洞 50% 进度 | 10% |
| **T-60** | -8.5w | Phase 0 完成 + Phase 1 启动 | 25% |
| T-45 | -6.5w | Tool + Prompt Unit Eval 完成 | 45% |
| **T-30** | -4w | Phase 1 完成 + Phase 2 启动 | 60% |
| T-21 | -3w | Skill Integration + Memory Eval 完成 | 70% |
| **T-14** | -2w | Phase 2 完成 + Red Team 首轮通过 | 80% |
| T-10 | -10d | 多地区合规 + 性能压测 | 88% |
| **T-7** | -1w | Phase 3 完成 + 法务 review 启动 | 95% |
| **T-3** | -3d | Kill Switch 演练 + 种子用户就位 | 98% |
| T-1 | -1d | Final Lockdown + L12 Sign-off | 100% |
| **T-0** | 0 | Launch Day | Canary 5% |
| T+2 | +2d | Beta 决策 | - |
| T+9 | +9d | GA 决策 | - |

### 11.3 关键路径瓶颈（CPM）

| 关键路径 | 瓶颈节点 | 缓解 |
|---------|---------|------|
| 灾难漏洞修复（4-6 周）| L1 KMS 集成 | 提早启动，T-90 前两周开始 |
| Golden 1660 条（6 周）| 4 人并行的工程协调 | 配置 A 必须 4 人到位（[09 § 10.5.3](./09-eval-plan.md#1053-新路线图配置-a--4-人并行-6-周)）|
| 多地区合规 sign-off | 法务调度 | T-30 前启动法务 review，留足 4 周 |
| Red Team 首轮 | 安全 expert 资源 | T-30 锁定红队 2 周窗口 |

### 11.4 Launch Day Checklist（T-7 起）

#### T-7 天

- [ ] Tech Gates T01-T12 全绿
- [ ] Product Gates P01-P07 全绿
- [ ] Safety Gates S01-S14 全绿（特别是灾难级 L1/L2/L3）
- [ ] Legal Gate L01-L12 全绿，法务 sign-off
- [ ] Cost & Ops Gate C01-O08 全绿
- [ ] Runbook 发到 on-call 团队，演练一次

### T-3 天

- [ ] Kill Switch L1/L2/L3 实际演练通过
- [ ] 20 种子用户已招募 + 知情同意签字
- [ ] Dashboard 所有面板工作正常
- [ ] Rollback 热切换演练 pass
- [ ] 48h monitoring 值班表确认

### T-1 天

- [ ] 所有 feature flag 状态按 § 7.3 配置
- [ ] `safety_policy.yaml` 最终版部署
- [ ] Legal 最终 sign-off 归档
- [ ] on-call rotation 激活

### T-0（Launch Day）

```
09:00 UTC  Canary 5% 开启
09:15      首批指标检查（Pass rate / Cost / Safety）
10:00      1h 小时检查点
11:00 ...  每小时检查
48h 后     进入 Beta 决策会
```

### T+48h Beta 决策

- 无 SEV-0/1 / 关键指标稳 → Beta 25%
- 有问题 → 按 Rollback 流程退回

### T+7d GA 决策

- Beta 期间无 SEV-0/1/2 + NPS ≥ 30 + 关键指标不退化 → GA 100%
- 否则 → 继续 Beta 或回退

---

## 12. Deprecation Policy（承接 08 移出）⭐

**背景**：08 Safety v0.2 决策将 Deprecation 移出（不属于安全范畴），现并入 11 Launch 运营范畴。

### 12.1 Prompt Deprecation（承接 07 § 4）

| 阶段 | 操作 |
|------|------|
| 1. 提议 | PR 提交 `deprecated=true` + `deprecated_at` + 原因 |
| 2. 通知 | Slack 通知工程 + PM 48h 内 ack |
| 3. 迁移期 | 2 周（v1 阶段）或 4 周（v2+）期间新版并行 |
| 4. 移除 | 代码删除 + 保留历史在 `07-archive.md` |

### 12.2 Tool Deprecation（承接 05 § 6.3）

| 阶段 | 操作 |
|------|------|
| 1. 标 deprecated | `status: deprecated` + log WARN |
| 2. grep 所有调用方 | 通知所有依赖方 + 迁移 guide |
| 3. 迁移期 | 2 周 |
| 4. 移除 | 代码删除 + schema 归档 `05-archive.md` |

### 12.3 Skill Deprecation

与 Tool 同流程，但需额外：
- 该 Skill 的 Golden set 归档（不删）
- Prompt Library 对应 prompts 也标 deprecated

### 12.4 Feature Flag / 能力 Deprecation

| 操作 | 规则 |
|------|------|
| Flag 关闭 | **先公告 30 天**（APP 内推 + Release Notes）|
| 能力下线 | 用户仍可查看历史数据（只读），不再新触发 |
| 关联策略处理 | 用户策略引用下线能力时 → UI 提示 + 自动 pause |
| 数据保留 | 对应数据按 [06 Memory § 1](./06-memory-spec.md#1-memory-layers-overview4-层记忆) 规则保留 |

### 12.5 Rule Deprecation（Safety Rules）

承接 [08 § 3.0 Rule ID 生命周期](./08-safety-policy.md#30-rule-id-生命周期规则v02-新增)：
- `status: deprecated` + `deprecated_at` + `deprecated_reason`
- ID 永久保留，不重用
- 历史 audit log 仍可按旧 ID 查询

### 12.6 交易策略 / 用户策略的"Deprecation"

**特殊**：用户自建的策略不是被下线而是用户主动暂停 / 归档。流程见 [03 PRD § 3.8](./03-prd.md#38-生命周期与一致性lifecycle--consistency)：
- `active → paused → archived`
- Archived 策略已开仓位继续监控到闭仓（不强平）

---

## 13. Gate Status 追踪表（v1 实时更新）

> 本表在 CI / Dashboard 实时刷新，离 launch 还差什么一目了然。

### 13.0 Gate Status 更新机制（v0.2 明确）

| Gate 类别 | 自动判定 | 人工 sign-off |
|---------|---------|-------------|
| Tech Gates | CI green = 自动绿 | - |
| Product Gates | 部分自动（Eval 数据）| **PM sign-off** P01-P07 |
| Safety Gates | 自动（Eval pass + 灾难漏洞 PR merged）| **安全 lead sign-off** S14 Red Team |
| Legal Gates | 部分自动（合规 check）| **法务 sign-off** L01-L12（**L12 必须**）|
| Cost & Ops | 自动（dashboard 数据）| **Ops lead sign-off** O01 / O07 / O08 |
| HITL | 自动（pass 测试）| - |

**Gate 状态枚举**：
- 🔴 `not_started` / `failing`
- 🟡 `in_progress` / `partial_pass`
- 🟢 `passing`（自动）/ `signed_off`（含人工签）
- ⚫ `waived`（特例放行，需 § 14.4 流程）

**审批流**：
- PR 提交时声明 Gate 影响（`Gate-Affected: T03, S07`）
- CI 自动跑相关 Gate
- 人工 sign-off 通过 `/api/admin/launch/gate/:id/signoff` API（带 audit log）
- Dashboard 实时显示进度

| 分类 | Gate 总数 | 绿 | 黄 | 红 | % |
|------|---------|----|----|----|---|
| § 1 Tech (T01-T12) | 12 | 0 | 0 | 12 | 0% |
| § 2 Product (P01-P07) | 7 | 0 | 0 | 7 | 0% |
| § 3 Safety (S01-S14) | 14 | 0 | 0 | 14 | 0% |
| § 4 Legal (L01-L12) | 12 | 0 | 0 | 12 | 0% |
| § 5 Cost & Ops (C01-O08) | 12 | 0 | 0 | 12 | 0% |
| § 6 HITL | 5 | 0 | 0 | 5 | 0% |
| **总计** | **62** | **0** | **0** | **62** | **0%** |

**v1 Launch Gate 公式**：62 项 Gate **100% 绿** → 允许 Canary → Beta → GA。

### 13.1 里程碑

- **T-30 天**：≥ 40% Gate 绿 + 所有灾难级 L1/L2/L3 修复
- **T-14 天**：≥ 80% Gate 绿 + Red Team 首轮通过
- **T-7 天**：**100% Gate 绿** + Legal sign-off
- **T-0**：Canary 开启

---

## 14. 现状 Gap（v1 必补清单，按优先级）

### 14.1 🔴 Critical（不修就不能上线）

1. **L1/L2/L3 灾难漏洞**（4-6 周）—— 见 § 3 + 08 § 6A
2. **Golden Set 建设**（6 周 · 4 人并行）—— 见 [09 § 10.5](./09-eval-plan.md#105-v1-冷启动策略v02-重算--人力--tool-优先级修订)
3. **Safety Policy Runtime**（2 周）—— safety_policy.yaml + policy_loader + audit log
4. **HITL 完整流程**（3 周）—— pending_approvals + 生物认证 + 推送
5. **Observability Tracing**（3 周）—— [15](./15-observability-tracing.md) 待建
6. **Incident Response SOP**（2 周）—— [12](./12-incident-response-sop.md) 待建
7. **Red Team 首轮**（2 周）—— [14](./14-red-team-playbook.md) 待建
8. **Legal Review**（贯穿，最后 sign-off）

### 14.2 🟠 Major（强烈建议，否则降级上线）

9. **Cost Budget 硬约束**（1 周）—— [13](./13-cost-budget.md) 待建
10. **Dashboard MVP**（2 周）
11. **Kill Switch 演练**（1 周）
12. **用户凭证擦除 < 60s 压测**（1 周）

### 14.3 🟡 Minor（v1 可延后）

13. Trajectory Eval（[16](./16-trajectory-eval.md)）—— v1 可只覆盖核心 2 场景
14. Memory Cross-device 同步 UI
15. 多地区合规深度（先 CN + US + EU，HK/JP/KR 可 v1.5）

### 14.4 v1 最小可行方案（若人力不够）

**降级门槛**：
- Golden Set 700 条（替代 1660）
- L4 Trajectory 暂跳过
- `feature.trade_strategy_auto` v1 完全不上（只 paper + notify_only）
- 合规只做 CN + US 基础 + 免责声明

**降级 Launch Gate 总数**：62 → 45 项硬门槛（去掉 L4 / auto 相关 / 高阶合规）

#### 14.4.1 降级审批流（v0.2 责任链）

降级**不是 PM 单独决定**。流程：

| 步骤 | 责任 |
|------|------|
| 1. PM 提议降级方案（写明哪些 Gate waived / 风险）| PM |
| 2. 安全 lead review（确认 S 系列降级不引入未知风险）| Sec Lead |
| 3. 法务 review（合规风险评估）| Legal |
| 4. 产品 lead 决策签字 | Product Lead |
| 5. 创始人 / CEO 最终批准（v1 阶段必走）| CEO |
| 6. 写入 `launch_audit_log` + 公告 | PM |

**降级后果归属**：
- 降级期间发生 SEV-0/1 事件 → 责任链上每个 sign-off 共担
- 不允许"降级 + 出事 + 找别人背锅"

#### 14.4.2 降级的反向恢复

降级方案上线后，**v1.1 必须在 8 周内**回补 waived Gate：
- 月度 review 进度
- 8 周未回补 → 自动触发 SEV-2 + 强制规划

---

## 15. 术语对照

| 术语 | 含义 |
|------|------|
| Launch Gate | 上线硬门槛（必达项）|
| Canary / Beta / GA | 灰度阶段 5% / 25% / 100% |
| HITL | Human-In-The-Loop 人机协作 |
| Kill Switch | 紧急停止开关 |
| Deprecation | 能力 / Tool / Prompt 下线 |
| SEV-0/1/2/3 | 事件严重级（见 [08 § 9.1](./08-safety-policy.md#91-sev-分级违规事件分级)）|
| Rollback | 回退到前一个稳定版本 |
| DR | Disaster Recovery 灾难恢复 |
| Runbook | on-call 应急手册 |

---

## Change Log

- **v0.2 (2026-04-24)**：Review 修订（5 P0 + 4 P1）
  - **§ 11.0 新增 Gate 依赖关系图**（4 Phase 时序，解决 v0.1 flat 列表问题）
  - **§ 11.1 新增 关键依赖表**（11 条 Gate 间硬依赖）
  - **§ 11.2 新增 时间轴反推**（T-90 到 T-0 详细 12 节点）
  - **§ 11.3 新增 关键路径瓶颈**（CPM 4 项 + 缓解）
  - **§ 8.1 Rollback 统计判定**：明确 McNemar's test（对齐 09 § 9.5）+ borderline 重跑 3 次中位数
  - **§ 9.0 新增 Kill Switch 实现选型**：L3 用 Redis pub/sub + 进程内 polling fallback + DB 兜底
  - **§ 2.2 新增 种子用户招募流程**（4 招募来源 / 3 协议签署 / 5 通过门槛）
  - **§ 13.0 新增 Gate Status 更新机制**（自动 vs 人工 sign-off + 4 种状态枚举 + API）
  - **§ 14.4.1 新增 降级审批流责任链**（PM → Sec → Legal → Product → CEO）
  - **§ 14.4.2 降级反向恢复**（v1.1 8 周内必回补）
  - **§ 10.3 新增 SLI/SLO 量化**（13 项 SLI + Error Budget 政策）
  - **§ 6 HITL 精简**到 5 项 Launch-specific 硬要求（H01-H05）+ 反馈回流 v1.1 启用
- **v0.1 (2026-04-24)**：首版完整填充
  - § 0 整合 03-10 所有 Gate 的**唯一事实源**定位
  - § 1 Tech Gates T01-T12（Eval / Latency / Cost / Observability / State / Golden）
  - § 2 Product Gates P01-P07（6 能力 + 负面 / EV / NL 转换 / E2E / 种子用户）
  - § 3 Safety Gates S01-S14（含 **L1/L2/L3 灾难漏洞必修** + AE 对抗 + CB 熔断）
  - § 4 Legal Gates L01-L12（多地区合规 + 托管声明 + 法务 sign-off）
  - § 5 Cost & Ops C01-O08（$1600/月预算 + Incident / Observability / 灰度 / 备份）
  - § 6 HITL Policy 汇总引用 + Launch 硬规定
  - § 7 Rollout：Canary 5% → Beta 25% → GA 100% + 14 个能力 feature flag 状态
  - § 8 Rollback：4 种自动触发 + 配置 / 代码双级回退
  - § 9 Kill Switch L1/L2/L3 + 演练要求
  - § 10 Post-Launch Monitoring（5 维指标 + 告警分级 + 复盘节奏）
  - § 11 **Launch Day Checklist**（T-7 / T-3 / T-1 / T-0 / T+48h / T+7d）
  - § 12 **Deprecation Policy**（承接 08 v0.2 移出 —— Prompt / Tool / Skill / Feature Flag / Rule / 用户策略 6 类）
  - § 13 Gate Status 追踪表（**62 项总 Gate 清单**）+ 里程碑
  - § 14 现状 Gap 分级（Critical 8 / Major 4 / Minor 3 + 最小可行降级方案）
- v0（2026-04-22）：初始骨架
