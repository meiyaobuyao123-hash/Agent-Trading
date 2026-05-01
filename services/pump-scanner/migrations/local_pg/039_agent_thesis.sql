-- ============================================================
-- Local PostgreSQL (agent_trading_local on server PG 14)
-- Migration: 039_agent_thesis
-- 执行: psql -h 127.0.0.1 -U agent_local -d agent_trading_local -f 039_agent_thesis.sql
-- 引用 docs/agent-pm/17-tech-plan.md 增量决策(2026-05-01):8 张新表迁本地 PG
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Migration 039: agent_thesis 表(S08 thesis-writer 输出独立持久化)
-- 引用 17-tech-plan.md Phase 2
-- 引用 docs/agent-pm/03-prd.md §2.7 Thesis 完整 Schema
-- 引用 docs/agent-pm/05-tool-catalog.md S08 thesis-writer

CREATE TABLE IF NOT EXISTS agent_thesis (
  thesis_id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id            UUID         NOT NULL,
  ts                   TIMESTAMPTZ  NOT NULL DEFAULT now(),
  chain                TEXT         NOT NULL,
  token_address        TEXT         NOT NULL,
  token_symbol         TEXT,
  level                TEXT         NOT NULL,                         -- 'L1' | 'L2' | 'L3'
  direction            TEXT         NOT NULL,
  conviction           NUMERIC(3,2) NOT NULL,
  entry_zone           JSONB,                                         -- {low: 1.10, high: 1.20}
  stop_loss            NUMERIC,
  target_price         JSONB,                                         -- [t1, t2, t3] 分批止盈
  risks                TEXT[]       NOT NULL,                         -- 长度 ≥ 2
  summary_30w          TEXT         NOT NULL,                         -- ≤ 30 字总结
  evidence             JSONB        NOT NULL,                         -- [{source, value, ts}, ...] 必引真实数据
  similar_past_cases   JSONB,                                         -- T04 recall_memory 结果
  technical_report     JSONB,                                         -- S01 输出
  sentiment_report     JSONB,                                         -- S02 输出
  onchain_report       JSONB,                                         -- S03 输出
  debate_record        JSONB,                                         -- L3 才有 (Bull R1/Bear R1/Bull R2/Bear R2/Facilitator)
  cost_usd             NUMERIC(10,6),
  latency_ms           INT,
  prompt_version_used  TEXT,
  user_feedback        TEXT,                                          -- 'helpful' | 'neutral' | 'misleading'(用户事后标注)
  CONSTRAINT thesis_level_valid     CHECK (level IN ('L1','L2','L3')),
  CONSTRAINT thesis_direction_valid CHECK (direction IN ('bullish','bearish','neutral','hold','avoid')),
  CONSTRAINT thesis_conviction_rng  CHECK (conviction BETWEEN 0 AND 1),
  CONSTRAINT thesis_risks_min_2     CHECK (array_length(risks, 1) >= 2),
  CONSTRAINT thesis_low_then_hold   CHECK (
    -- conviction < 0.5 时 direction 必为 hold/avoid (PRD 硬约束)
    conviction >= 0.5 OR direction IN ('hold','avoid','neutral')
  )
);

CREATE INDEX IF NOT EXISTS idx_thesis_device_ts ON agent_thesis(device_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_thesis_token     ON agent_thesis(chain, token_address, ts DESC);
CREATE INDEX IF NOT EXISTS idx_thesis_level     ON agent_thesis(level, ts DESC);

COMMENT ON TABLE agent_thesis IS 'S08 thesis-writer 输出 + L1/L2/L3 完整 Thesis 持久化';
COMMENT ON COLUMN agent_thesis.summary_30w IS '≤30 字白话总结,小白 persona 看这个';
COMMENT ON COLUMN agent_thesis.evidence IS '必须引真实数据源(不能 LLM 编造) [{source:"smart_money_signals",value:"+45000",ts:...}]';
