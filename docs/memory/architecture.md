# 系统架构

## 项目结构
```
Agent-Trading/
├── services/pump-scanner/   ← Python 后端（FastAPI）
├── apps/app/                ← Flutter App
├── apps/portal/             ← Next.js 监控 Portal（服务器部署，Vercel弃用）
└── supabase/migrations/     ← 18个 Migration
```
> ⚠️ `apps/web/` 已于 2026-03-17 删除（commit ce34576），被 `apps/portal` 替代

## 本地路径
- 后端: `/Users/wenruiwei/Desktop/Agent-Trading/services/pump-scanner/`
- Flutter: `/Users/wenruiwei/Desktop/Agent-Trading/apps/app/`
- Portal: `/Users/wenruiwei/Desktop/Agent-Trading/apps/portal/`

## 数据流

### 热币发现（外盘）— v2 实时管理器架构
- **发现** (10min): OKX toplist + GeckoTerminal trending/new_pools → 去重合并
  - OKX: 4时间帧(5m/1h/4h/24h) × 2排序 = 8次/链，每链 ~100 候选
  - GeckoTerminal: trending(5页) + new_pools(5页)，每链 ~200 候选
  - 合并去重后每链 ~300 独立候选
- **实时打分** (毫秒级): PriceFeed 回调 → HotCoinManager.on_price_update → 重新打分
- **刷新** (30s): DexScreener 批量 → Manager.on_full_refresh（多时间帧+退出判定）
- **进出榜单**: HotCoinManager 管理
  - 入榜: score ≥ 50 且无 goplus_risk
  - 退出: 低分3次 / 冲高回落 / 成交量枯竭 / 卖压碾压 / 发现源未命中5次
  - DB 节流: 同一代币最多 5s 写一次
- **安全**: GoPlus（蜜罐/税率/Top10集中度）
- **SOL持仓**: Helius RPC（精确Holder占比）
- **打分**: M+Q+P 三维，动量新鲜度（1h涨速 vs 24h均速）

### 聪明钱追踪
- **SOL**: DEX 程序级监控（logsSubscribe 5 个 DEX：Raydium/Jupiter/Pump.fun/CLMM/Orca）
  - 每笔 swap 用 HashSet(5222地址) O(1) 匹配，23ns/lookup，毫秒级
- **ETH/BSC/Base**: DEX Swap 事件监控（eth_subscribe logs，UniswapV2/V3 Swap topic）
  - 3 链并发 WS（publicnode.com 免费端点），HashSet(10540地址) 匹配，毫秒级
- **补充**: OKX 轮询 Group A (elite/verified) 每2min + Group B (watching) 每15min
- **分页加载**: smart_wallets 全量分页（Supabase 默认 limit 1000 → 分页获取 15,710）
- 种子钱包：`data/smart_wallets_expanded.json`（60个初始）
- **三层供给体系**（目标 2000+ 地址，当前 1506）：
  1. **自有数据挖掘**（每天 UTC 04:00）：smart_wallet_miner.py，从 token_trades 找毕业代币早期买家
  2. **热币 Top Holders**（实时）：入榜时 Helius/GoPlus 采集 Top 10 → hot_coin_top_holders 表 → D3涨20%+ 自动晋升
  3. **Dune Analytics**（每周一 UTC 05:00）：4链 DEX 高频交易者，过滤bot，LIMIT 5000
- **v3 五维度评估**（每 2h，smart_wallet_updater.py）：
  - 胜率(20) + PNL(20) + 交易规模(20) + 活跃度(20) + 时效性(20) = 总分100
  - elite≥75 / verified≥55 / watching≥35 / blacklisted<30
  - 14天无交易降级，28天移除
  - 实时bot检测：60秒买卖同代币→立即黑名单（不等2h）
- 分层: Elite(≥65%+≥10笔) / Verified(≥50%+≥5笔) / Watching(≥40%+≥3笔)
- 信号 → `smart_money_signals` 表；交易 → `smart_money_txns` 表（7天清理）

### OKX Web3 API（EVM 聪明钱）
- 端点: `GET https://web3.okx.com/api/v5/wallet/post-transaction/transactions-by-address`
- 参数: `chains=`（List，**不是** chainIndex=），需 `User-Agent: Mozilla/5.0`
- chainIndex: ETH=1 / BSC=56 / Base=8453
- 响应: `data[].transactionList[]`

### pump.fun 内盘（三阶段架构 + 实时信号池）
- **阶段1**: WS create → 零延迟直接写DB（pump_tokens），不丢弃任何币，目标3-5万/天
- **阶段2**: WS trade → 内存追踪活跃交易（MAX_TRADE_TRACKED=20,000），累积买家/进度
- **阶段3**: 初筛通过（buyers>=3 且 bc>=2%）→ Semaphore(20)并发拉REST详情
- **实时信号池**: score>=55 且 BC 3-35% 自动进入 `_signal_pool`，涨过(BC>35%)/死了(30min无交易)/超时(3h) 自动移出
- API: `GET /api/pump/signals`（APP 30s 轮询），`GET /api/pump/stats`（采集统计）
- 旧 daily_job 保留做历史记录，APP 新币 Tab 完全切换到实时 API

### Agent 交易（事件驱动架构）
- **LLM**: Claude Sonnet 4 解析自然语言 → StrategySpec JSON
- **执行**: 事件驱动（毫秒级）+ 30s fallback
  - event_listener.py 订阅 EventBus（hot_coin_update / pump_snapshot / kol_signal）
  - 去重 TTL 5s + 策略内存缓存 30s
  - monitor_job.py 30s 轮询保留为 fallback
- **风控**: 15 项检查（circuit_breaker/velocity/loss/position/blacklist/liquidity/tax/holders/honeypot/market_regime/chain_concentration...）
- **表现分析**: performance_analytics.py（胜率/PNL/夏普率/最大回撤）
- **回测**: backtester.py（7 天历史数据验证策略）
- **交易链路**: quote → swap → sign → broadcast → record（OKX DEX）
- **API**: /api/agent/chat|strategies|executions|alerts|performance|portfolio|daily-pnl|backtest

## Flutter App 架构
- **4-Tab**: 行情(MarketScreen) / Agent / 历史 / 我的
- **行情3-Tab**: 热币 / 聪明钱 / 新币（各带链过滤器）
- **K线**: WebView + klinecharts v9（7指标 + 5时间框架）
- **钱包**: flutter_secure_storage + 助记词派生多链(SOL/ETH/BSC/Base) + 私钥单链
- **聪明钱**: 卡片4行 + FlowBar + 买卖详情弹窗（DraggableScrollableSheet）
- **模拟器**: iPhone 17 Pro Max (DBC925B5-7657-4410-B770-F21E4605A9D6)

## 启动命令
```bash
# Flutter 模拟器
cd /Users/wenruiwei/Desktop/Agent-Trading/apps/app
flutter run -d DBC925B5-7657-4410-B770-F21E4605A9D6 \
  --dart-define=API_BASE_URL=http://43.156.207.26 \
  --dart-define=HELIUS_API_KEY=a194f0cb-e6f5-474d-a9fc-d13b6e916964
```

### AI Optimizer Agent（每3天自动优化推荐算法）
- **调度**: APScheduler CronTrigger `day="*/3", hour=3, minute=0, timezone="UTC"`
- **Governor** (governor.py): 检查指标→有pending提案则跳过→不达标启动Agent→回滚保护
- **pump/hot 交替调度**: day_of_year 奇偶决定跑 pump 还是 hot
- **Pump Agent** (optimizer_agent.py): Claude Opus 4.6 tool_use 循环（最多20轮）
  - 6个工具: read_metrics / read_scorer_code / read_config / query_tokens / backtest / propose_change
  - API Key: OPTIMIZER_API_KEY（.env）
  - 量化目标: hit_rate>=20%, recall>=15%, F1>=0.17
- **Hot Agent** (optimizer_agent.py → run_hot_optimization):
  - 5个工具: read_hot_metrics / read_hot_scorer_code / read_hot_config / backtest_hot / propose_hot_change
  - API Key: HOT_OPTIMIZER_API_KEY（.env）
  - 量化目标: D1正收益>=70%, D3>=20%比例>=40%, D0负收益<20%, 平均最佳>=30%
  - 当前基线: D1=37.7%, 50%命中=20.5%, 平均最佳=38.8%
- **Backtest**: pump用token_snapshots，hot用token_performance(hot_live)
- **审批**: 提案写入DB(pending) → Portal /tuning 页面审批
- **API**: `/api/optimizer/runs|proposals|metrics|trigger?mode=hot|pump|auto`
- **监控口径**: 热币追踪7天窗口，D3>=20%为主命中指标，入榜后1h涨幅，退出后3天对照追踪

## Supabase 表（主要）
- `hot_coins` / `hot_daily_picks` / `pump_daily_report`
- `smart_money_signals` / `smart_money_txns` / `smart_wallets`
  - `smart_wallets` 列名是 `wallet`（非 `address`），无 `chain` 列
- `strategies` / `strategy_executions`
- `user_api_quota`（Migration 017）
- `optimization_runs` / `optimization_proposals` / `optimization_metrics_history`（Migration 020）
- 共 25 个 Migration

### 数据库清理策略（db_cleanup.py，每 6h）
- Supabase 免费版 500MB 上限，月增长需控制在 ~150MB 以内
- `token_trades`: 保留 3 天（最大表，每天 ~20 万行，分批删除避免超时）
- `token_snapshots`: 保留 14 天
- `btc_eth_indicators`: 保留 7 天
- `pump_tokens + 依赖`: 30 天未毕业的连同 outcomes/snapshots/trades 一起删
- `kol_tweets / hot_funnel_stats / btc_eth_alerts`: 保留 30 天
- `token_performance`: 保留 90 天（已完成追踪的）
- `hot_coins DB_THROTTLE_INTERVAL`: 15s（从 5s 优化，减少 66% 写入）

### BTC/ETH 智能投资 Agent（btc_eth/ 独立模块）
- **数据采集**（13 个 collector，全部免费）：
  - 实时: Binance WS (BTC/ETH kline+ticker, 1连接6stream)
  - 5min: Binance REST (大户多空/散户多空/OI/爆仓) + OKX REST (费率/多空/OI)
  - 30min: CryptoPanic(新闻情绪) + Coinalyze(聚合OI) + Mempool(BTC拥堵)
  - 4h: DeFiLlama(ETF/稳定币/TVL) + Blockchain.com(哈希率/矿工/活跃地址) + TwelveData(DXY/标普/黄金) + LunarCrush(社交) + Alternative.me(恐慌指数)
  - Daily: Dune(交易所净流入/SOPR)
  - ⚠️ Blockchain.com WS 暂禁（unconfirmed_sub 每秒数百条消息阻塞事件循环）
- **指标引擎**: IndicatorEngine 50 项指标 + 5 项复合评分 + K线 ring buffer(200)
- **AI 分析**: CycleAnalyzer(7阶段周期,规则+Claude) + SignalGenerator(规则预筛+Claude确认) + ReportGenerator(每日) + AlertGenerator(事件驱动)
- **模拟盘**: PaperTradingEngine 自动执行信号 + 止盈止损 + 绩效(胜率/夏普/回撤)
- **API**: /api/btc-eth/* (health/indicators/dashboard/signals/alerts/reports/portfolio)
- **DB**: btc_eth_indicators / btc_eth_reports / btc_eth_signals / btc_eth_alerts / btc_eth_portfolios / btc_eth_paper_trades
- **Claude**: BTCETH_CLAUDE_API_KEY（fallback 到 ANTHROPIC_API_KEY），Sonnet，~$23/月

## 服务器部署架构
- 项目路径: `/opt/agent-trading/`
- 端口: 8000=FastAPI后端, 3000=Portal(Next.js), 80=nginx入口
- systemd 服务: `pump-scanner.service`（后端）, `portal.service`（Portal）, `tat_agent.service`
- nginx 分流（`/etc/nginx/sites-enabled/pump-scanner`）:
  - `/api/agent/*`、`/api/price/*`、`/api/device/*`、`/api/smart-money/*`、`/api/pump/*`、`/api/optimizer/*`、`/health`、`/docs` → :8000
  - 其余所有（`/pump`、`/market`、Portal API routes）→ :3000
- 注册表: `/opt/projects/README.md`
