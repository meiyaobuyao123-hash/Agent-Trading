-- =====================================================
-- AiTrading — Supabase 初始化 Migration
-- 原则：只存业务数据，行情/价格数据不入库（走Redis缓存）
-- =====================================================

-- 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =====================================================
-- 1. 官方策略代币组合（运营管理，预估 < 100 行）
-- =====================================================
CREATE TABLE official_portfolio (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token_address TEXT NOT NULL,
  chain_id     INTEGER NOT NULL,         -- 1=ETH, 56=BSC, 900=SOL
  symbol       TEXT NOT NULL,
  name         TEXT,
  entry_price  NUMERIC(30, 10) NOT NULL, -- 入选时价格快照（仅这一次写入）
  entry_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reason_tags  TEXT[] DEFAULT '{}',      -- ['聪明钱驱动','交易量异动']
  risk_level   TEXT NOT NULL DEFAULT 'medium' CHECK (risk_level IN ('low','medium','high')),
  status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','exited')),
  exit_price   NUMERIC(30, 10),          -- 下架时填入
  exit_at      TIMESTAMPTZ,
  created_by   UUID,                     -- admin 用户 id
  created_at   TIMESTAMPTZ DEFAULT NOW()
);
-- 当前价格不存库！实时从 Binance API 取，缓存在 Redis

COMMENT ON TABLE official_portfolio IS '官方推荐代币组合。价格数据不入库，实时从缓存取。';

-- =====================================================
-- 2. 信号表（只存计算后的轻量元数据，30天自动清理）
-- 不存 raw_data，不存 Binance API 原始响应
-- =====================================================
CREATE TABLE signals (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token_address    TEXT NOT NULL,
  chain_id         INTEGER NOT NULL,
  symbol           TEXT,
  direction        TEXT NOT NULL CHECK (direction IN ('long','watch','exit')),
  confidence_score INTEGER NOT NULL DEFAULT 0 CHECK (confidence_score BETWEEN 0 AND 100),
  trigger_price    NUMERIC(30, 10),       -- 信号生成时的参考价（快照一次）
  smart_money_count INTEGER DEFAULT 0,    -- 聪明钱数量（信号评分关键字段）
  risk_level       TEXT NOT NULL DEFAULT 'medium' CHECK (risk_level IN ('low','medium','high')),
  status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','triggered','expired','cancelled')),
  -- 不存 raw_data JSONB，太大，且不需要持久化
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  expires_at       TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days')
);

-- 自动清理 30 天前的信号（Supabase 可通过 pg_cron 或 Edge Function 定期执行）
-- 生产时加: DELETE FROM signals WHERE created_at < NOW() - INTERVAL '30 days';
COMMENT ON TABLE signals IS '只存信号元数据，不存原始API响应。过期7天自动失效，30天清理。';

-- =====================================================
-- 3. 策略表（用户自定义策略配置）
-- =====================================================
CREATE TABLE strategies (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  name             TEXT NOT NULL,
  description      TEXT,
  -- 条件树：用轻量 JSONB，避免存大对象
  condition_tree   JSONB NOT NULL DEFAULT '[]',
  exec_config      JSONB NOT NULL DEFAULT '{}',
  -- AI 生成的脚本：TEXT 类型，按需存储
  generated_script TEXT,
  status           TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','paused','archived')),
  is_official      BOOLEAN NOT NULL DEFAULT false,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE strategies IS '用户策略配置。condition_tree 和 exec_config 保持轻量 JSON。';

-- 自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER strategies_updated_at
  BEFORE UPDATE ON strategies
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =====================================================
-- 4. 交易记录（实际成交记录，必须持久化）
-- =====================================================
CREATE TABLE trades (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  strategy_id    UUID REFERENCES strategies(id) ON DELETE SET NULL,
  signal_id      UUID REFERENCES signals(id) ON DELETE SET NULL,
  token_address  TEXT NOT NULL,
  chain_id       INTEGER NOT NULL,
  symbol         TEXT,
  tx_hash        TEXT UNIQUE,            -- 链上交易 hash，唯一
  direction      TEXT NOT NULL CHECK (direction IN ('buy','sell')),
  amount_in      NUMERIC(30, 10),        -- 花费金额
  amount_out     NUMERIC(30, 10),        -- 获得金额
  exec_price     NUMERIC(30, 10),        -- 实际成交价
  gas_used       NUMERIC(30, 10),
  status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','confirmed','failed')),
  error_msg      TEXT,                   -- 失败原因
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE trades IS '链上实际成交记录，必须持久化。不存价格历史，只存每笔成交快照。';

-- =====================================================
-- 5. Row Level Security（RLS）— 用户只能看自己的数据
-- =====================================================
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;

-- 策略：用户只能读写自己的（官方策略所有人可读）
CREATE POLICY "users_own_strategies" ON strategies
  FOR ALL USING (
    user_id = auth.uid()
    OR is_official = true
  );

-- 交易：用户只能看自己的
CREATE POLICY "users_own_trades" ON trades
  FOR ALL USING (user_id = auth.uid());

-- 官方组合和信号：所有登录用户可读
ALTER TABLE official_portfolio ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anyone_read_portfolio" ON official_portfolio
  FOR SELECT USING (true);

CREATE POLICY "anyone_read_signals" ON signals
  FOR SELECT USING (true);

-- =====================================================
-- 6. 索引（只加必要索引，减少存储开销）
-- =====================================================
CREATE INDEX idx_signals_status ON signals(status) WHERE status = 'active';
CREATE INDEX idx_signals_created ON signals(created_at DESC);
CREATE INDEX idx_portfolio_status ON official_portfolio(status) WHERE status = 'active';
CREATE INDEX idx_trades_user ON trades(user_id, created_at DESC);
CREATE INDEX idx_strategies_user ON strategies(user_id) WHERE status != 'archived';

-- =====================================================
-- 完成
-- 预估存储：官方组合<10KB + 信号<500KB/月 + 策略按用户增长 + 交易按实际量
-- 远低于 Supabase 免费版 500MB 限制
-- =====================================================
