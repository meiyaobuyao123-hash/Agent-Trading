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
| Web用户端 | Next.js 14 | apps/web | 3000 | 🟡 框架搭建中 |
| Admin后台 | Next.js 14 + Ant Design | apps/admin | 3002 | 🟡 待开发 |
| App移动端 | **Flutter** | apps/app | - | 🟡 已创建项目 |

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
- API Key: `264f720b-1324-41b4-9c85-0b5f20d3696e`
- Secret Key: `57FDDAF653008E120F35631E9929FA91`
- Passphrase: `7745098wei@W`
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

### 🟡 进行中（Phase 1 MVP）
- [ ] Web 行情中心页面（Token 列表 + 实时价格）
- [ ] Web 信号中心页面（信号列表 + 详情）
- [ ] Web 官方策略组合追踪页面
- [ ] Admin 基础页面（官方策略管理 + 系统健康）
- [ ] Supabase 数据库表结构初始化（SQL migrations）
- [ ] API Route 层（/api/binance/*, /api/signals/*）
- [ ] Flutter App 基础框架（导航 + 主题）

### ⏳ 待开始（Phase 2+）
- [ ] 信号引擎后端服务
- [ ] 策略创建 + AI 生成脚本
- [ ] OKX 执行引擎
- [ ] 回测引擎（Python FastAPI）
- [ ] App 推送通知

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
