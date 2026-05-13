# 踩坑记录

## 资金安全 — 不可不审清单(R59 audit 揭露)
- **local_db._get_conn() autocommit=True 全局 pool**:多步 SQL 必须用 `_Tx` context manager 临时切 autocommit=False(`credit_service.py` 模板)。R57 漂复现过
- **tx_hash 必须 app 预检 + DB UNIQUE 双防**:RPC re-org / cron 重叠 → 同 tx_hash 双处理。UNIQUE INDEX (chain, chain_tx_hash) WHERE status='confirmed'
- **trade broadcast retry 必须 idempotency key**:request_id `f"{strategy_id}-{event_id}-{side}-{int(amount*100)}"`,float 用 `int(round(*100))` 防精度
- **dex_router pre-resolve 失败必须 fail-fast**:子路径 `_resolve_wallet()` 无 user_id 会落到 DEV_WALLET 替用户签。execute() user_id 在但 resolve 返空 → 返失败,子路径直接用入参
- **position_monitor 必须 atomic claim**:K8s 双进程 `_selling` set 不共享 → 双 SL/TP。`UPDATE status='closing' WHERE status='confirmed'`,0 行=已被 grab
- **strategy endpoint 必须 owner check**:R59 发现 /performance/{id} + /backtest + /rename 全漏过

## agent_executions.status 取值约定
`pending` / `submitted` / `confirmed`(open 持仓!) / `closing`(R59 atomic 中间态) / `closed` / `failed`
load_positions 拉 `status='confirmed'+action='buy'` 视为 open — 不是 'open',容易写错。

## 多 user SaaS 架构 vs 单 user toolkit 心智
- **WorkingMemory 是进程单例 deque(maxlen=200,跨所有用户)**: `agent/memory/working_memory.py:18` 没 user_id 字段,所有用户混在 200 条 deque,**进程重启 wipe**。R58 撤前端暴露面。要多 user 用 → 加 user_id 索引 + 持久化
- **SemanticMemory.get_all_active() 不 filter user_id**: `routes_agent.py:1057` 返所有用户规则。R58 撤前端暴露面
- **Flutter endpoint 路径错静默返 {}**: `agent_service.dart` 用 `try/catch (_) { return {}; }` 吞 404 — UI 永远显 0。R58 发现 `/api/agent/performance` 路径错(后端只有 `/performance/{strategy_id}`)。新 endpoint 前后端路径必须对齐

## Credit Service / DB
- **credit_transactions.type CHECK 约束**: 允许 `{recharge, consume, adjust, refund}`,**不接受 `admin_grant`**。给用户记入式增值用 `source_type='adjust'`
- **add_credit 失败时 UPDATE 已 commit**: 先 UPDATE user_credits 后 INSERT credit_transactions;若 INSERT 失败 throw,user_credits 仍 +N(脏数据)。**重试前先回滚或检查 balance**,否则 +N 两次。R57 给创始人 $200 翻车 balance $400 手动 SQL 改回
- **add_credit 没 ref 参数**: 签名只有 `(user_id, amount, source_type, note=...)`,传 `ref=...` → TypeError

## Flutter — 开发期 Demo 残留
- **W3 D3/D4/D5 demo banner 不要进生产**: Agent 屏顶部"试一试 X (Demo)" 是开发自测脚手架,CEO/PM 视角 = 不专业。R57 全删
- **Face ID 占位 + 文本框签名**: HITL 审批弹"输入任意字符串当签名"是 placeholder,生产必须接 `local_auth` + 钱包真签

## Python
- **Python 3.9**: 不支持 `X | None`，用 `Optional[X]` / `List[str]`
- **dict.get(key, fallback) 不防 None**: `d.get("k", default)` 如果 key 存在但值为 None，返回 None 而非 default。用 `d.get("k") or default`
- **零交易代币内存泄漏**: `if trades:` 跳过空列表，导致无交易代币永不驱逐。改为 `if not trades: evict`
- **load_dotenv(override=True)**: 防 shell profile 空变量覆盖 .env
- **sync API 阻塞 async 循环**: 用 `asyncio.to_thread()` 包装同步调用（如 Anthropic SDK）
- **ON CONFLICT DO UPDATE 重复行**: 同批次有相同约束键 → 用 `seen_keys: Set[tuple]` 先去重

## Flutter / Dart
- **withOpacity 弃用**: 改 `withValues(alpha: ...)`
- **TabBarView 状态丢失**: 需 `AutomaticKeepAliveClientMixin`
- **Navigator pop 后 context 失效**: pop 前用 `Navigator.of(context)` 拿 nav，pop 后只用 nav
- **JS `|| null` 误杀零值**: 涨跌幅/价格为 0 时被当 falsy，改用 `?? null`
- **substring 越界**: 先检查 `length >= n` 再截取

## Flutter i18n
- **flutter gen-l10n 单独运行无效**: 显示 "l10n.yaml overriding" 但不生成文件，需 `flutter pub get` 触发
- **const 与 S.of(context) 冲突**: `Tab(text: S.of(context).xxx)` 不能是 const，必须移除 const 关键字
- **initState 中无 BuildContext**: `_load()` 在 initState 调用时不能用 S.of(context)，改用 flag + build() 中解析
- **Model 层 i18n 陷阱**: Model getter 不应返回本地化字符串（无 BuildContext），应返回 raw key/enum，由 UI 层解析
- **locale_provider 必须校验**: SharedPreferences 可能存入非法 locale code，load() 需 `supportedLocales.any()` 验证
- **notifyListeners 异步延迟**: setLocale 中先 await 再 notifyListeners 会导致 UI 延迟，应立即 notifyListeners 再异步持久化
- **localeResolutionCallback**: 不设置时 fallback 取决于 supportedLocales 列表顺序，应显式回退到英文

## OKX API
- **web3.okx.com Cloudflare 403**: 必须加 `User-Agent: Mozilla/5.0`
- **transactions-by-address 参数**: 用 `chains=`（List），不是 `chainIndex=`
- **Wallet API 响应结构**: `data[].transactionList[]`，不是 `data[].tokenTransferDetails[]`
- **OKX Market API 需白名单**: Aggregator/toplist/candles 可用，price-info/basic-info 返回 code:-1
- **OKX toplist 429**: SOL WS 高频触发 → 每链 10s 冷却（`_okx_toplist_cooldown=10.0`）
- **禁止用 www.okx.com**: Wallet API 必须用 `web3.okx.com`
- **禁止用 /api/v5/wallet/post-transaction/transactions**: 需 accountId，不适合任意钱包监控

## Supabase / PostgreSQL
- **Supabase DDL**: 只能 Dashboard SQL Editor 手动执行，代码里无法自动运行
- **PostgREST FK join**: 无直接 FK 需通过中间表嵌套
- **Agent DEV_USER_ID 必须合法 UUID**: `00000000-0000-0000-0000-000000000001`

## 交易 / EVM
- **EVM nonce 必须动态获取**: hardcode 0 只对首笔交易有效，后续全败
- **EVM tokentx 返回代币数量非 USD**: 需乘以 price_usd 转换
- **to_amount 精度**: 从 OKX 响应 `toTokenDecimalNum` 动态获取，不可 hardcode 6

## Portal
- **Portal 热币日榜"加载中"**: 今天无数据正常（UTC 02:00 生成），切历史日期验证
- **DexScreener 限速**: 批量 30 个/批，30s 轮询较安全
- **Portal 部署在 apps/portal（不是 apps/web）**: systemd WorkingDirectory 必须指向 apps/portal
- **Portal Vercel 弃用**: 构建不稳定，已迁移到服务器 systemd + nginx

## Portal / 表现追踪
- **daily_highs key 格式不一致**: 后端写 `"D0"/"D1"` 格式，前端读 `"0"/"1"` → 用 `highs["D${d}"] ?? highs[String(d)]` 兼容
- **token_performance source 类型**: 旧日榜用 `"hot"`，新实时入榜用 `"hot_live"`，查询时用 `"hot_all"` 合并两者

## 聪明钱评估
- **旧胜率定义太宽松**：代币毕业或2x才算赢 → 改为72h内涨20%+
- **余额维度查链上不可行**：1506地址×4链 RPC 调用量太大 → 用单笔交易规模替代
- **6h评估太慢**：MEME 场景需要更快反应 → 改 2h
- **Dune LIMIT 500 全是 bot**：70K+笔/14天全是 MEV bot，需 BETWEEN 30 AND 5000 过滤
- **Dune 免费版不能 API 创建查询**：需在网页创建，用 API 执行/获取结果
- **Helius Webhook 免费版额度有限**：创建可能 429（max usage reached），回退 WS 模式
- **Helius WS 500 订阅打爆限流**：500 个 accountSubscribe 触发 429，降至 100 + 指数退避
- **nginx sed 插入 location 块失败**：`\n` 被字面插入，应用 heredoc 重写整个配置文件
- **Supabase 默认 limit 1000**：`_load_wallets` 只加载 1000 个，16623 个钱包丢失 94%。必须分页 `.range(offset, offset+999)`
- **DEX 程序监控优于钱包监控**：监控 5 个 DEX 程序 = 覆盖所有钱包的 swap，而监控 16000 个钱包 = 429 限流

## Supabase 免费版存储优化
- **token_trades 每天 20 万行**：13 天积累 130 万行，接近 500MB 上限。必须保留 ≤3 天
- **Supabase DELETE 大量数据超时**：直接 DELETE 70 万行会 statement timeout。必须分批（500 行/批 + sleep 0.3s）
- **pump_tokens 外键约束**：删除前必须先删 token_outcomes + token_snapshots + token_trades 中引用该 mint 的行
- **hot_coins DB_THROTTLE_INTERVAL**：5s 太频繁（每天 8800 次写入），改 15s（减少 66%）
- **btc_eth_indicators 每 5min 写入**：每天 576 行，可接受不需优化

## Agent 交易
- **trigger_count TOCTOU 竞态**：read-modify-write 并发丢失计数 → 改用 Supabase RPC 原子递增
- **LLM Parser 无重试**：Claude API 429/5xx 直接返回 None → 加 3 次指数退避重试
- **硬编码参数散落各处**：修改需改代码重启 → 统一到 config.py 从 .env 读取
- **btc_eth_indicators 写入失败静默**：snapshot 含 DB 不存在的列名 → 白名单过滤 + 日志
- **Paper Trading SL/TP 不检查**：check_exits 存在但未被定时调用 → 加 60s 循环

## KOL 采集
- **Twitter API 402 Credits Exhausted 疯狂重试**：额度耗尽后 212 KOL × 3 重试 = 每轮 636 条错误日志。必须设 `_credits_exhausted` flag，402 后立即停止整轮采集

## BTC/ETH 模块
- **Blockchain.com WS unconfirmed_sub 阻塞事件循环**: 每秒推送数百笔未确认交易，json.loads 全部解析导致 asyncio 过载，FastAPI 完全无响应。必须禁用或用 REST 替代
- **Binance WS 合并 stream**: 6 个 stream 用 1 个连接（`/stream?streams=a/b/c`），避免多连接

## iOS App Store / Xcode 签名
- **命令行 archive 跳过签名不可行**: `CODE_SIGNING_REQUIRED=NO` 产生的 archive 无 team 信息，Distribute 报 "No Team Found in Archive"
- **Xcode 自动签名需注册设备**: 无注册设备时无法创建 Development provisioning profile → 改用手动创建 App Store Distribution profile
- **iOS ATS 阻止 HTTP**: 默认 App Transport Security 阻止明文 HTTP，模拟器不受限但真机/审核会失败 → Info.plist 添加 `NSAllowsArbitraryLoads=true`
- **App 名称唯一**: App Store Connect 上 "AI Trading" 已被占用，需换名
- **Flutter 默认 icon**: 新项目自带 Flutter logo，Apple 审核会拒绝，必须替换

## Anthropic SDK / Optimizer
- **anthropic SDK v0.18.1 不兼容**: `Anthropic()` 构造函数报 `proxies` 参数错误，必须升级到 >=0.80
- **token_snapshots 无 score/social_score 列**: backtest/tools 查询不能 SELECT 这些列，用 `*` 或只选存在的列
- **run_optimization 阻塞事件循环**: 同步 Claude API 调用会阻塞 asyncio，必须 `asyncio.to_thread(run_optimization)`
- **systemd restart 时 optimizer stuck run**: SIGTERM 超时后 SIGKILL 产生 status=running 的孤儿记录，需手动标记 failed
- **nginx 需随 pump-scanner 重启**: pump-scanner 重启后 nginx 有时无法转发请求，需一起 `systemctl restart nginx`
- **Claude API 429 rate limit**: Opus 4.6 有 30K input tokens/min 限制，tool result 截断到 15K chars + 重试退避

## 2026-04-30 线上错误（堆积中，非致命）
- **`token_trades` 主键重复 ON CONFLICT**: 同批次有相同 id 没去重，error code 23505 → 用 `seen_keys: Set[tuple]` 先去重（前面已记但代码未彻底修，每隔几分钟仍在刷错误）
- **`btc_eth_indicators` 整数列写入小数**: error `invalid input syntax for type integer: "472688.0"`，列名白名单未覆盖 `volume_24h_usd` 等浮点列。**BTC/ETH 指标完全没在持久化**，需要扩白名单或显式 int() 转换
- **`daily_picks ↔ pump_tokens` PostgREST FK schema 找不到**: error `Could not find a relationship between 'daily_picks' and 'pump_tokens' in the schema cache`，performance_tracker 初始化失败，daily_picks 这条表现追踪链路没在跑（实时信号池 _signal_pool 仍正常）

## macOS / Linux 工具差异
- **macOS `sort` 是 locale-aware**: 跨机器 SHA1 哈希列表对比时，macOS sort 默认按 locale 排序，Linux sort 按字节序，会导致**对齐错位被误判为内容差异**。必须 `LC_ALL=C sort` 强制字节序才能真实 diff（实际遇到：首次 diff 报 47 个差异，加 `LC_ALL=C` 后只剩 1 个真差异）
- **macOS `shasum -a 1` vs Linux `sha1sum`**: 输出格式都是 `<sha>  <filename>`，直接 diff 可以，但前提是排序一致（见上条）

## pump-scanner systemd 重启 8000 不 LISTEN（2026-05-01 W3 D4 部署遇到）
- **现象**：任何 `sudo systemctl restart pump-scanner` 后，服务 active running，scanner/EventBus/smart_money/btc_eth/regime_detector 等 task 都跑（看 journalctl 一直有 httpx 请求），**但 FastAPI on 8000 永远不 LISTEN**。日志显示 `[INFO] api.app: Starting API server on 0.0.0.0:8000` 后**不再有 uvicorn "Application startup complete" / "Uvicorn running on" 等行**。
- **不是 agent-v1 的 bug**：回滚到 main 分支（`f7dc9fd`）同样症状
- **手动 dry-run uvicorn OK**：`python3 -c 'from api.app import start_api_server; await start_api_server(port=8005)'` 能成功 LISTEN on 8005，说明代码本身正确
- **首次启动（系统冷启）8000 LISTEN 成功**：之前 15:01:55 启动后 50 min uptime 内 8000 OK；问题在 systemctl restart 后才出现
- **猜测根因**：main.py 用 `asyncio.create_task(start_api_server(port=8000))` 创建 FastAPI task，但 `await scanner.run()` 之前的某些 task（SmartMoneyTracker WebSocket / EventListener / BTC/ETH manager 等）在 event loop 中持续抢占，uvicorn task 拿不到 cooperative yield 去 socket bind 8000
- **回避**：暂只能依赖系统冷启时正确启动，不要轻易 restart pump-scanner；真要重启用 `sudo reboot` 整机（70s 恢复）
- **失败的修复尝试（commit `c4ae116`）**：在 main.py 加 grace period 循环 `await asyncio.sleep(0.5)` × 20 + `asyncio.open_connection` 探测 socket。**冷启动时 work**(看到 `FastAPI on port 8000 ready` 日志,1s 即就绪);**但 systemctl restart 时无效**,event loop 在 `Starting API server on 0.0.0.0:8000` 后完全卡死。证明根因是 SmartMoneyTracker 启 8943 SOL + 15631 EVM WebSocket / EventBus 等持续抢占 event loop,uvicorn task 永远拿不到 socket bind 时机
- **✅ 已修复(2026-05-01,commits `03d9cd1` + `660f4dc`)**:走候选 3 — 独立 uvicorn systemd service:
  - 新 `services/pump-scanner/api_server.py`(独立入口,只跑 uvicorn)
  - 新 systemd unit `pump-scanner-api.service`(独立 process,跟 scanner 不共享 event loop)
  - 改原 `pump-scanner.service` 加 `Environment=ENABLE_API=false`(scanner 不再启 FastAPI)
  - **5 次 restart pump-scanner 后 8000 始终稳定;3 次同时 restart 两个服务都秒恢复**
  - **遗留**:`_signal_pool` 在 scanner 主进程内存,api 独立进程读不到 → 走文件 IPC(commit `660f4dc`):main.py `_dump_signal_pool_loop` 每 60s 写 `/tmp/pump_signal_pool.json`,routes_pump 读这个文件。最多 60s 延迟,Flutter 30s 轮询场景可接受
  - **下次再优化方向**:Redis pub/sub 做毫秒级 IPC / scanner 落 _signal_pool 到独立 DB 表

## asyncio.create_task 在 event loop starve 时不可靠（2026-05-01 W3 D5 修 Redis IPC 时发现）
- **现象**:`asyncio.create_task(_dump_signal_pool_loop())` 跑一次后 await sleep(5),**第二次永远不被调度回来**。Redis 只 set 了一次,TTL 过后再无数据
- **诊断**(py-spy dump):MainThread 卡在 `start_api_server` 的 uvicorn import lock(websockets/protocols);asyncio_0 thread 跑 sklearn HMM `train` (CPU bound)
- **根因**:主 event loop 被 SmartMoneyTracker WebSocket 重连 + EventBus 高频 + 13 collector + sklearn 子线程占着 GIL 多重夹击,sleep 后再不会 yield 回 dump task
- **解决**:轻量 IO 任务用 `threading.Thread + time.sleep` 绕开 event loop,scanner.get_signals() 是同步内存读,线程安全
- **教训**:不要假设 asyncio.sleep 一定会被准时唤醒;主 loop 拥挤时 task 会无声 starve,且没异常
- **诊断工具**:`py-spy dump --pid <PID>` 立刻能看到所有线程当前栈

## .env 文件 ENABLE_API=true 覆盖 systemd Environment=ENABLE_API=false（2026-05-01 W3 D5 部署遇到)
- **现象**:`/etc/systemd/system/pump-scanner.service` 设了 `Environment=ENABLE_API=false`,但 `systemctl show` 也显示 false,**main.py 实际跑出来 ENABLE_API 仍是 true**(日志看到 `FastAPI server starting on port 8000`)
- **根因**:`/opt/agent-trading/services/pump-scanner/.env` 文件里有 `ENABLE_API=true`,python-dotenv 加载顺序高于 systemd Environment(`load_dotenv()` 在 `os.getenv("ENABLE_API")` 之前跑)
- **解决**:删 .env 里这一行,或者改成 `ENABLE_API=false`(我用了后者,加了 .bak 备份)
- **后果**:pump-scanner 主进程仍想启 FastAPI,跟 pump-scanner-api 进程抢 8000 端口,uvicorn import 卡死,整个 main event loop 阻塞 → dump loop 不动
- **教训**:systemd Environment 不一定生效,要看代码加载顺序;改 .env 永远比改 systemd 更优先


---

## R38/R39(2026-05-04)新踩坑

### 1. 关键词预触发 hack 永远不可能完美
**症状**:为让 chat agent 调 query_top_movers,在 chat_loop / routes_agent 加关键词列表(涨幅/top/pump.fun ...)。结果:
- "涨幅最高的代币" → 命中 ✅
- "学习涨幅最高代币的特征,形成策略" → 命中(但应当不命中 — 用户意图是建策略)❌
- "pump.fun 涨" → 命中 ✅
- "把这 30 个代币..." → 不命中(指代上文,实际意图查涨幅)❌

加了反向词、强意图词,仍漏召 / 误召。

**根因**:意图识别本质是 NLU 任务,关键词不是答案。

**正解**(R39 v4 已落):**Anthropic tool_use** — LLM 自己看 18 个 tool description 决定调哪个。
- `messages.create(tools=ALL_TOOLS, ...)`,LLM 返 `stop_reason="tool_use"` 时 dispatch
- 完全不需要任何关键词预筛
- 改在 `agent/llm_parser.py`:`TOOLS = [...]` → `ALL_TOOLS = TOOLS + _get_extra_tool_specs()`(11 from registry)

### 2. workspace API key 不一致(诡异 quota error)
**症状**:Anthropic console 看 spend $0/$500(空),但 server 调 API 立刻报"workspace API usage limits reached"。
**根因**:server `.env` 里的 `ANTHROPIC_API_KEY` 属于另一个 workspace,**那个 workspace 的 limit 被设到 $0** 或满了。Console 默认显示当前 active workspace 不一定是 key 所属。
**确认方法**:`curl -H "x-api-key: $KEY" https://api.anthropic.com/v1/messages -d ...`,看 error 详情;Console → API Keys 页看每把 key 关联哪个 workspace。
**解决**:在有额度的 workspace 创建新 key,替换 server `.env` 的 ANTHROPIC_API_KEY,restart pump-scanner-api。

### 3. Google Fonts 国内 build 时常拉取失败
**症状**:`next build` 报 `Failed to fetch 'Inter' from Google Fonts` / `module-not-found inter_xxxxx.module.css`。
**原因**:`fonts.googleapis.com` 国内不稳。
**解决**:layout.tsx 删 `next/font/google`,改用系统字体栈 `Inter / PingFang SC / SF Mono` (在 globals.css `--font-sans` / `--font-mono` 直接配)。视觉影响极小(中文字仍是 PingFang SC,英文字 macOS/iOS Safari 自带 Inter)。

### 4. iOS 26.2 simulator + Flutter `objective_c` framework 路径错
**症状**:`flutter run` 装到 iOS 26.2 模拟器后,App 启动炸:
`Failed to load dynamic library 'objective_c.framework/objective_c': RuntimeRoot + objective_c.framework 拼接错(缺斜杠)`
**根因**:Flutter SDK 跟 iOS 26.2 simulator runtime 的 dlopen 路径有 bug,Pods 重生成时 framework signing 拷错。
**解决**:`brew reinstall cocoapods` + `LANG=en_US.UTF-8 pod install`(不加 LANG → Ruby 4.0.1 unicode normalize ASCII-8BIT 兼容错误)。然后 `flutter run` 通。

### 5. scp 反复卡(stale processes 抢带宽)
**症状**:scp 845KB 文件卡在 255KB 不动,重 scp 也卡。
**根因**:之前失败的 scp / sshpass 进程 zombie 状态没退,占着 SSH 连接。
**解决**:`killall -9 scp sshpass` + 找剩下的 zsh wrapper PID `kill -9` + 等 2-3s + 新 scp 立通。
**预防**:用 `TaskStop` 真停 background task,不要只关 stdout 假以为停了。

### 6. Process bug:"模块 ready, integration missing" 反复犯
**症状**:R36 audit 早标了"chat_loop 没接 tool_use",R37 P0 punch list 没修,R39 v1 关键词 hack 又是 patch,直到 v4 才真根因。Memory 4 层、cost_guard、input_filter、prompt_loader 等都是同样问题:**模块按文档做了,但产品最关键入口(chat endpoint)没接**。
**根因**:Eval L1 Tool 测的是"tool 自己能跑"(单元),L2 Skill 测"Skill 整合 tools",**但没有 end-to-end 测试"用户在 chat 框打字 → LLM 真调到 tool"**。
**预防**:每加新 tool / 模块 → 必须立刻验证 "在 /api/agent/chat 实测真能调到 / 真生效"。这条加 dev process 强制。
**audit 截止 2026-05-04**:8 项集成 7 项没接,详见 docs/agent-pm/IMPLEMENTATION-AUDIT.md + plan R39 v5 段。
