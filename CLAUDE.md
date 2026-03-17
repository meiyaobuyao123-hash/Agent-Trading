# Project Memory — Agent-Trading (CLAUDE.md — 仓库版，无凭证)
# 凭证见本地 credentials.md，不在此文件中

## 🔴 每次会话开始必须执行（强制）
立即读取以下所有 topic 文件，不得跳过：
- `CLAUDE.md`（本文件）— 索引 + 规则 + 速查
- `architecture.md` — 架构、数据流、启动命令
- `pitfalls.md` — 踩坑记录
- `rules.md` — 工作规则详细版
- `sessions-log.md` — 历史会话记录 + 讨论结论 + 被否定方案

## ⚠️ 工作规则摘要
**记忆更新**: 发现新信息 → 立即更新，不等任务结束
**双份同步**: 本地 topic 文件 + 仓库 CLAUDE.md 必须同时更新，内容完全一致
**数据源**: EVM聪明钱用 `web3.okx.com`，SOL用 Helius WS，禁止 Etherscan，禁止 www.okx.com
**实现规则**: 讨论完先验证API → 实现后grep验证 → 不得悄悄换数据源
**诚实原则**: 没做就说没做，做了必须有证据同步用户，不得虚报完成
**用户偏好**: 中文输出，真实数据，不估时间，不过度工程化

---

## 快速速查

### 线上地址
- Portal: http://43.156.207.26（服务器部署，nginx反代:3000）
- Portal (Vercel备): https://agent-trading-portal.vercel.app/hot
- Backend API: http://43.156.207.26（nginx分流到:8000）
- GitHub: https://github.com/meiyaobuyao123-hash/Agent-Trading

### 本地路径
- 后端: `services/pump-scanner/`
- Flutter: `apps/app/`
- Portal: `apps/web/`

### 服务器
- IP: `43.156.207.26`（腾讯云轻量，新加坡，到期 2026-05-16）
- SSH: `ssh ubuntu@43.156.207.26`（密码见本地 credentials.md）

### Flutter 启动
```bash
flutter run -d DBC925B5-7657-4410-B770-F21E4605A9D6 \
  --dart-define=API_BASE_URL=http://43.156.207.26 \
  --dart-define=HELIUS_API_KEY=<见credentials.md>
```

---

## 当前功能状态
| 模块 | 状态 | 备注 |
|------|------|------|
| pump.fun 采集 | ✅ 线上 | 三阶段+实时信号池：score>=55动态进出，APP 30s轮询 |
| 热币扫描 | ✅ 线上 | OKX toplist，4链，10min发现/30s刷新 |
| 聪明钱追踪 | ✅ 线上 | SOL ~400ms / EVM ~2.5s，55钱包 |
| KOL 舆情 | ✅ 线上 | 212 KOL，_evaluate_accuracy TODO |
| Agent 交易 | ✅ 线上 | Claude LLM + OKX DEX，SOL+EVM |
| Flutter App | ✅ 运行 | 模拟器 iPhone 17 Pro Max，i18n 4语言 |
| Portal | ✅ 线上 | 服务器部署(systemd+nginx)，Vercel备用 |
| i18n 国际化 | ✅ 完成 | zh/en/ja/ko，275+ 本地化字符串，语言切换器 |
| 合规 | ✅ | 免责声明Gate + CN IP屏蔽 + 推送限流 |
| XGBoost ML | ⏸ 待训练 | 管线就绪，3/27 提醒 |
| Firebase 推送 | ⏸ 待配置 | 需创建 Firebase 项目 |

## 待执行（手动）
- [ ] Supabase Dashboard 执行 `migrations/017_user_api_quota.sql`（如未执行）
- [ ] Firebase 项目创建 + 下载 google-services.json / GoogleService-Info.plist

---

## 系统架构摘要

### 热币数据源分层
- **发现** (10min): OKX toplist 多时间帧（4时间帧×2排序=8次/链），4链并行
- **刷新** (30s): DexScreener 批量
- **安全**: GoPlus；**SOL持仓**: Helius RPC；**打分**: M+Q+P 三维

### 聪明钱追踪
- SOL: Helius `accountSubscribe` WebSocket，~400ms
- ETH/BSC/Base: `GET https://web3.okx.com/api/v5/wallet/post-transaction/transactions-by-address`
  - 参数 `chains=`（List，不是chainIndex=），需 `User-Agent: Mozilla/5.0`
  - chainIndex: ETH=1 / BSC=56 / Base=8453，响应 `data[].transactionList[]`
  - 5s轮询，~2.5s感知

### Agent 交易链路
Claude LLM → 策略DSL → 规则引擎 → 风控 → OKX DEX（quote→swap→sign→broadcast→record）

### Supabase 主要表
- `hot_coins` / `hot_daily_picks` / `pump_daily_report`
- `smart_money_signals` / `smart_money_txns` / `smart_wallets`
  - `smart_wallets` 列名是 `wallet`（非 `address`），无 `chain` 列
- `strategies` / `strategy_executions` / `user_api_quota`
- 共 18 个 Migration

---

## 踩坑速查（详见 pitfalls.md）
- OKX Wallet API 必须用 `web3.okx.com`（www.okx.com 返回403）
- `transactions-by-address` 参数是 `chains=`（List），不是 `chainIndex=`
- 响应结构 `data[].transactionList[]`，不是 `tokenTransferDetails[]`
- EVM nonce 必须动态获取，hardcode 0 只对首笔有效
- Supabase DDL 只能 Dashboard SQL Editor 手动执行
- Flutter `|| null` 误杀零值，改用 `?? null`
- Python 3.9 不支持 `X | None`，用 `Optional[X]`
- ON CONFLICT 重复行：同批次去重用 `seen_keys: Set[tuple]`

---

## 2026-03-17 本次会话
- ✅ 聪明钱升级为实时：SOL Helius WS ~400ms + EVM OKX 5s轮询（commit c8fcad7）
- ✅ 修复 OKX base URL / endpoint / 参数 / 响应解析
- ✅ 修复 smart_money_txns 批次去重、OKX toplist 429
- ✅ 记忆文件重构：双份同步机制、topic文件拆分、sessions-log.md 新建
- ✅ pump采集三阶段架构（commit bac2a06）：WS全量捕获→交易追踪(20k)→按需enrich(Sem20)
- ✅ Portal 部署到服务器：systemd portal.service + nginx 反代分流（FastAPI:8000 / Next.js:3000）
- ✅ 实时信号池（commit 2c2e227）：替代每日推荐，score>=55 且 BC 3-35% 动态进出
- ✅ Flutter PicksScreen 重写：30s 轮询 /api/pump/signals 实时显示
- ✅ nginx 新增 /api/pump/ 路由
- ✅ **i18n 国际化**（commit fc4740a + 1158d63）：zh/en/ja/ko，275+ 字符串，语言切换器，QA 修复 80+ 遗漏

---

# 以下为旧内容（已废弃，忽略）
- 外盘：多链热币榜（SOL/BSC/Base），每2小时扫描更新
- 算法：规则打分冷启动 → XGBoost ML（2周后）
- 信号通过 **Flutter App** 推送给用户

## 开发仓库
- **GitHub**: https://github.com/meiyaobuyao123-hash/Agent-Trading
- **本地路径**: /Users/wenruiwei/Desktop/Agent-Trading
- **pump-scanner**: `/Users/wenruiwei/Desktop/Agent-Trading/services/pump-scanner/`
- **Flutter App**: `/Users/wenruiwei/Desktop/Agent-Trading/apps/app/`
- **GitHub 状态**: 已推送（services/、Flutter lib/、migrations 均已提交）

## API 凭证（保存在本地 .env，不提交到 Git）
- Supabase URL: 见 `services/pump-scanner/.env`（SUPABASE_URL）
- Supabase Service Key: 见 `services/pump-scanner/.env`（SUPABASE_SERVICE_KEY）
- Supabase Anon Key: 填入 `apps/app/lib/main.dart`（_supabaseKey）
- OKX DEX v6 Key/Secret/Pass: 见本地 `.env.example` 模板

## Supabase 数据库 Schema

### 内盘（003_pump_scanner.sql）
| 表 | 用途 |
|---|---|
| `pump_tokens` | 代币基础信息（mint PK，含creator、social） |
| `token_snapshots` | 每分钟特征快照（bc_progress、buy/sell比等） |
| `token_outcomes` | 72h结果标签（did_graduate、label_2x、label_10x） |
| `daily_picks` | 每日Top10推荐（score、score_detail JSONB） |
| `token_trades` | 交易流水（bc_progress列，30天滚动清理） |
| `smart_wallets` | 聪明钱钱包（tier/is_blacklisted等，需004 migration） |

### 外盘（005_hot_coins.sql ✅已执行）
| 表 | 用途 |
|---|---|
| `hot_coins` | 多链热币实时数据+评分，每2h更新，UNIQUE(chain,address) |
| `hot_daily_picks` | 热币日榜Top20，跨链分配（每链≤8），UNIQUE(pick_date,chain,address) |

### ⚠️ Migration 004 待执行
在 Supabase Dashboard → SQL Editor 执行：
```sql
ALTER TABLE smart_wallets
  ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'watching',
  ADD COLUMN IF NOT EXISTS avg_entry_bc FLOAT,
  ADD COLUMN IF NOT EXISTS active_weeks INT DEFAULT 1,
  ADD COLUMN IF NOT EXISTS is_blacklisted BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS total_sol_in NUMERIC DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_smart_wallets_tier ON smart_wallets(tier) WHERE is_blacklisted = FALSE;
CREATE INDEX IF NOT EXISTS idx_smart_wallets_blacklisted ON smart_wallets(is_blacklisted);
```

## pump-scanner 文件结构
```
services/pump-scanner/
├── main.py                  # 入口：6个 APScheduler 定时任务
├── collector.py             # WebSocket 采集 + 快照循环 + 聪明钱重载
├── features.py              # 特征提取（TokenFeatures + hard_filter）
├── scorer.py                # 7维度打分
├── daily_job.py             # UTC 00:05 生成内盘历史记录（APP已切换到实时信号池）
├── scanner_ref.py           # 全局 scanner 引用（避免循环导入）
├── outcome_labeler.py       # 每1h，72h后打结果标签
├── smart_wallet_updater.py  # 每6h，多维度分层（v2：Bot检测+时间衰减）
├── creator_stats_updater.py # UTC 01:00，计算 creator_success_rate
├── hot_coin_fetcher.py      # 多链热币采集（GeckoTerminal→GoPlus→Helius→DexScreener）
├── hot_scorer.py            # 热币打分（M×50 + Q×30 + P×20）
├── hot_coin_job.py          # 每2h扫描 + UTC 02:00 生成热币日榜
├── database.py              # Supabase 封装（含 upsert_hot_coins/save_hot_daily_picks）
├── config.py                # 常量配置
└── requirements.txt
```

## APScheduler 定时任务（main.py，共6个）
| 任务 | 时间 | 说明 |
|---|---|---|
| daily_picks | UTC 00:05 每天 | pump.fun 内盘 Top10 |
| creator_stats | UTC 01:00 每天 | 创建者成功率 |
| hot_daily_picks | UTC 02:00 每天 | 热币日榜 Top20 |
| outcome_labeler | 每1小时 | 72h结果标签 |
| hot_coin_scan | 每2小时 | 多链热币全链扫描 |
| smart_wallet | 每6小时 | 聪明钱分层更新 |

## 热币榜系统（2026-03-10 完成）

### 数据流水线
GeckoTerminal（发现）→ 硬过滤 → GoPlus（安全）→ Helius（SOL top1）→ DexScreener（社交）→ hot_scorer

### 链选择（最终确定：SOL/BSC/Base）
- ETH/Arbitrum：trending 全是老协议（>90d），Arbitrum avg 1000d
- Polygon/TON：new_pools 全是过新代币（<3d）
- SOL/BSC/Base：trending 含大量 3~90d 新兴项目 ✅

### 关键配置（config.py）
```python
HOT_CHAINS = {
    "solana": {"gecko_net": "solana",   "goplus_chain": "solana"},
    "bsc":    {"gecko_net": "bsc",      "goplus_chain": "56"},
    "base":   {"gecko_net": "base",     "goplus_chain": "8453"},
}
GECKO_PAGES = 3          # 每端点3页，trending+new_pools共6请求/链
HOT_MIN_AGE_DAYS  = 3    HOT_MAX_AGE_DAYS  = 90
HOT_MIN_LIQ_USD   = 30_000    HOT_MAX_LIQ_USD  = 5_000_000
HOT_MIN_MC_USD    = 200_000   HOT_MAX_MC_USD   = 50_000_000
HOT_MIN_VOL_24H_USD = 15_000  HOT_MIN_LIQ_MC_RATIO = 0.08
```

### 打分（hot_scorer.py）
- **M 动量分（×50）**: 1h涨幅+24h涨幅+量加速+买压+6h趋势
- **Q 品质分（×30）**: 持有者+社交+安全+集中度
- **P 潜力分（×20）**: 市值空间（log）+年龄（7-30d最佳）
- strong ≥ 72，normal ≥ 50，skip < 50

### 429 重试修复（已完成）
`_fetch_gecko_pools` 内层重试循环，429时等 25s/50s/75s 后重试**同一页**（原 `continue` 是 bug 会跳到下一页）

### 实测效果（最近一次）
solana=8  bsc=7  base=14  →  总计 29 个，strong=1，normal=6

## Flutter App

### 热币榜（HotScreen）— 2026-03-10 重构
- 数据源：`hot_coins` 表（多链外盘）← 之前错误读取 `token_snapshots`
- 查询：`fetchHotCoins()` 读 hot_coins，按 score 降序，排除 goplus_risk
- 链过滤 Tabs：全部 / SOL / BSC / BASE
- 卡片：排名 + 链徽章（紫/黄/蓝）+ 代币名/市值/天数 + 评分圆角矩形 + 24h涨跌
- 点击 → 跳转 DexScreener（不再是内部 detail 页）
- 每2h更新，手动刷新按钮（不再有60s倒计时）

### 整体架构
- **5-Tab**: 新币榜/热币榜/Agent/历史/我的
- **设计**: 白底极简科技风，AppColors（bg:#F5F7FA, primary:#2563EB）
- **关键文件**:
  - `models/hot_coin.dart` — 对应 hot_coins 表全字段
  - `models/daily_pick.dart` — pump.fun 历史推荐（history_screen 用）
  - `models/pump_signal.dart` — 实时信号模型（picks_screen/market_screen 用）
  - `services/pump_signal_service.dart` — 实时信号 API 服务
  - `widgets/hot_coin_card.dart` — 链徽章+评分+涨跌幅卡片
  - `widgets/pick_card.dart` — 内盘历史推荐卡片（history_screen 用）
  - `services/supabase_service.dart` — 3个查询

## 当前运行状态（2026-03-10）
- ✅ pump-scanner 后台运行（6个定时任务已注册）
- ✅ hot_coin_scan 每2h运行，hot_coins 表有 29 条数据
- ✅ hot_coins / hot_daily_picks 表已建（005 migration 已执行）
- ✅ Flutter HotScreen 改读 hot_coins（多链外盘）
- ⚠️ Migration 004 待执行（smart_wallets 新字段）
- ⚠️ GitHub 未推送（services/、Flutter lib/ 全是新增 untracked）

## 待开发（按优先级）
- [ ] **⚠️ Migration 004**：执行 smart_wallets SQL，重启服务
- [ ] **GitHub push**：提交所有 services/、Flutter、migrations 新文件
- [ ] **ML 训练**（2周后）：XGBoost 替换规则打分
- [ ] **App 推送通知**：Telegram Bot 或 iOS Push
- [ ] **Agent 实现**：Claude API + OKX 自动执行

## 踩坑记录
- **Python 3.9 不支持 `X | None`**：用 `Optional[X]`
- **Python 3.9 不支持 `list[str]`（小写）**：用 `List[str]`
- **Flutter withOpacity 弃用**：改 `withValues(alpha: ...)`
- **Flutter i18n**: gen-l10n 需 `pub get` 触发；const 与 S.of(context) 冲突；Model 层不应返回本地化字符串
- **GeckoTerminal 429 continue bug**：continue 跳下一页，应内层重试循环
- **ETH/Arbitrum/Polygon 不适合热币策略**：分别因太老/太新被过滤
- **token_trades 列名**：`bc_progress`（不是 bc_progress_at_buy）
- **smart_wallets 原列名**：`total_trades/win_trades/last_seen`
- **Supabase DDL**：只能 Dashboard SQL Editor 手动执行，service key 无法 DDL

## 用户偏好
- **始终使用中文输出**（不要韩文、不要随意切英文）
- 报告要有真实数据，不要粗糙概述
- 时间估计不要虚长
- 旧的 Web/Admin/Binance 代码已废弃，不再提及
