-- Migration 026: Agent 卖出支持
-- 为 agent_executions 表增加卖出相关字段

ALTER TABLE agent_executions
    ADD COLUMN IF NOT EXISTS exit_price NUMERIC,
    ADD COLUMN IF NOT EXISTS exit_tx_hash TEXT,
    ADD COLUMN IF NOT EXISTS pnl_usd NUMERIC,
    ADD COLUMN IF NOT EXISTS pnl_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS exit_trigger TEXT,  -- take_profit / stop_loss / trailing_stop / manual
    ADD COLUMN IF NOT EXISTS exited_at TIMESTAMPTZ;

-- 为 strategies 表增加风控参数（如果没有）
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS stop_loss_pct NUMERIC DEFAULT 30,
    ADD COLUMN IF NOT EXISTS take_profit_pct NUMERIC DEFAULT 100,
    ADD COLUMN IF NOT EXISTS trailing_stop_pct NUMERIC DEFAULT 0;

-- 索引：快速查找 open 持仓
CREATE INDEX IF NOT EXISTS idx_agent_exec_open
    ON agent_executions(status, action)
    WHERE status = 'confirmed' AND action = 'buy' AND exit_price IS NULL;
