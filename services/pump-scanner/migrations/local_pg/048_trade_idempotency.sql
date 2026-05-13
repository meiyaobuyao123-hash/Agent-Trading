-- R59 P0 — Trade idempotency key + USDC recharge tx_hash dedup
--
-- Background:
-- 1. action_dispatcher → execute_trade → dex_router.broadcast. If LLM/network
--    retry fires execute_trade twice for same event → 2 tx on chain (用户钱包双扣)
-- 2. credit_recharge_loop cron 60s tick; if RPC fork/re-org returns same tx_hash
--    twice → confirm_recharge_order called twice → +2x credit
--
-- Fix:
-- 1. agent_executions: add request_id TEXT UNIQUE — caller computes deterministic
--    request_id from (strategy_id, signal_id, action, amount), DB enforces unique
-- 2. recharge_orders: partial unique index on (chain, chain_tx_hash) WHERE
--    status='confirmed' — once confirmed, same tx_hash can't be reused

BEGIN;

-- ── 1. agent_executions.request_id (idempotency for trade execution) ──
ALTER TABLE agent_executions
    ADD COLUMN IF NOT EXISTS request_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uniq_agent_executions_request_id
    ON agent_executions(request_id)
    WHERE request_id IS NOT NULL;

COMMENT ON COLUMN agent_executions.request_id IS
    'R59 P0: idempotency key. Caller builds deterministic id from '
    '(strategy_id, signal_id, action, amount_cents). DB enforces unique → '
    'retry can detect duplicate and skip broadcast.';

-- ── 2. recharge_orders 防 RPC re-org 重复入账 ──
-- 仅对 confirmed 状态做 unique 约束(pending 可有多条同 tx_hash)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_recharge_orders_confirmed_tx
    ON recharge_orders(chain, chain_tx_hash)
    WHERE status = 'confirmed' AND chain_tx_hash IS NOT NULL;

COMMENT ON INDEX uniq_recharge_orders_confirmed_tx IS
    'R59 P0: once a tx_hash is confirmed on a chain, it cannot be confirmed '
    'again — protects against RPC fork/re-org / cron overlap re-processing.';

COMMIT;
