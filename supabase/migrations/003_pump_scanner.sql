-- ============================================================
-- pump.fun 内盘扫描器数据表
-- ============================================================

-- 1. 代币基础信息表
CREATE TABLE IF NOT EXISTS pump_tokens (
  mint            TEXT PRIMARY KEY,
  name            TEXT,
  symbol          TEXT,
  description     TEXT,
  image_uri       TEXT,
  creator         TEXT NOT NULL,          -- dev 钱包地址
  created_at      TIMESTAMPTZ NOT NULL,   -- 链上创建时间
  collected_at    TIMESTAMPTZ DEFAULT NOW(), -- 我们采集时间

  -- Social
  twitter         TEXT,
  telegram        TEXT,
  website         TEXT,
  has_social      BOOLEAN GENERATED ALWAYS AS (
    twitter IS NOT NULL OR telegram IS NOT NULL OR website IS NOT NULL
  ) STORED,

  -- 状态
  complete        BOOLEAN DEFAULT FALSE,  -- 是否已毕业
  graduated_at    TIMESTAMPTZ,            -- 毕业时间
  is_banned       BOOLEAN DEFAULT FALSE,

  -- 初始快照（创建瞬间）
  initial_buy_sol NUMERIC,               -- 创建者初始买入 SOL
  initial_mc_sol  NUMERIC,               -- 初始市值 SOL

  -- 创建者历史（后续计算填入）
  creator_prev_tokens     INT DEFAULT 0, -- 创建者历史发币数
  creator_success_rate    NUMERIC,       -- 创建者历史毕业率

  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 特征快照表（每个候选币在不同进度打快照）
CREATE TABLE IF NOT EXISTS token_snapshots (
  id              BIGSERIAL PRIMARY KEY,
  mint            TEXT NOT NULL REFERENCES pump_tokens(mint) ON DELETE CASCADE,
  snapshot_at     TIMESTAMPTZ DEFAULT NOW(),

  -- Bonding Curve 状态
  bc_progress     NUMERIC NOT NULL,       -- 0~100 毕业进度 %
  v_sol           NUMERIC,               -- vSolInBondingCurve
  market_cap_sol  NUMERIC,
  market_cap_usd  NUMERIC,

  -- 交易统计（从上次快照到现在的累计）
  buy_count       INT DEFAULT 0,
  sell_count      INT DEFAULT 0,
  buy_volume_sol  NUMERIC DEFAULT 0,
  sell_volume_sol NUMERIC DEFAULT 0,
  unique_buyers   INT DEFAULT 0,
  unique_sellers  INT DEFAULT 0,

  -- 买卖比（关键特征）
  buy_sell_ratio_count  NUMERIC,         -- buy_count / sell_count
  buy_sell_ratio_vol    NUMERIC,         -- buy_volume / sell_volume

  -- 流速特征
  inflow_rate_sol_pm    NUMERIC,         -- SOL 流入速率（每分钟）
  outflow_rate_sol_pm   NUMERIC,         -- SOL 流出速率（每分钟）
  net_inflow_sol_pm     NUMERIC,         -- 净流入速率

  -- 进度速度
  bc_progress_rate      NUMERIC,         -- 进度增速（%/小时）

  -- Dev 行为
  dev_sold        BOOLEAN DEFAULT FALSE, -- dev 是否已卖出
  dev_sold_pct    NUMERIC DEFAULT 0,     -- dev 卖出比例

  -- 大单
  large_buy_count INT DEFAULT 0,         -- 单笔 > 0.5 SOL 买入次数
  max_single_buy  NUMERIC DEFAULT 0,     -- 最大单笔买入 SOL

  -- Social 快照
  reply_count     INT DEFAULT 0          -- 讨论数
);

CREATE INDEX IF NOT EXISTS idx_snapshots_mint ON token_snapshots(mint);
CREATE INDEX IF NOT EXISTS idx_snapshots_bc ON token_snapshots(bc_progress);

-- 3. 结果标签表（72h 后回填）
CREATE TABLE IF NOT EXISTS token_outcomes (
  mint              TEXT PRIMARY KEY REFERENCES pump_tokens(mint),
  labeled_at        TIMESTAMPTZ DEFAULT NOW(),

  -- 毕业
  did_graduate      BOOLEAN DEFAULT FALSE,
  hours_to_graduate NUMERIC,              -- 从创建到毕业花了多少小时

  -- 毕业后价格
  price_1h_after    NUMERIC,             -- 毕业后 1h 最高涨幅 %
  price_4h_after    NUMERIC,
  price_24h_after   NUMERIC,
  peak_multiplier   NUMERIC,             -- 最高点相对毕业价的倍数

  -- 标签（用于训练）
  label_2x          BOOLEAN,             -- 内盘+外盘综合有没有达到 2x
  label_graduate    BOOLEAN,             -- 是否毕业
  label_10x         BOOLEAN              -- 是否达到 10x（可选目标）
);

-- 4. 每日推送表
CREATE TABLE IF NOT EXISTS daily_picks (
  id          BIGSERIAL PRIMARY KEY,
  pick_date   DATE NOT NULL DEFAULT CURRENT_DATE,
  mint        TEXT NOT NULL REFERENCES pump_tokens(mint),
  rank        INT NOT NULL,              -- 当日排名 1~10
  score       NUMERIC NOT NULL,          -- 综合评分 0~100
  score_detail JSONB,                   -- 各维度分数明细
  bc_progress  NUMERIC,                 -- 推送时的内盘进度
  market_cap_sol NUMERIC,               -- 推送时市值

  -- 结果追踪（后续回填）
  result_2x   BOOLEAN,
  result_peak NUMERIC,                  -- 实际最高涨幅 %

  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(pick_date, mint)
);

CREATE INDEX IF NOT EXISTS idx_picks_date ON daily_picks(pick_date);

-- 5. 原始交易流水（用于聪明钱分析，保留30天）
CREATE TABLE IF NOT EXISTS token_trades (
  id              BIGSERIAL PRIMARY KEY,
  mint            TEXT NOT NULL,
  tx_sig          TEXT UNIQUE,
  trader          TEXT NOT NULL,         -- 交易者钱包
  tx_type         TEXT NOT NULL,         -- 'buy' | 'sell'
  sol_amount      NUMERIC NOT NULL,
  token_amount    NUMERIC NOT NULL,
  bc_progress     NUMERIC,              -- 交易时内盘进度
  traded_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_mint ON token_trades(mint);
CREATE INDEX IF NOT EXISTS idx_trades_trader ON token_trades(trader);
CREATE INDEX IF NOT EXISTS idx_trades_at ON token_trades(traded_at);

-- 30天自动清理（节省免费额度）
CREATE OR REPLACE FUNCTION delete_old_trades() RETURNS void AS $$
  DELETE FROM token_trades WHERE traded_at < NOW() - INTERVAL '30 days';
$$ LANGUAGE SQL;

-- 6. 聪明钱钱包表（胜率追踪）
CREATE TABLE IF NOT EXISTS smart_wallets (
  wallet          TEXT PRIMARY KEY,
  total_trades    INT DEFAULT 0,
  win_trades      INT DEFAULT 0,         -- 参与并获利的次数
  win_rate        NUMERIC GENERATED ALWAYS AS (
    CASE WHEN total_trades > 0 THEN win_trades::NUMERIC / total_trades ELSE 0 END
  ) STORED,
  avg_profit_pct  NUMERIC DEFAULT 0,
  first_seen      TIMESTAMPTZ DEFAULT NOW(),
  last_seen       TIMESTAMPTZ DEFAULT NOW()
);
