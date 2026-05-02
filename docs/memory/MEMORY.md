# Project Memory — Agent-Trading

## 🔴 每次会话开始必须执行（强制）
立即读取以下所有 topic 文件，不得跳过：
- [credentials.md](./credentials.md) — API Key、URL、服务器密码
- [architecture.md](./architecture.md) — 架构、数据流、启动命令
- [pitfalls.md](./pitfalls.md) — 踩坑记录
- [rules.md](./rules.md) — 工作规则详细版
- [sessions-log.md](./sessions-log.md) — 历史会话记录 + 讨论结论 + 被否定方案

## ⚠️ 工作规则（每次会话必读）
详见 [rules.md](./rules.md)

**记忆更新**: 发现新凭证/踩坑/纠正/功能变更 → 立即更新，不等任务结束
**数据源**: EVM聪明钱用 `web3.okx.com`，SOL用 Helius WS，禁止 Etherscan，禁止 www.okx.com
**实现规则**: 讨论完先验证API → 实现后grep验证 → 不得悄悄换数据源
**诚实原则**: 没做就说没做，做了必须有证据同步用户，不得虚报完成
**双份同步**: 每次更新记忆文件，本地 topic 文件 + 仓库 CLAUDE.md 必须同时更新，内容一致
**用户偏好**: 中文输出，真实数据，不估时间，不过度工程化

---

## 快速速查

### 线上地址
- Portal: http://43.156.207.26（服务器部署，nginx反代:3000）
- Portal (Vercel备): https://agent-trading-portal.vercel.app/hot
- Backend API: http://43.156.207.26（nginx分流到:8000）
- GitHub: https://github.com/meiyaobuyao123-hash/Agent-Trading

### 本地路径
- 后端: `/Users/wenruiwei/Desktop/Agent-Trading/services/pump-scanner/`
- Flutter: `/Users/wenruiwei/Desktop/Agent-Trading/apps/app/`
- Portal: `/Users/wenruiwei/Desktop/Agent-Trading/apps/portal/`

### 服务器 SSH
```
ssh ubuntu@43.156.207.26  密码: 1234567890weiW%
```

### Flutter 启动
```bash
flutter run -d DBC925B5-7657-4410-B770-F21E4605A9D6 \
  --dart-define=API_BASE_URL=http://43.156.207.26 \
  --dart-define=HELIUS_API_KEY=a194f0cb-e6f5-474d-a9fc-d13b6e916964
```

---

## 项目概览
- **双轨**: pump.fun 内盘（BC 3-35%）+ 多链热币（SOL/BSC/Base/ETH）
- **信号**: 规则打分 → XGBoost ML（待训练，3/27 提醒）
- **端到端**: 信号采集 → 聪明钱追踪 → Agent策略 → OKX DEX 真实交易 → Flutter App 推送

## 当前功能状态
| 模块 | 状态 | 备注 |
|------|------|------|
| pump.fun 采集 | ✅ 线上 | 三阶段架构：WS全量捕获→交易追踪→按需enrich |
| 热币扫描 | ✅ 线上 | OKX+GeckoTerminal 双源，毫秒级打分，进出榜单 |
| 聪明钱追踪 | ✅ 线上 | DEX程序级监控（毫秒级），SOL 5222 + EVM 10540 地址，v3五维评估 |
| KOL 舆情 | ✅ 线上 | 212 KOL，_evaluate_accuracy TODO |
| Agent 交易 | ✅ 线上 | Claude LLM + OKX DEX，SOL+EVM |
| Flutter App | ✅ 运行 | 模拟器 iPhone 17 Pro Max，i18n 4语言 |
| Portal | ✅ 线上 | 服务器部署(systemd+nginx)，apps/portal，Vercel弃用 |
| AI Optimizer | ✅ 线上 | Claude Opus 4.6，pump/hot 交替优化，Portal审批 |
| i18n 国际化 | ✅ 完成 | zh/en/ja/ko，275+ 本地化字符串，语言切换器 |
| 合规 | ✅ | 免责声明Gate + CN IP屏蔽 + 推送限流 |
| XGBoost ML | ⏸ 待训练 | 管线就绪，3/27 提醒 |
| Firebase 推送 | ⏸ 待配置 | 需用户创建 Firebase 项目 |
| App Store 上架 | 🔄 进行中 | Build 2 已上传，待 Build 3（含新icon）+ 截图 + 提交审核 |

## 待执行（手动）
- [ ] Supabase Dashboard 执行 `migrations/017_user_api_quota.sql`（如未执行）
- [ ] Firebase 项目创建 + 下载 google-services.json / GoogleService-Info.plist

---

## 详细文档索引
| 文件 | 内容 |
|------|------|
| [credentials.md](./credentials.md) | 所有 API Key、URL、服务器密码 |
| [architecture.md](./architecture.md) | 系统架构、数据流、表结构、启动命令 |
| [pitfalls.md](./pitfalls.md) | 踩坑记录（API/Flutter/DB/交易） |
| [rules.md](./rules.md) | 工作规则详细版 |
| [feedback_data_sources.md](./feedback_data_sources.md) | 数据源优先级 |
| [sessions-2026-03-12.md](./sessions-2026-03-12.md) | 03-12 六次会话记录 |
| [testing-2026-03-13.md](./testing-2026-03-13.md) | 03-13 全量测试+修复记录 |
| [project_smart_money_status.md](./project_smart_money_status.md) | 聪明钱暂不可用，地址太少，后续单独优化 |
| [feedback_hot_coin_coverage.md](./feedback_hot_coin_coverage.md) | 热币全量扫描 vs 排行榜评估：排行榜够用，优先优化打分 |
| [project_agent_pm_docs_status.md](./project_agent_pm_docs_status.md) | docs/agent-pm/00-16 是 Agent v1 优化设计产出物，**从未实施**，讨论时不要当 baseline |
| [feedback_native_flutter.md](./feedback_native_flutter.md) | Flutter UI 验证用原生 iOS 模拟器,不要走 Flutter web preview |

---

## 2026-05-01 本次会话（W1 启动 + W3 D1/D2/D3 safety_engine）
- ✅ W1 启动包（commit `e08eae1`）：28 文件 +2266 行，migrations/agent骨架/Flutter models 全部就位
- ✅ W3 D1（commit `4bbc05d`）：safety_engine 10 HR + 5 C，**62 测试通过**；migrations 迁本地 PG；db_cleanup 加 8 表 TTL
- ✅ W3 D2（commit `ad5fd9f`）：safety_policy.yaml v0.3 全部 30 HR + 13 CB + 5 C 实施；safety_engine 加 BreakerState/trip/release/auto-expire/persister；migration 042 agent_global_state；**132 测试通过**
- ✅ W3 D3（commit `eca6037`）：global_state_persister.py（PG 持久化 + 启动恢复 + 幂等）；trade_executor 加 safety_ctx 参数 + check_safety_for_trade helper；**164 测试通过**（+22 persister + 10 trade safety）
- ✅ W3 D3 续（commit `19654be`）：main.py 启动调 attach_to_engine（恢复 _active_breakers）；Flutter AgentService.requestThesis() 接 /api/thesis MOCK_MODE；新增 ThesisCard widget（低置信度警告 + 方向 + 入场/止损/目标 + 风险列表 + 证据/历史折叠）；dart analyze 0 issues
- ✅ W3 D3 续 2：app.py 挂载 thesis/audit/admin routers；agent_screen.dart Chat Tab 加 ThesisCard Demo Banner（真实 API 调用 + 失败 fallback 本地 mock）；**Flutter widget test 18 个全部通过**；累计 **182 测试**（后端 164 + Flutter 18）
- ✅ W3 D3 续 3：用户纠正"跑偏了"，Flutter web preview 改为原生 iOS 模拟器；`flutter run -d DBC925B5...` 跑通 + 修复 `AgentService.instance` singleton 调用 + `xcrun simctl io booted screenshot` 验证 ThesisCard 完整渲染（TRUMP/L2/看涨 72%/价格三件套/风险/折叠/Footer 全部 OK）；写 feedback_native_flutter.md 防下次再跑偏
- ✅ W3 D4：routes_agent.chat/stream 接入 safety pre-check + cb_monitor 模块(CB07/CB08 外部触发) + routes_agent HITL endpoints(MOCK_MODE) + Flutter HitlApprovalPage(倒计时/策略/金额/嵌入 ThesisCard/批准+拒绝按钮) + Demo Banner 入口；**累计 222 测试通过**(后端 191 + Flutter 31);原生 iOS HITL 详情页截图验证(05-hitl-page.png);写 prod 部署 runbook
- ⚠️ W3 D4 部署服务器(用户授权 SSH 密码后):备份 + 切 agent-v1 + dry-run import OK(83 routes / 30 HR + 13 CB)+ **8 张本地 PG 表已建**(local_pg/034-039,041,042 全部 success)+ 服务重启;**遇基础设施 bug**:任何 systemctl restart 后 FastAPI 8000 不 LISTEN(回滚 main 也一样,跟 agent-v1 无关,见 pitfalls.md);已切回 main 分支保线上稳定;agent-v1 GitHub commit `a6e1674` 完整保留
- 🐛 W3 D4 修 8000 启动竞态尝试**失败**:第一版 commit `34b9c00` 用 `socket.create_connection` 同步阻塞引入新 bug;紧急修 commit `c4ae116` 换 `asyncio.open_connection`,**冷启动 work**(看到 "FastAPI on port 8000 ready" log)**但 systemctl restart 仍卡死**(根因可能是 SmartMoneyTracker WebSocket fd 残留/重连风暴)。承认修复尝试失败,4 条修复候选写入 pitfalls.md,用户再 reboot 救场后线上恢复。**当前线上稳定但避免 systemctl restart**(改用 sudo reboot)
- ✅ **W3 D4 8000 bug 治本**(commits `03d9cd1` + `660f4dc`):走候选 3 — 独立 uvicorn systemd service。新 `api_server.py`(独立 process)+ `pump-scanner-api.service`,原 pump-scanner 加 `ENABLE_API=false`(只跑 scanner)。8000 跟 scanner 完全脱钩。**5 次 restart pump-scanner 8000 全程稳定 + 3 次同时 restart 两服务都秒恢复**。遗留 _signal_pool 跨进程问题:文件 IPC 解决(`/tmp/pump_signal_pool.json` 60s dump,routes_pump 读)。线上现在 systemctl restart 完全稳定,不需要 reboot
- ✅ **W3 D5 agent-v1 切上线**(commit `2171af7` deploy):服务器切 agent-v1 + SafetyEngine v0.3 加载 `HR=30 CB=13 C=5 hr→cb=6 state=normal`,12 张 agent_v1 本地 PG 表全部确认存在,8000 正常 LISTEN
- ✅ **W3 D5 Redis IPC**(commits `5b39e14` + `769f849`):`pump:signal_pool` 5s set + 文件 60s 兜底,routes_pump 读取 Redis → 文件 → 空 三层降级,API `dump_age_ms` 实测 < 1s。dump loop 改 threading.Thread 绕开 event loop starvation。修服务器 `.env ENABLE_API=true` 覆盖 systemd 的隐藏 bug。3×restart 全稳定
- ✅ **W3 D5 Phase 3 Flutter UI**(commit `cd299f6`):3 个新组件 + 17 widget tests
  - cocreation_stepper.dart(7 阶段进度条 idle→...→saved)
  - review_page.dart(日/周/月切换 + Summary + 6 metrics + Insights + RuleProposals)
  - memory_management_page.dart(Active/Shadow/Dormant 状态 + 14d 倒计时 + Dormant 提示)
  - agent_service.dart 加 mock methods(getReview/listSemanticRules/etc.)
  - ai_insights_tab 加 Phase 3 入口卡 + agent_screen 加共创 demo banner
  - 原生 iOS 4 张截图验证渲染完整(/tmp/screenshot-1..4)
- ✅ **W3 D5+ Phase 3 后端 endpoints**(commit `ad8516f` deploy):5 个新 endpoint 对接 Flutter
  - GET /api/agent/memory/rules(读 Supabase agent_memory + 映射 SemanticRule schema)
  - PATCH/DELETE /api/agent/memory/rules/{id}(改 is_active + 强制缓存刷新)
  - POST /api/agent/memory/rule-proposals/{id}/approve(MOCK,W7-W12 接 reflection)
  - GET /api/agent/reviews?period=daily|weekly|monthly(MOCK,W7-W12 接 S07)
  - **16 单元测试全过**(local Py3.9 用 mini FastAPI 绕开 routes_thesis PEP 604)
  - 服务器 localhost curl 验证 5 endpoints 都返真实 JSON;CN IP 经 nginx 被 GEO middleware 拦,Flutter 自动 fallback 到本地 mock(数据形态对齐,UI 视觉一致)
- ✅ **W3 D5+ S07 review-engine 真实施**(commit `8f9c0c0` deploy):mock → 真实 trade 数据汇总
  - agent/review_engine.py:_load_trades(agent_executions + token_performance D3)+ _compute_metrics(win_rate/EV/Sharpe/max_dd/profit_factor/Kelly)+ 规则化 insights/proposals + Wilson CI
  - cold_start 三态:no_trades / few_trades / normal
  - routes /reviews 接通 + 失败降级 mock
  - **25 单元测试全过**;线上验证 source=rule_engine,0 trades → "今日暂无交易"
- ✅ **W3 D5+ 共创状态机骨架**(commit `8a63804` deploy):S04 状态机
  - agent/orchestration/cocreation_state_machine.py:7 阶段 + STAGE_TRANSITIONS + suggest_next_stage 启发式
  - load/create/append/transition/cleanup 操作本地 PG conversation_states
  - 5 个 endpoint:GET state / POST start / message / transition / abort
  - **29 单元测试全过**;线上 curl POST /cocreation/start 真返完整 state JSON
- ✅ **W3 D5+ 推送深链**(commit `210653f`):后端 + Flutter 双端
  - 后端 push_service.build_deep_link(category, **params) 6 类映射 + URL encode
  - action_dispatcher 两处推送 push_data 加 category + deep_link
  - Flutter lib/services/deep_link_router.dart:navigatorKey + handle/handleFromPushData
  - app.dart MaterialApp 注入 navigatorKey;push_notification_service 三处 handler 接 router
  - **后端 12 + Flutter 7 测试全过**
- ✅ **W3 D5+ 核心 3 Tool**(commit `72616c4` deploy):T11 + T13 + T15
  - T11 approve_rule:写 agent_memory + 14 天 Shadow Mode + 幂等(同 proposal_id 返 duplicate)
  - T13 send_push_notification:包装 push_service + build_deep_link,非幂等(side=PUSH)
  - T15 calc_risk_metrics:复用 review_engine,纯函数,permission=PUBLIC
  - get_tool_registry() 返 3 个 Tool 实例;to_anthropic_tool_spec 可直接喂 Messages API
  - **17 单元测试全过**;服务器 jsonschema 安装 + tools 注册 OK + api 健康
- ✅ **W3 D5+ 再加 3 Tool**(commit `3a11147` deploy):T04 + T14 + T17(Phase 1 Tool 共 6/17)
  - T04 recall_memory:三层 memory(working/episodic/semantic)合并查询;单 layer 失败不阻断其他 layer
  - T14 calc_technical_indicators:包装 btc_eth/indicators/technical.py(RSI/MACD/Bollinger/ATR/MA/SR);K 线不足返 null
  - T17 calc_position_size:fixed_pct / kelly(half-kelly) / atr_risk 三 mode + HR01/HR04 风控硬上限 + capped_by 透明返回
  - **19 单元测试全过**;服务器 6 Tool 注册 OK
- ✅ **W3 D5+ Memory 升级 + T05/T06**(commit `5bf2868` deploy):Phase 1 Tool 共 8/17
  - episodic.get_relevant 评分公式(trigger+3 / chain+2 / token_type+2 / mcap+1 / regime_distance / freshness 30d 半衰 / match_count log10)+ score≥3.0 过滤 + bump match_count
  - semantic.check_strict_promotion_gates 5 条硬门槛(3 反思 / 20 样本 / Wilson≥0.55 / Welch t-test p<0.05 / 2 regime)+ try_promote_strict 写入 + 14d Shadow Mode
  - reflection.deduplicate_proposed_rules JSON-diff < 20% 去重(jaccard 距离 + case 归一)
  - T05 list_strategies(StrategyManager 包装,精简 + active_count)+ T06 update_strategy_status(VALID_TRANSITIONS + 幂等 + 透明 reason)
  - **26 单元测试全过**;服务器 8 Tool 注册 OK
- ✅ **W3 D5+ T07/T09/T10/T12 四 Tool**(commit `2673c4a` deploy):Phase 1 Tool 共 12/17
  - T07 run_paper_trade:buy(open_position +1.5% 滑点)/ sell(close_position by trade_id),透明 missing 参数
  - T09 create_approval_request:写本地 PG pending_approvals,idempotency_key UNIQUE 强幂等(同 key 返已有 + idempotent_hit=true);默认 5min,上限 60min
  - T10 get_paper_performance:get_stats + 可选 get_comparison;加 promotion_eligible / promotion_blockers 字段(closed≥30 + avg_pnl_pct≥1.0 对齐 C5 晋升门槛)
  - T12 save_strategy:create_strategy + 默认配额(active≥20 阻止),skip_quota_check 可绕过;ValueError/RuntimeError 透明 reason
  - **24 单元测试全过**;服务器 12 Tool 注册 OK
- ✅ **W3 D5+ Prompt Library v1 骨架 + 6 核心 P**(commit `2f34696` deploy):
  - prompt_loader.py 完整重写:_parse_frontmatter(YAML 子集 + PyYAML 优先)/ _render_template({{var}}/{{nested.key}})/ PromptSpec(model/temp/max_tokens 派生属性)/ PromptLoader(load_from_disk + select_version + bucket + render + to_messages_request 含 cache_control + few-shot 拼接)
  - select_version 优先级:ga(rollout 100) > beta(25) > canary(5) > draft fallback;bucket = sha1(device + prompt_id) % 100 独立灰度
  - 6 个完整 P:P01 chat_clarify(澄清 2-4 回合)/ P02 thesis_writer(direction/conviction/risks≥2)/ P10 risk_reviewer(soft flags + verdict)/ P11 signal_strategy_builder(StrategySpec mode=paper)/ P13 review_engine_daily(headline+三段式 body)/ P18 persona_translator(newbie/intermediate/pro)
  - 每个 P:frontmatter.yaml + prompt.md + examples.md(≥3 条 few-shot)
  - **28 单元测试全过**;服务器 PyYAML 6.0.3 安装 + 6 P 加载 OK
- ✅ **W3 D5+ review_engine v2 LLM 接通**(commit `4beb912` deploy):S07 mock → Claude Haiku
  - generate_review 加 use_llm 参数 + _make_summary_with_llm:用 prompt_loader 调 P13 + anthropic.Anthropic
  - 失败降级:LLM 抛错 / 无 key / JSON 解析失败 / 部分 schema → fallback v1 rule_engine(透明 source 字段区分)
  - cold_start ≠ normal 直接走规则化(节省 token);body 超长强制裁剪 600 字
  - _log_prompt_invocation 异步写本地 PG prompt_invocations(schema 对齐 migration 038)
  - **12 v2 测试全过**(mock anthropic 覆盖 LLM 成功/失败/解析/裁剪);累计 review_engine 37 测试
- ✅ **W3 D5+ 共创 chat_loop LLM 真实施**(commit `961554f` deploy):P01+P11+T12 端到端串通
  - 新建 agent/loops/chat_loop.py(400+ 行)CocreationLoop 单 turn 处理:
    1. load_or_create state + abort 词全局检测
    2. stage handler 路由:clarifying(P01) → refining(P11→spec JSON) → dry_run(占位) → confirming(确认词→T12 save)
    3. LLM 失败永远不抛错 → fallback_text 占位回复;source 字段透明区分
  - 加 POST /api/agent/cocreation/chat 端点
  - **26 chat_loop 测试全过**(mock anthropic 覆盖所有分支)
  - **服务器 LLM 真调通**:curl POST /chat 返 source=llm + Claude Haiku 真澄清提问("确认一下:-10% 和 +30% 是百分比?")
- ✅ **W3 D5+ Thesis Loop 真实施**(commit `19aeccb` deploy):3 路 + P02 + agent_thesis 持久化
  - 新建 agent/loops/thesis_loop.py(400+ 行)ThesisLoop.generate(device_id, chain, token, level=auto/L1/L2/L3)
  - _select_level:position+score 综合判断;L3 暂 fallback L2(真 debate 留 W7-W12)
  - _gather_evidence:并发 3 路 analyst,失败 layer 用 NEUTRAL_FALLBACK 不阻断
  - L1 路径:_make_l1_thesis 0 LLM 成本(conviction < 0.5)
  - L2 路径:P02 + Sonnet → JSON 解析;LLM 失败降级 L1
  - _normalize_and_validate 实施 PRD 硬约束(conviction<0.5 必须 hold/avoid + risks≥2 + summary 60 字)
  - _persist_thesis 写本地 PG agent_thesis;非 UUID device_id 跳过
  - 重构 routes_thesis 全部 4 endpoint(POST/GET/{id}/{id}feedback/list)
  - **33 单元测试全过**;服务器 L1 真接通(score=75 → bullish + 0 cost)
- ✅ **W3 D5+ Reflect Loop 真实施**(commit `baf618a` deploy):反思→JSON-diff→5 硬晋升 闭环
  - 新建 agent/loops/reflect_loop.py(260+ 行)ReflectLoop.run_cycle(trigger=daily/count/emergency)
  - 复用 review_engine._load_trades + ReflectionEngine.run_reflection
  - dedupe(JSON-diff < 20%)+ 5 条硬晋升 try_promote_strict + 14d Shadow Mode
  - gate_blocked → 写 episodic 留底(propose_count++)
  - 反思总结写 episodic(供下次反思参考)
  - count trigger 重置 trade_counter
  - 加 POST /api/agent/reflect/run 手动触发端点
  - **13 单元测试全过**;服务器健康验证 OK
- ✅ **W3 D5+ Notify Loop 真实施**(commit `5f95fe2` deploy):strategy_triggered 完整路径
  - 新建 agent/loops/notify_loop.py(460+ 行)NotifyLoop.process(event, mode, dry_run)
  - 流程:safety pre-check → RiskManager 16 项 → T17 仓位 → mode 分支 → T13 push
  - 4 mode 分支:paper(T07)/ notify(只 push)/ auto+HITL(T09 创建 approval)/ auto-direct(v0 fallback notify-only,KMS 真接 W7-W12)
  - HITL 4 条触发(amount≥$200 / portfolio≥30% / 24h≥5笔 / conviction<0.6)
  - blocked 路径仍发拦截通知(对齐"safety/risk 任一 BLOCK 不静默")
  - 加 POST /api/agent/notify/trigger 手动触发(支持 dry_run)
  - **18 单元测试全过**;服务器 dry_run 真接通(verdict=dry_run + position_usd=50 + latency 710ms)
- ✅ **W3 D5+ Scout Loop 真实施**(commit `4e02b4a` deploy):signal → strategy match → NotifyLoop
  - 新建 agent/loops/scout_loop.py(200+ 行)ScoutLoop.process(signal_payload, source, dry_run, max_dispatch)
  - 复用现有 StrategyEvaluator + StrategyManager + rule_engine
  - 与 event_listener.py 共存(不破坏线上 EventBus 自动订阅);本 Loop 给 manual /scout/evaluate + 测试用
  - 流程:DataEvent → get_active_strategies(source) → evaluate → check_daily_limit → 拼 NotifyLoop event(注入 signal_payload 到 trigger_context.token_data) → notify.process(mode, dry_run) → record_trigger
  - max_dispatch 上限(默认 5)防爆炸;mode_override 测试用
  - 加 POST /api/agent/scout/evaluate(默认 dry_run=true)
  - **12 单元测试全过**;服务器接通(0 hot_coin 关联策略时正确返 0)
  - **🎉 Phase 2 5/5 Loop 全部完成 — Agent v1 编排层闭环!**
- ✅ **W3 D5+ T16 + 2 cron 接入**(commit `8d587ba` deploy):Phase 1 Tool 13/17 + cron 闭环
  - T16 run_backtest:包装 backtester.backtest_strategy + 规则化 warnings(sample_low/window_short/window_long/high_drawdown/disclaimer)
  - main.py 加 reflect_daily cron(UTC 12:00 = 北京 20:00)真触发 ReflectLoop.run_cycle
  - main.py 加 cocreation_cleanup cron(每 5min)清理过期共创会话
  - **13 T16 测试全过**;服务器 deploy 后两个 cron 都成功 Added job ✅
- ✅ **W3 D5+ Memory WAL 真实施**(commit `30da49c` deploy):Memory 写入可靠性闭环
  - agent/memory/wal.py 完整重写(占位 → 260 行真实施)
  - MemoryWAL.write:同步 INSERT memory_write_wal + ON CONFLICT 幂等
  - MemoryWAL.flush_once:扫 unflushed → 写主表 agent_memory → 失败 enqueue retry
  - MemoryWAL.retry_once:60s/5min/30min 退避;3 次失败 → P1 标记
  - try_promote_strict 接 WAL(异步 fire-and-forget,失败不阻断主路径)
  - main.py 加 memory_wal_flush(10s)+ memory_wal_retry(30s)2 cron
  - **20 单元测试全过**;服务器 2 cron 注册 OK
  - **Phase 1 Memory 4 层升级完成度:评分公式 ✅ + 5 条硬晋升 ✅ + JSON-diff dedupe ✅ + WAL 真接入 ✅**
- ✅ **W3 D5+ Cost Guard 真实施**(commit `05aa5a0` deploy):Phase 0 CB04 完成 — LLM 月预算降级
  - agent/cost_guard.py 完整重写(占位 → 220 行真实施)
  - 5 级降级:NORMAL(<70%) / SOFT(opus→sonnet) / HARD(双跳到 haiku) / EMERGENCY(L3 拒+L2 强 haiku) / HARD_STOP(全拒) / BLOCKED(>=150%)
  - check_before_call:LLM 调用前查 prompt_invocations 当月 SUM(60s 缓存),返 (allowed, actual_model, reason)
  - 接入 chat_loop / thesis_loop / review_engine 三个 LLM 调用站,blocked → fallback rule_engine
  - **28 单元测试全过**;服务器实测 chat 走 LLM(预算 <70%)正常 source=llm + Claude 真澄清
- ✅ **W3 D5+ L3 thesis 真 debate**(commit `5c083aa` deploy):L3 路径完整实施(替代之前的 fallback L2)
  - agent/loops/thesis_loop.py:_run_debate(cost_guard 检查 + DebateEngine.run_debate Bull/Bear/Facilitator 5 轮)
  - _adjust_with_debate:Bull 强 +0.05;Bear 强反转 neutral;Draw ×0.85;facilitator action=hold 强制 neutral;PRD 二次校验
  - debate_record 写 agent_thesis.debate_record JSONB 字段(migration 039 已建)
  - cost_guard EMERGENCY 时 debate 跳过(避免 4x token);失败 swallow 不阻断 P02 输出
  - **10 新测试全过**(累计 thesis_loop 43 测试);**Phase 2 thesis L1+L2+L3 完整路径 ✅**
- ✅ **W3 D5+ Skill 层 SKILL.md 化**(commit `02ec8a9` deploy):**Phase 2 完整 ✅**
  - agent/skills/loader.py 完整重写(占位 → 250 行真实施)
  - SkillLoader.load_all + load_full + skills_for_loop + loop_system_prompt + estimated_tokens
  - frontmatter parser:PyYAML 优先 / 降级支持 list / multiline / nested dict / 各类型
  - Progressive Disclosure(LOOP_TO_SKILLS):scout/notify/L1=[];L2=[S08];L3=[S01,S02,S03,S08];reflect=[S07];chat=[S04,S05,S08]
  - ALWAYS_LOADED(S01/S02/S03/S07/S08)预加载;LAZY(S04/S05)按需读
  - 7 个完整 SKILL.md(Anthropic Skill 格式 + frontmatter + system prompt + tools_required + failure_fallback)
  - **27 单元测试全过**;服务器实测 7 skill 加载 OK(thesis_l3 ~679 tokens / reflect ~172 tokens)
- ✅ **W3 D5+ Eval Phase 4 起步**(commit `76f0e4c`):L1 Tool runner + 6 Tool 66 case 100% pass
  - 新建 agent/eval/runner.py(280 行)+ agent/eval/golden/l1_tool/{6 JSON}
  - GoldenCase / EvalReport;_validate_metadata / _run_one_case / _check_idempotent
  - CLI:`python -m agent.eval.runner --suite=l1_tool [--tool=...]`
  - 6 核心 Tool fixture:calc_risk_metrics(11)/ calc_position_size(13)/ calc_technical_indicators(11)/ approve_rule(10)/ list_strategies(11)/ run_backtest(10)= **66 case 100% pass + metadata 全 ✓**
  - **27 runner 自身测试全过**;剩余 7 Tool fixture + L2/L3/L4 留 W7-W12
- ✅ **W3 D5+ L1 Tool 收尾 + L2 Skill 框架**(commit `ae2e9e3`):Phase 4 L1 100% + L2 骨架
  - 7 个剩余 L1 Tool fixture:recall_memory(11)/ update_strategy_status(11)/ run_paper_trade(10)/ create_approval_request(10)/ get_paper_performance(10)/ save_strategy(11)/ send_push_notification(11)= **74 case + 修 sell_with_trade_id 案例**
  - **L1 Tool 全套 13/13 tools / 140 case / 100% pass**
  - 新建 agent/eval/skill_runner.py(280 行)+ 7 个 l2_skill JSON(S01/S02/S03/S04/S05/S07/S08 共 44 case)
  - 4 outcome 类型:metadata_ok / loaded_full_content / tools_required_known / expect_fields(scalar + list subset)
  - **L2 Skill 全套 7/7 / 44 case / 100% pass**(只验静态契约,LLM cassette 留 W7-W12)
  - **26 skill_runner 自身测试全过**;pytest 全量 855/857 PASSED(2 pre-existing failures)
- 🆕 用户新规则：**长 session 每 10 分钟更新记忆三件套**（已写入 rules.md）
- 📦 数据库决策：8 张新表迁本地 PG（agent_trading_local PG 14）+ 040 留 Supabase
- 🐛 新踩坑：macOS sort 是 locale-aware，跨机器 SHA1 对比必须 `LC_ALL=C`（已记 pitfalls）

---

## 2026-04-30 本次会话
- ✅ 记忆恢复 + 服务器健康检查（43.156.207.26 新加坡运行正常，实例 lhins-ph7ak7k9 / Ubuntu-GFLK）
- ✅ 跨机器代码 SHA1 对比：服务器 vs 本地 387 个 tracked 文件**完全一致**（除 Podfile.lock 1 个本地未提交差异）
- ✅ 全量代码深读（5 Explore agent 并行）：后端 107 .py + Flutter 84 .dart + Portal/Admin → 9 大节代码地图
- ✅ **澄清**：`docs/agent-pm/00-16` 17 篇是 Agent v1 PM 设计产出物，**从未实施**，不要当 baseline
- ✅ **17-tech-plan.md 产出 + 落地**：v1 技术方案，4 Phase 16-20 周，完整 v1 范围（paper+notify+auto+真金+托管），配置 A Eval（1660 golden）。落到 `docs/agent-pm/17-tech-plan.md`，README 矩阵新增 L6 工程落地区。**只设计不写代码**
- 🐛 线上 3 个非致命错误（未修）：`token_trades_pkey` duplicate / `btc_eth_indicators` 整数列写小数 / `daily_picks ↔ pump_tokens` FK 缺失
- 📚 记忆更新：新建 `project_agent_pm_docs_status.md`、追加 `pitfalls.md` 3 条、追加 `sessions-log.md` 1 条、更新 `CLAUDE.md` 功能状态表

---

## 2026-03-17 本次会话
- ✅ 聪明钱追踪升级：SOL Helius WS ~400ms + EVM OKX Web3 API 5s轮询（commit c8fcad7）
- ✅ 修复：OKX base URL / smart_money_txns 去重 / OKX toplist 429
- ✅ 记忆文件重构：MEMORY.md 精简为索引，细节拆分到 topic 文件
- ✅ pump采集三阶段架构（commit bac2a06）：WS全量捕获→交易追踪(20k)→按需enrich(Sem20)
- ✅ Portal 部署到服务器：systemd portal.service + nginx 反代分流
- ✅ 实时信号池（commit 2c2e227）：替代每日推荐，score>=55 且 BC 3-35% 动态进出
- ✅ Flutter PicksScreen 重写：30s 轮询 /api/pump/signals，实时显示
- ✅ nginx 新增 /api/pump/ 路由
- ✅ AI Optimizer Agent（commit 04a68dd）：Claude Opus 4.6 自动分析+回测+提案
- ✅ Portal 从 Vercel 迁移到服务器：apps/portal build + systemd 更新
- ✅ **i18n 国际化**（commit fc4740a + 1158d63）：
  - 4语言支持：zh/en/ja/ko，默认跟随系统语言
  - 275+ 本地化字符串，覆盖 35+ 文件
  - LocaleProvider + SharedPreferences 持久化
  - Profile 语言切换器（跟随系统 + 4种语言）
  - 严格 QA 测试 → 发现并修复 80+ 遗漏问题
  - Model 层 i18n：返回 raw key → UI 层 S.of(context) 解析
- 📝 聪明钱暂时不好用（地址太少），用户后续单独优化
- ✅ **App Store 上传**（Build 2 已上传成功）：
  - 手动签名：Apple Distribution 证书 + AiTrading_AppStore provisioning profile
  - App 名称：AiTrading Pro（"AI Trading" 被占用）
  - ATS 修复：Info.plist NSAllowsArbitraryLoads=true（解决 Agent 页 Network error）
- ✅ **App Icon 替换**：从 Flutter 默认 logo 替换为之前设计的 AI 大脑+K线图 icon
- ✅ **Build 3 上传 + App Store 已提交审核**
- ✅ **热币实时管理器**（commit 9f5d6fe）：
  - HotCoinManager: PriceFeed 毫秒级回调 → 实时打分 → 进出榜单
  - GeckoTerminal 发现层：trending+new_pools，4链 ~542 候选
  - 退出机制：涨完/萎缩/卖压/消退 5 条规则
  - 双源发现：OKX toplist + GeckoTerminal 去重合并
  - 表现追踪口径修正：发现瞬间价格 + D0~D30 每日最高涨幅
  - 退出原因+价格写入 DB，漏斗统计（hot_funnel_stats 表）
  - Portal 修复：daily_highs key 映射 + D0 列 + hot_live source 支持
- ✅ **Hot Coin Optimizer Agent**（commit b775038）：
  - Claude Opus 4.6 自动分析热币表现 → 优化打分权重/阈值 → 回测验证 → Portal 审批
  - 当前数据：D1 正收益 37.7%，50%命中率 20.5%，平均最佳 38.8%
- ✅ **监控口径修正**（commit bdec08d）：
  - 热币追踪 7 天窗口（pump 保持 30 天）
  - D3≥20% 作为热币命中指标 + 入榜后 1h 涨幅追踪
  - 退出后继续追踪 3 天评估时机
- 🔄 **聪明钱地址供给系统**（进行中）：
  - 三层供给：自有数据挖掘(miner) + 热币 Top Holders + Dune(后续)
  - smart_wallet_miner.py 新建：毕业代币早期买家挖掘
  - fetch_top_holders()：入榜时采集 Top 10 持仓地址
  - _evaluate_top_holders()：D3涨20%+ 的 holder 自动晋升聪明钱
  - ✅ 交易金额 $0 修复（SOL nativeTransfers, EVM OKX amount）
  - ✅ migration 022 已执行，commit 988b51a 已部署
  - ✅ 第 3 层 Dune Analytics（commit e28c4cc）：Query 6850812，首次导入 493 个地址
  - smart_wallets 总数：60 → 1506（miner +12, Dune +493, 原有 ~1000）
  - ✅ v3 五维度评估体系（commit 16a4102）：
    - 胜率/PNL/交易规模/活跃度/时效性，总分100
    - elite≥75 verified≥55 watching≥35 blacklisted<30
    - 实时bot检测 + 2h评估周期 + 14天降级/28天移除
  - ✅ Dune 4链查询全部创建：SOL(6850812) ETH(6858638) BSC(6858633) Base(6858622)
  - SOL LIMIT 已改 5000，4链共 17,307 个候选
  - 首次4链导入：smart_wallets 总数 1506 → 2135+（还在继续导入中）
- ✅ **Agent 事件驱动升级**（commit ce12609）：
  - event_listener.py：EventBus 订阅，毫秒级策略评估（替代 30s 轮询）
  - performance_analytics.py：胜率/PNL/最大回撤/夏普率
  - backtester.py：策略回测引擎（7 天历史数据）
  - risk_manager.py：+2 风控检查（BTC 大盘 + 同链集中度），总计 15 项
  - 4 个新 API：performance/portfolio/daily-pnl/backtest
- ✅ **代币详情页增强**（commit c154732）：
  - Top Holders 卡片：Top 10 持仓排名，地址+占比+进度条，一键复制
  - 资金流向卡片：24h 净流入/流出，买卖力量条，大额交易统计
  - 交易分布图表：30min 聚合柱状图，买卖对比
  - 新 API：/api/token/{chain}/{address}/top-holders
- ✅ **BTC/ETH 智能投资 Agent**（commit 3d8aa82 + 35421d8）：
  - 13 个免费数据采集器（93-95% 覆盖率）：Binance WS/REST + OKX + CryptoPanic + DeFiLlama + Blockchain.com + TwelveData + LunarCrush + Coinalyze + Mempool + Alternative.me + Dune
  - 50 项指标引擎 + 5 项复合评分（momentum/sentiment/onchain/macro/risk）
  - 技术指标本地计算：RSI/MACD/布林带/ATR/MA/支撑阻力
  - AI 分析层：CycleAnalyzer(7阶段周期) + SignalGenerator(两阶段) + ReportGenerator + AlertGenerator
  - 模拟盘引擎：自动执行+止盈止损+绩效计算
  - API: /api/btc-eth/* (health/indicators/dashboard/signals/alerts/reports)
  - DB: migration 025（6张表）
  - ⚠️ Blockchain.com WS 暂禁（消息量阻塞事件循环）→ 改用 REST
  - ✅ DB migration 025 已执行（6 张表）
  - ✅ API 正常：/api/btc-eth/health + dashboard + signals + alerts
  - ✅ DB migration 025 已执行（6 张表）
  - ✅ API 正常：/api/btc-eth/health + dashboard + signals + alerts
  - 📝 Phase 5 Flutter UI 待做
- ✅ **PRD 需求文档体系**（docs/agent-trading/prd/）：
  - PRD-001 Agent 卖出执行：17/17 测试通过，已上线
  - PRD-002 风控 Bug 修复：11/11 测试通过，已上线
  - PRD-003 胜率定义统一：20/20 测试通过，已上线
  - PRD-004 中等问题合集：16/16 测试通过，已上线
  - **总计 64 个测试全部通过**
- ✅ **Agent 优化全景规划**：
  - 6 Phase 29 模块（交易Agent 18 + 优化Agent 11）
  - 深度调研：TradingAgents/FinMem/CryptoTrade/Walbi + 用户痛点 + DEX 对比
  - PRD-005 v1.1：记忆+反思系统（17项审查修订），TECH-005 + TEST-005 完成
  - Claude API 总月费预估：~$48/月（含记忆注入$5）
  - ✅ **PRD-005 Phase 1 已开发上线**：29/29 测试通过，7新文件+8修改=2424行
  - ✅ PRD-006 Phase 2 文档完成（PRD+TECH+TEST），待开发
  - ✅ PRD-007 Phase 3 文档完成，待开发
  - migration 028 已执行（agent_memory + agent_risk_events 表）
  - ✅ **PRD-006 Phase 2 已开发上线**：42/44 测试通过，1875 行，regime_detector+动态风控
  - PRD-008/009/010 Phase 4-6 文档已输出+审查修订（16项）
  - migration 029 已执行（agent_regime_history 表）
  - ✅ **Phase 3-6 全部开发完成**：
    - Phase 3 PRD-007 多角色 Agent：2474 行，31/36 测试通过
    - Phase 4 PRD-008 模拟盘+模板：2111 行，35/35 测试通过
    - Phase 5 PRD-009 多 DEX 路由：1911 行，21/22 测试通过
    - Phase 6 PRD-010 优化 Agent 升级：1843 行，33/39 测试通过
    - 总计新增 ~9000 行代码，120/132 测试通过（91%）
  - migration 030/031/032/033 已执行（debates/paper_trades/ab_tests/hot_sim_trades 表）
- ✅ **Supabase 优化**：
  - db_cleanup.py 每 6h 清理
  - token_trades 只存信号池+毕业代币（减少 95%）
  - 月增长从 ~120MB 降至 ~30MB，免费版可用 2 年+
- ✅ **全信号源策略监控**：
  - hot_sim_trader.py: 4 信号源（热币/聪明钱/内盘/BTC-ETH）
  - BTC $50 + ETH $20 + 其他 $10，止盈止损 15%
  - repeat + unique 两种模式（BTC/ETH 只有 repeat）
  - 毫秒级价格检查（DEX swap 事件驱动）
  - Flutter 策略监控看板：5 Tab + 弱化入口
- ✅ **数据 Tab**：全链盈亏分布 + 交易成本 + 时段/生命周期/金额分布
- ✅ **BTC/ETH 白色主题适配**：所有暗色→iOS 系统色
- ✅ **Agent 流式打字机**：SSE 推送 + 光标闪烁
- ✅ **Agent 多轮工具调用**：create_strategy + list_strategies + run_backtest
- ✅ **Supabase 优化**：
  - db_cleanup.py 每 6h 清理
  - token_trades 95% 缩减（只存信号池+毕业代币）
  - hot_coins 节流 15s
  - 预计可用 2 年+
