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
