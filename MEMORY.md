# AiTrading — 项目记忆文件
> 此文件存于 GitHub 仓库根目录，任何设备、任何会话加载后即可了解项目全貌。
> 最后更新：2026-03-08

---

## 项目概述
AI驱动的加密交易平台，核心能力：实时行情 + AI信号 + 自动化策略 + DEX执行。

**GitHub 仓库：** https://github.com/meiyaobuyao123-hash/Agent-Trading
**本地路径：** /Users/wenruiwei/Desktop/Agent-Trading
**参考文档（本地）：** /Users/wenruiwei/Desktop/Aitrading100/
  - `product-prd.html` — 完整产品需求文档
  - `tech-architecture.html` — 技术架构文档
  - `binance-vs-okx-report.html` — API实测对比报告

---

## 三端架构

| 端 | 框架 | 路径 | 端口 | 状态 |
|----|------|------|------|------|
| Web用户端 | Next.js 14 | apps/web | 3000 | 🟢 Phase 2 开发中 |
| Admin后台 | Next.js 14 + Ant Design | apps/admin | 3002 | 🟢 基础功能完成 |
| App移动端 | **Flutter** | apps/app | - | 🟢 Phase 1 完成 |

---

## 技术栈

### 前端
- Next.js 14 App Router + TypeScript + Tailwind CSS
- Zustand（状态）+ React Query（服务端状态）
- Lucide Icons + shadcn/ui（Web）
- Ant Design 5（Admin）
- **Flutter**（App，用户指定）

### App 设计规范（重要！）
- **交互逻辑：微信风格** — 底部最多5 Tab，功能不堆首页，导航清晰
- **视觉语言：Apple风格** — 大量留白、SF字体风格、卡片圆角、极简图标、科技感
- **禁止：支付宝风格** — 不堆功能入口、不用彩色图标矩阵、不过度营销化

### 后端（待开发）
- Node.js 20 + TypeScript（主服务）
- Python FastAPI（回测引擎，独立服务）
- BullMQ（队列，基于 Upstash Redis）

### 数据库
- **Supabase 免费版**（PostgreSQL + Auth + Realtime）— 用户指定
- **Upstash Redis**（缓存 + 队列）

---

## 共享 Packages

| Package | 路径 | 说明 |
|---------|------|------|
| @aitrading/types | packages/types | 所有 TS 类型定义（Token/Signal/Strategy/Trade/Position） |
| @aitrading/db | packages/db | Supabase 客户端封装 |
| @aitrading/api | packages/api | 通用 apiFetch 工具 |

---

## 外部 API 凭证

### Binance Skills API（无需认证，公开）
- Base URL: `https://web3.binance.com/bapi/defi/v1/public/`
- 客户端: `apps/web/lib/binance/client.ts`
- 实测延迟: avg 1242ms，抖动 466ms
- 链覆盖: ETH(1) / BSC(56) / SOL(900)
- ⚠️ 非官方 API，需监控可用性，Redis 降级兜底

### OKX DEX v6 API（需签名，服务端调用）
- Base URL: `https://www.okx.com/api/v6/dex/aggregator/`
- API Key: (见 .env)
- Secret Key: (见 .env)
- Passphrase: (见 .env)
- 客户端: `apps/web/lib/okx/client.ts`
- 实测延迟: avg 1275ms，抖动 153ms（更稳定）
- 链覆盖: 30条链，参数用 `chainIndex`（非 v5 的 chainId！）
- ⚠️ v5 已弃用（error 50050），只用 v6
- ⚠️ 签名顺序: timestamp + method + path + body

---

## 环境变量
模板文件: `.env.example`（根目录）
各 app 需创建 `.env.local`（不提交 git）

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
OKX_API_KEY=
OKX_SECRET_KEY=
OKX_PASSPHRASE=
ANTHROPIC_API_KEY=
```

---

## 开发进度

### ✅ 已完成
- [x] 产品 PRD 文档（Aitrading100/product-prd.html）
- [x] 技术架构文档（Aitrading100/tech-architecture.html）
- [x] API 实测对比报告（Aitrading100/binance-vs-okx-report.html）
- [x] Monorepo 结构搭建（apps/web + apps/admin + apps/app + packages/）
- [x] Next.js 14 Web App 初始化（暗色主题 + 路由组 + Sidebar + Topbar）
- [x] Next.js 14 Admin App 初始化
- [x] Flutter App 项目初始化（iOS + Android）
- [x] 共享 packages（types / db / api）
- [x] Binance API 客户端封装（lib/binance/client.ts）
- [x] OKX DEX v6 客户端封装（lib/okx/client.ts）
- [x] 环境变量模板（.env.example）
- [x] Binance 服务端代理 API Routes（4个：market-rank/signals/meme-rush/token-dynamic）
- [x] useMarketRank / useMemeRush / useSignals hooks（客户端请求 + 自动刷新）
- [x] TokenTable 组件（行情列表，带价格/涨跌/成交量/市值/链）
- [x] SignalCard 组件（信号卡片，带方向/信心分/触发价/标签）
- [x] 行情中心页面（/market）— 市场排名 + Meme Rush 双 Tab
- [x] 信号中心页面（/signals）— 全部/做多/做空/观察 过滤
- [x] Flutter App 完整实现（iOS 编译通过 ✅）
  - 文件结构: lib/{theme,models,services,screens,widgets}/
  - AppTheme 暗色主题（Binance 色系 + Apple 风格）
  - ApiService 调用 Web 端 Next.js 代理（localhost:3000）
  - TokenRank / SmartMoneySignal 数据模型
  - 行情页: NestedScrollView + TabBar + 链过滤 + Skeleton
  - 信号页: 统计筛选条 + 信号卡片（方向/触发价/信心分/标签）

### ✅ Phase 1 MVP 全部完成！
- [x] API Route 代理层（/api/binance/market-rank, signals, meme-rush, token-dynamic）← 解决403
- [x] Web 行情中心页面（Token 列表 + 链过滤 + Meme Rush + 自动刷新30s）
- [x] Web 信号中心页面（信号卡片 + 方向过滤 + 信心分 + 自动刷新20s）
- [x] Flutter App 完整框架（4 Tab 底部导航 + 暗色主题 + Apple风格）
- [x] Flutter 行情页（Token 列表 + 链过滤 + 下拉刷新 + Skeleton 加载）
- [x] Flutter 信号页（SmartMoney 信号卡片 + 方向/链过滤 + 信心分进度条）
- [x] Flutter 策略页（占位，Phase 2）
- [x] Flutter 我的页（钱包连接入口 + 设置项）
- [x] **Web 官方策略组合追踪页面（/portfolio）** ← 新完成
  - useOfficialPortfolio hook（Supabase + 实时价格富化）
  - GET /api/portfolio（Supabase 或演示数据回退）
  - 表格视图：入选价/当前价/P&L/状态/标签
  - 演示模式 banner（Supabase 未配置时）
  - 历史退出平均收益展示
- [x] **Supabase 数据库 migrations** ← 新完成
  - supabase/migrations/001_init.sql
  - 4张表：official_portfolio / signals / strategies / trades
  - RLS 策略 + 索引 + auto-update trigger
- [x] **Admin 基础页面** ← 新完成
  - 完整暗色主题 Admin UI（Sidebar + Topbar）
  - Dashboard：系统健康 + 服务状态 + 环境变量清单
  - 官方组合管理（/portfolio）：添加/退出/删除 CRUD + Modal
  - 信号管理（/signals）：Supabase 数据只读查看
  - API Routes: GET/POST /api/admin/portfolio + PATCH/DELETE /[id]
  - next.config.ts → next.config.js（同 web app 修复）

### ✅ Phase 2 进行中
- [x] **Flutter 生产 API URL 配置** ← 新完成
  - lib/config/app_config.dart（--dart-define=API_BASE_URL=... 注入）
  - Debug 默认 localhost:3000，Release 必须显式传入
  - AppConfig.printConfig() 在 main() 打印当前配置
  - api_service.dart 使用 AppConfig.apiBaseUrl + AppConfig.requestTimeout
  - 新增 getMemeRush / getOfficialPortfolio 接口
- [x] **Web 总览页升级**（/）← 新完成
  - 接入真实 Binance 信号 + 官方组合数据（useSignals + useOfficialPortfolio）
  - MarketSummaryBar：BSC Top6 实时行情 Ticker
  - 4 统计卡：活跃信号/做多信号/官方组合/平均P&L（全部接入真实数据）
  - 最新信号迷你列表（6条，链接到 /signals）
  - 官方组合迷你列表（6条，P&L，链接到 /portfolio）
  - 底部状态栏
- [x] **信号引擎简化版** ← 新完成
  - GET/POST /api/engine/sync-signals
  - 拉取 BSC/ETH/SOL 三链信号，按 (address, chain) upsert 到 Supabase
  - Vercel Cron: */5 * * * *（vercel.json）
  - CRON_SECRET 环境变量保护防未授权调用
  - Admin Engine 面板（/engine）：手动触发 + 同步结果展示

- [x] **策略创建 + AI 生成脚本** ← 新完成
  - GET/POST /api/strategies（列表 + 创建）
  - PATCH/DELETE /api/strategies/[id]（状态更新/删除）
  - POST /api/strategies/[id]/generate（Claude AI 生成 TypeScript 脚本）
  - 策略列表页（/strategy）：卡片展示 + 启用/暂停/删除 + 脚本查看 Modal
  - 策略创建页（/strategy/create）：条件构建器 + 执行配置 + AI 脚本生成
  - 支持：信号方向 / 信心分 / 链 / 风险等级 四类触发条件
  - AND/OR 逻辑 + 止损/止盈/滑点/Gas 执行配置
  - 无 API Key 时模板回退，有 Key 时调用 claude-haiku-4-5
  - 安装 @anthropic-ai/sdk

- [x] **OKX DEX 执行引擎** ← 新完成
  - `apps/web/lib/okx/client.ts` 新增 getSwapData() + STABLECOINS + usdToTokenAmount()
  - `POST /api/okx/quote` — OKX 报价代理（USDT→目标代币，自动换算精度）
  - `POST /api/okx/execute` — 执行引擎（干跑/真实双模式）
    - 干跑：获取 OKX 报价，记录 simulated 状态到 trades 表
    - 真实：getSwapData() → ethers 签名 → 广播 → 异步等待确认
    - 支持链：BSC/ETH/Polygon/Arbitrum/Base
  - `GET /api/trades` — 交易历史（Supabase + 演示回退）
  - `apps/admin/app/(dashboard)/execute/page.tsx` — DEX 执行测试面板
    - 链选择 + 代币地址 + 金额 + 获取报价 + 模拟/真实执行切换
    - 实时交易历史表格（链/代币/金额/获得量/时间/状态）
  - `.env.example` 新增 SERVER_WALLET_PRIVATE_KEY/ADDRESS + CHAIN_RPC
  - 依赖：ethers v6 (`npm install ethers`)

- [x] **回测引擎** ← 新完成
  - `services/backtester/main.py` — Python FastAPI + Monte-Carlo GBM 模拟
  - `services/backtester/requirements.txt` — fastapi/uvicorn/numpy/pandas
  - `POST /api/backtest` — 代理（Python优先，TS引擎兜底）
  - `apps/web/app/(dashboard)/backtest/page.tsx` — 回测UI
    - 预设快速加载 + 条件展示 + 参数滑块
    - 胜率/P&L/盈亏比/回撤 指标卡 + SVG资金曲线
    - 逐笔交易列表（止盈/止损/到期）
  - Web侧边栏新增「回测」（FlaskConical图标）
  - 启动: `uvicorn main:app --host 0.0.0.0 --port 8000`

### ✅ Phase 2 全部完成！
- [x] **App 推送通知** ← 新完成
  - `flutter_local_notifications: ^18.0.1`（pubspec.yaml）
  - `lib/models/notification_model.dart` — 通知数据模型（id/title/body/type/payload/isRead）
  - `lib/services/notification_service.dart` — 通知服务单例
    - 初始化插件、申请 iOS/Android 权限
    - 发送信号通知 / 策略执行通知 / 系统公告
    - 通知历史持久化（SharedPreferences，最多100条）
    - ValueNotifier<int> unreadCount（驱动 Badge 实时更新）
  - `lib/screens/notifications/notifications_screen.dart` — 通知中心页面
    - 全部/信号/策略/系统 四类筛选 Tab
    - Swipe-to-dismiss 单条删除
    - 未读红点 + 弹窗确认清空
  - `lib/app.dart` — 新增「通知」第5个 Tab，Badge 实时显示未读数
  - `lib/main.dart` — NotificationService.instance.init() 在 main() 中初始化
  - `lib/screens/profile/profile_screen.dart` — 通知开关真正可用
    - 开启时申请系统权限
    - 信号阈值设置（≥ 75 默认）
    - 发送测试通知按钮
  - `lib/screens/signals/signals_screen.dart` — 自动检测新高信心分信号
    - exitRate ≥ 75 的做多信号自动发推送
    - tokenAddress+chainId 去重，防止重复通知（SharedPreferences 持久化）
  - `apps/web/app/api/notifications/register/route.ts` — 设备 Token 注册 API
    - POST: 存储 FCM/APNs token 到 Supabase device_tokens 表
    - GET: 查询已注册设备数量
  - `supabase/migrations/002_device_tokens.sql` — device_tokens 表迁移
  - 验证：flutter analyze → No issues found ✅，tsc --noEmit → 0 errors ✅

## 已完成功能详细清单（Phase 2）

### 策略系统
- `apps/web/app/api/strategies/route.ts` — GET列表（Supabase/演示回退）+ POST创建
- `apps/web/app/api/strategies/[id]/route.ts` — PATCH状态 + DELETE
- `apps/web/app/api/strategies/[id]/generate/route.ts` — Claude AI脚本生成（无Key→模板回退）
- `apps/web/app/(dashboard)/strategy/page.tsx` — 列表页（卡片/条件预览/启停/脚本Modal）
- `apps/web/app/(dashboard)/strategy/create/page.tsx` — 创建向导（条件构建器+执行配置+AI生成）
- 依赖：`@anthropic-ai/sdk`，模型 claude-haiku-4-5

---

## 数据库设计（核心表，Supabase）

```sql
-- 官方策略代币组合
CREATE TABLE official_portfolio (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token_address TEXT NOT NULL,
  chain_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  name TEXT,
  entry_price NUMERIC NOT NULL,
  current_price NUMERIC,
  entry_at TIMESTAMPTZ DEFAULT NOW(),
  reason_tags TEXT[] DEFAULT '{}',
  risk_level TEXT DEFAULT 'medium',
  status TEXT DEFAULT 'active',
  exit_price NUMERIC,
  exit_at TIMESTAMPTZ
);

-- 信号表
CREATE TABLE signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token_address TEXT NOT NULL,
  chain_id INTEGER NOT NULL,
  symbol TEXT,
  direction TEXT NOT NULL,
  confidence_score INTEGER DEFAULT 0,
  trigger_price NUMERIC,
  raw_data JSONB,
  status TEXT DEFAULT 'active',
  risk_level TEXT DEFAULT 'medium',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ
);

-- 策略表
CREATE TABLE strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  name TEXT NOT NULL,
  condition_tree JSONB NOT NULL,
  exec_config JSONB NOT NULL,
  generated_script TEXT,
  status TEXT DEFAULT 'draft',
  is_official BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 交易记录
CREATE TABLE trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  strategy_id UUID REFERENCES strategies(id),
  token_address TEXT NOT NULL,
  chain_id INTEGER NOT NULL,
  tx_hash TEXT,
  direction TEXT NOT NULL,
  amount_in NUMERIC,
  amount_out NUMERIC,
  exec_price NUMERIC,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 关键设计决策

1. **Binance/OKX 数据不入 PostgreSQL** — 实时数据存 Redis（TTL 60s），历史快照存 TimescaleDB（Phase 2），业务数据才入 PostgreSQL
2. **Supabase 免费版**够用于 Phase 1（500MB，需每天 ping 防暂停）
3. **Upstash Redis** 替代自建 Redis（免费 10k req/day，支持 BullMQ）
4. **OKX API 只能服务端调用**（签名含 Secret，不能暴露给浏览器）
5. **Binance API 可浏览器直接调用**（公开，无认证）
6. **策略执行队列串行**（并发数=1，防超额买入）
7. **App 用 Flutter**（用户指定），非 React Native

---

## 启动命令

```bash
# Web 开发服务
cd /Users/wenruiwei/Desktop/Agent-Trading/apps/web && npm run dev

# Admin 开发服务
cd /Users/wenruiwei/Desktop/Agent-Trading/apps/admin && npm run dev -- --port 3002

# Flutter App
cd /Users/wenruiwei/Desktop/Agent-Trading/apps/app && flutter run

# 安装全部依赖（从根目录）
npm install
```

---

## 注意事项 / 踩坑记录

- Next.js 16.x 已发布（比 14 新），但 API 兼容
- Supabase 免费版项目超 1 周不活跃会暂停 → 需设置定时 ping
- OKX v6 Quote 用 `chainIndex` 参数，v5 用 `chainId`，不要混淆
- Binance API 偶发 Cloudflare 拦截（curl 可绕过，fetch 有时不行）
- Admin 部署须独立子域名 + IP 白名单
- **Binance API 403 根因**：Cloudflare 拦截浏览器直接请求 → Next.js API Route 做服务端代理，加 `Origin: https://web3.binance.com` + `Referer` 头
- **Binance 正确 API 路径**（实测验证，与旧文档不同）：
  - 市场排名 GET: `https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/exclusive/rank/list?chainId=56`
  - Meme Rush POST: `https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/rank/list` + body `{chainId, rankType:30, limit}`
  - 聪明钱信号 POST: `https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/web/signal/smart-money` + body `{chainId, page, pageSize, smartSignalType:''}`
  - chainId: `56`=BSC, `1`=ETH, `CT_501`=Solana（Solana 是字符串，不是数字！）
- **caniuse-lite 版本锁**：根 package.json `overrides: {caniuse-lite: 1.0.30001580}`，不要升级（新版删掉了 agents.js 导致 Next.js 崩溃）
- **next.config.ts → next.config.js**：TS config 触发 SWC 依赖链崩溃，已改成 JS
- API Routes `next: { revalidate: N }` 缓存（market-rank 30s, signals 20s）
- 最后更新：2026-03-08（Phase 2 全部完成 🎉 策略+OKX执行+回测+App推送通知）
