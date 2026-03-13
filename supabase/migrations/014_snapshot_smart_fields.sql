-- ══════════════════════════════════════════════════════════
-- 014 token_snapshots 新增聪明钱 + 加速度字段
-- ══════════════════════════════════════════════════════════
--
-- 修复 daily_picks 漏选问题：
--   之前 token_snapshots 不存储 inflow_acceleration 和 smart_money 数据，
--   导致 daily_job 重建 TokenFeatures 时这些维度永远为 0（35分缺失），
--   最高分只能拿 ~50 分，无法达到 55 分的 "normal" 门槛。

ALTER TABLE token_snapshots ADD COLUMN IF NOT EXISTS inflow_acceleration    NUMERIC DEFAULT 0;
ALTER TABLE token_snapshots ADD COLUMN IF NOT EXISTS smart_money_count      INTEGER DEFAULT 0;
ALTER TABLE token_snapshots ADD COLUMN IF NOT EXISTS smart_money_net_sol    NUMERIC DEFAULT 0;
ALTER TABLE token_snapshots ADD COLUMN IF NOT EXISTS smart_elite_count      INTEGER DEFAULT 0;
ALTER TABLE token_snapshots ADD COLUMN IF NOT EXISTS smart_verified_count   INTEGER DEFAULT 0;
ALTER TABLE token_snapshots ADD COLUMN IF NOT EXISTS smart_watching_count   INTEGER DEFAULT 0;
