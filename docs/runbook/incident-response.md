# Incident Response Runbook(Top 10 Failure Modes)

**目标**:任意运行时故障在 < 30min 内识别 + 缓解 + 恢复
**SLA**:
- SEV-0(Kill Switch / 真金资金风险):< 10 min ack + < 30 min mitigation
- SEV-1(API 大面积 5xx / 数据丢失):< 30 min ack + < 2 hour mitigation
- SEV-2(单功能降级):< 2 hour ack + 当天修

**适用环境**:服务器 `43.156.207.26`(Ubuntu)+ 本地 PG `agent_trading_local` + Supabase + Anthropic API + Helius/OKX + Redis localhost
**先跑命令**(任何 incident):
```bash
ssh ubuntu@43.156.207.26 "sudo systemctl status pump-scanner-api pump-scanner --no-pager | head -50"
ssh ubuntu@43.156.207.26 "sudo journalctl -u pump-scanner-api -n 100 --no-pager"
curl -s http://localhost:8000/health
```

---

## #1 — Agent 全局失控 / 用户报"莫名其妙真金交易"

**症状**:用户截图 / 日志显示 trade_executor 在没有用户授权的情况下执行真金。

**SEV-0 / 立即响应**

```bash
# 1. 立即 Kill Switch(< 10s SLA)
curl -X POST http://43.156.207.26/api/admin/agent/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"reason":"INCIDENT-001 用户报真金误触发","confirm":true}'
# 期望返 {"ok":true, "took_ms": <1000, "global_state": "blocked"}

# 2. 验证状态
curl http://43.156.207.26/api/admin/agent/state
# 期望 status="blocked" + active_cbs 含 CB14

# 3. 查近 1h 真金 trades
ssh ubuntu@43.156.207.26 "psql -h 127.0.0.1 -U agent_local -d agent_trading_local -c \
  \"SELECT * FROM security_audit_log WHERE event_type='trade_exec' AND ts > NOW() - INTERVAL '1 hour' ORDER BY ts DESC LIMIT 20;\""
```

**根因排查**:
- rollout_gate `agent_v1_auto_mode` 是否 = 0?(grep `agent/rollout_gate.py`)
- strategy mode 是否被绕开(SQL 直改 mode='live'?)
- T08 execute_swap pre-check 是否漏 safety_ctx?

**恢复**:
- 修根因 + 部署
- `kill-switch/release` 解除(必须 confirm=true)
- 通知用户 + 退款流程

---

## #2 — 8000 端口不 LISTEN(systemctl restart 失效)

**症状**:`curl http://localhost:8000/health` 超时;Flutter App 报 timeout。

**SEV-1 / 30 min ack**

```bash
ssh ubuntu@43.156.207.26 "sudo netstat -tnlp | grep 8000"
# 应见 uvicorn 监听;若空,以下任选:

# 方案 A:重启 api server(独立 service)
ssh ubuntu@43.156.207.26 "sudo systemctl restart pump-scanner-api"
sleep 5
ssh ubuntu@43.156.207.26 "sudo netstat -tnlp | grep 8000"

# 方案 B:看启动 log 找根因
ssh ubuntu@43.156.207.26 "sudo journalctl -u pump-scanner-api -n 200 --no-pager"

# 方案 C(终极): reboot
ssh ubuntu@43.156.207.26 "sudo reboot"
# 等 1-2 min 再 curl
```

**已知踩坑**(见 `docs/memory/pitfalls.md`):
- W3 D4 commit `34b9c00` `socket.create_connection` 同步阻塞 → 已修
- 独立 uvicorn service(commit `03d9cd1`)解决 SmartMoneyTracker fd 残留问题
- 若再现:用 `sudo reboot` 兜底

---

## #3 — Anthropic LLM 月预算超 100% / cost_guard 触发 HARD_STOP

**症状**:Cost Guard log "HARD_STOP triggered" / `routes_thesis` 返 cost-blocked / 用户反映 thesis 都返 fallback。

**SEV-1 / 30 min ack**

```bash
# 1. 查当月用量
curl -X POST http://43.156.207.26/api/admin/cost/refresh
# 期望返 {"monthly_used_usd": <>, "level": "HARD_STOP", "pct": >100}

# 2. 查最近 1h prompt invocations 看是不是 abuse
ssh ubuntu@43.156.207.26 "psql -h 127.0.0.1 -U agent_local -d agent_trading_local -c \
  \"SELECT prompt_id, COUNT(*) c, SUM(cost_usd) cost FROM prompt_invocations \
    WHERE ts > NOW() - INTERVAL '1 hour' GROUP BY prompt_id ORDER BY cost DESC;\""

# 3. 临时降级(改 rollout_gate 关 L3 真 debate,省 90% Opus token)
ssh ubuntu@43.156.207.26 "cd /opt/agent-trading && \
  sed -i 's/agent_v1_thesis_l3.*100/agent_v1_thesis_l3:0/' services/pump-scanner/agent/rollout_gate.py && \
  sudo systemctl restart pump-scanner-api"

# 4. 联系 Anthropic 看是否能临时提额度
```

**根因**:典型是 prompt cache miss(频繁全量 prompt) / 一个用户被滥用 / regime CRISIS 触发大量 L3。
**预防**:每日 monitor `prompt_invocations` 表 + 设 70% 软阈值告警。

---

## #4 — 数据库连接耗尽(本地 PG 或 Supabase)

**症状**:大量 "connection pool exhausted" / "too many clients" 日志;500 错误。

**SEV-1**

```bash
# 1. 查本地 PG 连接
ssh ubuntu@43.156.207.26 "sudo -u postgres psql -c 'SELECT count(*) FROM pg_stat_activity;'"
# 通常 < 50;若 > 100 异常

# 2. 找连接来源
ssh ubuntu@43.156.207.26 "sudo -u postgres psql -c 'SELECT application_name, COUNT(*) FROM pg_stat_activity GROUP BY application_name;'"

# 3. 紧急 kill idle connection
ssh ubuntu@43.156.207.26 "sudo -u postgres psql -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle' AND query_start < NOW() - INTERVAL '10 min';\""

# 4. 重启服务(释放连接)
ssh ubuntu@43.156.207.26 "sudo systemctl restart pump-scanner-api pump-scanner"
```

**根因**:typically pump-scanner 连接泄漏 / 高频写未 release。
**预防**:每个 cursor 用 `with conn.cursor() as cur:` 确保释放。

---

## #5 — Helius / OKX / 数据源 API rate limit

**症状**:大量 429 / "rate limit exceeded";smart_money_signals 表 1h 无新数据。

**SEV-2**

```bash
# 1. 查 dexscreener / Helius / OKX 当日调用量
ssh ubuntu@43.156.207.26 "sudo journalctl -u pump-scanner -n 500 --no-pager | grep -E '429|rate.limit' | wc -l"

# 2. 暂时降低扫描频率(改 .env 或 main.py interval)
# DexScreener:30s → 60s
# Helius WS:已是免费上限,降级 → 只 SOL,跳 EVM

# 3. 联系 vendor 升级 plan(Helius pro 已含 50 RPS 应该够;OKX 限速 is per-key)
```

---

## #6 — Anthropic LLM API down(503 / timeout)

**症状**:thesis_loop / chat_loop 大量超时,用户看到 "后端不可用 fallback"。

**SEV-1**

```bash
# 1. 验证 Anthropic 状态
curl -s https://status.anthropic.com/api/v2/status.json | jq

# 2. 切 fallback 模式 — review_engine + chat_loop 已内置 rule_engine fallback
# 不用任何手动操作,UI 自动降级(source="rule_engine"). 监控 Sentry 即可

# 3. 长期 down(>2h)→ 切 OpenAI fallback
# 改 cost_guard / prompt_loader 用 OPENAI_API_KEY,但目前没实施
# 内测期接受 thesis L1 only(0 LLM cost)
```

---

## #7 — Flutter App 大面积闪退(Crashlytics 报 "Null subtype" 等)

**症状**:Firebase Crashlytics 报某 release 闪退率 > 5%。

**SEV-1 / 30 min**

```bash
# 1. 查 dart-side 异常
# 看 Crashlytics 最常见 stack trace

# 2. 典型:后端 schema 变了 Flutter 没跟上(R36 EvidenceItem source/value→layer/text)
# 修 Flutter model + 紧急 hotfix build

# 3. iOS:重新打包 IPA
cd /Users/wenruiwei/Desktop/Agent-Trading/apps/app
flutter build ipa --release \
  --export-method=ad-hoc \
  --dart-define=API_BASE_URL=http://43.156.207.26 \
  --dart-define=HELIUS_API_KEY=a194f0cb-e6f5-474d-a9fc-d13b6e916964
# 给团队成员发新 IPA
```

---

## #8 — 推送通知不到(FCM / APNs)

**症状**:用户报 thesis triggered / HITL approval 不收到推送。

**SEV-2**

```bash
# 1. 验证 device_token 表
ssh ubuntu@43.156.207.26 "psql -h 127.0.0.1 -U agent_local -d agent_trading_local -c \
  \"SELECT COUNT(*), MAX(updated_at) FROM device_tokens WHERE last_seen_at > NOW() - INTERVAL '7 days';\""

# 2. 看 push_service log
ssh ubuntu@43.156.207.26 "sudo journalctl -u pump-scanner-api -n 200 --no-pager | grep -i push"

# 3. Firebase 配置(google-services.json)是否过期
# 重新生成 + 重打包 Flutter IPA
```

**已知**:Firebase 推送在 R37 仍待用户配置,看 [pitfalls.md](../memory/pitfalls.md)。

---

## #9 — HITL queue 卡死(用户 60min 没决定 + 超时 cron 没跑)

**症状**:`pending_approvals` 表大量 status='pending' 且 expires_at < now,但策略一直卡。

**SEV-1**

```bash
# 1. 手动跑一次扫描
curl -X POST http://43.156.207.26/api/admin/hitl/scan-timeouts
# 期望返 {"repushed": ..., "degraded": ..., "expired": ...}

# 2. 验证 cron 在跑(每 60s)
ssh ubuntu@43.156.207.26 "sudo journalctl -u pump-scanner -n 200 --no-pager | grep hitl-timeout"
# 应看到 "[hitl-timeout cron]" 每分钟一行

# 3. 看 active jobs
ssh ubuntu@43.156.207.26 "curl http://localhost:8000/api/admin/cb"
# 看 CB 是否触发导致 cron 不跑(理论不会,这是独立 cron)

# 4. 终极:重启 pump-scanner(scheduler 在 main process 里)
ssh ubuntu@43.156.207.26 "sudo systemctl restart pump-scanner"
```

---

## #10 — Memory 规则全部失效(Semantic 14d Shadow 评估漏掉一批)

**症状**:用户报 "AI 不再学到东西",`agent_memory` 全部 is_active=False / shadow_mode_until 都过期。

**SEV-2**

```bash
# 1. 手动跑 shadow eval
curl -X POST http://43.156.207.26/api/admin/memory/shadow-eval
# 期望返 {"graduated": >0, "dormant": ..., "failed": ...}

# 2. 验证 cron 在跑(每 6h)
ssh ubuntu@43.156.207.26 "sudo journalctl -u pump-scanner -n 1000 --no-pager | grep 'shadow eval'"

# 3. 查 Reflect Loop 是否有跑
ssh ubuntu@43.156.207.26 "sudo journalctl -u pump-scanner -n 1000 --no-pager | grep 'reflect cron'"

# 4. 手动触发 reflect
curl -X POST http://43.156.207.26/api/agent/reflect/run \
  -H "Content-Type: application/json" -d '{"trigger":"daily","lookback_days":7}'
```

---

# 通用排障流程

## A. 先看健康
```bash
curl http://43.156.207.26/health
curl http://43.156.207.26/api/admin/agent/state
```

## B. 看服务 log
```bash
ssh ubuntu@43.156.207.26 "sudo journalctl -u pump-scanner-api -n 100 --no-pager"
ssh ubuntu@43.156.207.26 "sudo journalctl -u pump-scanner -n 200 --no-pager"
```

## C. 看 PG 数据
```bash
ssh ubuntu@43.156.207.26 "psql -h 127.0.0.1 -U agent_local -d agent_trading_local"
```

## D. 紧急止血(最后手段)
```bash
# Kill Switch — 全局 BLOCK
curl -X POST http://43.156.207.26/api/admin/agent/kill-switch \
  -d '{"reason":"emergency","confirm":true}' \
  -H "Content-Type: application/json"

# 全停服务
ssh ubuntu@43.156.207.26 "sudo systemctl stop pump-scanner pump-scanner-api"

# 启动
ssh ubuntu@43.156.207.26 "sudo systemctl start pump-scanner-api pump-scanner"
```

## E. 关停后 10s 内复盘清单
1. 写 incident-XXX.md(时间 / 用户影响 / 根因 / 修复)
2. 更新 `docs/memory/pitfalls.md` 防重蹈
3. 添加自动监控告警(避免下次靠人工)

---

**Last updated**: 2026-05-03 R37 P0-5
**On-call**: 项目 owner(早期项目无值班轮换)
**Escalation**: 用户在中国大陆,联系微信群 / Telegram
