# Project Memory — Agent-Trading

## 项目方向
**双轨策略：pump.fun 内盘 + 多链外盘代币发现系统**
- 内盘：pump.fun 早期代币（BC 3-35%），每日推送 ≤10 个
- 外盘：多链热币榜（SOL/BSC/Base/ETH），每2小时扫描更新
- 算法：规则打分冷启动 → XGBoost ML（2周后）
- 信号通过 **Flutter App** 推送给用户

## 开发仓库
- **GitHub**: https://github.com/meiyaobuyao123-hash/Agent-Trading
- **本地路径**: /Users/wenruiwei/Desktop/Agent-Trading
- **pump-scanner**: `/Users/wenruiwei/Desktop/Agent-Trading/services/pump-scanner/`
- **Flutter App**: `/Users/wenruiwei/Desktop/Agent-Trading/apps/app/`

## API 凭证（已验证可用）
- Supabase URL: `https://qmzsruqgwaqusywprxlj.supabase.co`
- Supabase Service Key: `[见本地 .env 文件]`
- OKX DEX v6 Key: `[见本地 .env 文件]

## 已完成功能
- pump.fun 实时采集（WS双通道）+ 70+维度特征工程 + 规则打分
- 多链热币扫描（SOL/BSC/Base/ETH）+ M+Q+P 评分
- **多链聪明钱追踪**（SOL/ETH/BSC/Base，55个种子钱包，15分钟扫描）+ 交易级记录
- 聪明钱分层（elite/verified/watching + Bot黑名单）+ 买卖详情弹窗
- KOL 舆情采集（212 KOL + twitterapi.io + 情感分析 + 共振信号）
- Agent 框架（Claude LLM → 策略DSL → 规则引擎 → 事件总线 → 告警 + **风控系统**）
- **OKX DEX 真实交易**（quote→swap→sign→broadcast→record，SOL+EVM 签名）
- **钱包管理**（助记词/私钥导入 + flutter_secure_storage加密 + Agent策略钱包选择）
- 回测引擎（Monte-Carlo 模拟）
- Flutter App（行情3-Tab + Agent聊天+策略 + 历史 + 我的 + 详情页K线 + 策略P&L）
- Next.js Web + Admin 后台
- Supabase 17个 Migration（含 user_api_quota）
- **合规加固**（全局免责声明Gate + 中国大陆IP屏蔽中间件 + Agent/钱包合规弹窗 + 实时推送限流）

## 2026-03-11 修复
- ✅ outcome_labeler 口径修复、daily_highs ISO时间戳、K线折线图模式
- ✅ 详情页 Holder RPC 优先、initState bug、ETH 链全链路支持
- ✅ 聪明钱种子库导入、Agent DB Migration 008、Flutter AgentScreen 重写
- ✅ OKX 数据源集成（okx_market_client + 分层更新策略 + Flutter 全链路）

## 2026-03-12 六次会话
详见 [sessions-2026-03-12.md](./sessions-2026-03-12.md)
- 性能优化（刷新30s/发现10min/秒级追踪）+ DexScreener fallback
- 多链聪明钱 + 钱包管理 + 风控系统
- 策略全链路修复 + OKX DEX 真实交易
- 聪明钱升级（交易级追踪 + 买卖详情弹窗 + 卡片重设计）
- 策略交易记录 + P&L 展示

## 2026-03-13 全量测试 + 修复
详见 [testing-2026-03-13.md](./testing-2026-03-13.md)
- **测试范围**：全部功能模块（主流程 + 边界 + UX），120+ 问题发现
- **修复数量**：~27 项（CRITICAL 2 + HIGH 3 + MEDIUM 4 + 其余前端/后端）
- **CRITICAL 修复**：EVM nonce 动态获取 + to_amount 动态精度
- **HIGH 修复**：Claude API async化 + mark_alert_read 鉴权 + 多链价格追踪
- **MEDIUM 修复**：EVM volume USD转换 + Tab KeepAlive + TOCTOU 竞争 + SELECT 字段
- **验证**：Python 6文件 py_compile 通过、Dart 0 errors、模拟器运行 0 错误

## 2026-03-16 合规加固 + 云端部署 + 多链钱包优化
**合规（commit ba85605）：**
- ✅ Flutter DisclaimerPage：首次启动全屏使用须知（双语，滑到底+勾选才能进入）
- ✅ app.dart `_DisclaimerGate` 门禁层：未接受前阻止进入 MainShell
- ✅ Backend GeoBlockMiddleware：中国大陆 IP → HTTP 451，ip-api.com + 24h缓存
- ✅ 合规分析：属人/属地管辖不构成刑事风险；非托管+数据工具+非中国大陆上架=合规
- ✅ App Store 上架策略：全球上架，仅排除中国大陆；美/英/加/澳/日/韩/EU/新/UAE均安全

**云端部署：**
- ✅ 腾讯云轻量服务器：IP `43.156.207.26`，Ubuntu 2核4GB 60GB，到期2026-05-16
- ✅ pump-scanner 部署到云端，systemd 托管（开机自启 + 崩溃自动重启）
- ✅ Nginx 反向代理 80→8000，用户请求直达服务器，本地 Mac 不再参与
- ✅ App icon SVG 生成：`apps/app/icon.svg` + `apps/app/icon_preview.html`（1024x1024，暗色系电路板A字）
- ✅ 多链钱包优化（commit 956dd8d）：助记词一键派生 SOL/ETH/BSC/Base 四链，勾选框UI默认全选，显示BIP44路径；私钥模式保持单链选择
- ✅ 云服务器多项目管理：`/opt/projects/` 目录结构 + 端口注册表 + 命名规范

## 2026-03-14 第二轮 QA 自动审查 + 修复（commit ca6e9ce + 6df6add）
**Portal（Next.js）自动审查 21 个 bug，修复内容：**
- CRITICAL: migration 016 添加 `image_url` 列 + RLS 策略（hot_coins/hot_daily_picks/pump_daily_report）
- HIGH: Portal 刷新间隔 60s（原10s过频）、report_json null guard
- MEDIUM: ChainBadge CSS 变量拼接 → rgba 显式颜色、fetchSummaryStats 加 limit
- Portal picks/page: `|| null` → `?? null` 修复 0% 涨跌幅被误为 null
- Portal queries.ts: 零值市值/成交量 `|| null` → `!= null` 检测
- Portal utils.ts: `fmtUsd(0)` 返回 `'$0'` 而非 `'-'`，增加 NaN 防护

**Flutter App 自动审查 23 个 bug，修复内容：**
- CRITICAL: smart_money_detail_sheet context-after-pop 崩溃 → pop 前预构建 detail，用 nav 推送
- CRITICAL: token_detail_page substring 越界 → length >= 10 才截取
- HIGH: token_detail_service Future.wait 下标脆弱 → 具名 Future 并行（5个独立 Future）
- HIGH: helius_service API key 硬编码 → `--dart-define HELIUS_API_KEY` 注入
- MEDIUM: hot_screen 补全 ETH 链过滤选项（index 4 原先缺失）
- 已知未修复: 钱包私钥明文存 SharedPreferences（需 flutter_secure_storage）、地址派生非加密

## KOL 舆情系统状态
- 212 KOL（Mega 18 + Large 60 + Medium 72 + Small 62）
- 全链路：采集(twitterapi.io) → 情感分析 → 共振信号(24h) → K维度评分
- **待完善**：`_evaluate_accuracy()` 价格查询 TODO

## 调研结论（2026-03-11）
详见 [audit-findings.md](./audit-findings.md)

## 2026-03-13 第二次会话（5项待开发清理）
- ✅ Supabase RPC `increment_trigger_count` 已创建并执行
- ✅ 代码去重：提取 5 个公共模块（chain_utils/format_utils/token_avatar/rank_medal/chain_badge），删除 ~435 行重复
- ✅ API base URL 配置化：`lib/config/app_config.dart` + `--dart-define` 注入，消除 localhost 硬编码
- ✅ 推送通知接入：后端 push_service + routes_device + Flutter FCM 全链路（待用户创建 Firebase 项目）
- ✅ XGBoost ML 管线：ml_trainer/ml_scorer/ml_config 已就绪，默认关闭，**3/27 定时提醒训练**

## 2026-03-15 实时推送 + 合规 + 限流（commit 1e0eff0）

**后端：**
- `push_service.py`（新建）：广播推送封装，用户每小时10条/系统每日30条双层限流
- `collector.py`：事件驱动推送 — 高分新币(≥70)/BC里程碑(30%&60%)/聪明钱入场(≥1 SOL)/毕业，内存 set 防重复
- `routes_agent.py`：`user_api_quota` 限流，免费用户每月20次，超额返回429
- `migrations/017_user_api_quota.sql`（新建）：配额表 + RLS，需 Supabase Dashboard 手动执行

**Flutter App：**
- `wallet_service.dart`：私钥/助记词改用 `flutter_secure_storage`（iOS Keychain / Android EncryptedSharedPreferences）
- `wallet_import_sheet.dart`：非托管声明弹窗，首次导入显示，5条声明条目
- `agent_screen.dart`：Agent首次使用合规弹窗 + 策略启用风险二次确认

## 服务器信息
- **IP**: 43.156.207.26（腾讯云轻量，新加坡节点）
- **OS**: Ubuntu 22.04，用户 ubuntu
- **服务**: pump-scanner → systemd `pump-scanner.service`，端口8000
- **Nginx**: 80 → 8000 反向代理，已配置
- **部署路径**: `/opt/agent-trading/`（代码）+ `/opt/venv/`（Python venv）
- **多项目管理**: `/opt/projects/README.md` 端口注册表，新项目用 8001/8002/8003

## 服务器多项目规范
```
/opt/projects/
├── README.md        ← 端口/项目注册表（必须更新）
├── agent-trading/
│   ├── repo/ → /opt/agent-trading
│   └── venv/ → /opt/venv
└── _shared/
```
端口分配：8000=agent-trading，8001/8002/8003预留给新项目
systemd 命名：`<project>-<service>.service`

## 待执行（需手动）
- [ ] Supabase Dashboard 执行 `migrations/017_user_api_quota.sql`（如未执行）

## 待开发（按优先级）
- [ ] KOL 准确率评估补全价格查询（_evaluate_accuracy 中 TODO）
- [ ] Firebase 项目创建 + 配置文件下载（google-services.json / GoogleService-Info.plist）
- [ ] 代码重复：token_detail_page.dart 的 _fmtNum/_fmtWan 保留了中文本地化版本，可选统一

## Flutter App 架构
- **4-Tab**: 行情(MarketScreen) / Agent / 历史 / 我的
- **行情3-Tab**: 热币 / 聪明钱 / 新币（各带链过滤器）
- **K线**: WebView + klinecharts v9（7指标 + 5时间框架 + 折线/烛线切换）
- **实时价格**: PriceTickerService（多链支持，DexScreener 数据源）
- **详情页**: 3-Tab（行情/数据/详情）+ 安全检测(GoPlus) + RPC精确Holder
- **钱包管理**: flutter_secure_storage + 助记词一键派生多链(SOL/ETH/BSC/Base) + 私钥单链导入 + Agent策略钱包选择
- **聪明钱**: 卡片4行布局 + FlowBar + 买卖详情弹窗（DraggableScrollableSheet）
- **Agent**: 聊天+策略列表 + 策略详情P&L弹窗 + 交易参数设置

## 2026-03-13 OKX 全链路替换 + 多时间帧打分
- **发现**：GeckoTerminal → **OKX toplist 多时间帧**
  - 4个时间帧(5m/1h/4h/24h) × 2排序(成交量+涨幅) = 8次/链
  - 每代币获得完整 volume/change/txsBuy/txsSell 各时间帧数据
  - 4链候选 ~260个/链，图标100%覆盖
- **打分v2**：M+Q+P 全50分动量维度激活
  - M1(价格1h) + M3(成交量加速) + M4(买压比) + M5(动量新鲜度) 全部有数据
  - **动量新鲜度**：`1h涨速 vs 24h均速`，奖励刚启动的币，惩罚已涨完的
  - **多时间帧共振**：出现在4个toplist时间帧=强势信号（P3=6分）
  - 效果：TRUMP 被降权(已涨完)，KMNO 被发现(正在加速)
- **刷新30s**：DexScreener批量（返回5m/1h/6h/24h完整多时间帧数据）
- **发现10min**：OKX多时间帧toplist（8次/链，~16s/链）
- **OKX 429限速**：调用间隔2s避免429

## 热币链覆盖
- 4链：SOL/BSC/Base/ETH
- 数据源分层：
  - **发现**: OKX toplist 多时间帧（`get_toplist_multi_timeframe`）
  - **30s刷新**: DexScreener批量（`_batch_dexscreener_prices`，返回多时间帧/按地址）
  - **安全**: GoPlus（蜜罐/税率/Top10集中度）
  - **SOL持仓**: Helius RPC（Top1精确占比）
  - **社交**: DexScreener（Twitter/Telegram/Website）
- 调度：增量发现10min + 市场刷新30s + 表现追踪1s协程
- OKX price-info/basic-info 需白名单（code:-1），toplist/search/candles 可用

## 聪明钱系统
- 4链追踪：SOL(Helius) + ETH/BSC/Base(Etherscan)
- 55个种子钱包，`data/smart_wallets_expanded.json`
- 分层：Elite(≥65%+≥10笔) / Verified(≥50%+≥5笔) / Watching(≥40%+≥3笔)
- heat_score 加权公式，信号聚合到 `smart_money_signals` 表
- 交易级记录：`smart_money_txns` 表（7天自动清理）
- `smart_wallets` 表列名是 `wallet`（非 `address`），无 `chain` 列

## 踩坑记录
- **Python 3.9**: 不支持 `X | None`，用 `Optional[X]` / `List[str]`
- **Flutter withOpacity 弃用**：改 `withValues(alpha: ...)`
- **Supabase DDL**：只能 Dashboard SQL Editor 手动执行
- **load_dotenv(override=True)**：防 shell profile 空变量覆盖 .env
- **OKX Market API 需单独白名单**：Aggregator 可用但 Market 返回 code:-1
- **DexScreener 限速**：批量30个/批，30s轮询较安全
- **Agent DEV_USER_ID 必须合法 UUID**：`00000000-0000-0000-0000-000000000001`
- **PostgREST FK join**：无直接FK需通过中间表嵌套
- **EVM nonce 必须动态获取**：hardcode 0 只对首笔交易有效
- **EVM tokentx 返回代币数量非 USD**：需乘以 price_usd 转换
- **sync API 阻塞 async 循环**：用 `asyncio.to_thread()` 包装同步调用
- **TabBarView 状态丢失**：需 `AutomaticKeepAliveClientMixin`
- **Flutter Navigator pop 后 context 失效**：pop 前用 `Navigator.of(context)` 拿 nav，pop 后只能用 nav，不能再传 context
- **JS `|| null` 误杀零值**：涨跌幅/价格为 0 时被当 falsy，改用 `?? null`
- **Portal 热币日榜"加载中"**：今天无数据是正常（UTC 02:00 生成），切历史日期验证

## 用户偏好
- **始终使用中文输出**
- 报告要有真实数据，不要粗糙概述
- 时间估计不要虚长
- **每完成一个子任务立即更新记忆文件**
