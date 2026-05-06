-- ============================================================
-- Local PostgreSQL (agent_trading_local)
-- Migration: 044_users
-- 执行: PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local -d agent_trading_local -f 044_users.sql
-- ============================================================

-- R46 — 邮箱/Google 账户体系
-- 设计:
--   - 自建 users 表(不依赖 Supabase auth.users)
--   - email 唯一登录主键
--   - password_hash NULL = 仅 OAuth 登录;google_id NULL = 仅密码登录
--   - 一个 email 可同时绑定密码 + Google(后续扩展)
--   - user_wallets.user_id 关联此表(R42 P1 已建)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
  id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  email           TEXT         UNIQUE NOT NULL,
  email_verified  BOOLEAN      NOT NULL DEFAULT FALSE,
  password_hash   TEXT,                                                -- bcrypt,NULL = 仅 OAuth
  google_id       TEXT,                                                -- Google sub claim,NULL = 仅密码
  display_name    TEXT,
  avatar_url      TEXT,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
  last_login_at   TIMESTAMPTZ,
  is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
  CONSTRAINT email_format CHECK (email ~* '^[^@]+@[^@]+\.[^@]+$'),
  CONSTRAINT must_have_login CHECK (password_hash IS NOT NULL OR google_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_users_email      ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_google     ON users(google_id) WHERE google_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_active     ON users(is_active, created_at DESC);

COMMENT ON TABLE users IS 'R46 用户账户(邮箱主登录 + Google OAuth 可选)';
COMMENT ON COLUMN users.password_hash IS 'bcrypt hash(60 字符);NULL 表示用户仅用 Google 登录';
COMMENT ON COLUMN users.google_id IS 'Google ID token sub claim';
