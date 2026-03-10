-- ============================================================
-- 004_smart_wallet_v2.sql
-- 聪明钱多维度分层体系
-- 注：token_trades.bc_progress 列在 003 中已存在，无需重建
-- ============================================================

-- ── smart_wallets：扩展多维度字段 ────────────────────────────
-- 分级: elite / verified / watching / blacklisted
ALTER TABLE smart_wallets
  ADD COLUMN IF NOT EXISTS tier           TEXT    NOT NULL DEFAULT 'watching',
  ADD COLUMN IF NOT EXISTS avg_entry_bc   FLOAT,
  ADD COLUMN IF NOT EXISTS active_weeks   INT     DEFAULT 1,
  ADD COLUMN IF NOT EXISTS is_blacklisted BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS total_sol_in   NUMERIC DEFAULT 0;

COMMENT ON COLUMN smart_wallets.tier IS
  'elite(≥0.65胜率,≥10笔,≥2周,<15%BC) | verified(≥0.5,≥5笔) | watching(≥0.4,≥3笔) | blacklisted';
COMMENT ON COLUMN smart_wallets.avg_entry_bc IS
  '历史平均买入BC进度(%)，精英钱包通常 < 15%';
COMMENT ON COLUMN smart_wallets.active_weeks IS
  '有效交易分布的自然周数，≥2周说明能力稳定而非运气';
COMMENT ON COLUMN smart_wallets.is_blacklisted IS
  '疑似Bot（同代币买入60秒内卖出）或长期负盈利';
COMMENT ON COLUMN smart_wallets.total_sol_in IS
  '累计买入 SOL 量';

-- ── 索引 ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_smart_wallets_tier
  ON smart_wallets(tier)
  WHERE is_blacklisted = FALSE;

CREATE INDEX IF NOT EXISTS idx_smart_wallets_blacklisted
  ON smart_wallets(is_blacklisted);
