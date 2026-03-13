-- ============================================================
-- Migration 012: device_tokens 表（推送通知设备令牌）
-- 存储用户 FCM/APNs 设备令牌，支持多设备、令牌失效标记
-- ============================================================

CREATE TABLE IF NOT EXISTS device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    token TEXT NOT NULL UNIQUE,
    device_type TEXT NOT NULL CHECK (device_type IN ('ios', 'android')),
    device_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    last_registered_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_device_tokens_user_active
    ON device_tokens(user_id) WHERE is_active = TRUE;
