-- ══════════════════════════════════════════════════════════
-- 015 内盘每日数据报表
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS pump_daily_report (
    report_date       DATE PRIMARY KEY,
    -- 漏斗
    ws_creates        INTEGER DEFAULT 0,      -- 新币出现
    tokens_saved      INTEGER DEFAULT 0,      -- 我们抓到
    rest_success      INTEGER DEFAULT 0,      -- 详情拉取成功
    rest_fallback     INTEGER DEFAULT 0,      -- 用基础信息兜底
    observed_tokens   INTEGER DEFAULT 0,      -- 进入观察
    snapshots_written INTEGER DEFAULT 0,      -- 快照总数
    picks_count       INTEGER DEFAULT 0,      -- 推荐给用户
    graduated_count   INTEGER DEFAULT 0,      -- 真的毕业了
    hit_count         INTEGER DEFAULT 0,      -- 推中了
    miss_count        INTEGER DEFAULT 0,      -- 漏掉了
    -- 准确率
    hit_rate          NUMERIC DEFAULT 0,      -- 命中率
    miss_rate         NUMERIC DEFAULT 0,      -- 漏选率
    -- 质量
    avg_grad_hours    NUMERIC,                -- 平均毕业耗时(小时)
    -- 健康
    ws_reconnects     INTEGER DEFAULT 0,      -- WS断连次数
    rest_success_pct  NUMERIC DEFAULT 0,      -- REST成功率
    -- 完整报表JSON
    report_json       JSONB,
    created_at        TIMESTAMPTZ DEFAULT now()
);
