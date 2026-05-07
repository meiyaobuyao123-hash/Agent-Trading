-- R47 P4 — paper trades sl_pct/tp_pct ratio→percent 数据修复
--
-- 背景:R47 P3 之前,LLM 按 schemas.py 旧描述 (0.05-0.50) 写 ratio 单位,
-- 但 paper_engine 按 percent 解析 → token 一动 0.3% 就 SL,87 closed 95% 误触发。
--
-- 跑法(在服务器):
--   PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local \
--     -d agent_trading_local -f scripts/fix_paper_trades_unit.sql
--
-- 安全保证:
--   - 只动 status='open' 的 ratio 数据(sl_pct < 1)
--   - status='closed' 不动(历史 PnL 已固化,改了反而误导)

\set ON_ERROR_STOP on

BEGIN;

-- 修复前快照(便于回滚审计)
SELECT COUNT(*) AS open_with_ratio_unit
  FROM agent_paper_trades
 WHERE status = 'open' AND sl_pct < 1;

SELECT COUNT(*) AS closed_with_ratio_unit
  FROM agent_paper_trades
 WHERE status = 'closed' AND sl_pct < 1;

-- 修复 open 仓:ratio × 100 → percent
UPDATE agent_paper_trades
   SET sl_pct = sl_pct * 100,
       tp_pct = tp_pct * 100
 WHERE status = 'open'
   AND sl_pct < 1;

-- 修复后验证(应当全部 sl_pct >= 1)
SELECT MIN(sl_pct) AS min_sl_pct, MAX(sl_pct) AS max_sl_pct,
       MIN(tp_pct) AS min_tp_pct, MAX(tp_pct) AS max_tp_pct
  FROM agent_paper_trades
 WHERE status = 'open';

COMMIT;

\echo '✓ paper trades unit fix done'
