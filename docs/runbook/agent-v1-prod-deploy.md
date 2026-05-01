# Agent v1 Prod 部署 Runbook

> 把 `agent-v1` 分支的 W1-W3 工作部署到生产服务器。
> **执行前必须用户确认**(操作 prod 不可逆)。
> 引用 [`docs/agent-pm/17-tech-plan.md`](../agent-pm/17-tech-plan.md)

## 前置条件

- agent-v1 分支已推 GitHub(最新 commit `8b36efd` 或更新)
- 本地代码 = 服务器代码(SHA1 对照,见前 sessions-log W1 验证)
- 服务器 `agent_trading_local` PG 14 端口 5432 在跑(`local_db.py` 已配)
- Supabase Dashboard 可访问

## 执行步骤

### Step 1 — 备份(可逆性)

```bash
ssh ubuntu@43.156.207.26 << 'EOF'
cd /opt/agent-trading
# git 当前状态备份
git stash list > /tmp/git-stash-before-agent-v1.txt
git log --oneline -5 > /tmp/git-log-before-agent-v1.txt
# DB 备份
PGPASSWORD=agent_local_2026 pg_dump -h 127.0.0.1 -U agent_local agent_trading_local \
  > /tmp/agent-trading-local-$(date +%Y%m%d-%H%M).sql
ls -lh /tmp/agent-trading-local-*.sql | tail -1
EOF
```

### Step 2 — 切到 agent-v1 分支

```bash
ssh ubuntu@43.156.207.26 "cd /opt/agent-trading && \
  git fetch origin agent-v1 && \
  git checkout agent-v1 && \
  git pull origin agent-v1 && \
  git log --oneline -5"
```

### Step 3 — 执行本地 PG migrations(7 个)

```bash
ssh ubuntu@43.156.207.26 << 'EOF'
cd /opt/agent-trading/services/pump-scanner/migrations/local_pg
for f in 034_kms_migration 035_security_audit_log 036_pending_approvals_wal \
         037_conversation_states 038_prompt_versions 039_agent_thesis \
         041_eval_results 042_agent_global_state; do
  echo "=== Running ${f} ==="
  PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local \
    -d agent_trading_local -f ${f}.sql || { echo "FAILED: $f"; exit 1; }
done

# 验证表已建
echo "=== 验证表清单 ==="
PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local \
  -d agent_trading_local -c "\dt"
EOF
```

期望见 8 张新表:
- `kms_key_aliases`
- `security_audit_log`
- `pending_approvals`
- `memory_write_wal`
- `memory_write_retry_queue`
- `conversation_states`
- `prompt_versions` + `prompt_invocations`
- `agent_thesis`
- `eval_results`
- `agent_global_state` + `agent_global_state_history`

### Step 4 — 执行 Supabase migration 040(单独)

```
1. 打开 https://supabase.com/dashboard/project/qmzsruqgwaqusywprxlj
2. SQL Editor → New query
3. 复制 services/pump-scanner/migrations/040_semantic_shadow_mode.sql 内容粘贴
4. Run
5. 验证:
   SELECT column_name FROM information_schema.columns
     WHERE table_name='agent_memory'
     AND column_name IN ('active_regimes','shadow_mode_until','propose_count','match_count','wilson_ci_lower','dormant_since','evidence');
   期望返回 7 行
```

### Step 5 — 重启服务

```bash
ssh ubuntu@43.156.207.26 << 'EOF'
sudo systemctl restart pump-scanner
sleep 5
sudo systemctl status pump-scanner --no-pager | head -8
# 看启动日志中 [Safety] engine ready 行
sudo journalctl -u pump-scanner --since '30 seconds ago' --no-pager | grep -E "Safety|GlobalState|engine ready" | head -5
EOF
```

期望见:`[Safety] engine ready: HR=30 CB=13 C=5 state=normal`

### Step 6 — 健康检查

```bash
# Agent 全局状态
curl -s http://43.156.207.26/api/admin/agent/state | jq

# Thesis MOCK_MODE 触发(临时开启)
ssh ubuntu@43.156.207.26 "echo 'MOCK_MODE=true' | sudo tee -a /opt/agent-trading/.env && sudo systemctl restart pump-scanner"
sleep 5
curl -X POST http://43.156.207.26/api/thesis \
  -H "Content-Type: application/json" \
  -d '{"chain":"solana","address":"TRUMPaddr","level":"L2"}' | jq
# 期望返 thesis fixture(direction/conviction/risks 完整)

# 关掉 MOCK_MODE
ssh ubuntu@43.156.207.26 "sudo sed -i '/^MOCK_MODE=/d' /opt/agent-trading/.env && sudo systemctl restart pump-scanner"
```

### Step 7 — Flutter App 端验证

```bash
cd /Users/wenruiwei/Desktop/Agent-Trading/apps/app
flutter run -d DBC925B5-7657-4410-B770-F21E4605A9D6 \
  --dart-define=API_BASE_URL=http://43.156.207.26 \
  --dart-define=HELIUS_API_KEY=a194f0cb-e6f5-474d-a9fc-d13b6e916964
# 进 Agent Tab → 点 ✨ Thesis Demo → 应实时调真后端 routes_thesis(MOCK_MODE 关时返 501,fallback 本地 mock)
# 进 Agent Tab → 点 🛡 HITL Demo → 进入 HITL 详情页(已有 fixture 数据)
```

## 回滚步骤(出错时)

```bash
ssh ubuntu@43.156.207.26 << 'EOF'
# 1. 切回 main
cd /opt/agent-trading
git checkout main
sudo systemctl restart pump-scanner

# 2. 回滚 PG 表(如果 migration 之后出问题)
# 注意:这会丢 agent-v1 期间产生的所有 audit / hitl / WAL 数据
PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local \
  -d agent_trading_local << 'SQL'
DROP TABLE IF EXISTS agent_global_state_history CASCADE;
DROP TABLE IF EXISTS agent_global_state         CASCADE;
DROP TABLE IF EXISTS eval_results               CASCADE;
DROP TABLE IF EXISTS agent_thesis               CASCADE;
DROP TABLE IF EXISTS prompt_invocations         CASCADE;
DROP TABLE IF EXISTS prompt_versions            CASCADE;
DROP TABLE IF EXISTS conversation_states        CASCADE;
DROP TABLE IF EXISTS memory_write_retry_queue   CASCADE;
DROP TABLE IF EXISTS memory_write_wal           CASCADE;
DROP TABLE IF EXISTS pending_approvals          CASCADE;
DROP TABLE IF EXISTS security_audit_log         CASCADE;
DROP TABLE IF EXISTS kms_key_aliases            CASCADE;
SQL

# 3. 回滚 Supabase 040(Dashboard SQL Editor):
# ALTER TABLE agent_memory
#   DROP COLUMN IF EXISTS active_regimes,
#   DROP COLUMN IF EXISTS shadow_mode_until,
#   DROP COLUMN IF EXISTS propose_count,
#   DROP COLUMN IF EXISTS match_count,
#   DROP COLUMN IF EXISTS wilson_ci_lower,
#   DROP COLUMN IF EXISTS dormant_since,
#   DROP COLUMN IF EXISTS evidence;

# 4. 从备份恢复 DB
# PGPASSWORD=agent_local_2026 psql -h 127.0.0.1 -U agent_local \
#   agent_trading_local < /tmp/agent-trading-local-YYYYMMDD-HHMM.sql
EOF
```

## 部署后状态

```
+ 30 HR + 13 CB + 5 C 在 prod 生效(safety_engine 完整)
+ Agent global state 持久化(重启后自动恢复 active CB)
+ /api/thesis / /api/audit / /api/admin 端点可用(MOCK_MODE 切换)
+ trade_executor 接 safety_ctx(notify_loop / chat 待 W4-W6 调用)
+ Flutter Agent Tab 多了 Demo Banner(Thesis + HITL),用户可点
```

**线上能力变化**:
- 真金交易 pre-check 已就位(只要调用方传 safety_ctx)
- HITL 队列表已建,但 W7-W12 才接到 trade_executor 真触发
- multi_role_orchestrator 仍是旧逻辑(Phase 2 W7-W12 才重构成 thesis_loop)
- 用户实际操作体验差异:Agent Tab 多 2 个 Demo 入口,其他不变

## 操作责任

| 阶段 | 责任人 | 风险 |
|---|---|---|
| Step 1 备份 | DevOps | 低 |
| Step 2 切分支 | DevOps | 中(代码变化) |
| Step 3 本地 PG | DevOps | 中(DDL 不可逆) |
| Step 4 Supabase | DevOps + 安全 | 中(改业务表 agent_memory) |
| Step 5 重启 | DevOps | 中(服务中断 < 30s) |
| Step 6 健康检查 | DevOps | 低 |
| Step 7 Flutter | QA | 低 |

执行人:____________   日期:____________   验证签字:____________
