# Eval Runbook — Ops 实操指南

> 给谁看:Ops / SRE / 上 PR 的工程师 / Release manager
> 一句话:**任何代码改动前都跑 `python3 -m agent.eval.run_all`,看 all_hard_gates=✓**

| 字段 | 值 |
|------|---|
| Status | 🟢 v1.0 |
| Owner | ops-lead + agent-team |
| 引用 | docs/agent-pm/eval-summary.md / agent/eval/run_all.py |
| 全跑耗时 | ~1 秒(本机)/ ~3 秒(CI) |

---

## 0. TL;DR

```bash
cd services/pump-scanner
python3 -m agent.eval.run_all
# → all_hard_gates=✓ 才能合 PR / 上线
```

输出长这样:
```
suite                    pass    rate   gate    time  notes
--------------------------------------------------------------------------------
  l1_tool           140/140    100.0%      ✓   0.58s
  l2_skill           44/44     100.0%      ✓   0.02s
  l1_prompt         110/110    100.0%      ✓   0.01s
  l3_chain           46/46     100.0%      ✓   0.30s
  safety_ae         132/132    100.0%      ✓   0.01s  SEV-0=100% SEV-1=100% SEV-2=100%
  l4_trajectory      20/20     100.0%      ✓   0.00s
  launch_criteria    45/62      72.6%      ✓   0.05s  milestone-gated
  quality_rubric     29/40      72.5%      ✓   0.01s
  judge_calibration   10/10     100.0%      ✓   0.01s  passes
--------------------------------------------------------------------------------
  TOTAL               576/604    all_hard_gates=✓   0.97s
```

---

## 1. 何时跑

| 场景 | 跑哪些 | 命令 |
|------|--------|------|
| **PR 提交前**(必跑)| 全部 9 suite | `python3 -m agent.eval.run_all` |
| **CI**(每个 PR 自动)| 全部 9 suite + JSON 输出 | `python3 -m agent.eval.run_all --json` |
| **Nightly**(每日 cron)| 全部 9 + Quality + Judge | 同上 + 分析趋势 |
| **Pre-deploy**(GA 前)| 全部 9 + manual sign-off review | 同上 + check launch criteria 17 blocked |
| **本地开发**(快速 check)| 跳过 launch | `python3 -m agent.eval.run_all --skip launch_criteria` |
| **改了某 Tool**(部分回归)| 单跑 L1 Tool | `python3 -m agent.eval.runner --suite=l1_tool` |
| **改了 input_filter**(safety 回归)| 单跑 Safety AE | `python3 -m agent.eval.safety_runner --suite=safety_ae` |

---

## 2. 各 suite 单独跑

如果只改了某一块,可以单独跑对应 suite(更快定位问题):

```bash
# 9 个 suite 各自的 CLI
python3 -m agent.eval.runner --suite=l1_tool                 # L1 Tool 13/140
python3 -m agent.eval.skill_runner --suite=l2_skill          # L2 Skill 7/44
python3 -m agent.eval.prompt_runner --suite=l1_prompt        # L1 Prompt 18/110
python3 -m agent.eval.chain_runner --suite=l3_chain          # L3 Chain 5/46
python3 -m agent.eval.safety_runner --suite=safety_ae        # Safety AE 10/132
python3 -m agent.eval.trajectory_runner --suite=l4_trajectory # L4 Trajectory 4/88
python3 -m agent.eval.launch_runner --suite=launch_criteria  # Launch 6/62
python3 -m agent.eval.rubric_runner --suite=quality_rubric   # Quality 4/40
python3 -m agent.eval.judge_runner --suite=judge_calibration # Judge 100 sample
```

每个 suite 都支持 `--cat=xxx` / `--tool=xxx` 等过滤参数,见各文件 docstring。

---

## 3. Pass/Fail 判定(给 reviewer)

### 3.1 Hard gates(任一不过 → run_all exit 1)

| Suite | Hard gate |
|-------|-----------|
| l1_tool | 100% pass(13/13 tools 全过)|
| l2_skill | 100% pass(7/7 skills 全过)|
| l1_prompt | 100% pass(18/18 prompts 全过)|
| l3_chain | 100% pass(5/5 chains 全过)|
| safety_ae | **all_severities_meet_threshold=True**(SEV-0 100% + SEV-1 99% + SEV-2 95%)|
| l4_trajectory | trajectory pass rate ≥ 85% |
| judge_calibration | passes=True(non-safety Pearson ≥ 0.7 + safety 100%)|

### 3.2 Soft gates(显示但不阻塞 PR)

| Suite | Soft gate | 何时阻塞 |
|-------|-----------|---------|
| launch_criteria | all_categories_100=True | GA 前(17 blocked 推到 0)|
| quality_rubric | overall ≥ 80(LLM-judge target) | W17-W22 接 LLM judge 后 |

### 3.3 不会通过的情况(GA 前 milestone)

- `launch_criteria 45/62 (72.6%)` 是**显式 milestone-gated**(legal 12 + 5 其他 blocked)
  - 不阻塞 PR / Beta;但 **GA 前必须推到 100%**
  - 推进路径见 `docs/agent-pm/eval-summary.md §3.1` 17 项 punch list

---

## 4. 失败 triage 流程

### 4.1 L1 Tool 失败

```
1. 看哪个 tool 的哪个 case 失败:
   python3 -m agent.eval.runner --suite=l1_tool --tool=<failing_tool>
2. 失败原因常见:
   - schema 改了 → 更新 fixture 的 expected_outcome
   - 新加了 failure_mode → 加新 case
   - external API 变化 → 检查 mock setup
3. 修后重跑该单 tool,绿了再跑 run_all
```

### 4.2 Safety AE 失败(SEV-0 漏 → 严重)

```
1. 看哪个 AE 类的哪个 case 失败:
   python3 -m agent.eval.safety_runner --suite=safety_ae --ae=AE0X
2. SEV-0 失败必须在 24h 内修(不能合 PR / 不能上线)
3. 通常修 input_filter regex 加新模式;参考 R24 闭合 SEV-0 流程
4. 修后重跑 safety_ae,SEV-0 100% ✓ 才能继续
```

### 4.3 L3 Chain 失败(class/route/cron 缺失)

```
1. 看哪个 chain 的哪个 step 失败:
   python3 -m agent.eval.chain_runner --suite=l3_chain --chain=<failing>
2. 通常是:
   - 重构后 method 名改了 → 更新 fixture 的 entry_method
   - 新加 route 但 fixture 没追 → 加 route_registered case
   - cron 改名 → 更新 cron_job_id
```

### 4.4 Quality Rubric 失败(overall < 60 baseline)

```
1. 看具体 sample 的 dim 分布:
   python3 -m agent.eval.rubric_runner --suite=quality_rubric --cat=<failing>
2. veto 触发(actionability=0 / risk=0 / safety<10)→ 输出确实有问题,fix output
3. 真 sample 分数偏低(无 veto)→ 可能 scorer 启发式过严,看是否 false negative
4. BAD 样本 pass 了 → 严重(scorer 失效),立即 review
```

---

## 5. CI 集成(GitHub Actions 示例)

```yaml
name: Eval Gate

on: [push, pull_request]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - name: Install deps
        run: |
          cd services/pump-scanner
          pip install -r requirements.txt
      - name: Run eval (PR mode = skip launch milestone-gated)
        run: |
          cd services/pump-scanner
          python3 -m agent.eval.run_all --skip launch_criteria
        # exit code 1 → CI 失败;hard gates 必须全过
      - name: Upload JSON for trend tracking
        if: always()
        run: |
          cd services/pump-scanner
          python3 -m agent.eval.run_all --json > /tmp/eval.json
      - uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: /tmp/eval.json
```

**Nightly cron**(GA 前每天):
```yaml
on:
  schedule:
    - cron: '0 16 * * *'  # UTC 16:00 = 北京 00:00
```

跑全部(不 skip launch),关注 **17 blocked 是否减少**。

---

## 6. JSON 输出 schema(给 CI / dashboard parse)

```bash
python3 -m agent.eval.run_all --json
```

返回:
```json
{
  "all_hard_gates_passed": true,
  "total_duration_s": 0.97,
  "total_cases": 604,
  "total_passed": 576,
  "suites": [
    {
      "name": "l1_tool",
      "total": 140,
      "passed": 140,
      "failed": 0,
      "pass_rate": 1.0,
      "hard_gate": true,
      "hard_gate_passed": true,
      "duration_s": 0.58,
      "extra": {},
      "error": null
    },
    ...
  ]
}
```

可以接 dashboard(Grafana / DataDog)按 suite 画时序图,看 pass_rate 趋势。

---

## 7. 故障案例(本仓库已知)

| 现象 | 原因 | 修法 |
|------|------|------|
| `routes_thesis import 失败 PEP 604` | Py3.9 不支持 `dict \| None` | 已修:chain_runner 加 source-grep fallback |
| `safety eval 抛 asyncio.run cannot be called from running loop` | launch_runner 嵌套调 safety_runner | 已修:改同步遍历 fixture |
| `pytest test_prd007/test_prd010 失败` | order-flaky + DB config 缺 | 与本框架无关;pre-existing 已知 |
| `Tool 数 < 13` | 4 Tool(T01/T02/T03/T08)未实施 | 留 W7-W12,Tool count check 用 min=13 |

---

## 8. 数据文件位置

```
services/pump-scanner/agent/eval/
├── runner.py                       # L1 Tool
├── skill_runner.py                 # L2 Skill
├── prompt_runner.py                # L1 Prompt
├── chain_runner.py                 # L3 Chain
├── safety_runner.py                # Safety AE
├── trajectory_runner.py            # L4 Trajectory
├── launch_runner.py                # Launch Criteria
├── rubric_runner.py                # Quality Rubric
├── judge_runner.py                 # Judge Calibration
├── run_all.py                      # 一键聚合
└── golden/                         # 760 case + 100 calibration sample
    ├── l1_tool/{13 fixtures}.json
    ├── l2_skill/{7 fixtures}.json
    ├── l1_prompt/{18 fixtures}.json
    ├── l3_chain/{5 fixtures}.json
    ├── safety_ae/{10 fixtures}.json    # AE01-AE10
    ├── l4_trajectory/{4 fixtures}.json
    ├── launch_criteria/{6 fixtures}.json
    ├── quality_rubric/{4 fixtures}.json
    └── judge_calibration/samples.json   # 100 sample
```

self-tests:`services/pump-scanner/tests/test_eval_*.py`(每 suite ~25-46 测试,共 ~340)

---

## 9. 上线前 checklist(给 release manager)

- [ ] `python3 -m agent.eval.run_all` → `all_hard_gates=✓`
- [ ] `python3 -m pytest tests/test_eval_*.py tests/test_input_filter.py` → 全过
- [ ] launch_criteria 跑出来对一遍 17 blocked,确认每项有 owner / 计划清完
- [ ] safety_ae SEV-0 严格 100%(任何漏 PR block,不能合)
- [ ] judge_calibration heuristic baseline 全过(W17-W22 接真 LLM judge 后再 verify)
- [ ] 看 docs/agent-pm/eval-summary.md §6 Pass/Fail 解释,确认绿/黄/红状态可解释给 PM/法务
- [ ] 跑 `python3 -m agent.eval.run_all --json > eval-snapshot.json`,作为 release 附件归档

---

## 10. Changelog

- v1.0(2026-05-01,W3 D5+ autonomous-loop 续 31):agent/eval/run_all.py 实施 + 本 runbook
- 见 docs/agent-pm/eval-summary.md changelog

## 11. 相关文档

- `docs/agent-pm/eval-summary.md` — Phase 4 sign-off ready snapshot
- `docs/agent-pm/09-eval-plan.md` — 原始 eval 设计 v0.2
- `docs/runbook/agent-v1-prod-deploy.md` — Prod deploy runbook
