-- ============================================================
-- Local PostgreSQL (agent_trading_local on server PG 14)
-- Migration: 041_eval_results
-- 执行: psql -h 127.0.0.1 -U agent_local -d agent_trading_local -f 041_eval_results.sql
-- 引用 docs/agent-pm/17-tech-plan.md 增量决策(2026-05-01):8 张新表迁本地 PG
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Migration 041: Eval 跑批结果归档
-- 引用 17-tech-plan.md Phase 4
-- 引用 docs/agent-pm/09-eval-plan.md L1-L4 + Safety AE
-- 配置 A 目标:1660 条 golden + L1-L4 + LLM-as-judge Pearson ≥ 0.7

CREATE TABLE IF NOT EXISTS eval_results (
  id                  BIGSERIAL    PRIMARY KEY,
  ts                  TIMESTAMPTZ  NOT NULL DEFAULT now(),
  suite               TEXT         NOT NULL,                          -- 'L1_tool' | 'L1_prompt' | 'L2_skill' | 'L3_chain' | 'L4_trajectory' | 'safety_AE' | 'rubric'
  target_id           TEXT         NOT NULL,                          -- 'T01' / 'P05' / 'S04' / 'AE03' / etc
  golden_count        INT          NOT NULL,
  pass_count          INT          NOT NULL,
  fail_count          INT          NOT NULL,
  pass_rate           NUMERIC(5,4) NOT NULL,
  llm_judge_pearson   NUMERIC(5,4),                                   -- LLM-as-judge vs 人工 Pearson 相关性
  rubric_overall      NUMERIC(5,2),                                   -- Quality Rubric 综合分(0-100)
  rubric_breakdown    JSONB,                                          -- {Relevance, Reasoning, Actionability, Risk, Calibration}
  details             JSONB,                                          -- per-case 失败原因摘要
  triggered_by        TEXT         NOT NULL DEFAULT 'manual',
  pr_id               TEXT,                                           -- GitHub PR 号
  commit_sha          TEXT,
  prompt_version      TEXT,                                           -- A/B 追踪
  duration_seconds    INT,
  cost_usd            NUMERIC(10,4),
  model_used          TEXT,
  CONSTRAINT eval_suite_valid    CHECK (suite IN ('L1_tool','L1_prompt','L2_skill','L3_chain','L4_trajectory','safety_AE','rubric')),
  CONSTRAINT eval_pass_valid     CHECK (pass_count + fail_count = golden_count),
  CONSTRAINT eval_triggered_by   CHECK (triggered_by IN ('pr','nightly','weekly','manual','launch_gate'))
);

CREATE INDEX IF NOT EXISTS idx_eval_suite_ts  ON eval_results(suite, ts DESC);
CREATE INDEX IF NOT EXISTS idx_eval_target_ts ON eval_results(target_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_eval_pr        ON eval_results(pr_id) WHERE pr_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_eval_failures  ON eval_results(suite, ts DESC) WHERE pass_rate < 0.85;

COMMENT ON TABLE eval_results IS 'Eval 跑批归档;每 PR + nightly + weekly + launch gate 跑一次';

-- ============================================================
-- 通过门槛参考(只是注释,实际由 eval/runner.py 强制):
--   L1 Tool unit:        ≥ 100% (170 条)
--   L1 Prompt unit:      ≥ 90%  (540 条) + Safety 100%
--   L2 Skill integration:≥ 90%  (350 条)
--   L3 Agentic chain:    ≥ 85%  (40 条) nightly
--   L4 Trajectory:       ≥ 85%  (20 条) weekly
--   Safety AE01-AE10:    SEV-0 零漏 / SEV-1 ≥ 99% / SEV-2 ≥ 95% (270 条)
--   Quality Rubric:      overall ≥ 80;Actionability=0/Risk=0/Safety<10 一票否决
--   LLM-as-judge:        Pearson ≥ 0.7;Safety 100% 一致
-- ============================================================
