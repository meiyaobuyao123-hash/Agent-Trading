# 17 Flutter Agent Tab v1 技术落地方案

> 把 `docs/agent-pm/00-16` 16 篇 PM 设计文档落地为代码的工程方案。

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.1 Draft |
| Version | v0.1 |
| Owner | 工程负责人 |
| Target Release | v1 MVP - 2026 Q3 |
| 总周期 | 16-20 周(4 Phase 并行) |
| 落地范围 | paper + notify + auto + 真金 + 托管钱包(完整 v1) |
| 质量门槛 | 配置 A:1660 golden + L1-L4 + LLM-as-judge + Trajectory + 62 项 Launch Criteria 100% |
| 月预算 | $1500 @ 100 DAU |

---

## Context

`docs/agent-pm/` 16 篇 PM 设计文档(2026-04 产出,**从未实施**)定义了 Flutter App **Agent Tab**(chat / strategies / ai_insights 三个 sub-tab)的优化方案,现在要把这套设计实施进代码。

**设计要点**:7 Skills(S01-S08)+ 17 Tools(T01-T17)+ 4 层 Memory(working/episodic/semantic/reflection)+ 5 个 Loop(Scout/Thesis/Notify/Reflect/Chat)+ HITL 队列(10 触发 + 5/15/60min 超时)+ KMS 托管钱包 + 30 条 HardRule + 13 个 CB + 1660 条 Eval golden + $1500/月预算 @ 100 DAU。

**用户决策**(2026-04-30):
- **范围**:完整 v1(paper + notify + auto + 真金 + 托管钱包)
- **优先级**:三块并行(共创+Thesis、Memory 升级、Insight 复盘)
- **质量门槛**:配置 A(1660 golden + L1-L4 + LLM-as-judge + Trajectory + 62 项 Launch Criteria 100%)

**预期产出**:符合 PM 设计的 v1 MVP,Canary 5% → Beta 25% → GA;月成本 ≤ $1500;P95 latency 达标;Safety AE01-AE10 零漏。

---

## 当前 Baseline(代码事实,与设计目标的差距)

| 能力 | 现状代码 | 设计目标 | 差距 |
|---|---|---|---|
| Chat→策略生成 | `LLMParser.parse_strategy_stream` ✅ | S04 共创 7 阶段(澄清→draft→dry-run→反馈→确认) | 多轮澄清状态机、conversation_states 表 |
| 策略 CRUD | `strategy_manager.py` ✅(≤20+冷却) | C3/C4 + paper→notify→auto 晋升 | 模式晋升门槛(30d+30 笔+EV≥+1%)、mode_locked_until |
| 模拟盘 | `paper_engine` + `/paper-stats` ✅ | C5 paper 默认 + 切 auto 门槛 | 自动晋升判定 |
| Backtest | `backtester.py` + `/backtest` ✅ | C6 + 规则化 warnings(过拟合/样本不足/CRISIS窗口) | warnings 规则 |
| AI Insights | `getRegime/getMemory/getPerformance` 摘要展示 ✅ | S07 review-engine 日/周/月报 + 规则提议 + 采纳 | 完整复盘报告、T11 approve_rule、Shadow mode |
| L1/L2/L3 编排 | `multi_role_orchestrator.py` ✅ | Thesis Loop L2/L3 + S08 thesis-writer | S08 不存在;L3 触发硬编码($30/score>70)需重构;decision_agent 输出非 thesis schema |
| Memory 4 层 | `agent/memory/{working,episodic,semantic,reflection}.py` ✅ | 启发式相关性评分 + WAL + Semantic 50 上限 + Shadow Mode | 评分公式需对齐、WAL/重试队列、Shadow Mode 14d、晋升 5 条硬条件 |
| HITL 队列 | ❌ Optimizer 有 proposals,Agent 交易侧空白 | T09 + pending_approvals 表 + 10 触发条件 + 5/15/60min 超时 | 完全空白 |
| KMS / 托管钱包 | ❌ Flutter `flutter_secure_storage` 本地保管 | KMS 签名 + 60s 擦除 SLA + audit log | 完全空白 |
| Safety Policy | ❌ 散落 risk_manager/risk_reviewer | safety_policy.yaml + 30 HR + 13 CB + 5 C + runtime check | 需集中化重构 |
| Prompt Library | ❌ `templates.py` dict 5 个模板 | 18 P + frontmatter + cache_breakpoints + A/B 灰度 | 完全空白 |
| 18 个 Tool 规范 | 现有约 8 个能力散落 | JSON Schema + idempotent + permission + failure_modes 元数据 | 9 个新建 + 8 个补元数据 |
| Eval Golden | ❌ `tests/` 零散 pytest | 1660 条 + L1-L4 + LLM-as-judge Pearson≥0.7 | 完全空白 |
| 灾难漏洞 | L1 env 明文 / L2 DB 明文私钥 / L3 无授权硬校验 | 必修才能 Launch | Phase 0 阻塞 |

---

## 目标态架构

```
┌─ Flutter Agent Tab (3 sub-tab) ────────────────────────────────────┐
│  Chat: 共创 7 阶段 UI + Thesis schema 展示 + 推送                   │
│  Strategies: CRUD + HITL 详情页 + 模式晋升流程                       │
│  Insights: 日/周/月复盘 + 规则采纳 + 记忆管理 + 降级 UI              │
└─────────────┬──────────────────────────────────────────────────────┘
              │ HTTPS + SSE
┌─────────────▼──────────────────────────────────────────────────────┐
│  FastAPI Layer (api/routes_agent.py 重构 + 新增 ~10 个 endpoint)    │
│  含: /thesis /pending-approvals /memory/rules /reviews /skills/run  │
└─────────────┬──────────────────────────────────────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────────────────┐
│  Loop Orchestration (5 个 Loop)                                     │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐         │
│  │  Scout   │  Thesis  │  Notify  │  Reflect │   Chat   │         │
│  │ 规则引擎  │ L1/L2/L3 │  推送    │ 日/周/月  │  对话     │         │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘         │
└─────────────┬──────────────────────────────────────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────────────────┐
│  Skill Layer (7 个 Skill,SKILL.md + Anthropic tool_use)             │
│  S01 technical-analysis    S05 trade-strategy-builder               │
│  S02 sentiment-analysis    S07 review-engine                        │
│  S03 onchain-analysis      S08 thesis-writer 🆕                     │
│  S04 signal-strategy-builder                                        │
└─────────────┬──────────────────────────────────────────────────────┘
              │ tool_use
┌─────────────▼──────────────────────────────────────────────────────┐
│  Tool Layer (17 个 Tool, JSON Schema 强校验)                        │
│  T01-04 query   T05-06,11-12 CRUD   T07-09 execute                  │
│  T13 push       T14-17 calc                                          │
└─────────────┬──────────────────────────────────────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────────────────┐
│  Memory(4 层)+ Safety(yaml runtime)+ KMS + Audit Log               │
└────────────────────────────────────────────────────────────────────┘
```

---

## 分期落地路线图(并行推进,总 16-20 周)

### Phase 0 — 灾难漏洞 + 基础设施(4-6 周,**阻塞 Launch**)

| 任务 | 关键产出 | 关键文件 |
|---|---|---|
| L1 env 明文密钥 → KMS | 所有 ANTHROPIC/OKX/Helius key 移入 KMS,运行时拉取 | `services/pump-scanner/config.py`(改) + 新建 `kms_client.py` |
| L2 DB 明文私钥列删除 | `agent_strategies.private_key` 等敏感列迁移 + 删原列 | migration 034 + `wallet_service.dart` |
| L3 T08 execute_swap pre_condition 硬校验 | 7 项 pre_condition 全实施 | `agent/trade_executor.py`(改) |
| safety_policy.yaml + runtime | 30 HR + 13 CB + 5 C 集中化 + 加载失败 fail-safe BLOCKED | 新建 `agent/safety_policy.yaml` + `agent/safety_engine.py` |
| security_audit_log 表 + 三级查询 API | 180 天保留 + 用户/Admin/法务三级 | migration 035 + `api/routes_audit.py` |
| pending_approvals 表 + WAL | T09 基础设施;memory_write_wal / memory_write_retry_queue 表 | migration 036 + `agent/wal.py` |
| Cost 熔断器 CB04 | LLM 月预算软限 70% / 硬停 100% / BLOCKED 150% | `agent/cost_guard.py` |
| Kill Switch + Incident SOP | 1 键关闭 < 10s + runbook | `api/routes_admin.py` + `docs/runbook/` |

### Phase 1 — Tool 化 + Memory 升级(4-6 周,**并行 Phase 2/3**)

**Tool 规范化**(17 个全部 JSON Schema + idempotent 元数据,见 `docs/agent-pm/05-tool-catalog.md` § 4):

| 状态 | Tool |
|---|---|
| ✅ 现有补元数据(8) | T01 query_market / T02 query_holders / T03 query_onchain_activity / T05 list_strategies / T06 update_strategy_status / T07 run_paper_trade / T10 get_paper_performance / T12 save_strategy |
| 🆕 新建(9) | T04 recall_memory / T08 execute_swap(规范化) / T09 create_approval_request / T11 approve_rule / T13 send_push_notification(封装现有)/ T14 calc_technical_indicators / T15 calc_risk_metrics / T16 run_backtest(规范化)/ T17 calc_position_size |

**关键复用**:
- T14 复用 `services/pump-scanner/btc_eth/indicators/technical.py`(已有 RSI/MACD/MA/ATR/BB)
- T15 复用 `agent/performance_analytics.py`(胜率/PNL/夏普/最大回撤)
- T16 复用 `agent/backtester.py` + `services/pump-scanner/backtest.py`(pump/hot 用)+ 加规则化 warnings
- T13 复用 `agent/push_service.py` + `routes_device.py`(FCM/APNs 已通)

**Memory 4 层升级**:

| 层 | 改动 | 文件 |
|---|---|---|
| working | conversation_states 表新建(messages 最近 20 + draft_data + stage),会话+30min TTL | `agent/memory/working_memory.py`(改) + migration 037 |
| episodic | 启发式相关性评分公式对齐(`trigger_source+3 / chain+2 / token_type+2 / mcap+1 / regime_distance / freshness / match_count`)+ score≥3.0 才返回 | `agent/memory/episodic_memory.py`(改) |
| semantic | 50 条上限 + Shadow Mode 14d + 5 条硬晋升条件(3 反思+20 样本+Wilson CI+t-test+2 regime)+ 失效检测(30d 命中 0 次→dormant) | `agent/memory/semantic_memory.py`(改) |
| reflection | JSON diff < 20% 重复检测 + propose_count_so_far | `agent/memory/reflection.py`(改) |
| WAL | 关键写入(trade_outcome/risk_lesson/approve_rule/auto-promote)走 memory_write_wal → 异步入主 DB → 重试队列 60s/5min/30min 退避 → 3 次失败 P1 告警 | 新建 `agent/memory/wal.py` |

### Phase 2 — Skill + Loop + Prompt Library(4-6 周,**并行 Phase 1/3**)

**7 个 Skill SKILL.md 化**(Anthropic tool_use + Progressive Disclosure):

| Skill | 改动 | 文件 |
|---|---|---|
| S01 technical-analysis | 强制走 T14(不让 LLM 算 RSI/MA);domain knowledge 只讲解读 | 新建 `agent/skills/technical-analysis/SKILL.md` + `prompt.md` |
| S02 sentiment-analysis | 同上 | 同结构 |
| S03 onchain-analysis | 同上 | 同结构 |
| S04 signal-strategy-builder ⭐ | 7 阶段状态机(clarifying→refining→confirming→saved);conversation_states 持久化 | 新建 `agent/skills/signal-strategy-builder/` + `agent/orchestration/cocreation_state_machine.py` |
| S05 trade-strategy-builder | 模式晋升路径(paper→notify→auto)+ T15 风险预览 | 新建 `agent/skills/trade-strategy-builder/` |
| S07 review-engine | 日/周/月报 + 规则提议 + S07→T11 approve_rule | 新建 `agent/skills/review-engine/` |
| S08 thesis-writer 🆕 | 3 面合成 + thesis schema(direction/entry_zone/stop_loss/target/conviction/risks/evidence/similar_past_cases) | 新建 `agent/skills/thesis-writer/` |

**5 个 Loop 编排**:

| Loop | 触发 | 文件 |
|---|---|---|
| Scout | EventBus(pump_snapshot/hot_coin_update/kol_signal)→ 规则引擎(0 LLM)→ 是否触发 strategy | `agent/loops/scout_loop.py`(从现有 `event_listener.py` 重构) |
| Thesis | 用户 chat OR strategy.triggered | `agent/loops/thesis_loop.py`(从现有 `multi_role_orchestrator.py` 重构);L1 规则 / L2 单 Opus / L3 3 Haiku 分析师 + 5 轮 Sonnet 辩论 + 1 RiskReviewer + S08 |
| Notify | strategy.triggered → RiskManager 9 项 + T17 仓位 + (paper / notify / auto 分支)+ T13 推送 | `agent/loops/notify_loop.py` |
| Reflect | cron 20:00 / 10 笔闭仓 / 单笔<-25% | `agent/loops/reflect_loop.py` + cron 注册 |
| Chat | 用户 message | `agent/loops/chat_loop.py`(替换现有 `routes_agent.py:/chat` 逻辑) |

**Prompt Library v1**(18 个 P,版本化 + A/B 灰度 + cache):

| 改动 | 文件 |
|---|---|
| 目录结构 `prompts/v1/`(P01-P18)+ frontmatter(model/temp/cache_breakpoints/token 限额) | 新建 `services/pump-scanner/prompts/v1/` 目录 |
| 版本管理 + A/B 分桶 `hash(device_id) % 100` + Canary 5%/Beta 25%/GA 100% | 新建 `agent/prompt_loader.py` + migration 038 prompt_versions 表 |
| Few-shot ≥3 条/prompt(含 persona) | 各 P 配套 `examples.md` |
| Prompt cache > 80% 命中(system prompt 末尾硬加 cache_breakpoint) | `agent/prompt_loader.py` |
| 输出禁用表达 regex 拦截("稳的"/"百倍" 等) | `agent/output_filter.py` |
| Prompt injection 防御(XML 包裹 + blocklist + user_message ≤ 2000 字) | `agent/prompt_loader.py` |
| Progressive Disclosure(S08+S01-03+S07 always loaded;S04/S05 lazy) | `agent/skills/loader.py` |

### Phase 3 — Flutter Agent Tab 重构(3-4 周,**并行 Phase 2**)

**Chat Tab**:

| 改动 | 文件 |
|---|---|
| Thesis 卡片(direction/entry_zone/stop_loss/target/conviction/risks/evidence/similar_past_cases) | 新建 `lib/widgets/agent/thesis_card.dart` |
| 共创 7 阶段 UI(stage 指示 + 澄清提问 + draft 预览 + dry run 预估 + 确认按钮) | `lib/screens/agent/agent_screen.dart`(`_ChatTab` 改)+ 新建 `lib/widgets/agent/cocreation_stepper.dart` |
| 低置信度标注(conviction < 0.5 红色风险条) | `thesis_card.dart` |
| 推送通知(strategy_triggered / hitl_approval / review_ready)→ 深链跳转 | `lib/services/push_notification_service.dart`(扩展 deep_link) |

**Strategies Tab**:

| 改动 | 文件 |
|---|---|
| HITL 详情页(策略名+条件+thesis+风险卡+本次金额+剩余额度+approve/reject + Face ID/wallet sig) | 新建 `lib/screens/agent/hitl_approval_page.dart` |
| 模式晋升流程 UI(paper→notify→auto,显示 30d/30 笔/EV 进度条 + 切换按钮 + 二次风险确认) | `lib/screens/agent/strategy_detail_page.dart`(改) |
| 真金签名流程(Face ID/Touch ID + wallet signature)| 新建 `lib/services/wallet_signer_service.dart` |
| 策略数 ≤20(小白)/ ≤5(小白)/ ≤20(中级专业)按 persona 限制 | `agent_service.dart` 调用前校验 |

**Insights Tab**:

| 改动 | 文件 |
|---|---|
| 日/周/月复盘报告(完整 §7.7 PRD Review Schema) | 新建 `lib/screens/agent/review_page.dart` |
| 规则采纳按钮 → T11 approve_rule + Dry Run Preview(回溯 30d 对比) | `lib/widgets/agent/rule_proposal_card.dart` |
| 用户记忆管理(查看/编辑/禁用/删除/清空/导出 6 项控制) | 新建 `lib/screens/agent/memory_management_page.dart` |
| Shadow Mode 状态显示(规则 14d 观察期进度条) | `memory_management_page.dart` |
| 降级 UI(延迟模式/分析降级 L3→L2/Agent BLOCKED)横幅 | 新建 `lib/widgets/agent/degradation_banner.dart` |

**关键 Service 扩展**(`lib/services/agent_service.dart`):

```dart
Future<Thesis?> requestThesis({chain, address, level: 'auto'})
Future<List<PendingApproval>> getPendingApprovals()
Future<bool> approvePendingApproval(approvalId, signature)
Future<bool> rejectPendingApproval(approvalId)
Future<Review?> getReview(period: 'daily'|'weekly'|'monthly', date)
Future<List<RuleProposal>> getRuleProposals()
Future<bool> approveRule(proposalId, edits)
Future<List<SemanticRule>> listSemanticRules()
Future<bool> updateRule(ruleId, payload)
Future<bool> deleteRule(ruleId)
Future<DryRunResult> dryRunRulePreview(proposalId)
Future<ModePromotionStatus> getModePromotionStatus(strategyId)
Future<bool> requestModeUpgrade(strategyId, targetMode)  // paper→notify→auto
```

### Phase 4 — Eval + 上线门槛(配置 A,6 周)

| 任务 | 数量 | Pass 门槛 |
|---|---|---|
| L1 Tool unit | 17 Tool × ≥10 = 170 | 100% |
| L1 Prompt unit | 18 P × ≥30 = 540 | ≥90% + Safety 100% |
| L2 Skill integration | 7 Skill × ≥50 = 350 | ≥90% |
| L3 Agentic chain | 4 chain × ≥10 = 40 | ≥85%(nightly) |
| L4 Trajectory | 20 场景多轮 | ≥85%(weekly) |
| Safety AE01-AE10 | 270 条 | SEV-0 零漏 / SEV-1 ≥99% / SEV-2 ≥95% |
| Quality Rubric | 5 维(Relevance/Reasoning/Actionability/Risk/Calibration)+ 技术 5 维 | overall ≥80;Actionability=0 / Risk=0 / Safety<10 一票否决 |
| LLM-as-judge 冷启动 | 100 条人工 + Judge 双打 | Pearson ≥0.7;Safety 100% 一致 |
| 62 项 Launch Criteria | 12 Tech + 7 Product + 14 Safety + 12 Legal + 12 Cost/Ops + 5 HITL | 100% |
| 多地区合规 | CN/US/EU 免责 + 法务签字 | 法务最终签字 |
| Canary 5% → Beta 25% → GA | 渐进流量 | 各阶段 SLO 达标 |

---

## 关键文件改动清单

**后端 `services/pump-scanner/`**(新建 ~30 文件 + 改 ~15 文件):

```
agent/
  ├── safety_policy.yaml                🆕
  ├── safety_engine.py                  🆕
  ├── kms_client.py                     🆕
  ├── cost_guard.py                     🆕
  ├── output_filter.py                  🆕
  ├── prompt_loader.py                  🆕
  ├── loops/                            🆕
  │   ├── scout_loop.py
  │   ├── thesis_loop.py                (从 multi_role_orchestrator 重构)
  │   ├── notify_loop.py
  │   ├── reflect_loop.py
  │   └── chat_loop.py
  ├── skills/                           🆕
  │   ├── loader.py
  │   ├── technical-analysis/SKILL.md + prompt.md + examples.md
  │   ├── sentiment-analysis/...
  │   ├── onchain-analysis/...
  │   ├── signal-strategy-builder/... ⭐
  │   ├── trade-strategy-builder/...
  │   ├── review-engine/...
  │   └── thesis-writer/... 🆕
  ├── tools/                            🆕(17 个 Tool 规范化)
  │   ├── base.py(JSON Schema 校验+幂等检查)
  │   ├── t04_recall_memory.py
  │   ├── t09_create_approval.py
  │   ├── t11_approve_rule.py
  │   ├── t14_calc_indicators.py        (复用 btc_eth/indicators/technical.py)
  │   ├── t15_calc_risk.py              (复用 performance_analytics.py)
  │   ├── t16_run_backtest.py           (复用 backtester.py + 加 warnings)
  │   ├── t17_calc_position.py
  │   └── ...
  ├── memory/
  │   ├── wal.py                        🆕
  │   ├── working_memory.py             (改:conversation_states)
  │   ├── episodic_memory.py            (改:相关性公式对齐 + score≥3.0)
  │   ├── semantic_memory.py            (改:50 上限 + Shadow Mode + 5 条硬晋升)
  │   └── reflection.py                 (改:JSON diff < 20%)
  ├── orchestration/
  │   └── cocreation_state_machine.py   🆕
  └── eval/                             🆕
      ├── golden_sets/(L1-L4)
      ├── llm_as_judge.py
      └── runner.py

api/
  ├── routes_agent.py                   (改:扩展 ~10 endpoint)
  ├── routes_audit.py                   🆕
  ├── routes_admin.py                   🆕(Kill Switch)
  └── routes_thesis.py                  🆕

prompts/v1/                             🆕(18 个 P)
  └── P01-P18/{prompt.md, examples.md, frontmatter.yaml}

migrations/
  ├── 034_kms_migration.sql             🆕
  ├── 035_security_audit_log.sql        🆕
  ├── 036_pending_approvals_wal.sql     🆕
  ├── 037_conversation_states.sql       🆕
  ├── 038_prompt_versions.sql           🆕
  ├── 039_agent_thesis.sql              🆕
  ├── 040_semantic_shadow_mode.sql      🆕
  └── 041_eval_results.sql              🆕
```

**Flutter `apps/app/lib/`**(新建 ~12 文件 + 改 ~8 文件):

```
screens/agent/
  ├── agent_screen.dart                 (改:_ChatTab → 共创 7 阶段)
  ├── strategy_detail_page.dart         (改:模式晋升流程)
  ├── hitl_approval_page.dart           🆕
  ├── review_page.dart                  🆕
  └── memory_management_page.dart       🆕

widgets/agent/                          🆕
  ├── thesis_card.dart
  ├── cocreation_stepper.dart
  ├── rule_proposal_card.dart
  └── degradation_banner.dart

services/
  ├── agent_service.dart                (改:加 ~13 个新 method)
  ├── wallet_signer_service.dart        🆕
  └── push_notification_service.dart    (改:deep_link 路由)

models/
  ├── thesis.dart                       🆕
  ├── pending_approval.dart             🆕
  ├── review.dart                       🆕
  └── semantic_rule.dart                🆕
```

---

## 数据 Schema 变更(8 个新表 + 6 张表加字段)

**新表**:`security_audit_log` / `pending_approvals` / `memory_write_wal` / `memory_write_retry_queue` / `conversation_states` / `prompt_versions` / `agent_thesis` / `eval_results`

**加字段**:
- `agent_strategies`: + `mode_locked_until` / `paper_baseline_30d` / `auto_promotion_eligible_at`
- `agent_memory`: + `active_regimes` / `shadow_mode_until` / `propose_count_so_far` / `match_count` / `wilson_ci_lower`
- `agent_alerts`: + `category` 枚举对齐 T13 / `priority` / `deep_link`
- `agent_executions`: + `risk_check_passed` / `hitl_approval_id` / `audit_log_id`
- `device_tokens`: + `kms_key_alias`(托管钱包绑定)
- `agent_strategies`(再次): + `prompt_version_used`(A/B 追踪)

---

## 验收方式(端到端)

### 后端验收

```bash
# 1. Phase 0 灾难漏洞修复验证
cd /opt/agent-trading
grep -r "ANTHROPIC_API_KEY" services/ | grep -v "kms_client" && echo "FAIL: 仍有明文 key"
psql -c "SELECT column_name FROM information_schema.columns WHERE table_name='agent_strategies' AND column_name LIKE '%private%'" # 应返回 0 行

# 2. safety_policy.yaml runtime check
curl -X POST http://localhost:8000/api/agent/safety/runtime-check
# 期望:30 HR + 13 CB + 5 C 全部加载

# 3. Eval 全量
cd services/pump-scanner && python -m eval.runner --suite=all
# 期望:L1 100% / L2 ≥90% / L3 ≥85% / L4 ≥85% / Safety AE 零漏

# 4. Cost 熔断器演练
# 模拟超 70% 预算 → 验证 L3 自动降 Sonnet
# 模拟超 100% → 验证硬停

# 5. Kill Switch
curl -X POST http://localhost:8000/api/admin/agent/kill-switch -H "Authorization: ..."
# 验证 Agent 全局 BLOCKED < 10s
```

### Flutter 验收(配合 preview_*)

```
preview_start → 模拟器 iPhone 17 Pro Max
1. Chat Tab:
   - 输入"做聪明钱跟单" → 验证 7 阶段共创(澄清→draft→dry-run→反馈→确认)
   - 输入"分析 TRUMP" → 验证 thesis 卡片 schema 完整
2. Strategies Tab:
   - paper 策略验证 30 天 → 验证模式晋升按钮可点
   - 触发 HITL → 验证详情页 + Face ID 签名流程
3. Insights Tab:
   - 验证日/周/月复盘报告 schema 完整
   - 验证规则采纳按钮 + Dry Run Preview(对比 30d 采纳 vs 未采纳)
   - 验证记忆管理页(查看/编辑/禁用/删除/清空/导出)
4. 降级演练:
   - 服务端模拟 BLOCKED → 验证 Flutter 降级横幅显示
```

### 上线门槛(62 项 Launch Criteria 全过)

- 12 Tech sign-off:工程
- 7 Product:PM(种子用户 20 人 + NPS ≥ 30)
- 14 Safety:**安全 lead**(灾难 L1/L2/L3 100% 修复 + AE 对抗 + 13 CB 演练)
- 12 Legal:**法务最终签字**(L12 闸门,CN/US/EU 三地区)
- 12 Cost/Ops:Ops lead(月预算 ≤ $1500 + Incident SOP + Kill Switch 演练)
- 5 HITL:10 触发 + 5/15/60min 超时 + 生物认证

---

## 主要风险

1. **工作量巨大**(16-20 周):需要至少 4 人并行(后端 2 + Flutter 1 + Eval/QA 1)+ 安全/法务/Ops 兼职介入
2. **Phase 0 灾难漏洞期间 Agent 可能不可用**:KMS 切换 + 私钥列删除需停机窗口
3. **Eval Golden Set 是关键路径**:1660 条 + 4 人 6 周,任一人延期阻塞 Launch
4. **法务签字风险**:CN/US/EU 三地区合规可能需要 2-4 周往返
5. **Memory Shadow Mode 14d**:首批 Semantic 规则要 14d 观察期才能正式激活,影响"上线即有规则"体验
6. **Auto 模式真金交易**:首笔触发必走 HITL,用户体验 vs 安全的取舍
7. **现有线上服务影响**:重构 `multi_role_orchestrator` 需要灰度切换避免线上中断

## 关键复用(避免重复造轮子)

| 设计要求 | 复用现有代码 |
|---|---|
| T14 calc_technical_indicators | `services/pump-scanner/btc_eth/indicators/technical.py`(RSI/MACD/MA/ATR/BB) |
| T15 calc_risk_metrics | `agent/performance_analytics.py`(胜率/PNL/夏普/最大回撤) |
| T16 run_backtest | `agent/backtester.py` + `services/pump-scanner/backtest.py` |
| T13 send_push_notification | `agent/push_service.py` + `api/routes_device.py` |
| Episodic 相关性评分 | `agent/memory/episodic_memory.py`(已有评分骨架,需对齐文档公式) |
| L1/L2/L3 编排骨架 | `agent/multi_role_orchestrator.py`(需重构为 thesis_loop) |
| Bull/Bear 辩论 | `agent/debate.py`(可直接用于 Thesis L3) |
| Regime 7 状态 | `agent/regime_detector.py`(已实现 CUSUM+HMM+LLM) |
| 事件总线 | `agent/event_bus.py`(已有 asyncio.Queue 100K) |
| Strategy CRUD ≤20 + 冷却 | `agent/strategy_manager.py`(完整) |
| 私钥本地存 | Flutter `flutter_secure_storage`(iOS Keychain / Android Keystore) |
