-- PRD-007: agent_debates 表 — 多角色辩论记录
-- 记录 L3 全流程辩论的分析师报告、辩论过程、结论、风控审查、最终结果

CREATE TABLE IF NOT EXISTS agent_debates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID,
    token_address TEXT,
    chain TEXT,
    trigger_source TEXT,

    -- 分析师报告
    technical_report JSONB,
    sentiment_report JSONB,
    onchain_report JSONB,

    -- 辩论记录
    debate_log TEXT,
    debate_rounds INT DEFAULT 3,

    -- 结论
    conclusion_action TEXT,           -- buy/sell/hold
    conclusion_confidence NUMERIC,
    conclusion_winner TEXT,           -- bull/bear/draw
    conclusion_risk TEXT,
    conclusion_reasoning TEXT,

    -- 风控审查
    risk_review TEXT,                 -- APPROVE/REJECT/REDUCE
    risk_review_reason TEXT,

    -- 最终结果
    final_action TEXT,                -- buy/sell/hold/blocked
    actual_pnl_pct NUMERIC,          -- 回填：实际盈亏

    -- 评估
    debate_level INT,                 -- 1/2/3
    total_tokens_used INT,
    total_cost_usd NUMERIC,

    created_at TIMESTAMPTZ DEFAULT now()
);

-- 索引：按代币查询辩论历史
CREATE INDEX IF NOT EXISTS idx_debates_token ON agent_debates(token_address, created_at DESC);

-- 索引：按策略查询
CREATE INDEX IF NOT EXISTS idx_debates_strategy ON agent_debates(strategy_id, created_at DESC);

-- 索引：按辩论级别查询
CREATE INDEX IF NOT EXISTS idx_debates_level ON agent_debates(debate_level, created_at DESC);
