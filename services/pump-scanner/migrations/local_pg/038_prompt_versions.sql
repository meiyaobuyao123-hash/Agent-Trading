-- ============================================================
-- Local PostgreSQL (agent_trading_local on server PG 14)
-- Migration: 038_prompt_versions
-- 执行: psql -h 127.0.0.1 -U agent_local -d agent_trading_local -f 038_prompt_versions.sql
-- 引用 docs/agent-pm/17-tech-plan.md 增量决策(2026-05-01):8 张新表迁本地 PG
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Migration 038: Prompt Library 版本化 + A/B 灰度
-- 引用 17-tech-plan.md Phase 2
-- 引用 docs/agent-pm/07-prompt-library.md
-- 18 个 P(P01-P18) + Canary 5% / Beta 25% / GA 100% 渐进灰度

-- ============================================================
-- 1. prompt_versions(每个 prompt 多版本并存)
-- ============================================================
CREATE TABLE IF NOT EXISTS prompt_versions (
  id              BIGSERIAL   PRIMARY KEY,
  prompt_id       TEXT        NOT NULL,                              -- 'P01' ... 'P18'
  version         TEXT        NOT NULL,                              -- 'v1.0' / 'v1.1' / 'v2.0' (semver)
  content         TEXT        NOT NULL,                              -- 完整 prompt 文本
  frontmatter     JSONB       NOT NULL,                              -- model / temperature / cache_breakpoints / token_limit / few_shots
  examples        JSONB,                                             -- few-shot 示例数组
  status          TEXT        NOT NULL DEFAULT 'draft',
  rollout_pct     INT         NOT NULL DEFAULT 0,
  owner           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  promoted_at     TIMESTAMPTZ,
  retired_at      TIMESTAMPTZ,
  notes           TEXT,
  CONSTRAINT prompt_version_unique  UNIQUE(prompt_id, version),
  CONSTRAINT prompt_status_valid    CHECK (status IN ('draft','canary','beta','ga','retired')),
  CONSTRAINT prompt_rollout_valid   CHECK (rollout_pct BETWEEN 0 AND 100),
  CONSTRAINT prompt_id_format       CHECK (prompt_id ~ '^P[0-9]{2}$')
);

CREATE INDEX IF NOT EXISTS idx_prompt_active ON prompt_versions(prompt_id, status) WHERE status IN ('canary','beta','ga');

COMMENT ON TABLE prompt_versions IS 'Prompt Library v1;每个 P 多版本并存,渐进灰度 draft→canary 5%→beta 25%→ga 100%';

-- ============================================================
-- 2. prompt_invocations(A/B 调用回溯,可选,只采样)
-- ============================================================
CREATE TABLE IF NOT EXISTS prompt_invocations (
  id              BIGSERIAL   PRIMARY KEY,
  ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
  device_id       UUID        NOT NULL,
  prompt_id       TEXT        NOT NULL,
  version_used    TEXT        NOT NULL,
  bucket          INT,                                                -- hash(device_id) % 100
  input_tokens    INT,
  output_tokens   INT,
  cost_usd        NUMERIC(10,6),
  cache_hit       BOOLEAN,
  latency_ms      INT,
  skill_name      TEXT,                                               -- 调用方
  loop_name       TEXT,                                               -- 'thesis' | 'reflect' | 'chat' | ...
  outcome         TEXT                                                -- 'success' | 'parse_fail' | 'timeout' | 'safety_block'
);

CREATE INDEX IF NOT EXISTS idx_invok_prompt_ts ON prompt_invocations(prompt_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_invok_device_ts ON prompt_invocations(device_id, ts DESC);

COMMENT ON TABLE prompt_invocations IS 'Prompt 调用回溯(可采样写入,30 天保留);A/B 对比看版本表现';
