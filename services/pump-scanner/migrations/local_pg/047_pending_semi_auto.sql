-- ============================================================
-- Local PostgreSQL (agent_trading_local)
-- Migration: 047_pending_semi_auto
-- 执行: PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local \
--         -d agent_trading_local -f 047_pending_semi_auto.sql
-- ============================================================

-- R47 P6 — 半自动交易撤销窗口表
--
-- 单笔 ≥ $500 走半自动:写本表 status='pending',execute_after = now() + 10s
-- 1s tick cron 扫到 execute_after < now() 且 status='pending' → 调 trade_executor
-- 用户在 10s 内可调 cancel endpoint 改 status='cancelled'
-- 防 race:UPDATE WHERE status='pending' RETURNING — 同一行串行化

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS pending_semi_auto_trades (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  strategy_id    UUID,                      -- 关联 agent_strategies(可空,因为 strategies 删了不阻断 trade)
  chain          TEXT NOT NULL,
  token_address  TEXT NOT NULL,
  token_symbol   TEXT,
  action         TEXT NOT NULL CHECK (action IN ('buy','sell')),
  amount_usd     NUMERIC(12,2) NOT NULL,
  slippage_pct   NUMERIC(6,4),
  trigger_context JSONB,
  status         TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','executed','cancelled','expired','failed')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  execute_after  TIMESTAMPTZ NOT NULL,                 -- created_at + cancel_window_sec
  cancelled_at   TIMESTAMPTZ,
  executed_at    TIMESTAMPTZ,
  tx_hash        TEXT,
  cancel_reason  TEXT,
  error_message  TEXT
);

-- 关键索引:cron 扫 pending 用(partial index 只索引 pending,效率高)
CREATE INDEX IF NOT EXISTS idx_pending_semi_pending
  ON pending_semi_auto_trades(execute_after) WHERE status = 'pending';

-- 用户列表查询用(用户看自己的所有 pending / 历史)
CREATE INDEX IF NOT EXISTS idx_pending_semi_user_ts
  ON pending_semi_auto_trades(user_id, created_at DESC);

COMMENT ON TABLE pending_semi_auto_trades IS
  'R47 P6 半自动交易撤销窗口表。amount ≥ $500 入此表,10s 后 cron 自动执行,期间用户可撤销。';
COMMENT ON COLUMN pending_semi_auto_trades.execute_after IS
  '本笔交易允许执行的时间(创建时间 + cancel_window_sec,默认 10s)';

COMMIT;

\echo '✓ 047_pending_semi_auto applied'
