-- ══════════════════════════════════════════════════════════
-- 008 Agent 策略系统
-- ══════════════════════════════════════════════════════════
--
-- 表：
--   agent_strategies  — 用户策略（条件 + 动作）
--   agent_alerts      — 触发告警
--   agent_executions  — 交易执行记录（Phase 3）
--
-- 依赖：001_init.sql（auth.users）

-- ── smart_wallets 扩展字段（种子标记）───────────────────────
ALTER TABLE smart_wallets ADD COLUMN IF NOT EXISTS is_seed BOOLEAN NOT NULL DEFAULT FALSE;

-- ── 策略表 ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_strategies (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL,
  name            TEXT NOT NULL DEFAULT '未命名策略',
  description     TEXT,
  conditions      JSONB NOT NULL DEFAULT '{}',
  actions         JSONB NOT NULL DEFAULT '[]',
  filters         JSONB NOT NULL DEFAULT '{}',
  data_sources    TEXT[] DEFAULT '{}',
  cooldown_min    INT NOT NULL DEFAULT 30 CHECK (cooldown_min >= 5),
  status          TEXT NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'paused', 'archived')),
  trigger_count   INT NOT NULL DEFAULT 0,
  last_triggered  TIMESTAMPTZ,
  source_prompt   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_strategies_user
  ON agent_strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_strategies_status
  ON agent_strategies(status);
CREATE INDEX IF NOT EXISTS idx_agent_strategies_sources
  ON agent_strategies USING GIN(data_sources);

-- auto-update updated_at
CREATE OR REPLACE FUNCTION update_agent_strategy_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agent_strategy_updated ON agent_strategies;
CREATE TRIGGER trg_agent_strategy_updated
  BEFORE UPDATE ON agent_strategies
  FOR EACH ROW
  EXECUTE FUNCTION update_agent_strategy_timestamp();

-- ── 告警表 ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_alerts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL,
  strategy_id     UUID REFERENCES agent_strategies(id) ON DELETE CASCADE,
  trigger_context JSONB DEFAULT '{}',
  token_address   TEXT,
  token_name      TEXT,
  chain           TEXT,
  title           TEXT NOT NULL DEFAULT '',
  message         TEXT NOT NULL DEFAULT '',
  severity        TEXT NOT NULL DEFAULT 'info'
                  CHECK (severity IN ('info', 'warning', 'critical')),
  is_read         BOOLEAN NOT NULL DEFAULT FALSE,
  is_pushed       BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_alerts_user
  ON agent_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_alerts_strategy
  ON agent_alerts(strategy_id);
CREATE INDEX IF NOT EXISTS idx_agent_alerts_unread
  ON agent_alerts(user_id, is_read) WHERE is_read = FALSE;
CREATE INDEX IF NOT EXISTS idx_agent_alerts_created
  ON agent_alerts(created_at DESC);

-- ── 执行记录表（Phase 3）────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_executions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL,
  strategy_id     UUID REFERENCES agent_strategies(id) ON DELETE SET NULL,
  chain           TEXT,
  token_address   TEXT,
  action          TEXT CHECK (action IN ('buy', 'sell')),
  amount_usd      NUMERIC,
  amount_token    NUMERIC,
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'submitted', 'confirmed', 'failed')),
  tx_hash         TEXT,
  executed_price  NUMERIC,
  slippage_pct    NUMERIC,
  gas_fee_usd     NUMERIC,
  error_message   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  confirmed_at    TIMESTAMPTZ
);

-- ── RLS 策略 ─────────────────────────────────────────────────
ALTER TABLE agent_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_executions ENABLE ROW LEVEL SECURITY;

-- 用户只能访问自己的数据
CREATE POLICY agent_strategies_user ON agent_strategies
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY agent_alerts_user ON agent_alerts
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY agent_executions_user ON agent_executions
  FOR ALL USING (auth.uid() = user_id);

-- Service role 全权访问（后端 service_key）
CREATE POLICY agent_strategies_service ON agent_strategies
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY agent_alerts_service ON agent_alerts
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY agent_executions_service ON agent_executions
  FOR ALL USING (auth.role() = 'service_role');
