-- ============================================================
-- Local PostgreSQL (agent_trading_local)
-- Migration: 045_credits
-- 执行: PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local -d agent_trading_local -f 045_credits.sql
-- ============================================================

-- R47 — Credit 算力体系(USDC 充值 + LLM token 计费)
-- 用户必须先充值 → 才能用 chat;每次 LLM 调用按 token 价格扣费;余额≤0 拒绝
-- 详见 docs/agent-pm/19-credit-system-spec.md

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. 用户余额(每用户一行,REAL TIME)
CREATE TABLE IF NOT EXISTS user_credits (
  user_id         UUID          PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  balance_usd     NUMERIC(14,8) NOT NULL DEFAULT 0,
  total_recharged NUMERIC(14,8) NOT NULL DEFAULT 0,
  total_consumed  NUMERIC(14,8) NOT NULL DEFAULT 0,
  updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
  CONSTRAINT balance_non_negative CHECK (balance_usd >= -0.01)  -- 容许微量负数防并发
);

-- 2. 交易历史(append-only)
CREATE TABLE IF NOT EXISTS credit_transactions (
  id                 BIGSERIAL    PRIMARY KEY,
  user_id            UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type               TEXT         NOT NULL CHECK (type IN ('recharge','consume','adjust','refund')),
  amount_usd         NUMERIC(14,8) NOT NULL,        -- 正 = 入账,负 = 扣费
  balance_after      NUMERIC(14,8) NOT NULL,
  recharge_order_id  BIGINT,
  chain_tx_hash      TEXT,
  model              TEXT,
  tokens_in          INT,
  tokens_out         INT,
  request_id         TEXT,
  ts                 TIMESTAMPTZ  NOT NULL DEFAULT now(),
  meta               JSONB
);
CREATE INDEX IF NOT EXISTS idx_credit_tx_user_ts ON credit_transactions(user_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_credit_tx_type    ON credit_transactions(type, ts DESC);

-- 3. 充值订单(用户点充值 → 创建订单 → 给地址 + 唯一金额 → 监听到账 → confirmed)
CREATE TABLE IF NOT EXISTS recharge_orders (
  id              BIGSERIAL    PRIMARY KEY,
  user_id         UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  chain           TEXT         NOT NULL CHECK (chain IN ('solana','ethereum','base','bsc')),
  receive_address TEXT         NOT NULL,
  amount_usd      NUMERIC(12,6) NOT NULL,         -- 用户付的精确金额(带随机零头)
  amount_base     NUMERIC(12,6) NOT NULL,         -- 用户输入的整数金额(如 $10)
  amount_nonce    NUMERIC(8,6)  NOT NULL,         -- 零头(如 $0.0034 用于唯一识别 tx)
  status          TEXT         NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','confirmed','expired','manual_review')),
  chain_tx_hash   TEXT,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
  confirmed_at    TIMESTAMPTZ,
  expires_at      TIMESTAMPTZ  NOT NULL          -- 默认 30 min
);
CREATE INDEX IF NOT EXISTS idx_recharge_pending ON recharge_orders(status, expires_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_recharge_user_ts ON recharge_orders(user_id, created_at DESC);

COMMENT ON TABLE user_credits IS 'R47 用户算力余额;balance_usd USDT-equivalent';
COMMENT ON TABLE credit_transactions IS 'R47 算力交易流水;append-only';
COMMENT ON TABLE recharge_orders IS 'R47 USDC 充值订单;amount_usd 含 nonce 用于唯一识别 tx';
