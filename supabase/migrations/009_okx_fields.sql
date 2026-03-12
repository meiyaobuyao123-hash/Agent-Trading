-- ══════════════════════════════════════════════════════════
-- 009 OKX 数据源新增字段
-- ══════════════════════════════════════════════════════════
--
-- hot_coins 表新增 OKX 独有字段：
--   volume_5m_usd    — 5分钟成交量（OKX 5M 粒度）
--   volume_4h_usd    — 4小时成交量
--   price_change_5m  — 5分钟价格变化
--   price_change_4h  — 4小时价格变化
--   circ_supply      — 流通供应量
--   token_logo_url   — 代币图标 URL（OKX 提供）

ALTER TABLE hot_coins ADD COLUMN IF NOT EXISTS volume_5m_usd    NUMERIC;
ALTER TABLE hot_coins ADD COLUMN IF NOT EXISTS volume_4h_usd    NUMERIC;
ALTER TABLE hot_coins ADD COLUMN IF NOT EXISTS price_change_5m  NUMERIC;
ALTER TABLE hot_coins ADD COLUMN IF NOT EXISTS price_change_4h  NUMERIC;
ALTER TABLE hot_coins ADD COLUMN IF NOT EXISTS circ_supply      NUMERIC;
ALTER TABLE hot_coins ADD COLUMN IF NOT EXISTS token_logo_url   TEXT;
