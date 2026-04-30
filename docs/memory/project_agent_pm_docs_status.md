---
name: docs/agent-pm 设计文档状态
description: docs/agent-pm/00-16 系列是 Agent v1 优化设计产出物,从未落地,讨论时不要当成 baseline
type: project
originSessionId: 3b12747c-a69c-445e-bdcc-c755d41a1638
---
`docs/agent-pm/00-16.md`(共 17 篇 + README,2026-04 产出)是 Agent v1 优化的完整 PM 设计文档体系,**从未实施落地**,纯产出物。本地仓库领先 origin 6 个 docs commit 都是这套文档(消息:`docs(agent-pm): 12-16 完整填充 / 10-11 v0.2 修订`)。

**Why:** 2026-04 当时只为产出 PM 设计思考,**未列入开发计划**。用户在 2026-04-30 会话中明确纠正:"这个文档从来没有实现过,当时就是为了产出优化文档"。

**How to apply:**
- 讨论 Agent 现状时,**不要把 `docs/agent-pm/`(00-16)的 Skill/Tool/Memory/Prompt/Safety/Eval 设计当成已实现的 baseline**
- 实际线上 Agent 能力 = `services/pump-scanner/agent/` 真实代码(L1/L2/L3 编排 + 3 分析师 Haiku + Bull/Bear 辩论 + 4 层记忆 + 15 项风控 + DexRouter + RegimeDetector,详见 architecture.md 和 sessions-log)
- 不要再做"文档 §8 Gap vs 代码"的对照分析 — 文档自己 §8 写的"现状"就是事实
- **注意区分**两套不同的 docs:
  - `docs/agent-pm/00-16.md` = PM 设计文档系列,**未实施**(本条目)
  - `docs/agent-pm/prd/PRD-001~010/` = 落地实施 PRD,**部分已开发**(见 MEMORY.md 中 PRD 测试通过记录)

**完整文件清单**(17 篇):
- 00 data-sources / 01 product-vision / 02 user-persona-journey / 03 prd / 04 agent-spec
- 05 tool-catalog(7 Skills + 17 Tools 设计)/ 06 memory-spec / 07 prompt-library / 08 safety-policy
- 09 eval-plan / 10 quality-rubric / 11 launch-criteria-hitl / 12 incident-response-sop
- 13 cost-budget / 14 red-team-playbook / 15 observability-tracing / 16 trajectory-eval
- README.md

## 更新历史

- **2026-04-30**: 新增 `17-tech-plan.md`(v1 技术落地方案,16-20 周,完整范围 paper+notify+auto+真金+托管,配置 A Eval 1660 golden + 62 项 Launch Criteria 100%)落到 `docs/agent-pm/17-tech-plan.md`,README 矩阵新增 **L6 工程落地** 区。**仍未实施,只是设计产出**。本地 `~/.claude/plans/agent-app-tab-agent-lively-phoenix.md` 是同一份内容(plan 模式产物)。
