-- PRD-004 M-01: 原子递增 trigger_count（避免 TOCTOU 竞态）
CREATE OR REPLACE FUNCTION increment_trigger_count(sid UUID)
RETURNS void AS $$
BEGIN
    UPDATE strategies
    SET trigger_count = trigger_count + 1,
        last_triggered = NOW()
    WHERE id = sid;
END;
$$ LANGUAGE plpgsql;
