-- Migration 037: 共创流程持久化(Working Memory 之一)
-- 引用 17-tech-plan.md Phase 1
-- 引用 docs/agent-pm/06-memory-spec.md §3.1 working memory
-- 用于 S04 signal-strategy-builder 7 阶段共创流程的状态机持久化

CREATE TABLE IF NOT EXISTS conversation_states (
  conversation_id  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id        UUID        NOT NULL,
  skill_name       TEXT        NOT NULL,
  stage            TEXT        NOT NULL DEFAULT 'clarifying',
  messages         JSONB       NOT NULL DEFAULT '[]'::jsonb,           -- 最近 20 条 {role,content,ts}
  draft_data       JSONB,                                              -- 当前 draft 策略 (signal/trade strategy JSON)
  user_profile     JSONB,                                              -- {persona, preferred_chains, ...}
  dry_run_result   JSONB,                                              -- 第④阶段 dry run 历史预估结果
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at       TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '30 minutes',  -- 会话+30min TTL
  saved_strategy_id UUID,                                              -- 第⑦阶段写入策略的 id
  CONSTRAINT conv_skill_valid CHECK (skill_name IN ('signal-strategy-builder','trade-strategy-builder')),
  CONSTRAINT conv_stage_valid CHECK (stage IN (
    'clarifying',   -- ② 多轮澄清
    'refining',     -- ③ Draft 生成
    'dry_run',      -- ④ 历史预估中
    'confirming',   -- ⑤⑥ 反馈调整 → 确认
    'saved',        -- ⑦ 已保存激活
    'aborted'       -- 用户主动放弃
  ))
);

CREATE INDEX IF NOT EXISTS idx_conv_device   ON conversation_states(device_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_expired  ON conversation_states(expires_at) WHERE stage NOT IN ('saved','aborted');
CREATE INDEX IF NOT EXISTS idx_conv_active   ON conversation_states(device_id, stage) WHERE stage NOT IN ('saved','aborted');

COMMENT ON TABLE conversation_states IS 'S04/S05 共创流程的状态机持久化;TTL 30min 不活跃自动过期';
