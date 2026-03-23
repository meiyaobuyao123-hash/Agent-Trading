-- PRD-010: A/B Test table for optimizer

CREATE TABLE IF NOT EXISTS agent_ab_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id_a UUID,
    proposal_id_b UUID,
    config_a JSONB NOT NULL,
    config_b JSONB NOT NULL,
    status TEXT DEFAULT 'running',        -- running / completed / cancelled
    results_a JSONB,                      -- {trades, win_rate, pnl, sharpe}
    results_b JSONB,
    winner TEXT,                           -- 'a' / 'b' / null (tie)
    started_at TIMESTAMPTZ DEFAULT now(),
    ends_at TIMESTAMPTZ,                   -- started_at + duration_days
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ab_tests_status ON agent_ab_tests(status);

-- agent_executions: add A/B test tracking columns
ALTER TABLE agent_executions
    ADD COLUMN IF NOT EXISTS ab_test_id UUID,
    ADD COLUMN IF NOT EXISTS ab_group TEXT;
