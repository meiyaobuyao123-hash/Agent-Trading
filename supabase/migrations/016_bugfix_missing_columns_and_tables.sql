-- ══════════════════════════════════════════════════════════
-- 016 修复：补齐缺失列 + KOL 表 + RLS 策略 + 索引
-- ══════════════════════════════════════════════════════════

-- ── 1. hot_coins 补齐 image_url 列 ─────────────────────────
ALTER TABLE hot_coins ADD COLUMN IF NOT EXISTS image_url TEXT;

-- ── 2. pump_daily_report RLS（Portal anon key 读取需要）────
ALTER TABLE pump_daily_report ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "allow_public_read_pump_report"
    ON pump_daily_report FOR SELECT USING (true);

-- ── 3. hot_coins RLS ──────────────────────────────────────
ALTER TABLE hot_coins ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "allow_public_read_hot_coins"
    ON hot_coins FOR SELECT USING (true);

-- ── 4. hot_daily_picks RLS ────────────────────────────────
ALTER TABLE hot_daily_picks ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "allow_public_read_hot_daily_picks"
    ON hot_daily_picks FOR SELECT USING (true);

-- ── 5. daily_picks RLS（Flutter App anon key 读取）────────
ALTER TABLE daily_picks ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "allow_public_read_daily_picks"
    ON daily_picks FOR SELECT USING (true);

-- ── 6. hot_coins.address 索引（.in() 查询优化）────────────
CREATE INDEX IF NOT EXISTS idx_hot_coins_address
    ON hot_coins(address);

-- ── 7. KOL 舆情表（之前手动在 Dashboard 创建，补录 migration）
CREATE TABLE IF NOT EXISTS kol_accounts (
    id              BIGSERIAL PRIMARY KEY,
    twitter_uid     TEXT UNIQUE NOT NULL,
    username        TEXT NOT NULL,
    display_name    TEXT,
    bio             TEXT,
    tier            TEXT NOT NULL DEFAULT 'small'
                    CHECK (tier IN ('mega', 'large', 'medium', 'small')),
    followers_count INT DEFAULT 0,
    following_count INT DEFAULT 0,
    tweet_count     INT DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    last_scanned_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kol_tweets (
    id              BIGSERIAL PRIMARY KEY,
    tweet_id        TEXT UNIQUE NOT NULL,
    twitter_uid     TEXT NOT NULL,
    content         TEXT,
    tweeted_at      TIMESTAMPTZ,
    reply_count     INT DEFAULT 0,
    retweet_count   INT DEFAULT 0,
    like_count      INT DEFAULT 0,
    quote_count     INT DEFAULT 0,
    view_count      INT DEFAULT 0,
    is_retweet      BOOLEAN DEFAULT FALSE,
    is_reply        BOOLEAN DEFAULT FALSE,
    raw_json        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kol_signals (
    id              BIGSERIAL PRIMARY KEY,
    token_address   TEXT NOT NULL,
    chain           TEXT DEFAULT 'solana',
    ticker          TEXT,
    signal_strength TEXT DEFAULT 'weak'
                    CHECK (signal_strength IN ('strong', 'medium', 'weak')),
    kol_count       INT DEFAULT 0,
    mega_count      INT DEFAULT 0,
    large_count     INT DEFAULT 0,
    avg_sentiment   FLOAT DEFAULT 0,
    bullish_ratio   FLOAT DEFAULT 0,
    total_reach     INT DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    detected_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(token_address, chain)
);

-- KOL 表索引
CREATE INDEX IF NOT EXISTS idx_kol_accounts_active
    ON kol_accounts(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_kol_tweets_uid
    ON kol_tweets(twitter_uid, tweeted_at DESC);
CREATE INDEX IF NOT EXISTS idx_kol_signals_active
    ON kol_signals(is_active, detected_at DESC) WHERE is_active = TRUE;

-- KOL 表 RLS
ALTER TABLE kol_accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "allow_public_read_kol_accounts"
    ON kol_accounts FOR SELECT USING (true);

ALTER TABLE kol_tweets ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "allow_public_read_kol_tweets"
    ON kol_tweets FOR SELECT USING (true);

ALTER TABLE kol_signals ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "allow_public_read_kol_signals"
    ON kol_signals FOR SELECT USING (true);
