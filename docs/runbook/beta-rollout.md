# Beta Rollout Runbook — 5% → 25% → GA 灰度推进

> 给谁看:Release manager / Ops / PM(谁手按 rollout_pct 数字谁读)
> 一句话:**改 `agent/rollout_gate.py` 里的 DEFAULT_ROLLOUT_PCT 数字,然后跑 verify.sh + 看 24h 监控**

| 字段 | 值 |
|------|---|
| Status | 🟢 v1.0 |
| Owner | release-manager + ops-lead |
| 引用 | docs/agent-pm/eval-summary.md / docs/runbook/eval-runbook.md / agent/rollout_gate.py |

---

## 0. TL;DR

```
0%(today)
  ↓ 准入门槛:eval all_hard_gates=✓ + 17 launch criteria 至少 sign-off 推进 + 安全 lead 签字
5% Canary(≥1 周)
  ↓ 准入门槛:无 SEV-0 / cost ≤ 预算 1.5x / P95 latency 达标 / 0 用户 critical bug
25% Beta(≥2 周)
  ↓ 准入门槛:NPS ≥ 30 / 17 launch criteria 100% / cost ≤ 预算 1.0x / 法务 sign-off
100% GA
```

任何阶段:任何**hard gate fail / SEV-0 漏洞 / cost 超预算 2x** → 立即 rollback 到上一阶段。

---

## 1. 怎么改 rollout_pct

### 1.1 编辑 DEFAULT_ROLLOUT_PCT

文件:`services/pump-scanner/agent/rollout_gate.py`

```python
DEFAULT_ROLLOUT_PCT: Dict[str, int] = {
    "agent_v1": 0,                 # ← 主门:0 / 5 / 25 / 100
    "agent_v1_thesis_l3": 0,
    "agent_v1_auto_mode": 0,       # ← KMS 上线后才能 > 0
    "agent_v1_kms_signing": 0,
    "agent_v1_real_llm_judge": 0,
    "agent_v1_l3_debate_full": 0,
    "agent_v1_input_filter": 100,  # 已 v1.0 全开
    "agent_v1_safety_engine": 100,
}
```

**改主门 agent_v1**:0 → 5(开 Canary);0/5 → 25(开 Beta);任何 → 100(GA)。

**子 feature** 可独立 gate(更细粒度):
- `thesis_l3` 贵 + 风险高 → 主门到 100% 后才放
- `auto_mode` 真金交易 → KMS 上线 + S14 red team drill 完成才能 > 0
- `kms_signing` → 等 W7-W12 KMS 实施
- `real_llm_judge` → 等 W17-W22 真 LLM judge 接通

### 1.2 提交流程

1. **改 DEFAULT_ROLLOUT_PCT 的 PR**:必须含
   - 上一阶段 ≥ 准入观察期(5%≥1w / 25%≥2w)
   - eval-snapshot.json 截图(all_hard_gates=✓)
   - cost / latency / NPS 数据点(从 dashboard 截图)
   - safety lead + ops + PM 三方 LGTM

2. **CI 跑过**(eval-gate.yml 必须 ✓)

3. **本地 `./scripts/verify.sh`** 必须 ✓

4. **Merge 后 deploy**:重启 pump-scanner-api 让新 rollout_pct 生效

5. **24h 监控 + 准备 rollback PR 在抽屉**

### 1.3 紧急 rollback

```bash
# 1. 回退 PR(把 rollout_pct 改回上一阶段)
git revert <commit-of-rollout-bump> -m 1

# 2. 跑 verify
cd services/pump-scanner && ./scripts/verify.sh

# 3. force-merge + deploy(skip review,因为是 rollback)
ssh ubuntu@43.156.207.26 "cd /opt/agent-trading && git pull && \
  sudo systemctl restart pump-scanner-api"

# 4. 在 incident channel 通报回退 + 根因
```

**或更快的紧急 kill switch**(不改代码):
- POST /api/admin/agent/kill-switch(routes_admin.py 已实施)
- 让 safety_engine.agent_global_state = blocked
- 全部新流量 → BLOCKED;在线已发的 thesis 不受影响

---

## 2. 三阶段详细

### 2.1 Stage 0 → 5%(Canary 1w)

**准入门槛**:
- `python3 -m agent.eval.run_all` → all_hard_gates=✓
- launch_criteria Tech 12/12 100% / Safety SEV-0 100%
- 安全 lead + Ops 签字
- Kill switch / rollback PR 备好

**配置**:`agent_v1: 0 → 5`

**观察 ≥ 1 周看**:
| 维度 | 目标 | 红线(立即 rollback)|
|------|------|---------------------|
| 用户报告 critical bug | 0 | ≥ 1 |
| SEV-0 violation | 0 | ≥ 1 |
| 504 / 5xx 率 | < 1% | ≥ 5% |
| P95 latency | < 3s | ≥ 8s |
| 月 cost / DAU | ≤ $15 | ≥ $30 |
| Agent kill_switch 触发 | 0 | ≥ 1 |
| HITL queue 累积 | < 20 | ≥ 100 |

**升 25 准入**:全绿满 1 周 + PM 看 dashboard 确认

### 2.2 Stage 5% → 25%(Beta 2w)

**准入门槛**:
- 上述 5% 全绿满 1 周
- launch_criteria 17 blocked 至少推进了 5 项
- 已收集 ≥ 5 条 NPS 反馈
- 法务对 disclaimer 文本预审 OK(L01-L03)

**配置**:`agent_v1: 5 → 25`

**观察 ≥ 2 周看**(同 5% 表 + 新增):
| 维度 | 目标 |
|------|------|
| NPS(种子用户)| ≥ 20 |
| paper → notify 成功晋升数 | ≥ 5 |
| HITL approve 率 | > 70% |
| auto_mode 触发 → 用户 reject 率 | < 30% |

**升 100 准入**:全绿满 2 周 + 17 launch criteria 100% + L12 法务最终签字

### 2.3 Stage 25% → 100%(GA)

**准入门槛**(GA Gate):
- 17 launch criteria 全 100%(launch_runner all_categories_100=True)
- L12 法务最终签字
- NPS ≥ 30
- 安全 / Ops / PM / Legal 四方签字
- KMS 真上线 + auto_mode 可独立 gate

**配置**:`agent_v1: 25 → 100`(可同步 `agent_v1_thesis_l3: 0 → 100` 等子 gate)

**GA 后 30 天观察**(同 Beta 表 + 新增):
| 维度 | 目标 |
|------|------|
| 月 cost @ 100 DAU | ≤ $1500(对齐 17-tech-plan.md 预算)|
| Quality Rubric overall | ≥ 70(LLM-judge 真接通后到 80)|
| Safety AE SEV-0 30d 累计 | 0 |
| 用户留存 D30 | ≥ 30% |

---

## 3. Rollback trigger 优先级

按严重度从高到低,任一命中立即执行:

| 优先级 | Trigger | 行动 | SLA |
|-------|---------|------|-----|
| 🔴 P0 | SEV-0 violation 漏到用户 / 真金 loss / KMS 私钥泄露 | **kill_switch + rollback** | < 10 min |
| 🔴 P0 | regulation 违规(法务通知 cease & desist)| **kill_switch + 通知法务** | < 10 min |
| 🟠 P1 | hard gate eval CI 红 / cost 超预算 2x | rollback | < 1 hour |
| 🟠 P1 | 504/5xx ≥ 5% / P95 ≥ 8s | rollback | < 1 hour |
| 🟡 P2 | NPS < 0 / critical bug 用户 ≥ 5 | 评估 24h 后 rollback or 修复 | < 24 hours |
| 🟢 P3 | quality_rubric 单 dim 走低 / launch criteria 退步 | 评估 1w 后 rollback or 修复 | < 1 week |

---

## 4. 监控 dashboard 必看(GA 前每天 / GA 后每周)

```
1. eval-gate CI 当日 status        — green / red(red 必看 PR comment)
2. eval-snapshot trend             — 9 suite 每日 pass_rate 时序
3. cost: anthropic 月累计 / DAU    — 接近 $1500/100DAU = $15/DAU
4. P95 latency: thesis / chat / notify
5. SEV-0 count(input_filter blocked / safety_engine BLOCKED)
6. HITL queue: pending / approved / rejected / expired
7. agent_global_state(normal / soft / hard / blocked)
8. NPS / 用户报告 critical bug 数
9. paper→notify→auto 晋升漏斗
10. launch_criteria 17 blocked 推进进度
```

数据源:
- eval-snapshot.json artifact(GitHub Actions)
- prompt_invocations 表(成本 / latency)
- security_audit_log 表(SEV / kill switch)
- pending_approvals 表(HITL)
- agent_global_state 表(circuit breaker state)

---

## 5. 上线前最后 checklist

- [ ] `cd services/pump-scanner && ./scripts/verify.sh` → ✅
- [ ] `python -m agent.eval.run_all` → all_hard_gates=✓
- [ ] launch_runner 跑出来,17 blocked 至少推进了若干(canary 5)/全清(GA)
- [ ] safety lead 签字(本次推进 PR LGTM)
- [ ] ops lead 签字(monitoring + alert 都 ok)
- [ ] PM 签字(用户体验 + 准入门槛对齐 spec)
- [ ] (GA 阶段)L12 法务最终签字
- [ ] kill switch 演练成功一次(< 10 min 全 BLOCKED)
- [ ] rollback PR 已 draft(指向上一阶段的 commit)
- [ ] incident sop 链接已贴在 release notes(`docs/runbook/agent-v1-prod-deploy.md`)

---

## 6. 历史 rollout 记录(每次推进追加)

| Date | Stage | rollout_pct | Owner | Notes | Eval snapshot |
|------|-------|-------------|-------|-------|---------------|
| 2026-05-01 | 0% (initial) | agent_v1=0 | autonomous-loop 续 33 | rollout_gate framework 就位,等准入条件 | (本仓库 commit) |

(以后每次升降 rollout_pct 都追加一行)

---

## 7. 故障案例(本仓库已知)

无(rollout_gate 是新模块,首次实施)。

将来案例追加到这里,格式:
- 日期 / 阶段 / 触发 / 行动 / 根因 / 修法 / 教训

---

## 8. 相关文档

- `docs/agent-pm/eval-summary.md` — Phase 4 sign-off snapshot
- `docs/runbook/eval-runbook.md` — eval gate 跑法 + triage
- `docs/runbook/agent-v1-prod-deploy.md` — Prod deploy
- `services/pump-scanner/agent/rollout_gate.py` — 实施 + DEFAULT_ROLLOUT_PCT 真值
- `services/pump-scanner/tests/test_rollout_gate.py` — 23 测试覆盖 determinism + 边界
- `services/pump-scanner/api/routes_admin.py` — Kill switch endpoint
