-- Migration 036: HITL 队列 + Memory WAL(Phase 0 必装)
-- 引用 17-tech-plan.md Phase 0
-- 引用 docs/agent-pm/05-tool-catalog.md T09 create_approval_request
-- 引用 docs/agent-pm/06-memory-spec.md §3.5 Write Reliability

-- ============================================================
-- 1. pending_approvals(HITL 队列,T09 写入)
-- ============================================================
CREATE TABLE IF NOT EXISTS pending_approvals (
  approval_id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id                   UUID        NOT NULL,
  strategy_id                 UUID        NOT NULL,
  trigger_conditions_matched  JSONB       NOT NULL,
  thesis_id                   UUID,                                   -- 关联 agent_thesis
  token_address               TEXT,
  chain                       TEXT,
  amount_usd                  NUMERIC,
  status                      TEXT        NOT NULL DEFAULT 'pending',
  decision_reason             TEXT,
  decision_latency_ms         INT,
  tx_hash                     TEXT,
  signature                   TEXT,                                   -- 用户签名(Face ID + wallet sig)
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at                  TIMESTAMPTZ NOT NULL,
  decided_at                  TIMESTAMPTZ,
  idempotency_key             TEXT        UNIQUE,                     -- strategy_id + signal_event_id + amount_usd
  push_sent                   BOOLEAN     DEFAULT false,
  push_resent_at              TIMESTAMPTZ,                            -- 5min 无响应再推一次
  CONSTRAINT pending_status_valid CHECK (status IN ('pending','approved','rejected','expired'))
);

CREATE INDEX IF NOT EXISTS idx_pending_device_status ON pending_approvals(device_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pending_expires       ON pending_approvals(expires_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_pending_strategy      ON pending_approvals(strategy_id, created_at DESC);

COMMENT ON TABLE pending_approvals IS 'HITL 队列;5min 未响应再推/15min 降级 notify_only/60min 自动 reject(由 reflect_loop 处理过期)';

-- ============================================================
-- 2. memory_write_wal(Memory 关键写入先入 WAL,异步刷主表)
-- ============================================================
CREATE TABLE IF NOT EXISTS memory_write_wal (
  wal_id           BIGSERIAL   PRIMARY KEY,
  ts               TIMESTAMPTZ NOT NULL DEFAULT now(),
  device_id        UUID        NOT NULL,
  memory_type      TEXT        NOT NULL,
  payload          JSONB       NOT NULL,
  idempotency_key  TEXT        UNIQUE,                                -- hash(device_id + event_id + truncate_minute)
  flushed          BOOLEAN     DEFAULT false,
  flushed_at       TIMESTAMPTZ,
  CONSTRAINT wal_type_valid CHECK (memory_type IN ('episodic','semantic','reflection'))
);

CREATE INDEX IF NOT EXISTS idx_wal_unflushed ON memory_write_wal(flushed, ts) WHERE flushed = false;

COMMENT ON TABLE memory_write_wal IS '关键 memory 写入 WAL;trade_outcome / risk_lesson / approve_rule / auto-promote 必走';

-- ============================================================
-- 3. memory_write_retry_queue(WAL 刷主表失败时入这个)
-- ============================================================
CREATE TABLE IF NOT EXISTS memory_write_retry_queue (
  retry_id         BIGSERIAL   PRIMARY KEY,
  wal_id           BIGINT      NOT NULL REFERENCES memory_write_wal(wal_id),
  attempt_count    INT         NOT NULL DEFAULT 0,
  next_retry_at    TIMESTAMPTZ NOT NULL,                              -- 60s / 5min / 30min 退避
  last_error       TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved         BOOLEAN     DEFAULT false,
  -- 3 次失败 → P1 告警(由 cron_tasks.py 检测)
  failed_p1_alerted BOOLEAN    DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_retry_pending ON memory_write_retry_queue(next_retry_at) WHERE resolved = false;
CREATE INDEX IF NOT EXISTS idx_retry_alert   ON memory_write_retry_queue(attempt_count, failed_p1_alerted) WHERE attempt_count >= 3 AND failed_p1_alerted = false;
