-- ═══════════════════════════════════════════════════════
-- BTC/ETH Investment Agent System
-- 025_btc_eth_system.sql
-- ═══════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS btc_eth_indicators (
    id BIGSERIAL PRIMARY KEY,
    asset TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    price_usd NUMERIC NOT NULL,
    price_change_1h NUMERIC, price_change_4h NUMERIC, price_change_24h NUMERIC,
    volume_24h_usd NUMERIC,
    funding_rate NUMERIC, oi_usd NUMERIC, oi_change_4h NUMERIC,
    long_short_ratio NUMERIC, retail_long_short NUMERIC,
    taker_buy_sell_ratio NUMERIC, liquidation_24h_usd NUMERIC, liq_long_pct NUMERIC,
    exchange_netflow_usd NUMERIC, active_addresses INT, hash_rate NUMERIC,
    sopr NUMERIC, whale_txn_count INT,
    dxy_index NUMERIC, sp500_change_pct NUMERIC, gold_change_pct NUMERIC,
    fear_greed_index INT, social_volume INT, news_sentiment NUMERIC,
    etf_flow_usd NUMERIC, stablecoin_mcap NUMERIC, total_tvl_usd NUMERIC,
    rsi_14 NUMERIC, macd_signal NUMERIC, bb_position NUMERIC, atr_14 NUMERIC,
    mempool_size_mb NUMERIC, avg_fee_sat_vb NUMERIC,
    bid_depth_2pct NUMERIC, ask_depth_2pct NUMERIC, depth_imbalance NUMERIC,
    score_momentum INT, score_sentiment INT, score_onchain INT,
    score_macro INT, score_risk INT
);
CREATE INDEX IF NOT EXISTS idx_btc_eth_ind ON btc_eth_indicators(asset, ts DESC);

CREATE TABLE IF NOT EXISTS btc_eth_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset TEXT NOT NULL,
    report_date DATE NOT NULL,
    cycle_phase TEXT NOT NULL,
    cycle_confidence NUMERIC,
    direction TEXT NOT NULL,
    position_allocation JSONB,
    key_levels JSONB,
    risk_factors JSONB,
    indicator_snapshot JSONB,
    reasoning TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(asset, report_date)
);

CREATE TABLE IF NOT EXISTS btc_eth_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    entry_price NUMERIC NOT NULL,
    stop_loss NUMERIC NOT NULL,
    target_price NUMERIC NOT NULL,
    risk_reward NUMERIC,
    confidence INT,
    reasoning TEXT,
    indicator_snapshot JSONB,
    status TEXT DEFAULT 'active',
    exit_price NUMERIC, actual_pnl_pct NUMERIC,
    price_1h NUMERIC, price_4h NUMERIC, price_12h NUMERIC,
    price_24h NUMERIC, price_72h NUMERIC,
    created_at TIMESTAMPTZ DEFAULT now(),
    closed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_btc_eth_sig ON btc_eth_signals(asset, status, created_at DESC);

CREATE TABLE IF NOT EXISTS btc_eth_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset TEXT, severity TEXT NOT NULL, alert_type TEXT NOT NULL,
    title TEXT NOT NULL, message TEXT NOT NULL, data_snapshot JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS btc_eth_portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,
    mode TEXT DEFAULT 'paper',
    initial_capital NUMERIC DEFAULT 10000,
    current_equity NUMERIC DEFAULT 10000,
    peak_equity NUMERIC DEFAULT 10000,
    risk_preference TEXT DEFAULT 'moderate',
    binance_api_key_enc TEXT, binance_secret_enc TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS btc_eth_paper_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    signal_id UUID REFERENCES btc_eth_signals(id),
    asset TEXT NOT NULL, action TEXT NOT NULL, side TEXT NOT NULL,
    entry_price NUMERIC NOT NULL, exit_price NUMERIC,
    quantity NUMERIC NOT NULL, amount_usd NUMERIC NOT NULL,
    pnl_usd NUMERIC, pnl_pct NUMERIC,
    status TEXT DEFAULT 'open',
    stop_loss NUMERIC, take_profit NUMERIC,
    created_at TIMESTAMPTZ DEFAULT now(), closed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_btc_eth_paper_user ON btc_eth_paper_trades(user_id, status);
