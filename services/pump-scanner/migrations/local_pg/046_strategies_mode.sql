-- ============================================================
-- Local PostgreSQL (agent_trading_local)
-- Migration: 046_strategies_mode_audit
-- 执行: PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local \
--         -d agent_trading_local -f 046_strategies_mode.sql
-- ============================================================

-- R47 P4 — agent_strategies 加 daily_loss / consecutive_losses + mode 变化 audit trigger
--
-- 背景:agent_strategies 表已有 mode CHECK ('paper','live') 约束(R42 P0.4)。
-- 但缺少:
--   1. daily_loss_max_usd / consecutive_losses_max 强制保护字段
--   2. mode 变化 audit trigger(切实盘是 critical 操作必须落 audit_log)
--   3. live 策略 partial 索引(运维监控)

\set ON_ERROR_STOP on

BEGIN;

-- 1. 加风控保护字段(R42 P0.4 设计但未落 schema)
ALTER TABLE agent_strategies
  ADD COLUMN IF NOT EXISTS daily_loss_max_usd NUMERIC(10,2) DEFAULT 200,
  ADD COLUMN IF NOT EXISTS consecutive_losses_max INT DEFAULT 3;

-- 2. live 策略 partial 索引(运维快速找出所有 live 策略)
CREATE INDEX IF NOT EXISTS idx_agent_strategies_mode_live
  ON agent_strategies(mode) WHERE mode = 'live';

-- 3. audit trigger:每次 mode 列变化写 security_audit_log critical
CREATE OR REPLACE FUNCTION audit_strategy_mode_change() RETURNS TRIGGER AS $$
BEGIN
  IF OLD.mode IS DISTINCT FROM NEW.mode THEN
    INSERT INTO security_audit_log (device_id, event_type, severity, payload)
    VALUES (
      gen_random_uuid(),
      'config_change',
      'critical',
      jsonb_build_object(
        'kind', 'strategy_mode_change',
        'strategy_id', NEW.id::text,
        'name', NEW.name,
        'user_id', NEW.user_id::text,
        'old_mode', OLD.mode,
        'new_mode', NEW.mode,
        'changed_at', now()
      )
    );
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_strategy_mode ON agent_strategies;
CREATE TRIGGER trg_audit_strategy_mode
  AFTER UPDATE ON agent_strategies
  FOR EACH ROW EXECUTE FUNCTION audit_strategy_mode_change();

COMMENT ON COLUMN agent_strategies.daily_loss_max_usd IS
  'live 模式日亏损上限(美元)。R42 P0.4 daily_loss 锁回 paper。';
COMMENT ON COLUMN agent_strategies.consecutive_losses_max IS
  'live 模式连续亏损次数上限。超出自动暂停策略。';

COMMIT;

\echo '✓ 046_strategies_mode_audit applied'
