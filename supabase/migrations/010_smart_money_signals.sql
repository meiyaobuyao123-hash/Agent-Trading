-- 010: Smart Money Signals 聚合表
-- 多链聪明钱买卖信号，按代币聚合

CREATE TABLE IF NOT EXISTS smart_money_signals (
  id BIGSERIAL PRIMARY KEY,
  chain TEXT NOT NULL,
  token_address TEXT NOT NULL,
  token_name TEXT DEFAULT '',
  token_symbol TEXT DEFAULT '',

  -- 买卖聚合
  buy_count INT DEFAULT 0,
  sell_count INT DEFAULT 0,
  buy_volume DOUBLE PRECISION DEFAULT 0,
  sell_volume DOUBLE PRECISION DEFAULT 0,
  unique_buyers INT DEFAULT 0,
  unique_sellers INT DEFAULT 0,

  -- 分层统计
  elite_buy_count INT DEFAULT 0,
  elite_sell_count INT DEFAULT 0,
  verified_buy_count INT DEFAULT 0,
  verified_sell_count INT DEFAULT 0,

  -- 热度
  heat_score DOUBLE PRECISION DEFAULT 0,
  net_flow INT DEFAULT 0,
  signal_strength TEXT DEFAULT 'weak',

  -- 市场数据
  price_usd DOUBLE PRECISION DEFAULT 0,
  market_cap_usd DOUBLE PRECISION DEFAULT 0,
  liquidity_usd DOUBLE PRECISION DEFAULT 0,
  volume_24h_usd DOUBLE PRECISION DEFAULT 0,
  price_change_24h DOUBLE PRECISION DEFAULT 0,
  price_change_1h DOUBLE PRECISION DEFAULT 0,
  image_url TEXT,
  pair_address TEXT,
  dex_id TEXT,

  -- 时间
  latest_signal_at TIMESTAMPTZ,
  scan_time TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(chain, token_address)
);

CREATE INDEX IF NOT EXISTS idx_sms_heat ON smart_money_signals(heat_score DESC);
CREATE INDEX IF NOT EXISTS idx_sms_chain ON smart_money_signals(chain);
CREATE INDEX IF NOT EXISTS idx_sms_scan ON smart_money_signals(scan_time);

-- RLS
ALTER TABLE smart_money_signals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "smart_money_signals_read" ON smart_money_signals FOR SELECT USING (true);
