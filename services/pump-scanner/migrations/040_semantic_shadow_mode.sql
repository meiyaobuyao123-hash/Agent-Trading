-- Migration 040: agent_memory Shadow Mode + 模式晋升字段
-- 引用 17-tech-plan.md Phase 1 Memory 升级
-- 引用 docs/agent-pm/06-memory-spec.md §3.3 Semantic 规则晋升机制

-- ============================================================
-- 1. agent_memory 加 Shadow Mode 字段
-- ============================================================
-- Shadow Mode: 自动晋升的 Semantic 规则先 14 天观察期(只记录不注入 prompt)
-- 触发≥10 次且表现不劣于预期 20% 以上 → 正式激活
ALTER TABLE agent_memory
  ADD COLUMN IF NOT EXISTS active_regimes      TEXT[],               -- 规则适用的 regime 集合
  ADD COLUMN IF NOT EXISTS shadow_mode_until   TIMESTAMPTZ,          -- 14d 观察期结束时间
  ADD COLUMN IF NOT EXISTS propose_count       INT     DEFAULT 0,    -- 反思中提议次数(自动晋升需 ≥3)
  ADD COLUMN IF NOT EXISTS match_count         INT     DEFAULT 0,    -- 历史匹配次数(检索时 +1)
  ADD COLUMN IF NOT EXISTS wilson_ci_lower     NUMERIC(5,4),         -- 胜率/EV 差的 95% Wilson CI 下界
  ADD COLUMN IF NOT EXISTS dormant_since       TIMESTAMPTZ,          -- 30d 命中 0 次 → dormant
  ADD COLUMN IF NOT EXISTS evidence            JSONB;                -- {sample_size, win_rate_diff, t_test_p, regimes_observed}

CREATE INDEX IF NOT EXISTS idx_memory_shadow  ON agent_memory(shadow_mode_until) WHERE shadow_mode_until IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_dormant ON agent_memory(dormant_since)     WHERE dormant_since   IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_match   ON agent_memory(device_id, match_count DESC) WHERE memory_type = 'semantic';

COMMENT ON COLUMN agent_memory.shadow_mode_until IS 'Shadow Mode 观察期结束时间;此期间只记录不注入 prompt';
COMMENT ON COLUMN agent_memory.dormant_since     IS '30d 未匹配标记 dormant,90d 后由 cron 废弃';
COMMENT ON COLUMN agent_memory.evidence          IS '{sample_size, win_rate_diff, t_test_p, regimes_observed}';

-- ============================================================
-- 2. agent_strategies 加模式晋升字段(paper→notify→auto)
-- ============================================================
ALTER TABLE agent_strategies
  ADD COLUMN IF NOT EXISTS mode_locked_until         TIMESTAMPTZ,    -- 模式切换冷却(防快速 paper→auto)
  ADD COLUMN IF NOT EXISTS paper_baseline_30d        JSONB,          -- {trade_count, win_rate, ev_pct, sharpe, mdd}
  ADD COLUMN IF NOT EXISTS auto_promotion_eligible_at TIMESTAMPTZ,   -- 满足晋升条件后的可切时间(30d+30 笔+EV≥+1%)
  ADD COLUMN IF NOT EXISTS prompt_version_used       TEXT,           -- A/B 追踪
  ADD COLUMN IF NOT EXISTS first_live_trade_at       TIMESTAMPTZ;    -- 首笔真金触发时间(必走 HITL)

CREATE INDEX IF NOT EXISTS idx_strategy_promotion ON agent_strategies(auto_promotion_eligible_at) WHERE mode = 'paper';

COMMENT ON COLUMN agent_strategies.mode_locked_until IS 'paper→notify→auto 切换冷却;每次切换后锁 24h 防误操';
COMMENT ON COLUMN agent_strategies.paper_baseline_30d IS '{trade_count, win_rate, ev_pct, sharpe, mdd};paper 跑满 30d 才能切 auto';
