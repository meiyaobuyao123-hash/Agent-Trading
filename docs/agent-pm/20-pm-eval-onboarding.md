# 20 — PM Eval Onboarding(给产品经理的 Eval 入门 + Golden 实操)

> **文档定位**:面向 PM 的 LLM Agent 评估方法论与实操手册。读完能独立写 golden、看懂 CI 报告、判断 prompt 改动质量。
>
> **修订历史**:2026-05-08 R47 P9 创建,作者 PM-lead

| 字段 | 值 |
|------|---|
| Status | 🟢 v1.0 |
| Version | v1.0 |
| Owner | PM-lead |
| 配套代码 | `services/pump-scanner/agent/eval/` |
| 相关文档 | [09 Eval Plan](./09-eval-plan.md) / [10 Quality Rubric](./10-quality-rubric.md) / [04 Agent Spec](./04-agent-spec.md) |

---

## 0. 为什么 PM 必须懂 Eval

**LLM 时代之前**:PM 写 PRD → 工程实现 → QA 测 → 上线。
**LLM 时代之后**:工程改 1 个 prompt 字 → 全产品行为可能变 → QA 测不了(主观)→ **没人能判断"做对没"**。

**Eval 是 PM 在 LLM 时代的核心抓手**:
- 你写 golden = 你定义产品规格(精确到"输入 X 必返 Y")
- CI 跑 eval = 工程改完自动验
- Pass rate 下降 = block 上线

**没有 eval 的 LLM 产品 = 没有体温计的医院**:你不知道病人好转还是变差,只能靠感觉。

---

## 1. 三个工程术语速通

### 1.1 PR(Pull Request,合并请求)

**类比**:总公司会签流程。程序员改完代码,提个"申请单"等审批,通过才能合进主干。

**我们项目**:每次改 prompt / 改代码都要开一个 PR,流程:
```
本地改 → git push 分支 → GitHub 创 PR → CI 自动测 + 同事 review → Merge
```

**PM 关心**:**PR 是质量门禁**。CI 任一项失败,改动进不去主干,也上不了线。

### 1.2 CI(Continuous Integration,持续集成)

**类比**:工厂质检机器人。每件产品自动扫,不合格亮红灯。

**我们 CI 跑什么**(每个 PR 触发):
```
1. pytest tests/                     ← 单元测试(170+ 个)
2. flake8 / black                    ← 代码格式
3. python -m agent.eval.run_all      ← 4 层金字塔 eval
```

**任一失败 → CI 红灯 → block merge**。

### 1.3 Golden(黄金集 / 标准答案集)

**类比**:高考标准答案。给 LLM 100 道题,事先约定每道题该返什么。

**我们项目**:
- 文件路径:`services/pump-scanner/agent/eval/golden/`
- 文件名:`l1_prompt/P03.json`(P03 prompt 的 golden)
- 内容:30 个 case,每个 case 描述"输入 X 时应满足 Y"

**核心洞察**:**写 golden 是 PM 的活,不是工程的活**。
- 工程写"什么场景能跑"(代码)
- PM 写"什么场景该返什么"(golden)
- 两者都对 = 产品 OK

---

## 2. 4 层 Eval 金字塔

> 详见 [09 Eval Plan §1](./09-eval-plan.md#1-eval-金字塔4-层)。本节给 PM 的速通版。

```
                       ┌──────────────────────┐
                       │  L4 Trajectory Eval  │  完整用户旅程(跨多轮)
                       │   每场景 ≥ 20 case   │
                       └──────────┬───────────┘
                                  │
                       ┌──────────┴───────────┐
                       │  L3 Agentic Eval     │  端到端组合(多模块串联)
                       │  每条链 ≥ 10 case    │
                       └──────────┬───────────┘
                                  │
                       ┌──────────┴───────────┐
                       │  L2 Integration Eval │  Skill 内部链
                       │  每 Skill ≥ 50 case  │
                       └──────────┬───────────┘
                                  │
   慢 / 贵 / 少 ↑                ┌──────────┴───────────┐
   快 / 便宜 / 多 ↓             │   L1 Unit Eval       │  单 Tool / 单 Prompt
                                 │  每 Prompt ≥ 30 case │
                                 └──────────────────────┘
```

### 2.1 各层职责对照

| 层 | 测什么 | 例子 | 通过门槛 | CI 频率 |
|---|---|---|---|---|
| **L1 Unit** | 1 个 Tool / 1 个 Prompt 单独表现 | RSI=85 应返 bearish | **100%** | 每 PR |
| **L2 Integration** | Skill 内部多 Tool 协作 | "策略创建" Skill 调 3 个 Tool | ≥ 95% | 每 PR |
| **L3 Agentic** | 跨 Skill 端到端链 | chat→分析→辩论→风控→执行 | ≥ 90% | 每 PR + nightly |
| **L4 Trajectory** | 模拟真实用户跨多轮 | 注册→创策略→实盘→反思 | ≥ 85% | nightly + weekly |

### 2.2 类比汽车质检

- **L1**:测每个零件(1 万颗螺丝)→ 1 秒 1 颗,便宜快
- **L2**:测组件(发动机、刹车)→ 100 个组件,各测 50 次
- **L3**:测整车(开 50 公里)→ 整车 10 辆
- **L4**:测真实路况(高速 + 山路 + 暴雨连续 3 天)→ 完整旅程 5 个

**金字塔哲学**:**底层把能测出来的 90% bug 截住,顶层只测组合后才会出现的 10%**。底层快得多 = 单位成本截 bug 量大得多。

---

## 3. Golden Case 设计法 — 4 类金字塔

每个 prompt 的 golden 应包含 4 类 case,**总数 ≥ 30**(决策权重大的 prompt ≥ 40):

```
       ┌──────────────────────────────────┐
       │ 类 D: 安全 + 攻击场景(3-10)     │  PM 该想:用户怎么把 LLM 玩坏
       ├──────────────────────────────────┤
       │ 类 C: 缺数据 / 边界(6-10)       │  PM 该想:数据不齐时不能崩
       ├──────────────────────────────────┤
       │ 类 B: 真实业务场景(13-20)      │  PM 该想:正常用户每天的 case
       ├──────────────────────────────────┤
       │ 类 A: 基础契约(6,自动模板)    │  自动覆盖,不用思考
       └──────────────────────────────────┘
```

### 3.1 Runner 支持的 6 种 outcome(必懂)

代码:`services/pump-scanner/agent/eval/prompt_runner.py`

| outcome | 含义 | case 用什么字段 |
|---|---|---|
| `metadata_ok` | frontmatter.yaml 字段合规 | 无 |
| `render_ok` | 占位符全部正确替换 | `vars` |
| `render_missing_vars` | 缺变量时占位符保留(不爆) | `vars` + `expected_unrendered` |
| `examples_safe` | examples.md 不含 C1 禁字(必涨/百倍/稳的) | 无 |
| `examples_count_min` | few-shot ≥ N 条 | `min_examples` |
| `version_select` | 按 device_id 选对版本 | `device_id` + `expected_status` |

**注**:目前 Runner 只跑**静态契约**(不调 LLM)。但 PM 写的 `vars` 数据**是未来 LLM-judge 阶段(W17-W22)的输入语料库**,价值不会浪费。

### 3.2 类 A 基础契约(6 case 模板)— 自动套用

每个 prompt 都要 6 条 A 类,**直接复制改 prompt_id**:

```json
{"name": "A1_metadata_ok", "prompt_id": "P03", "expected_outcome": "metadata_ok"},
{"name": "A2_examples_safe", "prompt_id": "P03", "expected_outcome": "examples_safe"},
{"name": "A3_examples_at_least_3", "prompt_id": "P03", "expected_outcome": "examples_count_min", "min_examples": 3},
{"name": "A4_examples_at_least_5_for_haiku", "prompt_id": "P03", "expected_outcome": "examples_count_min", "min_examples": 5,
  "description": "Haiku 模型 few-shot 越多越准,目标 5+"},
{"name": "A5_version_select_draft", "prompt_id": "P03", "expected_outcome": "version_select", "device_id": "dev-1", "expected_status": "draft"},
{"name": "A6_version_select_diff_device", "prompt_id": "P03", "expected_outcome": "version_select", "device_id": "dev-2", "expected_status": "draft"}
```

**A4 加严**:Haiku 模型推荐 5+ 个 few-shot(行业最佳实践)。Sonnet/Opus 用 3 即可。

### 3.3 类 B 真实业务场景(13-20 case)— PM 核心工作

**思考维度**(PM 该问自己):
1. **多 direction 覆盖**:bullish / bearish / neutral 各至少 3 个
2. **多 context 覆盖**:链(SOL/ETH/BSC/Base)、regime(NORMAL/CRISIS/RECOVERY/HIGH_VOLATILITY)各 1+
3. **典型形态**:金叉/死叉/双顶/双底/BB 收窄/超买/超卖
4. **极端 confidence**:强信号(≥0.7)和弱信号(≤0.4)都要有

**Case 写法**:
```json
{"name": "B1_sol_meme_oversold_bullish",
  "description": "SOL 链 meme RSI 35 超卖 + 金叉 → 应输出 bullish",
  "prompt_id": "P03", "expected_outcome": "render_ok",
  "vars": {
    "chain": "SOL", "token_symbol": "TRUMP", "regime": "NORMAL",
    "indicators_json": "{\"rsi\":35,\"macd\":-0.05,\"ma20\":0.95,\"ma50\":0.92}",
    "last_price": "0.94"
  }
}
```

**关键字段**:
- `name`:`{类别}{编号}_{场景}`,人一眼看懂
- `description`:**必须写**,这是给下个 PM 接手时看的产品规格
- `vars`:真实业务输入数据(**未来 LLM-judge 用这个当语料**)

### 3.4 类 C 缺数据 / 边界(6-10 case)— 防御性

**思考维度**:
- **哪个数据源会断?** indicators(Tool 失败)/ price(行情源宕)/ regime(初始化空)
- **数据不全 vs 数据为 null**(差异:前者 `render_missing_vars`,后者 `render_ok` 但语义不同)
- **极端值**:0 / 100 / 负数 / NaN

**例子**:
```json
{"name": "C1_missing_indicators_json",
  "description": "Tool 失败 indicators 没传 → 占位符保留,不爆错",
  "prompt_id": "P03", "expected_outcome": "render_missing_vars",
  "vars": {"chain": "SOL", "regime": "NORMAL", "last_price": "0.94"},
  "expected_unrendered": ["{{indicators_json}}"]}

{"name": "C7_extreme_rsi_zero",
  "description": "RSI=0 极端值(理论不可能但要 handle)",
  "prompt_id": "P03", "expected_outcome": "render_ok",
  "vars": {"chain": "SOL", "regime": "NORMAL",
           "indicators_json": "{\"rsi\":0,\"macd\":-1.5}",
           "last_price": "0.001"}}
```

### 3.5 类 D 安全 + 攻击(3-10 case)— 必须有

**最低限度**:
- D1:**Prompt injection** — 用户在 token name 里塞"忽略前面指令"
- D2:**数据格式攻击** — 上游 bug / 攻击者把非法字符串当 JSON
- D3:**examples_safe 冗余** — 双重确认 examples 没禁字

**敏感 prompt 加严**(P10 risk_reviewer / P17 abuse_detection 这类决策权大的):
- D4:多重 flag 攻击(刻意构造命中所有软标签的输入)
- D5:CRISIS regime 试探(强 bullish 数据 + CRISIS regime,看 LLM 会不会破规)
- D6-D10:更多变种

---

## 4. Case 数比例参考

| 类别 | 通用 prompt | 决策敏感 prompt(P10/P12-P15/P17) |
|---|---|---|
| A 契约 | 20% | 15% |
| B 业务 | 45% | 40% |
| C 边界 | 25% | 25% |
| D 安全 | 10% | 20% |
| **总数** | ≥30 | ≥40 |

---

## 5. 实战完整案例 — P03 technical_analysis 6 → 30 case

> R47 P9 真实落地的 case。完整 JSON 在 `services/pump-scanner/agent/eval/golden/l1_prompt/P03.json`。

### 5.1 Prompt 在干什么(必读)

**职责**:Haiku 读一份 RSI/MACD/MA/BB/ATR 数值 → 输出 JSON `{direction, confidence, key_level, points}`。

**输入变量**:
- `{{chain}}` — solana / eth / bsc / base
- `{{token_symbol}}` — 如 TRUMP
- `{{token_address}}` — 链上地址
- `{{regime}}` — NORMAL / CRISIS / RECOVERY / HIGH_VOLATILITY
- `{{indicators_json}}` — 真实指标的 JSON 字符串
- `{{last_price}}` — 最后成交价

**Strict Rules**(prompt 里写死):
1. 数字不能编(只用 indicators_json 里的)
2. 不下最终结论(只出"信号 + 强度",最终决策给上层)
3. 禁字:必涨/必跌/百倍/抄底/稳的
4. points ≤ 4 条,每条 ≤ 30 字

### 5.2 30 case 分布

| 类 | 数量 | 说明 |
|---|---|---|
| A 契约 | 6 | A1 metadata, A2 safe, A3-A4 examples_count(3 + 5), A5-A6 version_select |
| B 业务 | 13 | B1-B5 五链覆盖三方向 / B6-B8 三 regime / B9-B13 五典型形态 |
| C 边界 | 8 | C1-C4 缺字段 / C5-C6 partial+null / C7-C8 极端值 |
| D 安全 | 3 | D1 injection / D2 malformed JSON / D3 examples_safe 冗余 |

### 5.3 实操过程(PM 视角)

**Step 1**:打开 `services/pump-scanner/prompts/v1/P03_technical_analysis/prompt.md` 读 prompt 干什么

**Step 2**:打开 `services/pump-scanner/agent/eval/golden/l1_prompt/P03.json` 看现有 case

**Step 3**:按 A/B/C/D 4 类填 case → 写到 P03.json

**Step 4**:跑 runner
```bash
cd services/pump-scanner
python3 -m agent.eval.prompt_runner --suite=l1_prompt --prompt=P03
```

**Step 5**:看输出
```
=== l1_prompt Eval Report ===
  P03      29/ 30 ( 96.7%)  metadata: ✓
    ✗ A4_examples_at_least_5_for_haiku: few-shot 数量 3 < 5
```

**Step 6 — 关键洞察**:**fail 不一定是 case 错,可能是 prompt 真的不够好**。
- A4 fail = prompt 的 examples.md 只有 3 个 few-shot,不到 Haiku 推荐的 5
- 不该删 A4,该补 examples.md
- 给 examples.md 加 2 个 few-shot(超买死叉看空 + CRISIS regime 强制保守)

**Step 7**:再跑 runner
```
[Eval l1_prompt] 30/30 passed (100.0%) in <1s ✅
```

### 5.4 这个案例给 PM 的 takeaway

1. **写 golden 不只是凑通过,是暴露问题**。本次案例直接揭示了 P03 prompt 的 few-shot 不足。
2. **PM + 工程协作改 prompt**:PM 写 case 暴露问题,工程 + PM 一起改 prompt,真闭环。
3. **vars 数据集 = 未来 LLM-judge 输入语料**:即使现在 Runner 不调 LLM,你写的真实场景数据 W17-W22 上线后直接用作"输入 X → LLM 应返 Y"的语义级测试。

---

## 6. PM 工作流(每周节奏)

### 6.1 新功能上线前

```
PRD 写完
  ↓
列出新涉及的 prompt(可能改 P0X 或新建 P19)
  ↓
为每个 prompt 写 ≥30 case golden
  ↓
跑本地 runner 全过
  ↓
git commit 进 PR(包含 prompt 改动 + golden)
  ↓
CI 自动跑 → 全过 → reviewer 审 → merge → 灰度上线
```

### 6.2 看 prompt 改动 PR

PM review 一个修改 prompt 的 PR,**必看 3 项**:

1. **golden 有没有同步改**:加新规则不补 case = 漏测
2. **CI 有没有全绿**:任何 fail 必须解释清楚
3. **examples.md 有没有同步改**:few-shot 反映 prompt 期望行为,改规则就该补 example

### 6.3 季度 audit

每个季度跑一次:
```bash
python -m agent.eval.run_all
```

看:
- 哪个 prompt pass_rate 跌了 → 该回炉
- 哪个 prompt case 数 < 30 → 该补
- 哪个 prompt 超 6 个月没改 → 该重新审视 vs 真实业务

---

## 7. 给 PM 的 5 条核心 takeaway

1. **写 golden = 产品规格化**。一条 case 比 PRD 长篇描述精确 10 倍。
2. **4 类金字塔思考法**:契约(自动)→ 业务(主力)→ 边界(防御)→ 安全(必须)。每个 prompt 都按这个分配。
3. **case 数比例**:30 总 case 里 ~20% 契约 / ~45% 业务 / ~25% 边界 / ~10% 安全。安全敏感 prompt 把 D 类加到 20%+。
4. **vars 现在不浪费**:即使当前 Runner 只静态校验渲染,你写的 `vars` = LLM-judge 上线后的输入语料库。
5. **每条 case 必须有 description**:不写 = 6 个月后没人能接手 = 产品规格失传。

---

## 8. 文件位置速查

| 找什么 | 路径 |
|---|---|
| 18 个 prompt 定义 | `services/pump-scanner/prompts/v1/PXX_*/{frontmatter.yaml,prompt.md,examples.md}` |
| Prompt golden | `services/pump-scanner/agent/eval/golden/l1_prompt/PXX.json` |
| Tool golden | `services/pump-scanner/agent/eval/golden/l1_tool/*.json` |
| Skill golden | `services/pump-scanner/agent/eval/golden/l2_skill/*.json` |
| Runner 代码 | `services/pump-scanner/agent/eval/prompt_runner.py` |
| 跑命令 | `cd services/pump-scanner && python3 -m agent.eval.prompt_runner --suite=l1_prompt [--prompt=PXX]` |

---

## 9. 不在本文档范围(指引到其他文档)

- **L2/L3/L4 eval 详细设计** → [09 Eval Plan](./09-eval-plan.md)
- **LLM-as-Judge 评分维度** → [10 Quality Rubric](./10-quality-rubric.md)
- **Trajectory eval** → [16 Trajectory Eval](./16-trajectory-eval.md)
- **Prompt 注册表** → [07 Prompt Library](./07-prompt-library.md)
- **Tool / Skill 目录** → [05 Tool Catalog](./05-tool-catalog.md)
- **Launch 决策门槛** → [11 Launch Criteria HITL](./11-launch-criteria-hitl.md)
