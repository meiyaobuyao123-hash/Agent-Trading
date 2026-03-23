-- ══════════════════════════════════════════════════════════
-- 031 Agent 模拟盘 + 策略模板 + AI 主动推荐 (PRD-008)
-- ══════════════════════════════════════════════════════════
--
-- 新增：
--   agent_paper_trades       — 模拟交易记录
--   agent_recommendations    — AI 主动推荐记录
-- 修改：
--   agent_strategies         — +mode 字段 (paper/live)

-- ── 模拟交易表 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_paper_trades (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id      UUID NOT NULL,
    user_id          UUID,
    chain            TEXT,
    token_address    TEXT,
    token_symbol     TEXT,
    action           TEXT NOT NULL CHECK (action IN ('buy', 'sell')),
    entry_price      NUMERIC NOT NULL,
    exit_price       NUMERIC,
    amount_usd       NUMERIC NOT NULL,
    pnl_usd          NUMERIC,
    pnl_pct          NUMERIC,
    sl_pct           NUMERIC,
    tp_pct           NUMERIC,
    trigger_context  JSONB,
    status           TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_strategy
    ON agent_paper_trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_paper_trades_user
    ON agent_paper_trades(user_id);
CREATE INDEX IF NOT EXISTS idx_paper_trades_status
    ON agent_paper_trades(status);
CREATE INDEX IF NOT EXISTS idx_paper_trades_created
    ON agent_paper_trades(created_at);

-- ── AI 主动推荐表 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_recommendations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID,
    token_address    TEXT NOT NULL,
    token_symbol     TEXT,
    chain            TEXT,
    source_type      TEXT NOT NULL,  -- smart_money / hot_spike / kol_resonance
    score            NUMERIC,
    reason           TEXT,
    context          JSONB,
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'accepted', 'dismissed')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recommendations_user
    ON agent_recommendations(user_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_token
    ON agent_recommendations(token_address);
CREATE INDEX IF NOT EXISTS idx_recommendations_created
    ON agent_recommendations(created_at);

-- ── agent_strategies 增加 mode 字段 ──────────────────────────
ALTER TABLE agent_strategies
    ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'paper'
    CHECK (mode IN ('paper', 'live'));

-- ── agent_strategies 增加 template_id 字段 ───────────────────
ALTER TABLE agent_strategies
    ADD COLUMN IF NOT EXISTS template_id TEXT;
