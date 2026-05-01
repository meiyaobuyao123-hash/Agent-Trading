-- ============================================================
-- Local PostgreSQL (agent_trading_local on server PG 14)
-- Migration: 042_agent_global_state
-- 执行: psql -h 127.0.0.1 -U agent_local -d agent_trading_local -f 042_agent_global_state.sql
-- 引用 docs/agent-pm/17-tech-plan.md Phase 0 + W3 D2(CB 持久化)
-- 引用 services/pump-scanner/agent/safety_engine.py CB 状态管理
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 全局 Agent 状态(单例,id=1)
-- 与 SafetyEngine._active_breakers 内存状态同步
-- 重启后 SafetyEngine 启动时从此表恢复
CREATE TABLE IF NOT EXISTS agent_global_state (
  id                INT          PRIMARY KEY DEFAULT 1,
  state             TEXT         NOT NULL DEFAULT 'normal',         -- normal / degraded / blocked
  active_breakers   JSONB        NOT NULL DEFAULT '[]'::jsonb,      -- [{cb_id, name, tripped_at, auto_release_at, reason, severity}, ...]
  updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_by        TEXT,                                            -- 'auto' / 'admin:<uid>' / 'cb_auto_release'
  CONSTRAINT singleton CHECK (id = 1),
  CONSTRAINT state_valid CHECK (state IN ('normal','degraded','blocked'))
);

-- 单例初始化
INSERT INTO agent_global_state (id, state, active_breakers, updated_by)
VALUES (1, 'normal', '[]'::jsonb, 'init')
ON CONFLICT (id) DO NOTHING;

-- 状态变更历史(审计用,90d 保留 — 由 db_cleanup 处理)
CREATE TABLE IF NOT EXISTS agent_global_state_history (
  id              BIGSERIAL    PRIMARY KEY,
  ts              TIMESTAMPTZ  NOT NULL DEFAULT now(),
  prev_state      TEXT,
  new_state       TEXT         NOT NULL,
  cb_id           TEXT,                                              -- 触发该次变化的 CB(若是 CB trip/release)
  action          TEXT         NOT NULL,                             -- 'trip' / 'release_manual' / 'release_auto' / 'reload'
  reason          TEXT,
  payload         JSONB,                                             -- 完整 active_breakers 快照
  updated_by      TEXT
);

CREATE INDEX IF NOT EXISTS idx_state_hist_ts   ON agent_global_state_history(ts DESC);
CREATE INDEX IF NOT EXISTS idx_state_hist_cb   ON agent_global_state_history(cb_id, ts DESC) WHERE cb_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_state_hist_act  ON agent_global_state_history(action, ts DESC);

COMMENT ON TABLE agent_global_state         IS '全局 Agent 状态单例;由 SafetyEngine 实时同步';
COMMENT ON TABLE agent_global_state_history IS '状态变更审计日志,90d 保留';
