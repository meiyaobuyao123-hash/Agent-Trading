-- 020: AI Optimizer Agent 数据表
-- 用于自动优化推荐算法的审计和审批系统

-- ═══════════════════════════════════════════════════
-- 1. optimization_runs — 每次优化 Agent 运行的完整记录
-- ═══════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS optimization_runs (
    id              BIGSERIAL PRIMARY KEY,
    run_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    status          TEXT NOT NULL DEFAULT 'running',  -- running | completed | failed

    -- 触发时的指标快照
    metrics_snapshot JSONB NOT NULL DEFAULT '{}',
    -- {hit_rate_7d, recall_7d, total_picks, total_graduated,
    --  missed_opportunities, avg_score, ...}

    -- Agent 完整对话记录 (Claude messages)
    conversation    JSONB NOT NULL DEFAULT '[]',

    -- Agent 分析结论
    analysis        TEXT,

    -- 使用的 API tokens
    tokens_used     INT DEFAULT 0,
    cost_usd        FLOAT DEFAULT 0,

    -- 时间
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_opt_runs_date ON optimization_runs(run_date DESC);
CREATE INDEX IF NOT EXISTS idx_opt_runs_status ON optimization_runs(status);


-- ═══════════════════════════════════════════════════
-- 2. optimization_proposals — Agent 提出的优化方案
-- ═══════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS optimization_proposals (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES optimization_runs(id),
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | applied | rolled_back

    -- 提案内容
    title           TEXT NOT NULL,              -- 简短标题
    rationale       TEXT NOT NULL,              -- Agent 的推理过程

    -- 具体变更
    changes         JSONB NOT NULL DEFAULT '[]',
    -- [{file: "scorer.py", type: "weight", param: "smart_money", old: 20, new: 25, reason: "..."},
    --  {file: "config.py", type: "threshold", param: "MIN_BUYERS_HARD", old: 5, new: 4, reason: "..."}]

    -- 回测结果
    backtest_before JSONB,     -- {hit_rate, recall, precision, f1, sample_size}
    backtest_after  JSONB,     -- {hit_rate, recall, precision, f1, sample_size}
    improvement_pct FLOAT,     -- 综合改善百分比

    -- 审批
    reviewed_by     TEXT,                       -- 审批人
    reviewed_at     TIMESTAMPTZ,
    review_comment  TEXT,

    -- 应用状态
    applied_at      TIMESTAMPTZ,
    rolled_back_at  TIMESTAMPTZ,
    rollback_reason TEXT,

    -- 应用前的参数快照（用于回滚）
    params_before   JSONB,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_opt_proposals_run ON optimization_proposals(run_id);
CREATE INDEX IF NOT EXISTS idx_opt_proposals_status ON optimization_proposals(status);


-- ═══════════════════════════════════════════════════
-- 3. optimization_metrics_history — 每日指标快照（用于趋势分析）
-- ═══════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS optimization_metrics_history (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_date   DATE NOT NULL UNIQUE,

    -- pump.fun 指标
    pump_picks_count    INT DEFAULT 0,
    pump_graduated      INT DEFAULT 0,
    pump_hit_count      INT DEFAULT 0,       -- 推荐的代币后来涨了
    pump_miss_count     INT DEFAULT 0,       -- 涨了但没推荐的
    pump_hit_rate       FLOAT DEFAULT 0,     -- hit_count / picks_count
    pump_recall         FLOAT DEFAULT 0,     -- hit_count / (hit_count + miss_count)
    pump_precision      FLOAT DEFAULT 0,     -- hit_count / picks_count
    pump_f1             FLOAT DEFAULT 0,     -- 2 * precision * recall / (precision + recall)

    -- 评分参数快照
    scorer_params       JSONB,               -- 当日生效的评分参数

    -- 信号质量
    avg_signal_score    FLOAT DEFAULT 0,
    signal_count        INT DEFAULT 0,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_opt_metrics_date ON optimization_metrics_history(snapshot_date DESC);
