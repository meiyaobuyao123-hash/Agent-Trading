CREATE TABLE IF NOT EXISTS hot_sim_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode TEXT NOT NULL,  -- 'repeat' | 'unique'
    chain TEXT NOT NULL,
    address TEXT NOT NULL,
    symbol TEXT,
    entry_price NUMERIC NOT NULL,
    exit_price NUMERIC,
    amount_usd NUMERIC DEFAULT 10,
    tp_pct NUMERIC DEFAULT 15,
    sl_pct NUMERIC DEFAULT 15,
    tp_price NUMERIC,
    sl_price NUMERIC,
    pnl_pct NUMERIC,
    pnl_usd NUMERIC,
    score_at_entry NUMERIC,
    status TEXT DEFAULT 'open',  -- 'open' | 'tp' | 'sl'
    entered_at TIMESTAMPTZ DEFAULT NOW(),
    exited_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_hot_sim_status ON hot_sim_trades(status, mode);
CREATE INDEX IF NOT EXISTS idx_hot_sim_mode ON hot_sim_trades(mode, entered_at DESC);
