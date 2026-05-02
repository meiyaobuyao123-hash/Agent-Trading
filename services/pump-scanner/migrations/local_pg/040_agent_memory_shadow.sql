-- ============================================================
-- Local PostgreSQL (agent_trading_local on server PG 14)
-- Migration: 040_agent_memory_shadow
-- 引用 docs/agent-pm/06-memory-spec.md §4.3 Shadow Mode + R37 P0-4
-- ============================================================
-- 给 agent_memory 表加 R37 P0-4 评估需要的列(若缺):
--   - shadow_mode_until: 14d 观察期截止时间(NULL = 已 graduated)
--   - wilson_ci_lower:   5-gate 第 3 关存档(0-1)
--   - match_count:       规则被触发的次数(蓝绿色统计)
--   - propose_count_so_far: 反思层第几次提议(去重防重复)
--   - comply_win / comply_lose: 触发后的 win/lose 计数
--
-- 幂等:全部 IF NOT EXISTS
-- ============================================================

ALTER TABLE IF EXISTS agent_memory
  ADD COLUMN IF NOT EXISTS shadow_mode_until    TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS wilson_ci_lower      NUMERIC(4,3),
  ADD COLUMN IF NOT EXISTS match_count          INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS propose_count_so_far INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS comply_win           INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS comply_lose          INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS metadata             JSONB   DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_agent_memory_shadow_until
  ON agent_memory(shadow_mode_until)
  WHERE shadow_mode_until IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_memory_active_shadow
  ON agent_memory(is_active, shadow_mode_until)
  WHERE is_active = true AND shadow_mode_until IS NOT NULL;

COMMENT ON COLUMN agent_memory.shadow_mode_until IS 'R37 P0-4: 14d Shadow Mode 截止时间;NULL = graduated 或从未影子';
COMMENT ON COLUMN agent_memory.wilson_ci_lower IS '5-gate 晋升时存档的 Wilson CI 下界(0-1)';
COMMENT ON COLUMN agent_memory.match_count IS 'rule 触发次数;evaluate_shadow_rules 用';
COMMENT ON COLUMN agent_memory.comply_win IS '规则触发后的 win 数(评估胜率用)';
