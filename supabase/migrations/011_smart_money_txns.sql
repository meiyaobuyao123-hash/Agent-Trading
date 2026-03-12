-- 011: Smart Money Transactions — 单笔交易级追踪
-- 记录每个聪明钱钱包的每笔买卖交易，支持详情展示

CREATE TABLE IF NOT EXISTS smart_money_txns (
  id BIGSERIAL PRIMARY KEY,
  chain TEXT NOT NULL,
  token_address TEXT NOT NULL,
  wallet_address TEXT NOT NULL,
  wallet_tier TEXT NOT NULL DEFAULT 'watching',
  tx_type TEXT NOT NULL CHECK (tx_type IN ('buy', 'sell')),
  volume_usd DOUBLE PRECISION DEFAULT 0,
  market_cap_at_tx DOUBLE PRECISION DEFAULT 0,
  price_at_tx DOUBLE PRECISION DEFAULT 0,
  tx_time TIMESTAMPTZ NOT NULL,
  scan_time TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(chain, token_address, wallet_address, tx_type, tx_time)
);

-- 按代币查交易（详情弹窗主查询）
CREATE INDEX IF NOT EXISTS idx_smt_token ON smart_money_txns(chain, token_address, tx_time DESC);
-- 按钱包查交易（未来钱包画像）
CREATE INDEX IF NOT EXISTS idx_smt_wallet ON smart_money_txns(wallet_address, tx_time DESC);
-- 清理旧数据
CREATE INDEX IF NOT EXISTS idx_smt_scan ON smart_money_txns(scan_time);

-- RLS: 所有人可读
ALTER TABLE smart_money_txns ENABLE ROW LEVEL SECURITY;
CREATE POLICY "smart_money_txns_read" ON smart_money_txns FOR SELECT USING (true);
