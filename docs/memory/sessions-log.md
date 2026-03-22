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

### 被否定的方案
- ~~Blockchain.com WS 实时大额转账~~：消息量太大，改用 REST 4h 轮询
- ~~Portal 展示价格/指标~~：看板目标是监控信号质量，不是再做一次行情展示
- ~~30s Agent 超时~~：不够用，改 90s
