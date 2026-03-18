-- 热币漏斗统计表
-- 每轮扫描记录一条：发现数 → 过滤后 → 入榜 → 退出 → 活跃
CREATE TABLE IF NOT EXISTS hot_funnel_stats (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    source TEXT NOT NULL DEFAULT 'hot',
    discovered INT NOT NULL DEFAULT 0,
    after_hard_filter INT NOT NULL DEFAULT 0,
    entered INT NOT NULL DEFAULT 0,
    exited INT NOT NULL DEFAULT 0,
    active INT NOT NULL DEFAULT 0,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hot_funnel_date ON hot_funnel_stats(report_date DESC);
