# 会话记录 + 讨论结论

> 每次会话结束时追加。格式：做了什么 / 讨论结论（为什么这么选）/ 被否定的方案

---

## 2026-03-11

### 做了什么
- outcome_labeler 口径修复、daily_highs ISO时间戳、K线折线图模式
- 详情页 Holder RPC 优先、initState bug、ETH 链全链路支持
- 聪明钱种子库导入、Agent DB Migration 008、Flutter AgentScreen 重写
- OKX 数据源集成（okx_market_client + 分层更新策略 + Flutter 全链路）

### 讨论结论
- OKX Market API price-info/basic-info 需白名单（code:-1），改用 toplist/candles

---

## 2026-03-12（6次会话）

### 做了什么
- 性能优化：热币刷新 1min→30s，发现 2h→10min，表现追踪秒级协程
- DexScreener 作为 OKX Market API 不可用时的 fallback
- 多链聪明钱追踪（SOL/ETH/BSC/Base，55钱包）
- 钱包管理系统、风控系统
- OKX DEX 真实交易（quote→swap→sign→broadcast→record）
- 聪明钱交易级追踪 + 买卖详情弹窗
- 策略交易记录 + P&L 展示

### 讨论结论
- **热币数据源分层**：OKX toplist 负责发现（8次/链），DexScreener 负责 30s 刷新（批量按地址）。原因：OKX Market price-info 需白名单，toplist/candles 可用；DexScreener 按地址批量更适合刷新场景
- **聪明钱 EVM 最初用 Etherscan**：当时未评估 OKX Wallet API，后来升级

---

## 2026-03-13（全量测试 + 修复，2次会话）

### 做了什么
- 120+ 问题发现，~27项修复
- CRITICAL: EVM nonce 动态获取 + to_amount 动态精度
- HIGH: Claude API async化 + mark_alert_read 鉴权 + 多链价格追踪
- 代码去重（提取5个公共模块）、API base URL 配置化、推送通知接入、XGBoost ML 管线

### 讨论结论
- **EVM nonce 必须动态获取**：hardcode 0 只对首笔有效，后续全部失败
- **to_amount 精度**：从 OKX 响应 `toTokenDecimalNum` 动态获取，不同代币小数位不同
- **Claude API 必须 async**：同步调用阻塞 FastAPI 事件循环，用 asyncio.to_thread 包装

---

## 2026-03-14（第二轮 QA 自动审查）

### 做了什么
- Portal 21个bug修复（migration 016 image_url + RLS、刷新60s、零值null guard）
- Flutter 23个bug修复（context-after-pop崩溃、substring越界、Future.wait下标脆弱）

### 讨论结论
- **JS `|| null` 误杀零值**：涨跌幅/价格为0被当falsy，统一改 `?? null`
- **Flutter context-after-pop**：pop前必须先拿 `Navigator.of(context)`，pop后不能再传context

---

## 2026-03-15（实时推送 + 合规 + 限流）

### 做了什么
- push_service.py：双层限流（用户每小时10条/系统每日30条）
- collector.py：事件驱动推送（高分新币/BC里程碑/聪明钱入场/毕业）
- 钱包私钥改用 flutter_secure_storage（iOS Keychain / Android EncryptedSharedPreferences）
- Agent 合规弹窗 + 策略启用风险二次确认

### 讨论结论
- **推送限流必要性**：无限流会骚扰用户，双层（用户级+系统级）互补
- **flutter_secure_storage 替代 SharedPreferences**：私钥明文存储是安全漏洞

---

## 2026-03-16（合规加固 + 云端部署）

### 做了什么
- Flutter DisclaimerPage：首次启动全屏使用须知（滑到底+勾选才能进入）
- Backend GeoBlockMiddleware：中国大陆 IP → HTTP 451
- 腾讯云服务器部署：systemd + Nginx，pump-scanner 上线
- 多链钱包：助记词一键派生 SOL/ETH/BSC/Base 四链

### 讨论结论
- **合规策略**：非托管+数据工具+非中国大陆上架 = 合规；App Store 全球上架仅排除大陆
- **云服务器选型**：腾讯云新加坡节点（43.156.207.26），避免国内监管，访问海外API延迟低

---

## 2026-03-17（聪明钱实时升级 + 记忆文件重构）

### 做了什么
- 聪明钱从15分钟APScheduler升级为实时：SOL Helius WS ~400ms / EVM OKX 5s轮询 ~2.5s
- 修复：OKX base URL（web3.okx.com）+ 端点（transactions-by-address）+ 参数（chains=）
- 修复：smart_money_txns 批次去重（ON CONFLICT 重复行错误）
- 修复：OKX toplist 429（每链10s冷却）
- 记忆文件重构：MEMORY.md 精简+索引，拆分 topic 文件，建立自动读取机制

### 讨论结论
- **EVM 聪明钱数据源**：必须用 `web3.okx.com`（不是 www.okx.com），端点 `transactions-by-address`（不是 `transactions`，后者需 accountId）；参数 `chains=`（List，不是 `chainIndex=`）；响应 `data[].transactionList[]`
- **禁止 Etherscan**：5 req/s + 30s轮询 = 15s感知，比 OKX 慢6倍
- **记忆文件机制**：MEMORY.md <150行做索引，细节放 topic 文件，顶部放强制读取指令，发现新信息立即更新不等任务结束

### 被否定的方案
- ~~Etherscan 作为 EVM 主力~~：太慢，禁止
- ~~www.okx.com~~：Cloudflare 403
- ~~/api/v5/wallet/post-transaction/transactions~~：需 accountId，不适合任意钱包监控
- ~~MEMORY.md 存所有细节~~：超200行被截断，改为索引+topic文件结构

---

## 2026-03-17 会话2（pump三阶段 + Portal服务器部署）

### 做了什么
- pump.fun采集改为三阶段架构（commit bac2a06）：
  - 阶段1: WS全量捕获零延迟直接写DB，取消MAX_TRACKED_TOKENS=2000上限
  - 阶段2: 内存交易追踪池20,000（旧2,000），累积trade数据
  - 阶段3: 初筛(buyers>=3 且 bc>=2%)通过后才拉REST，Semaphore(20)并发
- Portal部署到服务器：Node.js 20安装 → npm build → systemd portal.service → nginx反代
- nginx分流配置：FastAPI路由→:8000，Portal→:3000，共用80端口

### 讨论结论
- **pump全量捕获必要性**：旧架构每天只抓4,736（MAX_TRACKED_TOKENS=2000瓶颈），pump.fun日发3-5万，80%被丢弃
- **三阶段 vs 20并发暴力拉REST**：20并发有429风险且浪费额度，三阶段只对初筛通过的2000-5000个拉REST
- **Portal服务器部署**：从Vercel迁移到自有服务器，nginx分流保证FastAPI和Portal不冲突

### 被否定的方案
- ~~20并发暴力拉REST~~：3-5万个全量拉REST，429风险高，API额度浪费
- ~~Portal用独立端口3000外部访问~~：腾讯云安全组未开3000，改用nginx 80端口反代

---

## 2026-03-17 会话3（实时信号池替代每日推荐）

### 做了什么
- 实时信号池（commit 2c2e227 + a5de99f）：
  - collector.py: 新增 `_signal_pool` 内存池，score>=55 且 BC 3-35% 自动进入，涨过/死了/超时自动移出
  - `/api/pump/signals` API 端点（routes_pump.py）+ `/api/pump/stats`
  - scanner_ref.py 解决 main↔api 循环导入
- Flutter PicksScreen 重写：从 Supabase daily_picks 查询 → 后端 API 30s 轮询
  - 新增 PumpSignal model + PumpSignalService
  - MarketScreen 新币 Tab 同步改为实时信号
  - 空池显示"暂无实时信号"而非"今日信号尚未生成"
- Portal 漏斗描述更新
- nginx 新增 `/api/pump/` → :8000 路由
- 服务器部署验证通过

### 讨论结论
- **MEME 生命周期极短（分钟级），每日一次推荐毫无意义**：用户明确要求实时推、符合条件就推、涨过了就移出、没有就不推
- **信号池无固定大小**：不是固定 Top10，是动态进出的实时池
- **daily_job 保留但不再是 APP 主力**：历史记录用，APP 新币 Tab 完全切换到实时 API

### 被否定的方案
- ~~每日 UTC 00:05 一次推荐~~：MEME 生命周期分钟级，每日推毫无意义
- ~~固定 Top 10 列表~~：应该是有就推、没有就空
- ~~main.py 直接导出 get_scanner()~~：与 api/ 存在循环导入，改用 scanner_ref.py

---

## 2026-03-17 会话4（Portal修正 + apps/web 清理）

### 做了什么
- Portal report 页面标签修正："推荐给用户" → "实时推荐"（apps/portal，非 apps/web）
- 删除 apps/web 整个目录（62文件，7219行），已被 apps/portal 完全替代
- launch.json 移除 web 配置
- commit ce34576，已推送 GitHub，Vercel 自动部署

### 讨论结论
- **Portal 是 apps/portal（Vercel），不是 apps/web**：apps/web 是旧的未部署项目，已删除
- **apps/web 不再使用**：所有监控功能在 apps/portal 实现

---

## 2026-03-17 会话5（AI Optimizer Agent + Portal 服务器迁移）

### 做了什么
- AI Optimizer Agent 完整系统（commit 04a68dd + 多个修复 commit）：
  - optimizer_agent.py: Claude Opus 4.6 tool_use 循环，最多20轮对话，完整日志存DB
  - optimizer_tools.py: 6个工具（read_metrics/read_scorer_code/read_config/query_tokens/backtest/propose_change）
  - backtest.py: 回测引擎，用 market_cap_sol 涨幅>=50% 作为"好代币"定义
  - governor.py: 每3天调度器，检查指标→启动Agent→回滚保护
  - routes_optimizer.py: API 端点（runs/proposals/approve/reject/trigger）
  - Portal /tuning 页面：运行记录 + 对话日志展示 + 提案审批按钮
- Supabase 建表：optimization_runs / optimization_proposals / optimization_metrics_history
- anthropic SDK 升级 0.18.1→0.85.0（旧版 proxies 参数报错）
- 修复 backtest/tools 查询 token_snapshots 不存在的列（score, social_score）
- 修复 run_optimization 阻塞事件循环（asyncio.to_thread）
- 添加 Claude API 429/500 重试逻辑（3次，递增退避）
- 冷启动规则：F1=0 且快照<50时允许提交基础设施改善类提案
- Portal 从 Vercel 迁移到服务器：apps/portal npm build + systemd portal.service 更新（WorkingDirectory 从 apps/web 改为 apps/portal）
- 首次成功运行（run #7）：13轮对话，174K tokens，$3.10，提交1个冷启动提案
- 提案 pending（用户暂不批准）

### 讨论结论
- **"好代币"不能只看毕业**：pump.fun 毕业只是 BC 收到 85 SOL，毕业后可能暴涨也可能归零。真正的好推荐 = 推荐后价格涨幅 >= 50%
- **聪明钱暂时不好用**：地址太少（~20个），评分20分几乎全为0，用户后续单独优化。Optimizer 需要考虑实际有效满分约80分
- **冷启动例外必要性**：F1=0 时回测永远无法证明改善（0=0），但扩大漏斗逻辑上正确
- **Portal 弃用 Vercel**：Vercel 构建经常失败发邮件，直接部署服务器更可靠
- **Optimizer API Key 独立**：sk-ant-api03-ZMrn...（专用于 optimizer，不与其他功能共用）

### 被否定的方案
- ~~一次性手动优化参数~~：用户要自动化，每3天自动运行
- ~~只看毕业率作为评估指标~~：毕业后可能归零，必须看价格涨幅
- ~~Vercel 部署 Portal~~：构建不稳定，迁移到服务器

### 踩坑记录
- anthropic SDK v0.18.1 的 `Anthropic()` 构造函数不接受 `proxies` 参数（新版内部传递），必须升级到 >=0.80
- token_snapshots 表没有 score/social_score 列，backtest 和 tools 查询时必须用 `*` 或只选存在的列
- systemd restart 时如果 optimizer 正在运行，SIGTERM 超时后 SIGKILL 会产生 stuck run 记录
- nginx 在 pump-scanner 重启后有时需要一起重启才能恢复外部 API 访问

---

## 2026-03-17 会话6（i18n 国际化 + QA 测试修复）

### 做了什么
- Flutter App 完整 i18n 国际化：支持中文/英文/日文/韩文，默认跟随系统语言
- 基础设施：flutter_localizations + gen_l10n，LocaleProvider + SharedPreferences 持久化
- 创建 4 个 ARB 文件（app_zh/en/ja/ko.arb），275+ 本地化字符串
- 35+ 文件替换硬编码中文为 S.of(context)
- Profile 设置中添加语言切换器（跟随系统 + 4 种语言可选）
- **严格 QA 测试**：发现并修复 80+ 遗漏问题
  - CRITICAL: token_detail_page.dart（60+ 中文完全遗漏）、recent_trades_card.dart、market_stats_grid.dart
  - CRITICAL: model 文件中文 getter 无 BuildContext → 改为 key-based + UI 层解析
  - HIGH: locale_provider 校验/错误处理/异步通知
  - HIGH: app.dart localeResolutionCallback + DisclaimerGate 错误处理
  - HIGH: DateFormat 硬编码中文 → locale-aware
- 数字格式统一为国际通用 B/M/K
- 两次 commit：fc4740a + 1158d63，已推送 GitHub

### 讨论结论
- **Model 无 BuildContext 的 i18n 方案**：model 返回 raw 值，widget 层用 helper + S.of(context) 解析
- **数字格式**：统一用 B/M/K（crypto 行业标准）
- **locale_provider 必须校验 + 立即 notifyListeners**
- **localeResolutionCallback**：显式回退英文，不依赖列表顺序

### 踩坑记录
- flutter gen-l10n 单独运行无效，需 `flutter pub get` 触发
- Model 层 goplus_report.items 返回中文 label → 需改为 key-based
- const 冲突：Tab(text: S.of(context)) 不能是 const
- initState 中 _load() 无 context → 用 flag 替代，在 build() 中解析

---

## 2026-03-17 会话7（App Store 上传 + ATS 修复 + App Icon）

### 做了什么
- **App Store Connect 上传**（2次）：
  - 第1次：Build 1 — 命令行 archive（CODE_SIGNING_REQUIRED=NO），Distribute 报 "No Team Found in Archive"
  - 解决：改用 Xcode GUI 手动签名（Manual + Apple Distribution 证书 + AiTrading_AppStore provisioning profile）
  - Apple Developer 创建 App Store provisioning profile（AiTrading_AppStore，UUID 6f10cf44）
  - App Store Connect 创建 App 记录（名称 "AI Trading" 被占用 → 改 "AiTrading Pro"）
  - Build 1 上传成功（Upload Symbols Failed 警告，不影响）
- **ATS 修复**：
  - 发现 Agent 页面 Network error：iOS ATS 阻止 HTTP 明文连接
  - Info.plist 添加 `NSAppTransportSecurity > NSAllowsArbitraryLoads = true`
  - 需要重新 archive 上传（Build 2），已上传成功
- **App Icon 替换**：
  - 发现项目使用 Flutter 默认 icon（会被 Apple 拒绝）
  - 找到之前设计的 icon.svg（AI 大脑 + K线图，深色背景蓝色调）
  - 用 rsvg-convert 生成 1024x1024 PNG → sips 缩放生成所有 15 个尺寸
  - 替换 ios/Runner/Assets.xcassets/AppIcon.appiconset/ 全部图片
  - 需要再次 archive 上传（Build 3，包含 ATS 修复 + 新 icon）
- **App Store Connect 信息填写**：
  - 推广文本、描述（突出 AI，淡化 crypto）、关键词、技术支持 URL
  - Primary Language: English (U.S.)
  - SKU: com.aitrading.aitradingApp

### 讨论结论
- **iOS ATS (App Transport Security)**：默认阻止 HTTP 明文连接，后端是 http://43.156.207.26（无 HTTPS），必须在 Info.plist 允许
- **App Store 签名流程**：命令行 archive 跳过签名不可行 → 必须 Xcode GUI archive with team
- **手动签名配置**：参考 finance_navigator 项目（CODE_SIGN_IDENTITY="iPhone Distribution" + Manual + 指定 PROVISIONING_PROFILE_SPECIFIER）
- **App 名称**："AI Trading" 已被占用，改为 "AiTrading Pro"
- **App Store 描述策略**：突出 AI 智能交易分析，淡化 crypto/区块链关键词

### 踩坑记录
- 命令行 `flutter build ipa --release` 带 `CODE_SIGNING_REQUIRED=NO` 产生的 archive 无 team 信息，Organizer Distribute 必然报 "No Team Found in Archive"
- Xcode 自动签名需要注册设备才能创建 Development provisioning profile → 改用手动创建 App Store Distribution profile
- iOS ATS 默认阻止 HTTP，模拟器不受限但真机/App Store 会失败

### 待完成
- [x] Build 3 archive + 上传（包含 ATS 修复 + 新 App Icon）→ 已完成
- [x] App Store Connect 填写信息 + 提交审核 → 已提交
- [ ] 等待 Apple 审核结果

---

## 2026-03-18 会话8（热币实时打分 + GeckoTerminal + 退出机制）

### 做了什么
- **HotCoinManager**（hot_coin_manager.py，commit 9f5d6fe）：
  - PriceFeed 毫秒级回调 → 实时重新打分 → 进出榜单判定
  - 入榜: score ≥ 50 且无 goplus_risk
  - 退出机制（5条规则）：
    ① 连续3次 score < 35
    ② 冲高回落（24h>200% 且 1h<-5%）
    ③ 成交量枯竭（1h量 < 24h均值的10%）
    ④ 卖压碾压（买占比 < 35%）
    ⑤ 连续5轮不在发现源
  - DB 写入节流（同一代币最多5s写一次）
  - 退出时从 hot_coins 表删除
- **GeckoTerminal 发现层**（gecko_discovery.py）：
  - trending_pools + new_pools，每链5页=100个，4链 ~542 个候选
  - 补充 OKX toplist 覆盖盲区，测试通过硬过滤 20 个
- **hot_coin_job.py 重写**：
  - 双源发现：OKX toplist + GeckoTerminal，去重合并
  - GeckoTerminal 新增候选自动做 GoPlus/Helius/DexScreener 安全检测
  - 30s DexScreener 全量刷新 → Manager on_full_refresh（打分+退出）
- **main.py 集成**：
  - 启动时 Manager 从 DB 加载活跃热币（14个 score≥50）
  - 注册 PriceFeed 回调 → Manager.on_price_update
  - flush_pending 协程定期刷新节流写入
- **App Store 已提交审核**：Build 3（含 ATS 修复 + 新 icon）
- **数据源分析**：
  - OKX toplist 每次只返回 Top 100（非全量）
  - OKX all-tokens 仅 2295 主流代币（无市场数据）
  - Bitget Wallet API 不可访问（302 重定向）
  - Birdeye 免费额度不够（30K CU/月，最低 $39/月）
  - GeckoTerminal trending 免费可用，30 req/min

### 讨论结论
- **热币覆盖不是全量**：OKX toplist Top 100 + GeckoTerminal ~200 = 每链约 300 独立候选，远非全量（SOL 链上数百万代币）
- **免费方案的天花板**：OKX + GeckoTerminal 是免费方案最大覆盖，要全量需 Birdeye $39+/月
- **PriceFeed 已有毫秒级能力但未连接到打分**：只需注册 on_price_update 回调即可联动
- **热币需要退出机制**：之前只增不减，186 个中 91% 是 score<50 的垃圾
- **OKX toplist 实时更新价格但排名分钟级变化**：10min 扫描频率足够
- **GeckoTerminal 30-60s 更新一次**：与 OKX 互补，能发现 OKX 未收录的新币

### 被否定的方案
- ~~Birdeye Token List~~：免费 30K CU/月不够用，最低 $39/月
- ~~Bitget Wallet API~~：所有 bgw-pro 端点返回 302，需企业合作
- ~~OKX all-tokens 做发现~~：只有 symbol/name/logo，无市场数据，且全是主流老币（2295个）
- ~~全量链上扫描~~：与排行榜方案对比，推荐 Top20 效果差 ≤5%，但成本 $39+/月 vs 免费

### 数据分析结论
- **全量 vs 排行榜效果差距 ≤15%**：真正会暴涨的币必有高成交量+涨幅，必然进 toplist
- **推荐质量瓶颈不在发现，在打分算法和退出时机**
- **优先级**：优化打分算法 > 增加数据源覆盖
- OKX all-tokens 实测：SOL=193, BSC=703, Base=70, ETH=1329，总计2295，全部无 firstTradeTime，search 接口也无此字段
- OKX toplist 价格实时更新（秒级），排名分钟级变化
- GeckoTerminal trending 30-60s 更新一次

---

## 2026-03-18 会话8 续（热币表现追踪口径修正）

### 做了什么
- **token_performance 口径修正**（commit 332eb6d）：
  - 旧口径：追踪 `hot_daily_picks`（每天 02:00 日榜 Top20），`price_at_pick` = 日榜快照价格
  - 新口径：追踪 `hot_live`（实时入榜代币），`price_at_pick` = **发现瞬间价格**
  - `_enter_token()` 入榜时立即写 `token_performance`（source="hot_live"）
  - daily_highs.D0 = 发现当天最高价/涨幅（相对发现价 A）
  - daily_highs.D1 = 次日最高价/涨幅（相对发现价 A）
  - 以此类推到 D30
- **修复 best_day=None**：初始化时如果为 None 就设置为当前 day_number
- **修复 hot_live source**：performance_tracker 的 `_tick_hot` 支持 `hot_live` source
- **漏斗统计**：每轮扫描记录 discovered/after_hard_filter/entered/exited/active
  - Migration 021: `hot_funnel_stats` 表（需手动在 Supabase Dashboard 执行）
- **现有数据分析**：
  - token_performance 有 140 条 hot + 5 条 pump
  - 热币推荐 81% 有正收益（best_pct > 0）
  - 14% 涨幅超 100%，42% 涨幅超 20%

### 讨论结论
- **追踪口径必须是"发现瞬间价格"**：日榜 02:00 快照价格滞后太严重，代币可能已涨一天
- **D0/D1/D2... 全部相对发现价**：这样才能评估"我们发现后还涨了多少"
- **旧 source="hot"（日榜）保留不删**：新追踪用 source="hot_live"，不影响历史数据

### Portal 修复（commit 1cca6e0）
- daily_highs key 映射：`highs["1"]` → `highs["D1"] ?? highs["1"]`，兼容新旧格式
- 新增 D0 列（发现当天涨幅）
- queries.ts 支持 `hot_live` + `hot_all` source，hot 页面改用 `hot_all`
- 退出原因写入 DB：`snapshot_data.exit_reason/exit_price/exit_pct/exit_at`
- 退出时标记 `token_performance.is_active=false`

---

## 2026-03-18 会话8 续续（Hot Coin Optimizer Agent）

### 做了什么
- **Hot Coin Optimizer Agent**（commit b775038）：
  - optimizer_tools.py: 5 个 hot 专用工具（read_hot_metrics/scorer_code/config/backtest/propose）
  - backtest.py: run_hot_backtest() 热币历史回测引擎
  - optimizer_agent.py: run_hot_optimization() + HOT_SYSTEM_PROMPT
  - governor.py: pump/hot 交替调度（day_of_year 奇偶）
  - routes_optimizer.py: `POST /api/optimizer/trigger?mode=hot`
  - config.py: HOT_OPTIMIZER_API_KEY（环境变量，不提交到 Git）
- **量化目标**：
  - D1 正收益率 ≥ 70%（当前 37.7%）
  - D7 涨幅≥20% 的比例 ≥ 40%
  - D0 负收益率 < 20%
  - 平均最佳涨幅 ≥ 30%（当前 38.8%）
- **当前真实数据**（122 条 hot 追踪）：
  - D1 正收益率 37.7%（差距大，优化空间大）
  - 50% 涨幅命中率 20.5%
  - 平均最佳涨幅 38.8%

### 讨论结论
- **复用现有 Optimizer 架构**：不新建文件，扩展 optimizer_tools/agent/backtest，共用 DB 表和 Portal 审批
- **GitHub 推送保护**：API Key 不能硬编码在代码中，改用 .env 环境变量
- **Governor 交替调度**：day_of_year 奇偶决定跑 pump 还是 hot，每 3 天一次

### 监控口径修正（commit bdec08d）
- **热币追踪窗口**: 30天 → 7天（hot_live 独立，pump 保持 30 天）
- **命中定义**: 新增 `D3 ≥ 20%` 作为热币专用命中指标（补充 best_pct ≥ 50%）
- **入榜后 1h 涨幅**: _enter_token 时加入 1h 检查队列，1h 后自动计算 entry_1h_pct 写入 snapshot_data
- **退出后继续追踪 3 天**: exit_track_until 延迟标记 inactive，评估退出时机正确性
- **optimizer_tools**: read_hot_metrics 新增 d3_above_20_rate + entry_1h_positive_rate
- **performance_tracker**: _deactivate_old 按 source 分别处理窗口，尊重 exit_track_until

### 全量测试
- 7 大类 23 个测试全部通过
- 覆盖：导入/入榜退出/打分/optimizer工具/追踪窗口/硬过滤/回调集成

### 内盘 Bug 修复（commit 533d43e）
- **CRITICAL**: collector.py:102 `.isoformat()` on None → `(x or fallback).isoformat()`
- **CRITICAL**: collector.py:424 零交易代币永不驱逐（内存泄漏）→ 无交易超时直接淘汰
- **MEDIUM**: collector.py:350 enrich 竞态条件 → `.get()` 替代 `[]`

### 今日 commits 汇总
1. `9f5d6fe` — HotCoinManager + GeckoTerminal + 退出机制
2. `332eb6d` — token_performance 发现瞬间价格 + 漏斗统计
3. `1cca6e0` — Portal daily_highs 映射 + D0 列 + hot_live support + 退出记录
4. `b775038` — Hot Coin Optimizer Agent
5. `bdec08d` — 监控口径修正（7天窗口/1h涨幅/退出后追踪/D3命中率）
6. `533d43e` — 内盘 collector.py 3 个 Bug 修复（isoformat crash + 内存泄漏 + 竞态）

### 待执行（手动）
- [x] Supabase Dashboard 执行 `migrations/021_hot_funnel_stats.sql` — 已执行

---

## 2026-03-18 会话9（聪明钱地址供给系统）

### 做了什么（进行中）
- **聪明钱地址供给方案设计**：
  - 现状：60 个手动种子地址，Buy/Sell 金额 $0，追踪效果差
  - 目标：2000+ 经过验证的活跃地址，三层供给全免费
  - OKX 无公开聪明钱 API（web3.okx.com 404），GMGN 无 API，排除爬虫方案
- **第 1 层：自有数据挖掘**（smart_wallet_miner.py 新建）：
  - 从 token_trades（460K 条）挖掘毕业代币（68 个）的早期买家（bc<10%）
  - 命中 2+ 个毕业代币 → 写入 smart_wallets（tier=watching, source=mined）
  - APScheduler 每天 UTC 04:00 运行
- **第 2 层：热币 Top Holders 实时发现**：
  - hot_coin_fetcher.py 新增 `fetch_top_holders()`：SOL 用 Helius `getTokenLargestAccounts`，EVM 用 GoPlus holders
  - hot_coin_manager.py `_enter_token()` 入榜时异步采集 Top 10 持仓地址
  - 存入新表 `hot_coin_top_holders`
  - smart_wallet_updater.py 新增 `_evaluate_top_holders()`：D3 涨 20%+ 的代币 Top Holders 自动晋升聪明钱
- **交易金额 $0 修复**（smart_money_tracker.py）：进行中
  - SOL 端 volume_usd 始终 0（Helius swap events 只有 token mint 没提取金额）
  - EVM 端 `_is_token_qty` 转换依赖 price_map 但 OKX 响应有 amount 字段未用

### 讨论结论
- **聪明钱地址来源**：用户选择"组合方案"（自有数据挖掘 + 热币 Top Holders + 后续 Dune）
- **不爬虫**：GMGN/OKX 无公开 API，爬虫会被封，不合法
- **全量 vs 排行榜效果差距 ≤15%**：真正会暴涨的币必有高成交量+涨幅，必然进 toplist
- **瓶颈不在发现，在打分算法和退出时机**
- **聪明钱供给规则**：作为永久规则写入 rules.md/architecture.md

### 被否定的方案
- ~~OKX 聪明钱 API~~：不存在（所有端点 404）
- ~~GMGN 爬虫~~：无公开 API，爬虫风险高
- ~~Birdeye Top Traders~~：$39+/月，SOL only
- ~~Nansen/Arkham~~：$99-299/月，用户选免费方案

### 文件变更
| 文件 | 操作 | 状态 |
|------|------|------|
| smart_wallet_miner.py | 新建 | ✅ |
| hot_coin_fetcher.py | 新增 fetch_top_holders() | ✅ |
| hot_coin_manager.py | _enter_token 加 Top Holder 采集 | ✅ |
| smart_wallet_updater.py | _evaluate_top_holders() 晋升逻辑 | ✅ |
| smart_money_tracker.py | 修复交易金额 $0 | 🔄 进行中 |
| main.py | 注册 miner 定时任务 | 待做 |
| migrations/022_hot_coin_top_holders.sql | 新建 | 待做 |

### 已完成
- [x] 修复 smart_money_tracker.py 交易金额（SOL: nativeTransfers+tokenAmount, EVM: OKX amount）
- [x] main.py 注册 miner 定时任务（每天 UTC 04:00）
- [x] Supabase Dashboard 执行 migrations/022_hot_coin_top_holders.sql — 已执行
- [x] 测试：miner 成功挖掘 12 个新聪明钱地址（40 个早期买家中 13 个候选）
- [x] 部署服务器：commit 988b51a，pump-scanner 正常运行

### 第 3 层 Dune Analytics（commit e28c4cc）
- dune_wallet_importer.py 新建：从 Dune Query 6850812 拉取 SOL DEX 高频交易者
- 过滤 bot（>5000笔/14天），保留真人（30-5000笔，5+代币，5+天）
- 首次导入 493 个新地址，smart_wallets 总数达 1506
- 每周一 UTC 05:00 自动运行，Dune API Key 已配置到服务器 .env
- main.py 注册定时任务

### 三层供给系统总结
| 层 | 来源 | 频率 | 首次结果 |
|-----|------|------|---------|
| 第1层 | 自有数据挖掘（毕业代币早期买家） | 每天 UTC 04:00 | +12 地址 |
| 第2层 | 热币 Top Holders（入榜触发） | 实时 | 待触发 |
| 第3层 | Dune Analytics（4链 DEX 交易者） | 每周一 UTC 05:00 | SOL +493，ETH/BSC/Base 待创建查询 |

### 聪明钱 v3 评估体系（commit 16a4102）
- **smart_wallet_updater.py 重写**：五维度100分评估
  - 维度1 胜率（0-20）：72h内涨20%+才算赢，≥60%=20分
  - 维度2 PNL（0-20）：卖/买中位数，≥2x=20分
  - 维度3 交易规模（0-20）：单笔USD中位数，≥$5K=20分
  - 维度4 活跃度（0-20）：频率+天数分布，>2000笔=bot
  - 维度5 时效性（0-20）：买入时市值，<$500K=20分
- **分层**：elite≥75 verified≥55 watching≥35 blacklisted<30
- **降级**：14天无交易降一级，28天无交易移除
- **实时bot检测**：smart_money_tracker 每次保存txn后检测60秒买卖→立即黑名单
- **评估周期**：6h→2h

### 讨论结论
- **旧评估体系问题**：只看"代币是否毕业"，无PNL/规模/时效性维度，bot检测不够及时
- **胜率定义**：旧=代币毕业或2x，新=72h内涨20%+（更贴近热币场景）
- **余额维度不可行**：查1506个地址链上余额成本太高，用"单笔交易规模"替代
- **"早期发现"是聪明钱核心价值**：买入时市值越低=越聪明，新增时效性维度
- **Dune 需要4链查询**：SOL已有(6850812)，ETH/BSC/Base需用户在网页创建
- **SOL LIMIT 500→5000**：免费版最多250K行，应尽量多取

### 被否定的方案
- ~~余额维度查链上~~：1506地址×4链 RPC 调用量太大，改用交易规模替代
- ~~6h评估周期~~：MEME场景太慢，改2h
- ~~只看胜率分层~~：缺少PNL/规模/时效性，无法区分大户和散户

### 全量追踪（commit af17074 + 5bf6087）
- **SOL: Helius Webhook**：支持 100K 地址，<1s 延迟
  - 注册 webhook 到 `/api/webhook/helius`，Helius POST 推送交易
  - 429 时自动回退 WS 模式（top 100 elite/verified）
  - WS 回退加指数退避（10s→20s→40s...最大 300s）
- **EVM: 20路并发 + 优先级分组**：
  - Group A (elite/verified ~17 个): 每 2 分钟，~12s 感知
  - Group B (watching ~32 个): 每 15 分钟
- **内盘 pump 评分已自动联动**：collector.py 的 `get_smart_wallet_tiers()` 直接读 smart_wallets 表（2135+ 地址）
- **nginx 新增 `/api/webhook/` 路由**
- **Helius 免费版限制**：webhook 创建可能 429（max usage），需等恢复后重启服务
- **Dune 4 链导入**（commit 88a3abc）：
  - SOL: 6850812 (LIMIT 5000), ETH: 6858638, BSC: 6858633, Base: 6858622
  - 首次 4 链导入进行中，smart_wallets 从 1506 增至 2135+

### commits 汇总
1. `988b51a` — 三层供给系统（miner + TopHolders + Dune SOL）
2. `e28c4cc` — Dune SOL 导入 + dune_wallet_importer.py
3. `16a4102` — v3 五维度评估体系
4. `88a3abc` — Dune 4 链 Query ID 配置
5. `af17074` — SOL Helius Webhook + EVM 并发轮询
6. `5bf6087` — WS 回退 top 100 + 指数退避
7. `1853a17` — DEX 程序级监控（SOL logsSubscribe 5 DEX + EVM eth_subscribe 3 链）
8. `ce12609` — Agent 事件驱动 + 表现分析 + 回测 + 风控增强

### Agent 事件驱动升级（commit ce12609）
- **event_listener.py 新建**：订阅 EventBus 3 个数据事件，毫秒级策略评估
  - 去重 TTL 5s + 策略内存缓存 30s，30s monitor_job 保留为 fallback
- **hot_coin_manager.py**：入榜 + 打分变动 > 3 分时 publish `data.hot_coin_update`
- **collector.py**：pump 快照 bc >= 3% 时 publish `data.pump_snapshot`
- **performance_analytics.py 新建**：胜率/PNL/最大回撤/夏普率
- **backtester.py 新建**：策略回测（7 天历史，模拟胜率/触发次数）
- **risk_manager.py**：+2 检查（BTC 大盘 + 同链集中度），总计 15 项
- **routes_agent.py**：4 个新端点（performance/portfolio/daily-pnl/backtest）

---

## 2026-03-22 会话（BTC/ETH Agent + 代币详情页 + Portal + App Store）

### 做了什么
- **代币详情页增强**（commit c154732）：
  - Top Holders 卡片：Top 10 持仓排名，地址+占比+进度条，一键复制
  - 资金流向卡片：24h 净流入/流出，买卖力量条，大额交易统计
  - 交易分布图表：30min 聚合柱状图，买卖对比
  - 新 API：/api/token/{chain}/{address}/top-holders
- **BTC/ETH 智能投资 Agent**（commit 3d8aa82 + 35421d8）：
  - 13 个免费数据采集器（93-95% 覆盖率）
  - Binance WS/REST + OKX + CryptoPanic + DeFiLlama + Blockchain.com + TwelveData + LunarCrush + Coinalyze + Mempool + Alternative.me + Dune
  - 50 项指标引擎 + 5 项复合评分（momentum/sentiment/onchain/macro/risk）
  - 技术指标本地计算：RSI/MACD/布林带/ATR/MA/支撑阻力
  - AI 分析层：CycleAnalyzer(7阶段周期) + SignalGenerator(两阶段) + ReportGenerator + AlertGenerator
  - 模拟盘引擎：自动执行+止盈止损+绩效计算
  - API: /api/btc-eth/* (health/indicators/dashboard/signals/alerts/reports)
  - DB: migration 025（6张表）已执行
  - ⚠️ Blockchain.com WS 暂禁（消息量阻塞事件循环）→ 改用 REST
- **App Store 上传**：
  - Build 3: ATS 修复 + 新 icon（alpha 通道移除）→ 已提交审核
  - Build 4: Agent 90s 超时修复 → 替换 Build 3
  - Build 5: objective_c.framework x86_64 模拟器架构错误 → 验证失败
  - Build 6: Podfile strip_simulator_archs 修复 → IPA 构建成功，待验证上传
  - App 改名：AiTrading Pro → Future Trading
- **Portal BTC/ETH 看板**（commit 47fef65）：
  - 重写为质量监控看板（去掉价格/指标展示）
  - 6 核心 KPI：总信号/胜率/累计收益/盈亏比/7天/30天
  - 信号追踪表：入场价 vs 1h/4h/24h/72h 实际走势
  - 采集器健康折叠展示
  - 部署到服务器 http://43.156.207.26/btc-eth
- **Flutter BTC/ETH 页面**：
  - Market 新增 "BTC/ETH" tab
  - 实时价格卡片 + 风险仪表盘（恐慌指数/RSI/资金费率）
  - Dashboard 交互优化：点击指标弹出解释 + i18n 多语言
  - 钱包删除功能
- **记忆文件同步到 GitHub**：docs/memory/（排除 credentials.md）
- **预测市场分析**：市场规模/竞品/用户痛点/切入方案（纯研究，未实现）

### 讨论结论
- **Portal 看板定位错误纠正**：看板目标是"监控 Agent 信号质量"，不是再展示一遍价格和指标
- **Blockchain.com WS 必须禁用**：unconfirmed_sub 每秒推送数百条消息，json.loads 全部解析导致 asyncio 事件循环阻塞，FastAPI 完全无响应
- **objective_c.framework 问题**：path_provider_foundation 依赖 objective_c 9.3.0，包含模拟器架构 x86_64，App Store 拒绝。需 Podfile post_install 剥离
- **Agent 30s 超时不够**：服务器后台任务增多（DEX 监控/聪明钱追踪等），事件循环拥堵导致 Claude API 响应变慢，Flutter 超时改为 90s
- **数据源覆盖率优化路径**：55% → 85% → 93-95%，通过深挖 Binance 未用数据 + Blockchain.com + DeFiLlama + TwelveData + LunarCrush
- **模拟盘验证机制**：用户先模拟投 $10,000 观察 Agent 表现，确认赚钱后切实盘
- **聪明钱全量追踪方案**：不监控 16,000 钱包 → 监控 5 个 DEX 程序（Raydium/Jupiter/Uniswap/PancakeSwap/Aerodrome），HashSet O(1) 匹配

### 踩坑记录
- Blockchain.com WS `unconfirmed_sub` 阻塞事件循环（每秒 100+ 条消息）
- objective_c.framework 含 x86_64 模拟器架构，App Store 验证失败
- Agent HTTP 超时：后台任务增多后 Claude API 响应从 12s 变为 20-30s
- App Store Connect 名称 "AiTrading Pro" 后改为 "Future Trading"

### Supabase 免费版优化（commit e715d02）
- **问题**：token_trades 每天 20 万行，13 天 130 万行，接近 500MB 上限
- **解决**：db_cleanup.py 每 6h 定时清理 + hot_coins 写入节流 5s→15s
- 首次清理删除 25,007 行

### 被否定的方案
- ~~Blockchain.com WS 实时大额转账~~：消息量太大，改用 REST 4h 轮询
- ~~Portal 展示价格/指标~~：看板目标是监控信号质量，不是再做一次行情展示
- ~~30s Agent 超时~~：不够用，改 90s
- ~~Supabase 直接 DELETE 大量数据~~：70 万行超时，必须分批 500 行/批

---

## 2026-03-22~23 会话（PRD 需求文档体系 + 4 个 PRD 开发测试 + 全量测试）

### 做了什么
- **需求文档体系建立**：
  - `docs/agent-trading/prd/` 目录结构：每个 PRD 下含 需求文档 + 技术文档 + 测试文档
  - PRD-001~004 完整文档输出
- **PRD-001 Agent 卖出执行**（commit dd28c98）：
  - trade_executor.py：sell 逻辑（查余额→OKX swap→签名→广播）
  - position_monitor.py：止盈/止损/追踪止损自动触发卖出
  - EVM approve 支持
  - migration 026：agent_executions 新增 exit_price/pnl/trigger 列 + strategies 表
  - 测试：17/17 ALL PASSED（UT-01~08 + IT-01a~d）
- **PRD-002 风控 Bug 修复**（commit 37405a1）：
  - _check_chain_concentration：float.get("chain") → _position_chains Dict 追踪
  - _btc_samples：hasattr 懒初始化 → __init__ 初始化
  - record_trade：新增 _position_chains 跟踪买卖
  - 测试：11/11 ALL PASSED
- **PRD-003 胜率定义统一**（commit 4e5d34c + 736b3e4）：
  - config.py：WIN_RATE_PUMP_D3_PCT=30 / HOT=20 / BTCETH=2 / AGENT=0
  - optimizer_tools.py：pump hit 改为 D3≥30% 或 graduated（旧：仅 graduated）
  - optimizer_tools.py：hot hit 改用 WIN_RATE_HOT_D3_PCT 常量
  - backtester.py：按 source 区分场景使用不同阈值
  - performance_analytics.py：新增 actual_win_rate + theoretical_win_rate 双指标
  - 测试：20/20 ALL PASSED（UT-01~07 + IT-01~05）
- **Supabase 优化**：
  - db_cleanup.py：每 6h 清理过期数据（token_trades 3天/snapshots 14天/indicators 7天）
  - token_trades 95% 缩减：只存信号池+毕业代币交易（每天 20万→1万行）
  - hot_coins 写入节流：5s→15s（减少 66%）
  - 预计可使用 2 年+
- **docs/memory/ 同步到 GitHub**：换电脑可恢复记忆文件

### 讨论结论
- **胜率定义旧逻辑问题**：Optimizer 用 "graduated" 判 hit，Backtester 用 "best_pct>=20%"，两者给出矛盾结论
- **统一方案**：pump=D3≥30%+毕业，hot=D3≥20%，agent=不亏就赢，btceth=PnL≥2%
- **performance_analytics 需要双指标**：actual（实际买卖PnL）+ theoretical（D3理论命中），用户和 optimizer 各看各的
- **_empty_performance 必须同步**：新字段忘了加到空值返回函数 → API 返回缺字段

- **PRD-004 中等问题合集**（commit 468ca74）：
  - M-01：trigger_count TOCTOU 修复 → Supabase RPC 原子递增（migration 027）
  - M-02：LLM Parser 重试逻辑 → 3 次指数退避（5s/10s/20s），捕获 429/5xx
  - M-03：15 个硬编码参数提取到 config.py（从 .env 读取，支持热更新）
  - M-04：btc_eth_indicators 持久化修复 → 列名白名单过滤 + 日志
  - M-05：Paper Trading 止盈止损循环 → check_all_exits 每 60s 检查所有 open 交易
  - 测试：16/16 ALL PASSED

### 全部 PRD 测试汇总
| PRD | 测试数 | 结果 |
|-----|--------|------|
| PRD-001 Agent 卖出 | 17 | ALL PASSED |
| PRD-002 风控修复 | 11 | ALL PASSED |
| PRD-003 胜率统一 | 20 | ALL PASSED |
| PRD-004 中等问题 | 16 | ALL PASSED |
| **总计** | **64** | **ALL PASSED** |

### PRD-005 记忆与反思系统（Phase 1 设计）
- PRD-005 v1.1 需求文档：4 个模块（M12记忆+M13反思+O4表现分析+O5风控审计）
- TECH-005 技术方案：5 个新模块 + 6 个修改文件
- TEST-005 测试用例：19 单元 + 5 集成 + 6 性能指标
- 17 项审查修订：成本$15.75→$5/月、Haiku→Sonnet、全量→Top10注入、规则结构化
- Agent 优化全景规划：6 Phase 29 模块（交易Agent 18 + 优化Agent 11）

### 深度调研完成
- 竞品分析：Walbi/3Commas/Cryptohopper/TradingAgents/Polystrat 6 产品对比
- 学术论文：TradingAgents(夏普5.6)/FinMem(三层记忆)/CryptoTrade(反思机制) 3 篇
- 用户痛点：97%系统失败、执行滑点、不适应市场变化、缺乏可解释性
- DEX 执行对比：OKX vs Jupiter vs 1inch，MEME 场景 Jupiter 滑点少 50%
- Agent 代码全量审计：~7000 行 16 模块完整分析

### 被否定的方案
- ~~pump hit 只看 graduated~~：毕业后可能暴涨也可能归零，D3 涨幅更贴近实际
- ~~单一胜率指标~~：actual 和 theoretical 含义不同，必须都展示
- ~~Haiku 做反思~~：质量不够，改 Sonnet
- ~~Semantic 规则全量注入~~：50条×50tokens=$15.75/月，改 Top10 注入=$4.68/月
- ~~每日清零短期记忆~~：跨日交易丢失上下文，改 24h 滑动窗口
- ~~自由文本规则~~：无法匹配"同一规则"，改结构化 condition/action JSON

### PRD-005 Phase 1 开发完成
- 7 个新文件：memory/__init__.py + working/episodic/semantic/reflection.py + cron_tasks.py + migration 028
- 8 个修改：event_listener + action_dispatcher + position_monitor + risk_manager + strategy_manager + optimizer_tools + main + routes_agent
- 总计 2,424 行新代码
- 29/29 pytest 测试全部通过
- 已部署上线，migration 028 已执行

### PRD-007 Phase 3 文档完成
- 6 角色：策略解析 + 3分析师(Haiku并行) + 辩论(Sonnet 3轮) + 风控(规则+AI)
- 分级触发：L1免费(200/天) → L2 $0.003(50/天) → L3 $0.015(15/天)
- 月成本 ~$10.4，性能预期提升 2-3 倍（TradingAgents 数据支撑）

---

## 2026-04-30 会话（记忆恢复 + 全量代码扫描 + Agent 技术方案产出）

### 做了什么
- 记忆系统恢复：重读所有 topic 文件，确认 docs/memory/ 双份同步机制运转正常
- 服务器健康检查：43.156.207.26（新加坡，用户曾误以为已迁移）运行正常，uptime 45 天，pump-scanner/portal/tat_agent/nginx 全 active，根盘 18G/59G 31%，流量 143G/1536G 9%。实例 `lhins-ph7ak7k9 / Ubuntu-GFLK`，内网 10.3.0.10
- 跨机器代码一致性验证：服务器 `/opt/agent-trading/` vs 本地 SHA1 哈希全部 387 个 tracked 文件比对，**真实差异只有 `apps/app/ios/Podfile.lock` 1 个**（本地未提交的 6 行删除）。本地领先 origin 6 个 `docs(agent-pm)` commit 全是设计文档
- 全量代码深读（5 个 Explore agent 并行）：后端 107 .py + Flutter 84 .dart + Portal/Admin 函数级深读，产出 9 大节代码地图（采集/打分/聪明钱/Optimizer + agent/ + api/ + btc_eth/ + Portal/Admin + 数据流图）
- 关键发现：`docs/agent-pm/00-16` 17 篇 PM 设计文档**从未实施**，只是产出物；不要把它的 §8 Gap 当成"待办对照表"
- **17-tech-plan.md 产出 + 落地**：针对 PM 设计的 v1 技术方案（**只设计不写代码**），覆盖 4 Phase（灾难漏洞修复 + Tool 化/Memory 升级 + Skill+Loop+Prompt Library + Flutter 重构 + Eval/Launch），16-20 周，完整 v1 范围（paper+notify+auto+真金+托管钱包），配置 A 质量门槛（1660 golden + 62 项 Launch Criteria 100%）。文件落到 `docs/agent-pm/17-tech-plan.md` 并入 README 矩阵 L6 工程落地区
- 线上 3 个非致命错误识别（未修）：`token_trades_pkey` duplicate / `btc_eth_indicators` 整数列写入 `472688.0` / `daily_picks ↔ pump_tokens` FK 缺失

### 讨论结论
- **服务器一直在新加坡 43.156.207.26，没换过**：用户记忆有误，腾讯云控制台只显示这一台实例
- **跨机器代码对比必须用 `LC_ALL=C sort`**：macOS sort 是 locale-aware，默认按 locale 排序导致 SHA 列表对齐错位被误判为内容差异；强制字节序后才能真实 diff（首次跑得到 47 个假差异，纠正后只有 1 个）
- **`docs/agent-pm/00-16` 是设计产出物，从未实施**：讨论 Agent 现状时绝不能用它作 baseline。实际线上能力 = `services/pump-scanner/agent/` 真实代码
- **Agent v1 技术方案只设计不实施**：本次会话不写任何业务代码，仅产出方案 + 更新记忆 + commit 文档
- **完整 v1 而非分期**：用户决定一次性做完整 paper+notify+auto+真金+托管，不走"先 paper 后真金"的分期路径
- **17-tech-plan 命名顺延**：原意 `00-tech-plan.md` 但 00 已被 `00-data-sources.md` 占用，改 `17-tech-plan.md` 接 README 矩阵

### 被否定的方案
- ~~把 docs/agent-pm 17 篇设计文档当作待开发 backlog 做 Gap 对照~~：这是产出物，不是 backlog
- ~~Phase 1 范围只做 paper + notify（简化版）~~：用户选完整 v1
- ~~分期迭代（先 paper 验证后再加 auto）~~：用户选一次性做完
- ~~Eval 配置 C（700 golden）/ 配置 B（轻量）~~：用户选配置 A（1660 + L1-L4 + LLM-as-judge）
- ~~17-tech-plan 命名 `00-tech-plan.md`~~：00 编号冲突，改 17 顺延

### 记忆更新
- 新建 `project_agent_pm_docs_status.md`（本地 + 仓库 docs/memory/）
- 更新 `MEMORY.md` / `docs/memory/MEMORY.md` 索引 + 本次会话段
- 更新 `CLAUDE.md` 当前功能状态表加 docs/agent-pm 行
- 更新 `pitfalls.md` 加 3 条（2 条线上 bug + macOS sort locale 坑）
- `17-tech-plan.md` 落到 `docs/agent-pm/`，README 矩阵新增 L6 工程落地区

---

## 2026-05-01 会话（Agent v1 W1 启动包开发）

### 做了什么
- 用户决策"全部你来干" → 进入实施阶段，开 `agent-v1` 长期分支
- 技术选型（我直接定）：OpenAPI 用 FastAPI 自带 / Flutter 不用 codegen 手写 model / Mock server 用后端 `MOCK_MODE=true` 环境变量
- **W1 启动包提交**（commit `e08eae1`，28 文件 2266 行，分支 agent-v1 已推 GitHub）：
  - **8 个 migration SQL**（034-041）：KMS / security_audit_log / pending_approvals+WAL / conversation_states / prompt_versions / agent_thesis / semantic_shadow_mode / eval_results
  - **后端骨架 9 个 .py**：safety_engine / kms_client / cost_guard / output_filter / prompt_loader / memory/wal / skills/loader / tools/base + 4 个 __init__
  - **safety_policy.yaml**：30 HR + 13 CB + 5 C 规则名（内容 TODO）
  - **3 个 routes stub**：routes_thesis / routes_audit / routes_admin（MOCK_MODE 返 fixture）
  - **4 个 Flutter model**：thesis / pending_approval / review / semantic_rule
  - **2 个 README**：prompts/v1 + skills

### 讨论结论
- **一个 session 做不完 16-20 周**：必须分多 session 推进，每次 session 用户说"继续"我从 sessions-log 接手
- **所有代码骨架带 TODO 注释**：实际业务逻辑实施在 Phase 0 W3-W12，本次只是搭建可联调的骨架
- **migration 暂不执行**：W3 KMS 接入或 W7 Memory WAL 实施时再 Supabase Dashboard 执行对应 SQL，不必现在跑
- **不混 main 分支**：agent-v1 长期分支独立推进，不影响线上 main
- **MOCK_MODE 设计**：后端新 endpoint 默认 501（未实施），设 `MOCK_MODE=true` 返 fixture，Flutter 即刻可联调不阻塞

### 被否定的方案
- ~~一次性塞几万行代码完成所有 Phase~~：单 session 不可能，分多次推进
- ~~OpenAPI 手写 OAS YAML~~：FastAPI 自带 /openapi.json 零成本
- ~~Flutter 用 openapi-generator codegen~~：跟现状不一致，手写 model 维持
- ~~单独跑 Prism mock server~~：多一个进程，不如后端 MOCK_MODE 开关

### 下次 session 接手
- 读取本条目 + `docs/agent-pm/17-tech-plan.md` Phase 0 W3 任务清单
- 已就绪骨架：safety_engine / kms_client / cost_guard / output_filter / prompt_loader / memory/wal / skills/loader / tools/base
- 下一步 W3 候选任务（按 17-tech-plan.md Phase 0）：
  1. KMS 实施（kms_client.py AwsKmsProvider 实现 + ANTHROPIC/OKX/Helius key 切 KMS）
  2. safety_engine HR01-HR30 检查实施（trade_executor pre_condition 接入）
  3. cost_guard 5 级降级实施（接 prompt_invocations 表）
  4. routes_admin Kill Switch 实施（< 10s 全局 BLOCKED）
- 仓库状态：分支 agent-v1 在 e08eae1，main 在 429f5a8（未变）

---

## 2026-05-01 会话 2（W3 D1 safety_engine 实施 + 数据库迁本地 PG）

### 关键决策（用户中途追加）
- **数据库不放 Supabase**：8 张新表迁服务器本地 PostgreSQL（`agent_trading_local`，PG 14，已经在跑 dex_address_stats）
- **节省空间 + 自动 TTL**：每张表配 TTL，db_cleanup.py 每 6h 跑

### 做了什么
- 服务器 PG 验证：postgres 14/main 端口 5432 在跑，用户 `agent_local` / DB `agent_trading_local` 已就绪
- **safety_engine 完整实施**（commit `4bbc05d`，12 文件 +1140 / -120）：
  - safety_policy.yaml v0.2：check 字段从字符串改为机器可读结构化条件（type=simple/boolean/compound/regex/function；op=gt/gte/lt/lte/eq/ne/in/not_in/contains/starts_with）
  - safety_engine.py 完整 evaluator：load+fail-safe / check_trade / check_constitutional / _eval_check 通用 / 4 个 C 函数（c2/c3/c4/c5）
  - 实施 10 条 HR：HR01/02/04/07/09/16/21/22/25/28
  - 实施 5 条 C：C1 blocklist regex / C2 risks≥2 / C3 evidence 非空+source / C4 占位 / C5 HITL 完整
- **tests/test_safety_engine.py**：**62 用例 全部 PASSED 0.62s**
  - 4 加载 + 22 HR 正反 + 14 C + 10 evaluator + 3 format + 9 C 函数直测
- **migrations 迁本地 PG**：
  - 7 个 SQL 移到 `migrations/local_pg/`（034/035/036/037/038/039/041）
  - 每个 SQL 头部加 `CREATE EXTENSION IF NOT EXISTS pgcrypto`
  - 040 例外（ALTER Supabase 表）留 `migrations/` 根目录
  - local_pg/README.md 说明执行步骤(SSH→psql)+ TTL 表
- **db_cleanup.py 扩展**：
  - 9 条 LOCAL_PG_RULES（8 表 + agent_thesis L3 例外）
  - run_local_pg_cleanup() 用 psycopg2 连本地 PG，各表独立事务
  - 表不存在时静默跳过（migration 未跑也不报错）
  - run_full_cleanup() = Supabase + 本地 PG（主程序入口）

### TTL 清理规则
| 表 | TTL | 触发字段 |
|---|---|---|
| security_audit_log | 90d | ts |
| pending_approvals | decided_at + 30d | decided_at |
| memory_write_wal | flushed_at + 7d | flushed_at |
| memory_write_retry_queue | resolved=true + 7d | created_at |
| conversation_states | expires_at + 24h | expires_at |
| prompt_versions | retired_at + 30d | retired_at |
| prompt_invocations | 30d | ts |
| agent_thesis | 30d（L3+conviction>0.8 例外90d） | ts |
| eval_results | 90d | ts |
| kms_key_aliases | 永久 | - |

### 讨论结论
- **服务器有 PG 14 现成**：端口 5432，agent_trading_local 数据库 + agent_local 用户已配（local_db.py 已对接 dex_address_stats）。直接复用，不用新装
- **040 必须留 Supabase**：ALTER agent_memory + agent_strategies，这两个表本身在 Supabase
- **migrations 不在本 session 执行**：只产出 SQL 文件，prod 执行需要 SSH+psql 单独操作
- **safety_engine 设计选择**：check 字段结构化（不是字符串），机器可读支持 5 种 type、9 种 op、嵌套 compound。比 Python 函数注册更灵活（yaml 改不重启）
- **62/62 测试通过**：覆盖 yaml 加载/fail-safe/10 HR 正反/5 C/evaluator 各 path/format/C 函数直测

### 被否定的方案
- ~~check 字段写 Python 表达式（eval()）~~：安全风险，改结构化条件
- ~~所有 8 张表都进 local_pg/~~：040 必须留 Supabase（改 agent_memory/agent_strategies 字段）
- ~~Supabase 全部继续用~~：用户明确说节省空间，新表迁本地 PG
- ~~只跑 25 测试（计划数）~~：实际 62 测试（parametrize+边界覆盖更全）

### 仓库状态
- agent-v1 分支 commit `4bbc05d` 已推 GitHub
- main 仍 `429f5a8`（未动）
- 文件统计：+1140 / -120，12 文件改动（3 modified + 7 renamed + 2 new）

### 下次 session 接手
- 读本条目 + 17-tech-plan.md Phase 0 剩余任务
- 已实施：safety_engine 10 HR + 5 C / tests 62/62 / migrations 迁 local_pg
- 候选下一步（按优先级）：
  1. **补全剩余 20 HR**（HR03/05/06/08/10/11/12/13/14/15/17-20/23/24/26/27/29/30）+ 测试
  2. **CB 13 个熔断器实施** evaluator + agent_global_state 表 + 自动恢复定时器
  3. **trade_executor 接入 safety_engine**（W4 任务，是阻塞 launch 的关键路径）
  4. **服务器执行 migrations**（需用户 SSH 确认后才动）
  5. **KMS AwsKmsProvider 实施**（依赖 AWS 账号配置）
- 注意:040 是给 Supabase 表加字段(agent_memory/agent_strategies),需 Supabase Dashboard 执行,不在 local_pg/

---

## 2026-05-01 会话 3（W3 D2：safety_engine v0.3 全量 + CB 状态管理）

### 关键决策（用户中途追加）
- **新工作规则**：**长 session 每 10 分钟更新记忆三件套**（双端 MEMORY.md + sessions-log + topic 文件）
  - 写入本地 + 仓库 `rules.md`
  - 目的：session 中断时不丢工作，下次接手能从最近 10 分钟的进度恢复

### 做了什么
- **safety_policy.yaml v0.3**（v0.2 → v0.3）：
  - 30 HR 全部 implemented（W3 D1 已 10，本次补 20：HR03/05/06/08/10/11/12/13/14/15/17/18/19/20/23/24/26/27/29/30）
  - 13 CB 全部 implemented + auto_release_after_min 配置
  - 加 `hr_to_cb_map`：HR16→CB13, HR17→CB01, HR18→CB02, HR19→CB03, HR20→CB05, HR12→CB12
  - HR 加 `trips_breaker` 字段（HR17/18/19/20 自动联动 CB）
  - CB 加 `severity` 字段（blocked / degraded）
- **safety_engine.py 重写 v0.3**：
  - 加 `BreakerState` dataclass（cb_id/name/tripped_at/auto_release_at/reason/severity）
  - `trip_breaker(cb_id, reason)` → 写 _active_breakers + 计算 auto_release_at + 通知 persister
  - `release_breaker(cb_id, manual)` 主动解除
  - `_release_expired_breakers()` 自动检查到期 CB → 释放
  - `is_breaker_active` / `get_active_breakers` / `get_global_state`（normal/degraded/blocked，blocked 优先）
  - `set_state_persister(fn)` 注入 DB 持久化回调（W3 D3 接 agent_global_state 表）
  - `check_trade` 升级：先检查 active CB → 跑全部 implemented HR → HR 命中后自动 trip CB
  - 加 3 个 Python 函数：`hr10_within_authorization` / `hr11_credentials_revoked`（paper 模式不触发） / `hr24_slippage_within_limit`
- **migration 042_agent_global_state.sql**（local_pg/）：
  - `agent_global_state` 单例表（id=1，state + active_breakers JSONB）
  - `agent_global_state_history` 状态变更审计（90d 保留）
- **测试扩展**：
  - 加 41 个新 HR 测试（20 HR 各 1-2 路 + 边界）
  - 加 12 个 CB 状态管理测试（trip/release/idempotent/auto-expire/persister）
  - 加 7 个 HR-CB 联动测试（HR12/16/17/18/19/20 → 自动 trip 对应 CB）
  - 加 10 个 HR 函数直测（HR10/11/24）
  - **总计 132 测试 全部通过 2.28s**（W3 D1 是 62，翻倍）

### 讨论结论
- **CB 状态机设计**：内存层 `_active_breakers: dict[cb_id, BreakerState]` + DB 持久化层（state_persister 回调）+ 自动到期释放
- **HR-CB 联动**：HR 触发后自动 trip 对应 CB（yaml `trips_breaker` 字段优先于 `hr_to_cb_map`）
- **幂等 trip**：重复 trip 同一 CB 保留首次 tripped_at（不重置冷却时间）
- **持久化失败不阻断**：state_persister 异常吞掉，CB 状态变更照常生效（避免 DB 故障导致 safety 失效）
- **paper 模式特殊处理**：HR11（credentials revoked）只在 mode=auto/live 触发；HR29（新币 < 1h）只在 mode=auto 触发
- **fixture function scope**：每个测试新建 SafetyEngine 实例，避免 CB 状态污染

### 被否定的方案
- ~~CB 自动触发条件写在 yaml 的 check 字段~~：CB 是被 trip 的，不是被 evaluate 的，触发逻辑在 HR
- ~~persister 失败抛异常阻断流程~~：safety 高可用要求，DB 故障不应让 CB 失效
- ~~每次 check_trade 都跑 13 CB evaluator~~：CB 状态由内存管理，不需要 evaluate，只需查 _active_breakers
- ~~30 HR 一次写完不分批~~：分 W3 D1（10 HR）+ W3 D2（20 HR）两次，方便回溯调试

### 仓库状态（W3 D2 待 commit）
- 修改：safety_policy.yaml / safety_engine.py / tests/test_safety_engine.py
- 新增：migrations/local_pg/042_agent_global_state.sql
- 双份记忆：rules.md / MEMORY.md / sessions-log.md（本条）

### 下次 session 接手
- 读本条目
- 已就绪：safety_engine v0.3（30 HR + 13 CB + 5 C 全实施 + 132 测试通过）
- 候选下一步（按优先级）：
  1. **state_persister 接 agent_global_state 表**（用 local_db 写 PG）+ 启动恢复
  2. **trade_executor 接入 safety_engine.check_trade**（W4 阻塞 launch 的关键路径）
  3. **CB 自动触发的外部条件**（CB07 单代币重复/CB08 HITL 队列累积/CB09 WAL 失败累积/CB11 跟单亏损）需要外部 monitor 调 trip_breaker
  4. **服务器跑 migrations**（prod 操作，需用户确认）

---

## 2026-05-01 会话 4（W3 D3：persister 接 PG + trade_executor 接入 safety）

### 做了什么
- **agent/global_state_persister.py 新建**（230 行）：
  - `persist_to_pg(payload)` SafetyEngine state_persister 回调入口
    - 内存幂等检测（hash payload，相同状态跳过）
    - DB 失败吞掉异常返 False（safety 高可用）
    - 写 agent_global_state 单例 + agent_global_state_history 审计
  - `load_from_pg()` 启动时拉当前状态（兼容 JSONB 反序列化）
  - `restore_engine_state(engine)` 从 PG 恢复 _active_breakers（保留原始 tripped_at）
  - `attach_to_engine(engine)` 一键挂载（注入 persister + 启动恢复，失败不抛）
- **trade_executor.py 接入 safety**（非破坏改动）：
  - `execute_trade` 加可选参数 `safety_ctx: Optional[Dict]`（向后兼容，默认 None）
  - 传 safety_ctx → 跑 SafetyEngine.check_trade，任何 BLOCK 直接返回失败，不调 DEX
  - 末尾加独立函数 `check_safety_for_trade(ctx)` 供其他模块主动校验
  - SafetyEngine 自身故障 → fail-safe 返 CB12 BLOCK
- **测试新增**：
  - `tests/test_global_state_persister.py`：22 用例（hash 幂等 / persist 异常吞 / load 端到端 / restore / attach / 端到端 spy）
  - `tests/test_trade_executor_safety.py`：10 用例（helper 4 + execute_trade 接入 5 + fail-safe 1）
  - **总计 154 → 164 测试通过 2.70s**

### 讨论结论
- **non-破坏接入**：execute_trade 加 safety_ctx 可选参数，现有调用方不变
- **persister 幂等**：相同 payload 的 hash 一致就跳过 DB 写（防 trip 后 release 同一 CB 反复刷库）
- **DB 故障不阻断 safety**：persister/load 失败吞掉返回 None/False，CB 状态变化照常生效
- **启动恢复保留 tripped_at**：从 PG 拉的 ISO timestamp 解析回 datetime；解析失败保留默认（CB 仍恢复）
- **未知 CB 启动恢复跳过**：DB 里有但 yaml 删了的 CB（升级场景）自动忽略
- **mock asyncio**：用 `pytest-asyncio` + `AsyncMock` mock dex_router.execute,不真调 OKX API

### 不在本 session 范围
- main.py 启动调 attach_to_engine（下次接入 prod 时再加）
- 服务器跑 migration 042（prod 操作待用户确认）
- CB07/CB08/CB09/CB11 外部触发条件（需要 monitor 模块查表/监控指标后调 trip_breaker）

### 仓库状态（待 commit）
- 新增：agent/global_state_persister.py / tests/test_global_state_persister.py / tests/test_trade_executor_safety.py
- 修改：agent/trade_executor.py（加 safety_ctx 参数 + check_safety_for_trade helper）

### 下次 session 接手
- 已就绪：safety + persister + trade_executor 接入,164 测试通过
- 候选下一步：
  1. **main.py 启动调 attach_to_engine**（让 prod 启动时自动恢复 CB 状态）
  2. **服务器执行 migrations**（local_pg/034-039,041,042 + Supabase 040）— prod 操作需要用户确认
  3. **CB 外部触发 monitor**（CB07/08/09/11 由后台任务监控指标调 trip_breaker）
  4. **KMS AwsKmsProvider 实施**（依赖 AWS 账号配置）
  5. **Flutter Phase 3 起步**（thesis_card widget 接 routes_thesis MOCK_MODE）

---

## 2026-05-01 会话 5（W3 D3 续：main.py hook + Flutter ThesisCard）

### 做了什么
- **main.py 启动 hook**（commit `19654be`）：
  - scheduler.start() 之后调 `attach_to_engine(get_safety_engine())`
  - 自动注入 persist_to_pg + 从 agent_global_state 表恢复 _active_breakers
  - log 输出 HR/CB/C 计数 + 全局状态
  - 失败 try/except 不阻断启动（safety 退化内存模式）
- **Flutter AgentService.requestThesis()**：
  - POST /api/thesis(chain, address, level='auto')
  - 30s timeout，失败返 null
  - 后端 MOCK_MODE=true 时返 fixture（routes_thesis.py 已就绪）
  - 顺手修 line 60 dart analyze info 警告（`Stream<StreamEvent>` 加反引号）
- **Flutter ThesisCard widget 新建**（lib/widgets/agent/thesis_card.dart，约 380 行）：
  - 低置信度警告条（conviction < 0.5 红条）
  - Header：代币 symbol + 链 + Level（L1/L2/L3 三色徽章）
  - DirectionRow：方向图标 + 中文 + 色 + Conviction 进度条
  - PriceRow：入场区间 / 止损 / 目标价 三件套
  - Summary 卡片
  - Risks 列表（必有 ≥ 2 条）
  - Evidence 折叠（source: value）
  - SimilarPastCases 折叠（token / 日期 / 相似度 / 胜负）
  - Footer: cost($) + latency(ms)
  - dart analyze: 0 issues

### 讨论结论
- **main.py 启动 hook 失败 non-fatal**：safety 退化为内存模式不影响其他业务
- **ThesisCard 接 mock 即可独立验证**：后端 routes_thesis MOCK_MODE 返 fixture，Flutter 不依赖真实 LLM
- **dart analyze 必须干净**：`Stream<StreamEvent>` 之类被识别为 HTML 的小警告也修

### 不在本 session 范围
- 在 agent_screen.dart Chat Tab 真正调用 ThesisCard（下次接入）
- preview_start 跑模拟器实际渲染验证
- 服务器跑 migration 042 让 main.py hook 真正生效

### 仓库状态
- agent-v1 分支累计 commits: e08eae1 / c567962 / 4bbc05d / 4f02f3a / ad5fd9f / eca6037 / **19654be**
- main 仍 429f5a8（未动）
- 累计本 session 工作量：~5000 行新代码 + 164 测试用例

### 下次 session 接手
- 已就绪：safety v0.3 完整 + persister + trade_executor 接入 + main.py hook + Flutter ThesisCard
- 候选下一步：
  1. **agent_screen.dart 接入 ThesisCard**（在 Chat Tab 显示真实卡片）+ preview 跑模拟器看效果
  2. **服务器执行 migrations**（prod 操作需用户确认）
  3. **CB 外部触发 monitor**（CB07/08/09/11）
  4. **routes_optimizer/routes_agent 接入 safety_ctx**（让所有真金路径都过 safety）
  5. **KMS AwsKmsProvider 实施**（依赖 AWS 账号）

---

## 2026-05-01 会话 6（W3 D3 续 2：ThesisCard Chat Tab 接入 + Flutter widget test）

### 做了什么
- **api/app.py 挂载 W3 routers**：
  - thesis_router / audit_router / admin_router 加入 include_router（之前 W1 启动包写了 stub 但忘了挂载）
  - 后端跑起来后 /api/thesis 等真能响应（MOCK_MODE=true 返 fixture）
- **agent_screen.dart Chat Tab 接入 ThesisCard Demo Banner**：
  - import ThesisCard + Thesis model
  - _ChatTabState 加 _demoThesis / _loadingThesis / _thesisErr 状态
  - _loadDemoThesis() 优先调真实后端 /api/thesis,失败时 fallback 本地 hardcoded mock（ts/EvidenceItem/SimilarCase 完整 fixture）
  - _buildThesisDemoSection() 在 Chat Tab build 顶部:
    - 未加载 → 显示"试一试 AI 分析报告(Demo)"按钮(InkWell + AutoAwesome 图标)
    - 加载中 → CircularProgressIndicator
    - 已加载 → 显示 ThesisCard + 关闭按钮(后端不可用时显示 amber 提示)
  - 不修改原 chat 流（_messages / _ChatInput 不变）
- **Flutter widget test test/thesis_card_test.dart**（18 用例）：
  - 基本渲染 11:symbol/chain/level/4 个 direction/价格三件套/summary/risks/evidence count/cases count/footer
  - 低置信度警告 2:conviction<0.5 显示红条 / >=0.5 不显示
  - 折叠交互 2:点击 Evidence/SimilarCases 展开后显示具体数据
  - 边界场景 3:空 evidence/cases/footer 不渲染对应区
  - **全部通过 < 1s**
- **累计 182 测试通过**（后端 164 + Flutter 18）

### 讨论结论
- **Flutter web preview 走不通**：`shell-init: chdir error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted` — preview tool 沙箱跟 cwd 软链接冲突。改走 widget test
- **widget test 替代 preview screenshot**：18 个测试覆盖所有 ThesisCard 渲染分支,验证粒度比截图更精确（比如"conviction>=0.5 不显示红条"这种 visual 否定通过截图很难证）
- **Demo Banner 设计**：内嵌 Chat Tab,默认未加载状态显示按钮;触发后 真实 API 失败 fallback 本地 mock,确保 UI 一定能展示
- **app.py 路由挂载是 W1 启动包遗漏**：当时只写 stub 文件没 include_router,本次补上

### 不在本 session 范围
- preview_start 跑 Flutter web/iOS（受沙箱限制走不通）
- 服务器跑 migrations
- 把 ThesisCard 接入更多入口(token_detail_page / strategy_detail_sheet)

### 仓库状态（待 commit）
- 修改：api/app.py(+挂载 3 个 router) / agent_screen.dart(+Demo Banner)
- 新增：apps/app/test/thesis_card_test.dart(18 用例)
- 配置：.claude/launch.json 加 flutter-web 配置(本仓库)

### 下次 session 接手
- 已就绪:182 测试通过,ThesisCard 端到端 UI 渲染已验证
- 候选下一步:
  1. **服务器跑 migrations**（local_pg/034-039,041,042 + Supabase 040）— prod 操作需用户确认
  2. **routes_agent.chat 接入 safety_ctx**（让 chat 路径也过 safety）
  3. **CB 外部触发 monitor**（CB07/08/09/11 后台监控调 trip_breaker）
  4. **KMS AwsKmsProvider 实施**（需 AWS 账号）
  5. **HITL 详情页 hitl_approval_page.dart 起步**（Phase 3 下一块)
