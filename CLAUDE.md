# Project Memory — Agent-Trading

## 项目方向
**双轨策略：pump.fun 内盘 + 多链外盘代币发现系统**
- 内盘：pump.fun 早期代币（BC 3-35%），每日推送 ≤10 个
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
├── daily_job.py             # UTC 00:05 生成内盘 Top10
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
  - `models/daily_pick.dart` — pump.fun 内盘推荐
  - `widgets/hot_coin_card.dart` — 链徽章+评分+涨跌幅卡片
  - `widgets/pick_card.dart` — 内盘推荐卡片
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
