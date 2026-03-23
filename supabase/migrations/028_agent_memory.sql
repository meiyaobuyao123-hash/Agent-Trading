-- PRD-005: 记忆与反思系统 — agent_memory + agent_risk_events
-- 2026-03-23

-- ═══════════════════════════════════════════════════════
-- 1. agent_memory — 中期 (episodic) + 长期 (semantic) 记忆
-- ═══════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS agent_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,                  -- 'episodic' | 'semantic'
    category TEXT NOT NULL,              -- 'trade_review' | 'rule' | 'market_pattern' | 'risk_lesson'
    content TEXT NOT NULL,               -- 自然语言描述
    structured_data JSONB,               -- 结构化数据（condition/action JSON，交易配对等）
    importance NUMERIC DEFAULT 0,        -- 重要性评分（0-10）
    chain TEXT,                          -- 关联链
    token_type TEXT,                     -- 'meme' | 'hot' | 'btc_eth'
    trigger_source TEXT,                 -- 'smart_money' | 'kol' | 'hot_score' | 'pump_score'
    mcap_bucket TEXT,                    -- '<100K' | '100K-1M' | '1M-10M' | '>10M'
    market_regime TEXT,                  -- 'trending_up' | 'ranging' | 'high_volatility' 等
    usage_count INT DEFAULT 0,           -- 被检索使用次数
    comply_win INT DEFAULT 0,            -- 遵守规则时赢
    comply_lose INT DEFAULT 0,           -- 遵守规则时输
    violate_win INT DEFAULT 0,           -- 违反规则时赢
    violate_lose INT DEFAULT 0,          -- 违反规则时输
    source_reflection_id UUID,           -- 产生该记忆的反思 ID
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_memory_type ON agent_memory(type, is_active);
CREATE INDEX IF NOT EXISTS idx_memory_source ON agent_memory(trigger_source);
CREATE INDEX IF NOT EXISTS idx_memory_category ON agent_memory(category, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_expires ON agent_memory(expires_at) WHERE expires_at IS NOT NULL;


-- ═══════════════════════════════════════════════════════
-- 2. agent_risk_events — 风控拦截/警告记录（只记 block+warn）
-- ═══════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS agent_risk_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action TEXT NOT NULL,                 -- 'block' | 'warn'（不记录 pass）
    reason TEXT NOT NULL,
    chain TEXT,
    token_address TEXT,
    token_symbol TEXT,
    amount_usd NUMERIC,
    risk_data JSONB,                      -- 触发时的风控数据快照
    token_price_at_event NUMERIC,
    token_price_1h_later NUMERIC,
    token_price_4h_later NUMERIC,
    token_price_24h_later NUMERIC,
    token_min_price_24h NUMERIC,          -- 24h 内最低价
    token_max_drawdown_24h NUMERIC,       -- 最大回撤百分比
    was_correct BOOLEAN,                  -- 综合判定
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_risk_events_action ON agent_risk_events(action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_backfill ON agent_risk_events(created_at DESC)
    WHERE token_price_24h_later IS NULL;
