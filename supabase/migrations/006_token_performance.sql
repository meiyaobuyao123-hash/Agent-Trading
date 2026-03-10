-- ============================================================
-- 006_token_performance.sql
-- 推荐代币表现追踪：监控 daily_picks + hot_daily_picks 的价格变化
-- 追踪周期：1d ~ 30d，记录每天最高价和涨幅
-- ============================================================

CREATE TABLE IF NOT EXISTS token_performance (
    id                  BIGSERIAL PRIMARY KEY,

    -- 推荐来源
    source              TEXT    NOT NULL,                -- 'pump' | 'hot'
    pick_date           DATE    NOT NULL,                -- 推荐日期
    chain               TEXT    NOT NULL,                -- 'solana'|'bsc'|'base'
    address             TEXT    NOT NULL,                -- mint (pump) 或合约地址 (hot)
    symbol              TEXT,
    name                TEXT,
    rank                INT,                             -- 推荐排名
    score               FLOAT,                           -- 推荐评分

    -- 推荐时价格（基准点）
    price_at_pick       NUMERIC NOT NULL,                -- 推荐时价格
    denomination        TEXT    NOT NULL DEFAULT 'usd',  -- 'usd' | 'sol'

    -- 当前价格（每次运行更新）
    current_price       NUMERIC,
    current_pct         FLOAT,                           -- 当前涨跌幅 %
    current_updated_at  TIMESTAMPTZ,

    -- 每日最高价 JSONB: {"1": {"high": 0.5, "pct": 25.0}, "2": {...}, ...}
    -- key = 推荐后第 N 天, value = 那天的最高价和涨幅
    daily_highs         JSONB   NOT NULL DEFAULT '{}',

    -- 全周期最佳表现
    best_price          NUMERIC,
    best_pct            FLOAT,
    best_day            INT,                             -- 最佳表现出现在第几天

    -- 状态
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,   -- 超过30天后停用
    tracking_days       INT     NOT NULL DEFAULT 0,      -- 已追踪天数

    -- 推荐时完整快照
    snapshot_data       JSONB,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(source, pick_date, chain, address)
);

COMMENT ON TABLE token_performance IS '推荐代币表现追踪，监控 daily_picks 和 hot_daily_picks 的价格变化';
COMMENT ON COLUMN token_performance.daily_highs IS 'JSONB: 每天最高价，key=天数(1-30)，value={"high": price, "pct": change%}';

-- 索引
CREATE INDEX IF NOT EXISTS idx_perf_active
    ON token_performance(is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_perf_source_date
    ON token_performance(source, pick_date DESC);

CREATE INDEX IF NOT EXISTS idx_perf_chain
    ON token_performance(chain, pick_date DESC);

-- RLS: 允许匿名读取（Portal 前端用 anon key 查询）
ALTER TABLE token_performance ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_public_read"
    ON token_performance FOR SELECT
    USING (true);
