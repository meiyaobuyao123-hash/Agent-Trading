-- Agent 交易系统
-- 008_agent_system.sql
-- Phase 1: 策略定义 + 告警；Phase 3: 交易执行

-- 1. 策略主表
CREATE TABLE IF NOT EXISTS agent_strategies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    conditions      JSONB NOT NULL,                  -- 条件树 {operator, rules[]}
    actions         JSONB NOT NULL DEFAULT '[]',      -- 动作列表
    filters         JSONB NOT NULL DEFAULT '{}',      -- 过滤条件 {chains, min_score}
    data_sources    TEXT[] NOT NULL DEFAULT '{}',      -- 关联数据源名
    cooldown_min    INT NOT NULL DEFAULT 30,           -- 冷却时间（分钟）
    status          TEXT NOT NULL DEFAULT 'active',    -- active / paused / archived
    trigger_count   INT NOT NULL DEFAULT 0,
    last_triggered  TIMESTAMPTZ,
    source_prompt   TEXT,                              -- 用户原始自然语言输入
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategies_user ON agent_strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_strategies_status ON agent_strategies(status);
CREATE INDEX IF NOT EXISTS idx_strategies_sources ON agent_strategies USING GIN(data_sources);

-- 2. 告警记录
CREATE TABLE IF NOT EXISTS agent_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    strategy_id     UUID REFERENCES agent_strategies(id) ON DELETE CASCADE,
    trigger_context JSONB NOT NULL,                   -- 触发时的数据快照
    token_address   TEXT,
    token_name      TEXT,
    chain           TEXT,
    title           TEXT NOT NULL,
    message         TEXT NOT NULL,
    severity        TEXT DEFAULT 'info',               -- info / warning / critical
    is_read         BOOLEAN DEFAULT FALSE,
    is_pushed       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alerts_user ON agent_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_strategy ON agent_alerts(strategy_id);
CREATE INDEX IF NOT EXISTS idx_alerts_unread ON agent_alerts(user_id, is_read) WHERE is_read = FALSE;
CREATE INDEX IF NOT EXISTS idx_alerts_created ON agent_alerts(created_at DESC);

-- 3. 交易执行（Phase 3）
CREATE TABLE IF NOT EXISTS agent_executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    strategy_id     UUID REFERENCES agent_strategies(id) ON DELETE SET NULL,
    chain           TEXT NOT NULL,
    token_address   TEXT NOT NULL,
    action          TEXT NOT NULL,                     -- buy / sell
    amount_usd      NUMERIC,
    amount_token    NUMERIC,
    status          TEXT DEFAULT 'pending',            -- pending / submitted / confirmed / failed
    tx_hash         TEXT,
    executed_price  NUMERIC,
    slippage_pct    NUMERIC,
    gas_fee_usd     NUMERIC,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    confirmed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_executions_user ON agent_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_executions_strategy ON agent_executions(strategy_id);
CREATE INDEX IF NOT EXISTS idx_executions_status ON agent_executions(status);

-- 4. 自定义数据源（Phase 2）
CREATE TABLE IF NOT EXISTS user_data_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    name            TEXT NOT NULL,
    source_type     TEXT NOT NULL,                     -- builtin / polling / webhook
    endpoint_url    TEXT,
    poll_interval_s INT DEFAULT 300,
    webhook_path    TEXT UNIQUE,
    webhook_secret  TEXT,
    field_mapping   JSONB DEFAULT '{}',
    fields          JSONB DEFAULT '[]',                -- [{name, type, description}]
    is_active       BOOLEAN DEFAULT TRUE,
    last_polled_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_datasources_user ON user_data_sources(user_id);
CREATE INDEX IF NOT EXISTS idx_datasources_type ON user_data_sources(source_type);

-- 更新时间触发器
CREATE OR REPLACE FUNCTION update_strategy_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_strategies_updated ON agent_strategies;
CREATE TRIGGER tr_strategies_updated
    BEFORE UPDATE ON agent_strategies
    FOR EACH ROW
    EXECUTE FUNCTION update_strategy_updated_at();

-- RLS 策略（用户只能访问自己的数据）
ALTER TABLE agent_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_data_sources ENABLE ROW LEVEL SECURITY;

-- 策略：用户只能读写自己的记录
CREATE POLICY agent_strategies_user_policy ON agent_strategies
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY agent_alerts_user_policy ON agent_alerts
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY agent_executions_user_policy ON agent_executions
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY user_data_sources_user_policy ON user_data_sources
    FOR ALL USING (auth.uid() = user_id);

-- 风控限制函数
CREATE OR REPLACE FUNCTION check_strategy_limits()
RETURNS TRIGGER AS $$
DECLARE
    strategy_count INT;
BEGIN
    -- 单用户策略上限 20 个
    SELECT COUNT(*) INTO strategy_count
    FROM agent_strategies
    WHERE user_id = NEW.user_id AND status != 'archived';

    IF strategy_count >= 20 THEN
        RAISE EXCEPTION 'Strategy limit reached (max 20 active strategies per user)';
    END IF;

    -- 冷却时间下限 5 分钟
    IF NEW.cooldown_min < 5 THEN
        NEW.cooldown_min := 5;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_check_strategy_limits ON agent_strategies;
CREATE TRIGGER tr_check_strategy_limits
    BEFORE INSERT ON agent_strategies
    FOR EACH ROW
    EXECUTE FUNCTION check_strategy_limits();
