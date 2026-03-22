# 踩坑记录

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
