-- 热币 Top Holders 表（聪明钱发现用）
-- 入榜时采集 Top 10 持仓地址，后续评估是否晋升为聪明钱

CREATE TABLE IF NOT EXISTS hot_coin_top_holders (
    id BIGSERIAL PRIMARY KEY,
    chain TEXT NOT NULL,
    token_address TEXT NOT NULL,
    holder_address TEXT NOT NULL,
    holder_rank INT NOT NULL,
    holder_pct FLOAT,
    holder_amount FLOAT,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    token_d3_pct FLOAT,
    promoted_to_smart BOOLEAN DEFAULT FALSE,
    UNIQUE(chain, token_address, holder_address)
);

CREATE INDEX IF NOT EXISTS idx_top_holders_holder ON hot_coin_top_holders(holder_address);
CREATE INDEX IF NOT EXISTS idx_top_holders_chain_token ON hot_coin_top_holders(chain, token_address);
