-- ============================================================
-- 007_kol_system.sql
-- KOL 舆情采集系统：Twitter KOL 监控、推文存储、代币提及、
-- 共振信号检测、准确率追踪
-- 数据源：twitterapi.io / twscrape
-- ============================================================

-- ── 1. KOL 账号管理 ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kol_accounts (
    id                  BIGSERIAL PRIMARY KEY,
    twitter_uid         TEXT UNIQUE NOT NULL,       -- Twitter 用户 ID
    username            TEXT NOT NULL,              -- @handle
    display_name        TEXT,
    bio                 TEXT,
    followers_count     INT DEFAULT 0,
    following_count     INT DEFAULT 0,
    tweet_count         INT DEFAULT 0,
    category            TEXT DEFAULT 'crypto',      -- crypto|defi|nft|meme|vc|media|analyst|developer
    tier                TEXT DEFAULT 'small',       -- mega|large|medium|small
    language            TEXT DEFAULT 'en',          -- en|zh|...
    accuracy_2x         REAL DEFAULT 0,             -- 提及后翻倍成功率
    total_calls         INT DEFAULT 0,              -- 总提及次数
    successful_calls    INT DEFAULT 0,              -- 翻倍成功次数
    avg_engagement      REAL DEFAULT 0,             -- 平均互动率
    is_active           BOOLEAN DEFAULT TRUE,
    last_scanned_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kol_accounts IS 'KOL 账号管理：Twitter KOL 基本信息与历史表现';
COMMENT ON COLUMN kol_accounts.tier IS 'mega(>500K) | large(100K-500K) | medium(20K-100K) | small(5K-20K)';
COMMENT ON COLUMN kol_accounts.accuracy_2x IS '该 KOL 提及代币后 7 天内翻倍的概率';

CREATE INDEX IF NOT EXISTS idx_kol_accounts_tier
    ON kol_accounts(tier);

CREATE INDEX IF NOT EXISTS idx_kol_accounts_category
    ON kol_accounts(category);

CREATE INDEX IF NOT EXISTS idx_kol_accounts_followers
    ON kol_accounts(followers_count DESC);

CREATE INDEX IF NOT EXISTS idx_kol_accounts_accuracy
    ON kol_accounts(accuracy_2x DESC);

CREATE INDEX IF NOT EXISTS idx_kol_accounts_active
    ON kol_accounts(is_active) WHERE is_active = TRUE;

-- ── 2. 推文存储 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kol_tweets (
    id                  BIGSERIAL PRIMARY KEY,
    tweet_id            TEXT UNIQUE NOT NULL,
    twitter_uid         TEXT NOT NULL REFERENCES kol_accounts(twitter_uid),
    content             TEXT NOT NULL,
    tweeted_at          TIMESTAMPTZ NOT NULL,
    reply_count         INT DEFAULT 0,
    retweet_count       INT DEFAULT 0,
    like_count          INT DEFAULT 0,
    quote_count         INT DEFAULT 0,
    view_count          INT DEFAULT 0,
    sentiment           TEXT DEFAULT 'neutral',     -- bullish|bearish|neutral
    sentiment_score     REAL DEFAULT 0,             -- -1.0 ~ 1.0
    has_token_mention   BOOLEAN DEFAULT FALSE,
    is_retweet          BOOLEAN DEFAULT FALSE,
    is_reply            BOOLEAN DEFAULT FALSE,
    is_promotion        BOOLEAN DEFAULT FALSE,      -- 广告/推广标记
    engagement_score    REAL DEFAULT 0,
    raw_json            JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kol_tweets IS 'KOL 推文存储：原始推文内容与互动数据';
COMMENT ON COLUMN kol_tweets.sentiment_score IS '情绪分数 -1.0(极度看空) ~ 1.0(极度看多)';
COMMENT ON COLUMN kol_tweets.is_promotion IS '检测到广告关键词（#ad, sponsored 等）标记为 TRUE';

CREATE INDEX IF NOT EXISTS idx_kol_tweets_uid
    ON kol_tweets(twitter_uid);

CREATE INDEX IF NOT EXISTS idx_kol_tweets_tweeted
    ON kol_tweets(tweeted_at DESC);

CREATE INDEX IF NOT EXISTS idx_kol_tweets_sentiment
    ON kol_tweets(sentiment);

CREATE INDEX IF NOT EXISTS idx_kol_tweets_mention
    ON kol_tweets(has_token_mention) WHERE has_token_mention = TRUE;

CREATE INDEX IF NOT EXISTS idx_kol_tweets_uid_tweeted
    ON kol_tweets(twitter_uid, tweeted_at DESC);

-- ── 3. 代币提及 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS token_kol_mentions (
    id                  BIGSERIAL PRIMARY KEY,
    tweet_id            TEXT NOT NULL REFERENCES kol_tweets(tweet_id),
    twitter_uid         TEXT NOT NULL REFERENCES kol_accounts(twitter_uid),
    token_address       TEXT,                       -- 合约地址（可能为空，仅有 $TICKER）
    chain               TEXT,                       -- solana|bsc|base|ethereum
    ticker              TEXT NOT NULL,              -- 代币符号，如 SOL, PEPE
    sentiment           TEXT DEFAULT 'neutral',
    sentiment_score     REAL DEFAULT 0,
    price_at_mention    REAL,                       -- 提及时价格 (USD)
    mcap_at_mention     REAL,                       -- 提及时市值 (USD)
    followers_at_mention INT,                       -- 提及时 KOL 粉丝数
    mentioned_at        TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE token_kol_mentions IS '代币提及记录：KOL 推文中提到的具体代币';
COMMENT ON COLUMN token_kol_mentions.token_address IS '合约地址，仅有 $TICKER 时为 NULL';

CREATE INDEX IF NOT EXISTS idx_mentions_token
    ON token_kol_mentions(token_address, chain);

CREATE INDEX IF NOT EXISTS idx_mentions_ticker
    ON token_kol_mentions(ticker);

CREATE INDEX IF NOT EXISTS idx_mentions_time
    ON token_kol_mentions(mentioned_at DESC);

CREATE INDEX IF NOT EXISTS idx_mentions_uid
    ON token_kol_mentions(twitter_uid);

-- ── 4. 共振信号 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kol_signals (
    id                  BIGSERIAL PRIMARY KEY,
    token_address       TEXT,
    chain               TEXT,
    ticker              TEXT NOT NULL,
    signal_strength     REAL NOT NULL,              -- 综合信号强度 0~100
    kol_count           INT DEFAULT 0,              -- 提及 KOL 总数
    mega_count          INT DEFAULT 0,
    large_count         INT DEFAULT 0,
    medium_count        INT DEFAULT 0,
    small_count         INT DEFAULT 0,
    avg_sentiment       REAL DEFAULT 0,             -- 平均情绪
    bullish_ratio       REAL DEFAULT 0,             -- 看多比例
    total_reach         INT DEFAULT 0,              -- 覆盖粉丝总数
    window_hours        INT DEFAULT 24,             -- 检测窗口（小时）
    kol_usernames       TEXT[],                     -- 提及的 KOL username 列表
    detected_at         TIMESTAMPTZ DEFAULT NOW(),
    expires_at          TIMESTAMPTZ,                -- 信号过期时间
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kol_signals IS '共振信号：多 KOL 同时提及同一代币时触发';
COMMENT ON COLUMN kol_signals.signal_strength IS '综合信号强度 0~100，基于 KOL 数量×质量×情绪';
COMMENT ON COLUMN kol_signals.window_hours IS '信号检测时间窗口，默认24小时';

CREATE INDEX IF NOT EXISTS idx_signals_token
    ON kol_signals(token_address, chain);

CREATE INDEX IF NOT EXISTS idx_signals_strength
    ON kol_signals(signal_strength DESC);

CREATE INDEX IF NOT EXISTS idx_signals_active
    ON kol_signals(is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_signals_detected
    ON kol_signals(detected_at DESC);

-- ── 5. 准确率追踪 ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kol_accuracy_log (
    id                  BIGSERIAL PRIMARY KEY,
    mention_id          BIGINT NOT NULL REFERENCES token_kol_mentions(id),
    twitter_uid         TEXT NOT NULL REFERENCES kol_accounts(twitter_uid),
    token_address       TEXT,
    chain               TEXT,
    ticker              TEXT,
    price_at_mention    REAL,
    price_after_24h     REAL,
    price_after_72h     REAL,
    price_after_7d      REAL,
    change_24h_pct      REAL,
    change_72h_pct      REAL,
    change_7d_pct       REAL,
    hit_2x              BOOLEAN DEFAULT FALSE,      -- 7天内是否翻倍
    hit_2x_days         INT,                        -- 翻倍用了几天
    evaluated_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kol_accuracy_log IS '准确率追踪：记录每次代币提及后的价格变化';
COMMENT ON COLUMN kol_accuracy_log.hit_2x IS '提及后7天内价格是否达到2x';

CREATE INDEX IF NOT EXISTS idx_accuracy_uid
    ON kol_accuracy_log(twitter_uid);

CREATE INDEX IF NOT EXISTS idx_accuracy_hit
    ON kol_accuracy_log(hit_2x) WHERE hit_2x = TRUE;

CREATE INDEX IF NOT EXISTS idx_accuracy_mention
    ON kol_accuracy_log(mention_id);

-- ── 更新时间触发器 ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_kol_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_kol_accounts_updated ON kol_accounts;
CREATE TRIGGER tr_kol_accounts_updated
    BEFORE UPDATE ON kol_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_kol_updated_at();

-- ── RLS：允许匿名读取 ───────────────────────────────────────
ALTER TABLE kol_accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "kol_accounts_public_read"
    ON kol_accounts FOR SELECT USING (true);

ALTER TABLE kol_tweets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "kol_tweets_public_read"
    ON kol_tweets FOR SELECT USING (true);

ALTER TABLE token_kol_mentions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "token_kol_mentions_public_read"
    ON token_kol_mentions FOR SELECT USING (true);

ALTER TABLE kol_signals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "kol_signals_public_read"
    ON kol_signals FOR SELECT USING (true);

ALTER TABLE kol_accuracy_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "kol_accuracy_log_public_read"
    ON kol_accuracy_log FOR SELECT USING (true);
