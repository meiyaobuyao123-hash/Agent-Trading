-- Migration 035: 安全审计日志(Phase 0 必装)
-- 引用 17-tech-plan.md Phase 0 + docs/agent-pm/08-safety-policy.md §11.5
-- 180 天保留(由 db_cleanup.py 处理)
-- 三级查询权限(用户/Admin/法务)由 routes_audit.py 实现

CREATE TABLE IF NOT EXISTS security_audit_log (
  id            BIGSERIAL   PRIMARY KEY,
  ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
  device_id     UUID        NOT NULL,
  event_type    TEXT        NOT NULL,
  severity      TEXT        NOT NULL,
  payload       JSONB       NOT NULL,
  ip_addr       INET,
  user_agent    TEXT,
  approval_id   UUID,                              -- 关联 pending_approvals(如果是 HITL 触发)
  thesis_id     UUID,                              -- 关联 agent_thesis(如果是分析触发)
  CONSTRAINT severity_valid    CHECK (severity   IN ('info','warn','error','critical')),
  CONSTRAINT event_type_valid  CHECK (event_type IN (
    'auth',              -- 登录 / token 刷新
    'wallet_op',         -- 钱包导入 / 切换 / 删除
    'trade_exec',        -- DEX swap 执行(成功/失败)
    'config_change',     -- 策略 / 风控规则 / Memory 规则修改
    'kms_use',           -- KMS 签名调用
    'safety_block',      -- safety_policy 拦截
    'cb_trigger',        -- 熔断器触发
    'hitl_decision',     -- 用户审批 / 拒绝
    'memory_write',      -- 记忆写入(critical 才记)
    'kill_switch',       -- 全局停机
    'admin_action'       -- Admin 操作
  ))
);

CREATE INDEX IF NOT EXISTS idx_audit_device_ts   ON security_audit_log(device_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event_ts    ON security_audit_log(event_type, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_severity_ts ON security_audit_log(severity, ts DESC) WHERE severity IN ('error','critical');
CREATE INDEX IF NOT EXISTS idx_audit_approval    ON security_audit_log(approval_id) WHERE approval_id IS NOT NULL;

COMMENT ON TABLE security_audit_log IS '审计日志,180 天保留 (TTL 由 db_cleanup.py 处理)';
COMMENT ON COLUMN security_audit_log.severity IS 'info|warn|error|critical;critical 触发立即告警';
