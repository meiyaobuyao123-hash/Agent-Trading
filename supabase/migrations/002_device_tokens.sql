-- ============================================================
-- Migration 002: device_tokens table
-- 存储 App 设备推送令牌（FCM / APNs），供 Phase 3 真实推送使用
-- ============================================================

CREATE TABLE IF NOT EXISTS device_tokens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token       TEXT NOT NULL UNIQUE,           -- FCM / APNs token
  platform    TEXT NOT NULL CHECK (platform IN ('ios', 'android')),
  user_id     UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  app_version TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 按 user_id 快速查询该用户的全部设备
CREATE INDEX IF NOT EXISTS idx_device_tokens_user ON device_tokens(user_id);

-- RLS: 仅服务角色可写，用户只读自己的设备
ALTER TABLE device_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_full_access" ON device_tokens
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "user_read_own" ON device_tokens
  FOR SELECT USING (auth.uid() = user_id);

-- auto-update updated_at trigger（复用 001 中的 trigger 函数）
CREATE TRIGGER trg_device_tokens_updated_at
  BEFORE UPDATE ON device_tokens
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
