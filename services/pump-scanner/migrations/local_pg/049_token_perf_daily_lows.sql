-- R60 Phase B — token_performance 加 daily_lows 字段(铺底数据)
--
-- 背景:回测最大回撤需要"持仓期最低跌幅",当前表只有 daily_highs。
-- 加 daily_lows JSONB 同结构,让 performance writer 同时双写。
-- 数据积累 ~3-7 天后,回测可读 D3 worst_pct = max_drawdown_pct。
--
-- 不破坏现有 writer / reader — daily_lows 默认 {}(空 dict),老逻辑不读不影响。

BEGIN;

ALTER TABLE token_performance
    ADD COLUMN IF NOT EXISTS daily_lows JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN token_performance.daily_lows IS
    'R60: 每日最低跌幅 {"D1":{"pct":-12.3,"ts":"..."},"D2":{...},"D3":{...}}。'
    '配 daily_highs 算最大回撤。R60 加,~1 周数据回填够才能用';

-- 可选索引(若未来按 worst_pct 查询常用):暂不建,等真用上再说
-- CREATE INDEX IF NOT EXISTS idx_token_perf_daily_lows
--     ON token_performance USING gin (daily_lows);

COMMIT;
