-- migration 017: 用户 API 配额表
-- 用于限制每个用户每月调用 Agent Chat 接口的次数
-- 执行方式：Supabase Dashboard → SQL Editor → 粘贴并运行

-- 用户 API 配额表
CREATE TABLE IF NOT EXISTS user_api_quota (
    user_id      UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    period_start DATE        NOT NULL DEFAULT CURRENT_DATE,
    used_count   INTEGER     NOT NULL DEFAULT 0,
    quota_limit  INTEGER     NOT NULL DEFAULT 20,
    created_at   TIMESTAMPTZ          DEFAULT NOW(),
    updated_at   TIMESTAMPTZ          DEFAULT NOW()
);

-- 启用行级安全
ALTER TABLE user_api_quota ENABLE ROW LEVEL SECURITY;

-- 用户只能查看自己的配额
CREATE POLICY "用户只能查看自己的配额"
    ON user_api_quota
    FOR SELECT
    USING (auth.uid() = user_id);

-- 用户可更新自己的配额
CREATE POLICY "用户可更新自己的配额"
    ON user_api_quota
    FOR ALL
    USING (auth.uid() = user_id);

-- service role 拥有全部权限（后端服务使用）
CREATE POLICY "service role 全权限"
    ON user_api_quota
    FOR ALL
    TO service_role
    USING (true);

-- 自动更新 updated_at 字段的触发器函数（若尚未存在则创建）
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为 user_api_quota 绑定触发器
CREATE TRIGGER user_api_quota_updated_at
    BEFORE UPDATE ON user_api_quota
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
