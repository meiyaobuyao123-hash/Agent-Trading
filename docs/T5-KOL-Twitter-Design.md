# Twitter/X KOL 数据采集系统设计文档

## 一、系统概述

为 Agent-Trading 加密交易 App 构建 Twitter/X 加密 KOL 舆情数据采集与分析系统。

### 核心价值
- **早期信号发现**：多个 KOL 在短时间窗口内提及同一代币 = 强烈关注信号
- **情绪量化**：将 KOL 对特定代币的看法量化为可打分维度，融入 hot_scorer 评分
- **KOL 可信度追踪**：基于历史推荐准确率对 KOL 分级

### 架构位置

```
Twitter/X API (或 snscrape)
        │
        ▼
  kol_collector.py   ← 采集 KOL 推文
  kol_analyzer.py    ← NLP 分析 + 代币提取
  kol_scorer.py      ← KOL 信誉打分
  kol_job.py         ← 调度入口
        │
        ▼
  Supabase: kol_tweets / kol_accounts / token_kol_mentions / kol_signals
        │
        ▼
  现有评分体系 (hot_scorer) → K 维度（满10分）
        │
        ▼
  Flutter App: KOL 徽章 + 信号页面
```

---

## 二、数据采集方案

### 推荐：分层策略

**主方案：Twitter API v2 Basic ($100/月)**
- 10,000 tweets/月读取额度
- 100 KOL x 3-5 条/天 = 9,000-15,000 条/月

**备选：snscrape（零成本冷启动）**
- 先用 snscrape 验证逻辑
- 代码做好 adapter 抽象，方便切换

---

## 三、数据库 Schema

### Migration: `007_kol_system.sql`

#### 1. kol_accounts — KOL 账号管理
```sql
CREATE TABLE kol_accounts (
    id              BIGSERIAL PRIMARY KEY,
    twitter_uid     TEXT UNIQUE NOT NULL,
    username        TEXT NOT NULL,
    display_name    TEXT,
    category        TEXT NOT NULL DEFAULT 'general',
    -- 'analyst'|'trader'|'degen'|'whale_watcher'|'news'|'memecoin_hunter'|'project_founder'
    followers_count INT DEFAULT 0,
    tier            TEXT NOT NULL DEFAULT 'standard',
    -- 'elite'(准确率>60%, 粉丝>50K) | 'verified'(>40%) | 'standard' | 'spam'
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    scan_priority   INT NOT NULL DEFAULT 1,
    total_calls     INT DEFAULT 0,
    hit_2x_count    INT DEFAULT 0,
    accuracy_2x     FLOAT DEFAULT 0,
    avg_return_pct  FLOAT DEFAULT 0,
    last_tweet_id   TEXT,
    last_scanned_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### 2. kol_tweets — 推文存储
```sql
CREATE TABLE kol_tweets (
    id              BIGSERIAL PRIMARY KEY,
    tweet_id        TEXT UNIQUE NOT NULL,
    twitter_uid     TEXT NOT NULL REFERENCES kol_accounts(twitter_uid),
    text            TEXT NOT NULL,
    tweet_type      TEXT NOT NULL DEFAULT 'original',
    likes           INT DEFAULT 0,
    retweets        INT DEFAULT 0,
    replies         INT DEFAULT 0,
    sentiment       TEXT,        -- 'bullish'|'bearish'|'neutral'
    sentiment_score FLOAT,       -- -1.0 ~ 1.0
    is_promotion    BOOLEAN DEFAULT FALSE,
    has_contract_addr BOOLEAN DEFAULT FALSE,
    tweeted_at      TIMESTAMPTZ NOT NULL,
    collected_at    TIMESTAMPTZ DEFAULT NOW(),
    analyzed_at     TIMESTAMPTZ
);
```

#### 3. token_kol_mentions — 代币提及
```sql
CREATE TABLE token_kol_mentions (
    id              BIGSERIAL PRIMARY KEY,
    tweet_id        TEXT NOT NULL REFERENCES kol_tweets(tweet_id),
    twitter_uid     TEXT NOT NULL,
    ticker          TEXT,
    contract_address TEXT,
    chain           TEXT,
    hot_coin_address TEXT,
    mention_type    TEXT NOT NULL DEFAULT 'ticker',
    sentiment       TEXT,
    sentiment_score FLOAT,
    price_at_mention NUMERIC,
    mentioned_at    TIMESTAMPTZ NOT NULL,
    UNIQUE(tweet_id, COALESCE(ticker, ''), COALESCE(contract_address, ''))
);
```

#### 4. kol_signals — 共振信号
```sql
CREATE TABLE kol_signals (
    id              BIGSERIAL PRIMARY KEY,
    signal_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    ticker          TEXT,
    contract_address TEXT,
    chain           TEXT,
    mention_count   INT NOT NULL DEFAULT 0,
    elite_count     INT DEFAULT 0,
    avg_sentiment   FLOAT DEFAULT 0,
    signal_strength TEXT,  -- 'strong'|'moderate'|'weak'
    price_at_signal NUMERIC,
    price_72h_later NUMERIC,
    max_return_7d_pct FLOAT,
    first_mention_at TIMESTAMPTZ,
    last_mention_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(signal_date, COALESCE(ticker,''), COALESCE(contract_address,''), chain)
);
```

#### 5. kol_accuracy_log — 准确率追踪
```sql
CREATE TABLE kol_accuracy_log (
    id              BIGSERIAL PRIMARY KEY,
    twitter_uid     TEXT NOT NULL REFERENCES kol_accounts(twitter_uid),
    tweet_id        TEXT NOT NULL,
    ticker          TEXT,
    contract_address TEXT,
    price_at_call   NUMERIC NOT NULL,
    called_at       TIMESTAMPTZ NOT NULL,
    price_72h       NUMERIC,
    max_price_7d    NUMERIC,
    hit_2x          BOOLEAN,
    hit_5x          BOOLEAN,
    return_pct      FLOAT,
    max_return_pct  FLOAT,
    evaluated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 四、Python 文件结构

```
services/pump-scanner/
├── kol_collector.py         # 推文采集（API / snscrape 双 adapter）
├── kol_analyzer.py          # NLP: 情绪判定 + 代币提取 + 广告检测
├── kol_scorer.py            # KOL 信誉评分 + 准确率计算
├── kol_signal_detector.py   # 共振信号检测
├── kol_job.py               # APScheduler 入口
├── kol_config.py            # 配置常量
└── kol_seed.py              # 种子列表初始化（一次性）
```

### APScheduler 新增任务
| 任务 | 频率 | 说明 |
|------|------|------|
| kol_scan | 每2h | 采集+分析+信号检测 |
| kol_evaluator | 每6h | 结果回填+信誉更新 |

---

## 五、NLP 分析方案

### V1: 规则引擎（冷启动）
- 关键词匹配（bullish/bearish 各 ~20 个词）
- Emoji 信号（火焰/火箭 → bullish，骷髅 → bearish）
- 否定词反转
- 广告检测（airdrop/giveaway/sponsored 等）

### 代币提取
- `$TICKER` cashtag 正则
- Solana 合约地址 (Base58, 32-44字符)
- EVM 合约地址 (0x + 40位hex)
- DexScreener/Birdeye URL 解析

### 共振信号检测
- strong: >=3 KOL 在 6h 内提及 + 含 elite
- moderate: >=2 KOL 在 12h 内提及
- weak: 单个 KOL（仅记录）

---

## 六、KOL 种子列表（65-96 个）

| 类别 | 数量 | 示例 |
|------|------|------|
| 分析师 | 15-20 | @CryptoCapo_, @AltcoinSherpa, @HsakaTrades |
| 交易员 | 15-20 | @trader1sz, @CryptoTony__, @PostyXBT |
| DeFi | 10-15 | @DefiIgnas, @TheDeFiEdge, @Route2FI |
| 巨鲸监控 | 5-8 | @lookonchain, @whale_alert, @spotonchain |
| 快讯 | 5-8 | @WuBlockchain, @tier10k, @BlockBeatsAsia |
| Meme猎手 | 10-15 | @MustStopMurad, @SOLBigBrain, @ZssBecker |
| 项目方 | 5-10 | @rajgokal, @VitalikButerin |

---

## 七、评分集成

在 hot_scorer.py 新增 K 维度（满10分）：

```
新总分 = M(45) + Q(27) + P(18) + K(10) = 100

K1. KOL 提及数量（4分）：>=3 → 4分, 2 → 3分, 1 → 1.5分
K2. KOL 质量（3分）：elite → 3分, verified → 2分
K3. 情绪一致性（3分）：全bullish → 3分, 多数 → 2分
```

---

## 八、实施顺序

| 阶段 | 周 | 内容 |
|------|-----|------|
| Phase 1 | 1 | 建表 + kol_seed + kol_collector (snscrape) |
| Phase 2 | 2 | kol_analyzer (规则V1) + kol_signal_detector |
| Phase 3 | 3 | kol_scorer + kol_job + 接入 main.py |
| Phase 4 | 4 | hot_scorer K维度 + Flutter KOL徽章 |
| Phase 5 | 5-6 | Twitter API Basic 切换 + 情绪分析 V2 (ML) |

---

## 九、成本

| 项目 | snscrape 方案 | API Basic 方案 |
|------|-------------|---------------|
| Twitter API | $0 | $100/月 |
| NLP (规则引擎) | $0 | $0 |
| **月总计** | **$0** | **~$100** |
