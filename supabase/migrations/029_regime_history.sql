-- PRD-006: 市场 Regime 检测历史
-- 存储：48 条/天 × 3 资产 × 0.5KB = 72KB/天 ≈ 2.2MB/月（30 天清理）

CREATE TABLE IF NOT EXISTS agent_regime_history (
    id BIGSERIAL PRIMARY KEY,
    asset TEXT NOT NULL,                -- 'BTC' | 'SOL' | 'ETH'
    regime TEXT NOT NULL,               -- TRENDING_UP/DOWN/RANGING/HIGH_VOLATILITY/BREAKOUT/CRISIS/RECOVERY
    confidence NUMERIC,
    btc_price NUMERIC,
    atr_14 NUMERIC,
    funding_rate NUMERIC,
    fear_greed INT,
    hmm_state_probs JSONB,
    cusum_up NUMERIC,
    cusum_down NUMERIC,
    explanation TEXT,
    is_transition BOOLEAN DEFAULT FALSE,
    previous_regime TEXT,
    false_transition BOOLEAN,           -- 事后回填：是否为误报
    transition_cost_usd NUMERIC,        -- 事后回填：误报造成的 PnL 损失
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_regime_ts ON agent_regime_history(asset, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_regime_transition ON agent_regime_history(is_transition, created_at DESC);
