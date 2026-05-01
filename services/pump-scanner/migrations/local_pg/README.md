# Local PostgreSQL Migrations

> 8 张 Agent v1 新表,**不放 Supabase**,放服务器本地 PG 14。
> 引用 [`docs/agent-pm/17-tech-plan.md`](../../../../docs/agent-pm/17-tech-plan.md) 增量决策(2026-05-01)。

## 为什么不放 Supabase

1. **节省 Supabase 免费额度**(已用 token_trades 占大头)
2. **零网络延迟**适合高频写入(WAL / audit_log / prompt_invocations)
3. **服务器已有 PG 14 在跑**(`local_db.py` 已对接 `dex_address_stats`),复用基础设施

## 数据库连接信息

| 项 | 值 |
|---|---|
| Host | `127.0.0.1` |
| Port | `5432` |
| Database | `agent_trading_local` |
| User | `agent_local` |
| Password | 见服务器 `.env` 的 `LOCAL_DB_DSN` |

## 执行步骤(prod)

```bash
# 1. SSH 到服务器
ssh ubuntu@43.156.207.26

# 2. 切到代码目录
cd /opt/agent-trading

# 3. git pull 最新 agent-v1 分支
git fetch origin && git checkout agent-v1 && git pull

# 4. 按编号顺序执行本地 PG migrations(7 个)
cd services/pump-scanner/migrations/local_pg
for f in 034_kms_migration 035_security_audit_log 036_pending_approvals_wal 037_conversation_states 038_prompt_versions 039_agent_thesis 041_eval_results; do
  echo "=== $f ==="
  PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local -d agent_trading_local -f ${f}.sql
done

# 5. 040_semantic_shadow_mode.sql 是给 Supabase 表加字段,**不在本目录**,
#    需在 Supabase Dashboard SQL Editor 单独执行
#    见 services/pump-scanner/migrations/040_semantic_shadow_mode.sql

# 5. 验证表已创建
PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local -d agent_trading_local -c "\dt"
# 期望见 8 张新表 + 既有的 dex_address_stats
```

## 8 张表 + TTL 清理(由 db_cleanup.py 每 6h 跑)

| Migration | 表 | TTL | 触发字段 |
|---|---|---|---|
| 034 | `kms_key_aliases` | 永久 | - |
| 035 | `security_audit_log` | **90 天** | `ts` |
| 036 | `pending_approvals` | `decided_at + 30 天` | `decided_at` |
| 036 | `memory_write_wal` | `flushed_at + 7 天` | `flushed_at` |
| 036 | `memory_write_retry_queue` | `resolved=true + 7 天` | `created_at` |
| 037 | `conversation_states` | `expires_at + 24h`(完结/过期清) | `expires_at` |
| 038 | `prompt_versions` | `retired_at + 30 天`(retired 才清) | `retired_at` |
| 038 | `prompt_invocations` | **30 天** 滚动 | `ts` |
| 039 | `agent_thesis` | **30 天**(L3+conviction>0.8 例外保 90 天) | `ts` |
| 041 | `eval_results` | 90 天 | `ts` |

⚠️ **040 不在本目录**:`040_semantic_shadow_mode.sql` 是给 Supabase 表(`agent_memory` + `agent_strategies`)加字段,需在 Supabase Dashboard SQL Editor 单独执行。文件路径:`services/pump-scanner/migrations/040_semantic_shadow_mode.sql`(根目录)

## 状态

- 🟢 v0.1 SQL 已就绪
- 🔴 prod 未执行(等 Phase 0 KMS / safety_engine 实施完后再跑)
- 🟢 db_cleanup.py 的 `run_local_pg_cleanup()` 已就绪;表不存在时静默跳过
