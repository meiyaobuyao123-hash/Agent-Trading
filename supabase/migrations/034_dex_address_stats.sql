-- 034: DEX 活跃地址统计表
-- 用于从 DEX swap 事件中发现新的聪明钱地址（替代 Dune Analytics）
--
-- 架构：DEX WS 捕获全量 swap → 内存计数未知地址 → 每 30min flush 高频地址到此表
-- → txns_wallet_miner 定期从此表挖掘 → 晋升为 smart_wallets.watching

CREATE TABLE IF NOT EXISTS dex_address_stats (
    wallet_address TEXT PRIMARY KEY,
    chain TEXT NOT NULL DEFAULT 'evm',       -- 'evm' | 'solana'
    total_tx_count INTEGER DEFAULT 0,        -- 累积交易总数
    total_unique_tokens INTEGER DEFAULT 0,   -- 累积交易代币种类
    active_windows INTEGER DEFAULT 0,        -- 出现在几个 30min 窗口
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    -- 以下由 txns_wallet_miner 定期回填
    promoted_at TIMESTAMPTZ,                 -- 被晋升为 smart_wallet 的时间
    promoted_tier TEXT                        -- 晋升的 tier
);

-- 查询索引：按活跃度查候选
CREATE INDEX IF NOT EXISTS idx_dex_addr_stats_active
    ON dex_address_stats (active_windows DESC, total_tx_count DESC)
    WHERE promoted_at IS NULL;
