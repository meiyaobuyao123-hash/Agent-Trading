-- Migration 034: KMS 接入(Phase 0 灾难漏洞 L1+L2 修复前置)
-- 引用 17-tech-plan.md Phase 0
-- 执行方式: Supabase Dashboard SQL Editor 手动执行(代码无法自动 DDL)

-- ============================================================
-- 1. KMS key 别名映射表
-- ============================================================
-- 真实 KMS key id 不存 DB,只存别名 → 由 kms_client.py 用别名拉真值
-- 支持多 provider:AWS KMS / GCP KMS / Azure Key Vault
CREATE TABLE IF NOT EXISTS kms_key_aliases (
  alias                 TEXT        PRIMARY KEY,
  kms_provider          TEXT        NOT NULL DEFAULT 'aws-kms',
  external_key_id       TEXT        NOT NULL,                       -- KMS 那边的 key id (arn / resource id)
  rotation_period_days  INT         NOT NULL DEFAULT 90,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  rotated_at            TIMESTAMPTZ,
  is_active             BOOLEAN     NOT NULL DEFAULT true,
  CONSTRAINT kms_provider_valid CHECK (kms_provider IN ('aws-kms','gcp-kms','azure-kv','local-dev'))
);

COMMENT ON TABLE  kms_key_aliases    IS 'KMS key 别名注册;真实 key id 由 kms_client.py 按 alias 拉取';
COMMENT ON COLUMN kms_key_aliases.kms_provider     IS 'aws-kms / gcp-kms / azure-kv / local-dev (开发用,仅本机)';
COMMENT ON COLUMN kms_key_aliases.external_key_id  IS 'KMS provider 那边的 key id;不要直接拉 secret';

-- ============================================================
-- 2. device_tokens 加 kms_key_alias(托管钱包绑定)
-- ============================================================
ALTER TABLE device_tokens
  ADD COLUMN IF NOT EXISTS kms_key_alias TEXT REFERENCES kms_key_aliases(alias);

COMMENT ON COLUMN device_tokens.kms_key_alias IS '托管钱包用的 KMS key 别名,签名走 KMS 不落地私钥';

-- ============================================================
-- 3. agent_strategies 准备删除明文私钥列(L2 灾难漏洞)
-- ============================================================
-- 注意: 这一步只新增 alias 列,**不删** 原列。Phase 0 W3 数据迁移完成后再单独跑 drop。
-- 防止迁移中途丢数据。
ALTER TABLE agent_strategies
  ADD COLUMN IF NOT EXISTS kms_key_alias TEXT;

-- TODO Phase 0 W3 数据迁移完成后(确认所有钱包已切 KMS)单独跑:
--   ALTER TABLE agent_strategies DROP COLUMN IF EXISTS private_key;
--   ALTER TABLE agent_strategies DROP COLUMN IF EXISTS mnemonic;
--   ALTER TABLE agent_strategies DROP COLUMN IF EXISTS encrypted_seed;
-- 该步骤需 PM + Security 双签

-- ============================================================
-- 4. KMS 使用审计(配合 035 security_audit_log)
-- ============================================================
-- KMS 操作记录在 security_audit_log(event_type='kms_use')
-- 此处不重复建表
