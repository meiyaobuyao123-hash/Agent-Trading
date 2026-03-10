-- ============================================================
-- 005_hot_coins.sql
-- 热币榜：多链外盘代币发现系统
-- 覆盖链：SOL / BSC / ETH / Base
-- 数据源：GeckoTerminal + GoPlus + Helius + DexScreener
-- ============================================================

-- ── 热币实时表（每2小时更新）────────────────────────────────
CREATE TABLE IF NOT EXISTS hot_coins (
    id              BIGSERIAL PRIMARY KEY,
    chain           TEXT    NOT NULL,          -- 'solana' | 'bsc' | 'ethereum' | 'base'
    address         TEXT    NOT NULL,          -- 代币合约地址
    name            TEXT,
    symbol          TEXT,
    pair_address    TEXT,                      -- DEX 交易对地址
    dex_id          TEXT,                      -- raydium / pancakeswap / uniswap / aerodrome 等

    -- 市场数据（GeckoTerminal）
    price_usd           NUMERIC,
    market_cap_usd      NUMERIC,
    liquidity_usd       NUMERIC,
    volume_24h_usd      NUMERIC,
    volume_1h_usd       NUMERIC,

    -- 价格变化
    price_change_1h     FLOAT,
    price_change_6h     FLOAT,
    price_change_24h    FLOAT,

    -- 交易数据
    buys_1h     INT,
    sells_1h    INT,
    buys_24h    INT,
    sells_24h   INT,

    -- 代币年龄
    pair_created_at     TIMESTAMPTZ,
    age_days            FLOAT,

    -- 持有者（GoPlus；SOL top1 来自 Helius）
    holder_count        INT,
    top10_holder_pct    FLOAT,               -- GoPlus: top10 持仓比例
    top1_holder_pct     FLOAT,               -- Helius(SOL) / NULL(其他链)

    -- 安全检测（GoPlus）
    is_honeypot         BOOLEAN  DEFAULT FALSE,
    is_open_source      BOOLEAN  DEFAULT TRUE,
    buy_tax             FLOAT    DEFAULT 0,
    sell_tax            FLOAT    DEFAULT 0,
    goplus_risk         BOOLEAN  DEFAULT FALSE,  -- 任何风险标记

    -- 社交（DexScreener）
    has_twitter         BOOLEAN  DEFAULT FALSE,
    has_telegram        BOOLEAN  DEFAULT FALSE,
    has_website         BOOLEAN  DEFAULT FALSE,

    -- 打分结果
    score               FLOAT,
    score_m             FLOAT,               -- 动量分（满50）
    score_q             FLOAT,               -- 品质分（满30）
    score_p             FLOAT,               -- 潜力分（满20）
    score_detail        JSONB,
    recommendation      TEXT,               -- 'strong' | 'normal' | 'skip'

    scanned_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(chain, address)
);

COMMENT ON TABLE hot_coins IS '热币榜：多链外盘代币实时数据+评分，每2小时更新';
COMMENT ON COLUMN hot_coins.top1_holder_pct IS 'SOL链由Helius精确计算，其他链为NULL';
COMMENT ON COLUMN hot_coins.goplus_risk IS '蜜罐/高税/高集中度等任一风险为TRUE';

-- ── 热币日榜（每天 UTC 02:00 生成）──────────────────────────
CREATE TABLE IF NOT EXISTS hot_daily_picks (
    id              BIGSERIAL PRIMARY KEY,
    pick_date       DATE    NOT NULL DEFAULT CURRENT_DATE,
    chain           TEXT    NOT NULL,
    address         TEXT    NOT NULL,
    name            TEXT,
    symbol          TEXT,
    rank            INT,
    score           FLOAT,
    market_cap_usd  NUMERIC,
    price_change_24h FLOAT,
    recommendation  TEXT,
    snapshot        JSONB,                   -- 完整快照（含 score_detail、dex 等）
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(pick_date, chain, address)
);

COMMENT ON TABLE hot_daily_picks IS '热币日榜 Top20，跨链分配（每链最多8个）';

-- ── 索引 ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_hot_coins_score
    ON hot_coins(score DESC)
    WHERE goplus_risk = FALSE;

CREATE INDEX IF NOT EXISTS idx_hot_coins_chain
    ON hot_coins(chain, score DESC);

CREATE INDEX IF NOT EXISTS idx_hot_coins_scanned
    ON hot_coins(scanned_at DESC);

CREATE INDEX IF NOT EXISTS idx_hot_daily_date
    ON hot_daily_picks(pick_date DESC, rank ASC);
