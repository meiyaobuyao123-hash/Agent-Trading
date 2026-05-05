-- ============================================================
-- Local PostgreSQL (agent_trading_local on server PG 14)
-- Migration: 043_user_wallets
-- 执行: psql -h 127.0.0.1 -U agent_local -d agent_trading_local -f 043_user_wallets.sql
-- ============================================================

-- R42 P1 — 用户钱包私钥安全存储
-- 设计:AES-256-GCM 加密 + master_key 单独管(env)
-- 详见 docs/agent-pm/18-trade-execution-spec.md §1
-- 详见 services/pump-scanner/agent/crypto_box.py

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS user_wallets (
  id                       BIGSERIAL   PRIMARY KEY,
  user_id                  UUID        NOT NULL,                 -- Supabase auth.users.id
  chain                    TEXT        NOT NULL,                 -- 'solana' / 'ethereum' / 'bsc' / 'base'
  public_key               TEXT        NOT NULL,                 -- 钱包地址(显示用,可公开)
  encrypted_private_key    TEXT        NOT NULL,                 -- base64(nonce|ct|tag),crypto_box.encrypt_private_key 输出
  label                    TEXT,                                  -- 用户起的名字 "我的主钱包" 等
  is_default               BOOL        NOT NULL DEFAULT FALSE,
  is_active                BOOL        NOT NULL DEFAULT TRUE,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at             TIMESTAMPTZ,
  CONSTRAINT chain_valid   CHECK (chain IN ('solana','ethereum','bsc','base','arbitrum','polygon','optimism')),
  CONSTRAINT unique_pubkey UNIQUE (user_id, chain, public_key)  -- 同一 user 同链同 pub_key 只存一份
);

CREATE INDEX IF NOT EXISTS idx_user_wallets_user        ON user_wallets(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_user_wallets_user_chain  ON user_wallets(user_id, chain, is_active);

COMMENT ON TABLE user_wallets IS 'R42 P1 用户钱包私钥(AES-256-GCM 加密)';
COMMENT ON COLUMN user_wallets.encrypted_private_key IS 'base64(nonce|ciphertext|auth_tag),master_key 来源 WALLET_MASTER_KEY env';
COMMENT ON COLUMN user_wallets.public_key IS '可公开的钱包地址(SOL base58 / EVM 0x...)';

-- 安全提示(写到 README):
-- 1. encrypted_private_key 永不返给 Flutter
-- 2. master_key (WALLET_MASTER_KEY env) 单独管,不入 git
-- 3. PG dump 单独泄漏 → 拿不出私钥
-- 4. master_key 单独泄漏 → 拿不出私钥(需 PG)
-- 5. 同时拿到 → 私钥可解(同 KMS 同问题)
