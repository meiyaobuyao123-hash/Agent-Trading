# Agent v1 实施 vs 设计文档对比审计

**日期**: 2026-05-03
**范围**: `docs/agent-pm/00-17.md` 18 篇设计文档 vs `services/pump-scanner/agent/` + `apps/app/lib/` 实际代码
**方式**: 4 个并行 Explore agent 独立审计 + 主上下文交叉核验

---

## TL;DR

- **总对齐率 ~70%** — 骨架完整,深度有差距
- **结构对齐 95%+**: 17/17 Tools, 18/18 Prompts, 5/5 Loops, 7/7 Skills, 30 HR + 13 CB + 5 C, 62/62 Launch Criteria 全部就位
- **深度对齐 ~50%**: 多处属于 "metadata 写了但运行时未完整接通"(Semantic 5-gate / HITL 时限 / Kill Switch / LLM judge calibration 等)
- **R35 决策性偏差**: KMS / 法务 / Beta 灰度 / Red Team 等 "GA 流程" 被用户明确判定为不需要(早期项目无付费用户),改为 not_applicable;不属于实施缺陷

**用一句话**: v1 可供团队内测使用(rollout 全开 + auto_mode=0 安全锁),但若要面向付费用户上线,P0 punch list 还有 6-8 项。

---

## 1. 模块对齐总览

| 模块 | 设计要求 | 实际实施 | 对齐率 | 来源审计 |
|---|---|---|---|---|
| **5 Loops** | scout/thesis/notify/reflect/chat | 5 个文件 + LLM 真实施(L3 fallback L2) | 80% | A |
| **7 Skills** | S01-S08 SKILL.md + prompt.md | 全部就位(thesis-writer 新建) | 100% | A |
| **17 Tools** | T01-T17 JSON Schema + idempotent + permission + failure_modes | 17/17 全部实施(R35 补完 T01/T02/T03/T08) | 95% | B |
| **4 Memory 层** | working/episodic/semantic/reflection + WAL + Shadow Mode | 4 文件就位,episodic 评分公式对齐,Semantic 5-gate **stub** | 70% | B |
| **18 Prompts** | P01-P18 frontmatter + few-shot ≥3 + cache_breakpoints | 18/18 文件,few-shot 全到位,**版本/CHANGELOG 缺** | 80% | C |
| **Safety Policy** | 30 HR + 13 CB + 5 C + runtime check | 全部 in YAML + safety_engine 加载 + fail-safe BLOCK | 95% | C |
| **Input/Output Filter** | 5 attack class + blocklist regex | input_filter 5 类 + output_filter blocklist 全到位 | 100% | C |
| **62 Launch Criteria** | 12T + 7P + 14S + 12L + 12C + 5H | 6 类 JSON 全在,41 自动通过,21 manual(其中 17 R35 已改 not_applicable) | 100% / 100% pass | D |
| **Cost Guard 5 tier** | 70/85/95/100/150% | 5 阈值 in cost_guard.py + degradation 逻辑全在 | 90%(real-time DB hook 待) | D |
| **Phase 0 灾难修复** | KMS / 私钥列删 / 7 pre_condition / Kill Switch / runbook | KMS→Flutter Keychain(R35 决策);Kill Switch **501 stub**;runbook 已写 | 50% | D |
| **Phase 3 Flutter UI** | Chat 共创 / HITL / Insight / Memory | 5 个 page 全部就位(部分 mock 数据) | 80% | D |
| **Phase 4 Eval** | 1660 case + 4 层 + LLM judge Pearson≥0.7 + 62 Launch | 9 suite runner 完整;case 数量未完整跑过 | 35% | D |

> 审计来源:A = Loops/Skills,B = Tools/Memory,C = Prompts/Safety,D = Launch/Cost/Phase

---

## 2. 重要 ✅ 对齐项(亮点)

### 结构性对齐 100%
- **17 Tools**:全部继承 base.py 抽象,JSON Schema + idempotent + permission + failure_modes + side_effects 元数据齐全
- **18 Prompts**:每个 P 都有 frontmatter.yaml + prompt.md + examples.md(≥3 few-shot)
- **Safety**:30 HR + 13 CB + 5 C 全部在 safety_policy.yaml,fail-safe(yaml 损坏 → BLOCKED)已验证
- **Loops**:5 个文件全在,trigger source 大体对齐
- **Skills**:7 个 SKILL.md 全在(包括新增 S08 thesis-writer)

### 行为性对齐
- **Episodic 评分公式**:trigger_source(+3) / chain(+2) / token_type(+2) / mcap(+1) / regime_distance / freshness_30d 半衰 / match_count log10 — 全部按 06-memory-spec 实施
- **Reflection JSON-diff < 20%**:propose_count_so_far + jaccard 距离去重 in `reflection.py`
- **review_engine v2**:S07 真接 Claude Haiku + P13 daily prompt + fallback 规则化 + cold_start 三态
- **chat_loop**:7 阶段共创 + abort 词检测 + LLM 失败永远不抛错(fallback_text)
- **thesis_loop**:L1 规则化 / L2 P02 + Sonnet / `conviction<0.5 → hold/avoid` 强约束 + risks≥2 + summary≤60 字
- **rollout_gate**:确定性 sha1 分桶,5 feature flag 全在;`agent_v1_auto_mode = 0` 真金安全锁
- **Cost Guard 5 tier**:阈值 + degradation 逻辑实施;触发"L3→L2→Haiku"链路

---

## 3. ⚠️ 偏差项(已知妥协 / 待修)

### 3.1 R35 决策性偏差(早期项目妥协,**非缺陷**)

| 设计要求 | 实施现状 | 决策依据 |
|---|---|---|
| KMS 托管钱包 + 60s 擦除 SLA | Flutter `flutter_secure_storage`(iOS Keychain)+ 调用方传 private_key | 无 AWS 账号,不申请新付费服务;Keychain 自己用够用 |
| 法务 12 项 CN/US/EU 签字 | 全 not_applicable | 没付费用户没合规问题 |
| Canary 5% / Beta 25% / GA 100% 渐进发布 | rollout_gate `agent_v1=100` 直接全开 | 自己用 + 团队内测,无需灰度 |
| Red Team 红队演练 | not_applicable | 内测期不展开 |
| NPS ≥ 30 种子用户 | not_applicable | 无外部用户 |
| Beta 5/15/60min HITL 真演练 | 框架在,timeout handler 缺 | 内测无紧迫;auto_mode=0 兜底 |

### 3.2 命名 / 字段 / 终态偏差(可见 P0/P1)

| 设计 | 代码 | 影响 | 优先级 |
|---|---|---|---|
| mode = `paper / notify_only / auto`(03-prd §5.4) | mode = `paper / live`(strategy_manager.py) | 缺中间 notify_only 状态;前端要拆三档展示困难 | P1 |
| **Paper→Auto 晋升门槛**(30d + 30 笔 + EV≥+1% + max_dd<30%) | `go_live()` 不做任何门槛检查 | **用户可绕过验证直接上线真金策略** | 🔴 **P0** |
| Thesis schema 18 字段(03-prd §2.7) | 缺 `regime_at_generation` / `disclaimer` / `used_tools[]` | trace_id 上能追到决策上下文,但 regime/工具调用不完整 | P1 |
| Semantic 5-gate 自动晋升(reflections≥3 / samples≥20 / Wilson CI≥0.55 / Welch t<0.05 / regimes≥2) | 5 个常数定义在 `semantic_memory.py`,但 `try_promote_strict()` 函数 stub | Reflection→Semantic 自动晋升通路断 | 🔴 **P0** |
| 14d Shadow Mode 真观察(actual vs predicted) | T11 只 set 时间戳,无 cron/handler 评估 | 影子规则到期后无人接管,不会自动 promote/demote | P1 |
| HITL 10 触发条件 | notify_loop.py 只有 4(amount/portfolio/24h_freq/conviction) | 6 个触发条件未实施(volatility / wallet_anomaly / first_time_user 等) | P1 |
| HITL 5/15/60min 超时升级 | `pending_approvals` 表已建,timeout handler **没接** | 超时不降级到 notify_only 也不拒绝,卡死队列 | 🔴 **P0** |
| Kill Switch < 10s 全局 BLOCK | `routes_admin.py` 返 **501 stub** | 紧急时无法 1 键关 | 🔴 **P0** |
| L3 Bull/Bear/RiskReviewer Debate | thesis_loop.py L3 **fallback 到 L2**(代码注释 W7-W12) | L3 高 conviction 决策路径仅做了 metadata,实际是 L2 单 prompt | P1 |
| similar_past_cases 通过 T04 recall_memory 填 | thesis_loop 路径里看不到 T04 调用 | similar cases 字段为空数组 | P1 |
| Prompt cache_breakpoints > 80% 命中率 | `prompt_loader.to_messages_request` 加了 cache_control,但 18 frontmatter 里大多缺 token 限额 / cache 标记 | 命中率未度量,但 SDK 层加了缓存 | P2 |
| Prompt 版本管理 + CHANGELOG | 全部 frontmatter 标 `status: draft`,无 canary/beta/ga 状态机 | A/B 灰度框架在 rollout_gate,但 prompt 自身无版本流转 | P2 |
| LLM-as-Judge calibration Pearson≥0.7 + 100 人工对 | `agent/eval/llm_judge.py` 有 placeholder,未跑 | Eval 5 维 Quality Rubric 当前 heuristic | P2 |

### 3.3 数据通路尚未接通(WAL / 持久化)

| 设计 | 代码 | 缺口 |
|---|---|---|
| Episodic 关键写入(trade_outcome/risk_lesson/approve_rule)走 WAL | wal.py 类已就位,但 episodic.add() 无 `await wal.write(...)` 调用 | 高频写仍直接打 PG,失败时丢失 |
| Cost Guard 实时 DB 查月累 | 60s TTL 缓存 prompt_invocations,无每次 LLM call 后即时 update | 高峰期可能滞后判 BLOCKED |
| Semantic 失效检测(30d 命中 0 → dormant) | 仅 cron 框架,handler 未实施 | 旧规则不会自动归档 |

---

## 4. ❌ 缺失项(完全未实施)

| 设计 | 出处 | 优先级 |
|---|---|---|
| Pydantic `ThesisModel` BaseModel(18 字段强 schema 校验) | 03-prd §2.7 | P1 |
| `GET /api/agent/strategies/:id/promotion-check` 端点(查 paper→auto 是否合格) | 04-agent-spec §3.1 | P0(配套 paper→auto 门槛) |
| Audit Log 三级查询 API(用户 / Admin / 法务) | 08-safety §11.5 | P2(早期不要) |
| Paper vs Auto 价格分歧监控(>5% alert) | 03-prd §4.11 case 866 | P2 |
| Constitutional Rules C1-C5 注入到所有 System Prompt | 08-safety §C | P1 |
| Token overflow 6 级降级截断 | 07-prompt §5.6 | P2 |
| 多语言 few-shot(zh-CN + en-US) | 07-prompt §5.8 | P2 |
| Incident Response Runbook(top 10 failure mode) | 12-incident-response-sop | P0(已写部分,需补全) |
| Chat Tab Dry Run preview(共创 stage 4 backtest 集成) | 04-agent-spec §S04 | P2(代码标记 W7-W12) |

---

## 5. Phase 0-4 进度评分

| Phase | 范围 | 完成度 | 关键 punch list |
|---|---|---|---|
| **Phase 0 灾难修复** | KMS / 私钥列 / safety_engine / Kill Switch / pending_approvals / runbook | **55%** | Kill Switch 实施 / KMS 决策已替换;runbook 补全 |
| **Phase 1 Tools+Memory** | 17 Tool + 4 Memory 层 + WAL | **80%** | Semantic 5-gate / WAL 接通 / Shadow Mode 14d 评估 |
| **Phase 2 Skills+Loops+Prompts** | 7 Skill + 5 Loop + 18 Prompt | **85%** | L3 真 debate / Prompt 版本管理 / Constitutional 注入 |
| **Phase 3 Flutter UI** | Chat / HITL / Insight / Memory | **70%** | mode 三档晋升 UI / dry run preview / 真后端接通(部分仍 mock) |
| **Phase 4 Eval** | 9 suite + Golden 1660 + LLM judge | **35%** | Golden case 量化跑通 / Pearson calibration / Trajectory 实测 |

**整体加权 ~65-70%**(权重:Phase 0 关键性 30% + Phase 1-3 各 20% + Phase 4 10%)

---

## 6. P0/P1/P2 修复路径(优先级)

### 🔴 P0(阻塞团队内测以外的任何使用场景)

1. **paper→auto 晋升门槛**:`strategy_manager.go_live()` 加 `check_promotion_eligibility()` — 30d / 30 笔 / EV≥+1% / max_dd<30%(~40 行 + 测试)
2. **HITL 5/15/60min 超时 escalation**:`agent/loops/notify_loop.py` 加 timer + handler;5min→升级提示 / 15min→ degrade 到 notify_only / 60min→ reject + audit log(~80 行 + 测试)
3. **Kill Switch 真实施**:`api/routes_admin.py` 接 Redis pub/sub + 进程内标志位 + safety_engine.global_state=blocked(~60 行 + 演练验证 < 10s)
4. **Semantic 5-gate `try_promote_strict()` 实施**:`agent/memory/semantic_memory.py` 加 Wilson CI helper + Welch t-test + 5 条件检查(~50 行 + 单元测试)
5. **Incident Response Runbook 补完**:`docs/runbook/` 加 top 10 failure mode(LLM 故障 / DB 挂 / Helius 限流 / KMS 私钥泄露应急 / 真金交易意外触发等)

### 🟡 P1(post-内测,正式上线前)

6. **Thesis schema 补 3 字段**:`regime_at_generation` / `disclaimer` / `used_tools[]` + Pydantic Model + thesis_loop.py 填充
7. **Mode 命名对齐**:strategies 表加 `mode notify_only` 中间值;Flutter 三档晋升 UI
8. **L3 真 Debate 实施**:thesis_loop.py L3 路径接 P12 Bull / P14 Bear / P15 Facilitator + RiskReviewer
9. **HITL 6 个剩余触发**:volatility / wallet_anomaly / first_time_user / strategy_drift / risk_score>70 / regime CRISIS
10. **Constitutional Rules C1-C5 注入 System Prompt**:prompt_loader.to_messages_request 自动追加
11. **WAL 接通 Episodic**:`episodic.add()` 关键 category 走 WAL + 重试队列

### 🟢 P2(v1.1+)

12. **LLM-as-Judge calibration**:跑 100 人工对 + Pearson≥0.7
13. **Audit Log 三级查询 API**(早期不要,有付费用户再做)
14. **Prompt CHANGELOG.md + 版本流转**(canary/beta/ga 状态机)
15. **Token overflow 6 级降级**(目前 prompt token 余量大不会触发)
16. **Semantic 失效检测 cron**(30d 命中 0 → dormant)
17. **Chat Dry Run Preview**(7 阶段第 4 步真接 backtest)

---

## 7. 与 R35 决策一致的合规性确认

R35 用户决策(2026-05-01)明确:
> 早期项目,没有真实付费用户,自己用 / 内部测试为主。没有 AWS 账号;不愿意申请新的第三方收费服务。

以下"未实施"项目已在 launch_criteria/{legal,safety,cost_ops,product,hitl}.json 改为 `not_applicable` + reason,**不视为对齐缺口**:

- L01-L12 法务 12 项 → not_applicable("早期项目无付费用户")
- S13 KMS / S14 Red Team → not_applicable("Flutter Keychain 已就位 / 内测无需红队")
- C12 Budget signoff → not_applicable("自己用 0 DAU")
- P07 NPS ≥ 30 → not_applicable("无外部用户")
- H05 Biometric drill → not_applicable("Flutter Face ID 已就位")

合计 17 项,Launch Criteria 实际通过率 = 41 自动 + 17 N/A + 4 manual = **62/62 = 100%**(算法:not_applicable 视为 pass)。

---

## 8. 结论

**对齐评价**:**~70%** 对齐设计文档,且大多 P0/P1 缺口在 punch list 里有明确出处,可在 1-2 个 sprint 内补完。

**适合场景**:
- ✅ 团队内测(rollout 全开 + auto_mode=0 真金硬锁)
- ⚠️ 任何 paper / notify 模式策略均可用,但用户无法自行升级到 auto
- ❌ 面向付费用户公开:还需补完 P0 punch list 5 项 + 启动 P1 / Legal

**最关键风险**:
1. **paper→auto 晋升门槛缺失**:用户若手动改数据库 mode 字段或绕开 strategy_manager,可直接走真金 — 当前靠 `agent_v1_auto_mode = 0` 兜底
2. **HITL 超时不降级**:用户错过 60min 后审批队列卡死,无 auto fallback
3. **Kill Switch 501**:紧急时只能 ssh 改 rollout_gate 或 systemctl stop,达不到 < 10s SLA

**建议下一阶段(假设 1 sprint = 1 周):**
- W1: Phase 0 P0 punch list(5 项,~250 行 + 测试 + 演练)
- W2: Phase 1 P0(Semantic 5-gate)+ P1(Thesis 字段 / Mode 命名 / WAL 接通)
- W3: Phase 4 (Golden case 真跑 + Pearson calibration)
- W4: 团队内测反馈收集 + 修 bug + 准备 v1.1 候选清单

---

**审计员**: Claude Code(主上下文 + 4 个并行 Explore agent)
**原始报告**: `/tmp/audit-loops-skills.md`(完整版)+ `/tmp/audit-launch-cost.md`(完整版)
**下次审计建议**: Phase 0 P0 punch list 完成后 + 团队内测 1 周反馈后
