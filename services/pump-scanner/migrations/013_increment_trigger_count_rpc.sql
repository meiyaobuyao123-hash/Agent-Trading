-- 013: 创建 increment_trigger_count RPC 函数
-- 用途：原子递增 agent_strategies.trigger_count，避免 TOCTOU 竞争
-- 调用方：strategy_manager.py → record_trigger()

CREATE OR REPLACE FUNCTION increment_trigger_count(sid UUID)
RETURNS void
LANGUAGE sql
AS $$
  UPDATE agent_strategies
  SET trigger_count = trigger_count + 1
  WHERE id = sid;
$$;
