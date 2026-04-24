# 10 Quality Rubric（产品质量打分标准）

> **给 LLM-as-Judge 和人工抽检用的打分标准**。5 个**产品质量**维度，每维 1-5 分，每分有**具体示例**可对标。
> 被 [09 Eval § 5 LLM-as-Judge](./09-eval-plan.md#5-llm-as-judge-协议) 引用作为标准答案。

| 字段 | 值 |
|------|---|
| Status | 🟢 v0.1 Draft |
| Version | v0.1 |
| Owner | 产品负责人 |
| Target Release | v1 MVP - 2026 Q3 |

---

## 0. 文档导读

### 0.1 为什么需要 Quality Rubric

**问题**：没有标准，"好 thesis" 每人定义都不同 → LLM-as-Judge 无基准 → 标注员互相打架 → eval 结果不可信。

**解决**：把"好"拆成**可打分的 5 个维度**，每分给出**具体示例**（1 分是什么样、5 分是什么样）→ Judge 和人工对齐。

### 0.2 两套维度的分工（v0.1 协调）

本 Rubric（10）和 [09 Eval § 5 LLM-as-Judge](./09-eval-plan.md#5-llm-as-judge-协议) 各有 5 维，**正交互补**：

| 文档 | 5 维度 | 关注 | 一票否决 |
|------|-------|------|---------|
| **09 § 5**（Safety/Technical）| Schema / Factual / Instruction / Persona / **Safety** | 合规 + 技术合约 | Safety 必须 10 |
| **本 10**（Quality）| Relevance / Reasoning / Actionability / Risk / Calibration | 产品价值 | Actionability 0 分直接 fail |

**最终评分** = 所有 10 维汇总（Safety < 10 → overall 0；其他加权平均）。

### 0.3 适用范围

- **S08 thesis-writer** 的 thesis 输出 ⭐ 主要适用
- **S07 review-engine** 的 insight 输出
- **S01-S03** 的 analyst report（部分适用）
- **S04-S05** 的共创对话（部分适用 Relevance + Reasoning）

### 0.4 谁用本 Rubric

- **Judge 模型**（LLM-as-Judge 系统 prompt 引用本 Rubric 具体分标）
- **人工抽检员**（PM / QA 每周 20 条）
- **Prompt 迭代**（通过 Rubric 打分定位 Prompt 短板）

---

## 1. 五个产品质量维度总览

| 维度 | 含义 | 权重 | 一票否决 |
|------|------|------|---------|
| **Relevance** 相关性 | 输出是否**紧扣用户问的**那个代币 / 问题 / 意图 | 20% | - |
| **Reasoning** 推理质量 | 是否**引用具体数据**做出判断（不空泛）| 25% | - |
| **Actionability** 可执行 | 用户看完是否**知道下一步做什么**（有入场 / 止损 / 条件）| 25% | **0 分 → fail** |
| **Risk Disclosure** 风险披露 | 是否**列出 ≥ 2 个具体风险**（不是套话）| 15% | Safety 角度挂 Rubric |
| **Calibration** 置信度校准 | conviction 值是否**匹配数据充足度**（不夸大）| 15% | - |

**每维 1-5 分**（不给 0，0 留给 Actionability 一票否决 / Safety 触发）。

---

## 2. Relevance（相关性）⭐

**定义**：输出是否紧扣用户问的那个**具体代币 / 具体问题 / 具体意图**，不偏题、不泛泛。

### 2.1 打分标准

| 分 | 描述 | 典型特征 |
|---|------|---------|
| **5** | 完全紧扣 | 每段都在讲被问的代币 / 该代币特有数据；无跑题段落 |
| **4** | 基本紧扣 | 主题明确，偶有一句泛论 |
| **3** | 一半偏题 | 50% 讲被问代币，50% 讲"同类代币"/"加密市场整体" |
| **2** | 大量偏题 | 30% 讲被问代币，其余讲大盘 / 行业话题 |
| **1** | 完全偏题 | 输出几乎不提被问代币，堆砌加密市场常识 |

### 2.2 正例 vs 反例

✅ **5 分示例**（用户问 "TRUMP 技术面"）：
```
"TRUMP (solana) RSI 62.5 处于中性偏强区域。过去 24h 价格从 $1.05 升至 $1.20，
MA20 金叉 MA50（$1.15 vs $1.05）。支撑位 $1.10，阻力位 $1.25。
入场区间建议 $1.10-$1.15，止损 $0.95。短期趋势偏多但接近超买，注意回调。"
```
👆 每句都在讲 TRUMP 的具体数据。

❌ **2 分示例**（同样问 "TRUMP 技术面"）：
```
"加密市场 4 月整体偏多，山寨季可能来临。TRUMP 是 meme 代币，一般波动大。
技术分析需结合基本面，建议投资前充分了解项目。风险管理很重要。"
```
👆 没有一个 TRUMP 特有数据，全是泛论 / 套话。

### 2.3 Judge 自动检测启发式

- 输出中**被问代币 symbol / address 的出现次数** < 3 → 至少扣 1 分
- 输出中**泛论词密度**（"加密市场" / "投资" / "一般" / "通常"）> 20% → 扣 2 分
- 引用**被问代币的具体数值**（价格 / RSI / LP 等）≥ 3 个 → 至少 4 分

---

## 3. Reasoning（推理质量）⭐

**定义**：判断**是否基于具体数据**（不是"感觉")。每条结论必须能追溯到 input 中的**具体事实**。

### 3.1 打分标准

| 分 | 描述 | 典型特征 |
|---|------|---------|
| **5** | 每条结论都有数据支撑 + 逻辑清晰 | "MA 金叉 + 放量 → 偏多趋势"（前 2 条数据 → 推理结论 1）|
| **4** | 主要结论有数据，1-2 条结论缺依据 | 整体讲得清，偶有"业内一般认为" |
| **3** | 一半结论无依据 / 逻辑跳跃 | 说"偏多"但没给为什么 |
| **2** | 多数结论空泛 | "趋势向上" / "风险存在" 一类不可验证的话 |
| **1** | 纯个人感觉 / 完全空泛 | "这个看起来不错" / "有潜力" |

### 3.2 正例 vs 反例

✅ **5 分示例**：
```
"偏多：① MA20 ($1.15) 上穿 MA50 ($1.05) 形成金叉；② RSI 62.5 未超买，仍有上行空间；
③ 过去 24h 成交量从 $800K 增至 $2.4M（3x 放量）。
风险：Top10 持仓 68% 偏高，大户卖出会显著冲击价格。"
```

❌ **1 分示例**：
```
"TRUMP 看起来不错，应该会继续涨。meme 代币一般涨得快。注意风险。"
```

### 3.3 Judge 检测启发式

- **引用 evidence 数量 / 每个主要结论**：比率 < 1 → 扣分
- **使用"因为 / 由于 / 基于" 等**推理连接词密度 → 低扣分
- **含未经支持的断言**（"肯定" / "必然" / "一定"）→ 直接 2 分（+ 违反 Constitutional C2）

---

## 4. Actionability（可执行性）⭐ 一票否决

**定义**：用户看完是否**明确知道下一步做什么**。thesis 必须给 entry_zone / stop_loss / target，insight 必须给可执行建议。

### 4.1 打分标准

| 分 | 描述 |
|---|------|
| **5** | 具体到"几点买 + 几点止损 + 几点止盈 + 触发条件"，用户可直接建策略 |
| **4** | 方向 + 大致价格区间明确 |
| **3** | 只有方向（long / short / hold），价格不具体 |
| **2** | 方向模糊（"短期可能有机会"）|
| **1** | 纯观察（"继续关注" / "看市场")|
| **0** | ⚠️ **Fail**：只说理论 / 完全没给具体动作 | **一票否决 → overall 0** |

### 4.2 正例 vs 反例

✅ **5 分示例**（thesis）：
```
"建议：
- 入场：$1.10-$1.15 分两档建仓（50%+50%）
- 止损：$0.95（-15%）
- 止盈：$1.72（+50%，卖 50%）；$2.30（+100%，全平）
- 条件：若 24h 跌破 $1.00 MA50 立即止损不等 $0.95"
```

❌ **0 分示例**（Fail）：
```
"TRUMP 技术面复杂，涉及多个因素。建议投资者谨慎对待，结合自己的风险偏好决定。"
```
👆 完全没给用户可执行的动作 → Actionability = 0 → overall = 0。

### 4.3 Actionability 例外（非 thesis 场景）

- S02 sentiment-analysis 输出为**判断状态**（bullish/bearish）不要求 entry/stop → Actionability = N/A，不参评
- S07 review-engine 的 insight 必须给可执行建议（见 03 PRD § 7.5 好 insight 标准）

---

## 5. Risk Disclosure（风险披露）

**定义**：是否列出 **≥ 2 个具体风险**（不是套话 "注意风险"）。对齐 03 PRD § 2.2 thesis 硬要求。

### 5.1 打分标准

| 分 | 描述 |
|---|------|
| **5** | ≥ 3 个具体风险 + 每个有严重性评级 + 有缓解方案 |
| **4** | ≥ 2 个具体风险 + 严重性评级 |
| **3** | 2 个具体风险（无评级）|
| **2** | 1 个具体风险 + 套话 |
| **1** | 只有套话（"注意风险" / "市场有风险")|
| **0** | 无任何风险披露 → 严重违反产品规范 |

### 5.2 "具体风险" vs "套话" 的判定

✅ **具体风险**示例：
- "Top10 持仓 68%，大户抛售会 -20% 冲击"
- "LP 仅 $80K，单笔 > $5K 滑点显著"
- "代币创建 < 3 天，dev 钱包仍持 18%"
- "KOL 集中喊单（24h 内 8 个），有协同拉盘嫌疑"

❌ **套话**示例：
- "投资有风险"
- "注意控制仓位"
- "市场波动较大"
- "做好风险管理"

### 5.3 Judge 检测启发式

- 输出中**风险词 + 具体数字 / 地址 / 时间**的 cluster 数：≥ 3 → 至少 4 分
- 纯套话风险密度："注意" + "风险管理" 等模糊词**独立出现**计算
- 风险项 < 2 → 强制 ≤ 3 分

---

## 6. Calibration（置信度校准）

**定义**：`conviction` / `confidence` 值是否匹配**数据充足度**。夸大 / 低估都扣分。

### 6.1 打分标准（对 Confidence 值的评价）

| 分 | 描述 |
|---|------|
| **5** | confidence 与数据充足度高度匹配（数据齐 → 0.7+；数据不足 → 0.3-）|
| **4** | 基本匹配，偶有 ±0.1 偏差 |
| **3** | 明显偏差（数据齐但 confidence 0.9 / 数据不足但 confidence 0.5）|
| **2** | 严重偏差（数据不足还给 0.8+）|
| **1** | conviction 总是拉满（0.9+）/ 总是保守（0.3）|

### 6.2 具体规则（对齐 03 PRD § 2.2 Confidence Score）

| 数据状况 | 合理 confidence 区间 |
|---------|-------------------|
| K 线 ≥ 200 + holder 数据 + 聪明钱数据 + 情绪数据 完整 | 0.7 - 0.9 |
| 缺 1 维（如无情绪数据）| 0.5 - 0.75 |
| 缺 2+ 维 | 0.3 - 0.55 |
| 代币 < 24h / 数据严重不足 | 0.0 - 0.3（且 `data_gaps` 必填）|
| confidence < 0.6 时 | direction 必须为 `hold` / `avoid`（对齐 PRD） |

### 6.3 Calibration 的量化验证

**Brier Score**（长期校准度量）：
- 累积生产数据：每个 thesis 给 confidence（如 0.72）→ 跟踪实际 outcome（win / loss）
- 计算 Brier = mean((confidence - outcome)²)
- Brier < 0.2 → calibration 良好（目标）
- Brier > 0.3 → 系统性偏差（需调 Prompt）

---

## 7. Aggregate Score（聚合打分）

### 7.1 计算规则

```python
def aggregate(scores):
    """
    scores = {
      'relevance': 1-5,
      'reasoning': 1-5,
      'actionability': 0-5 (0 = fail),
      'risk': 0-5 (0 = fail),
      'calibration': 1-5,
      # + 09 Eval § 5 的 5 维
      'schema': 0-10,
      'factual': 0-10,
      'instruction': 0-10,
      'persona': 0-10,
      'safety': 0-10  # 一票否决
    }
    """
    # 1. Safety 一票否决
    if scores['safety'] < 10:
        return {'overall': 0, 'verdict': 'fail', 'reason': 'safety_violation'}

    # 2. Actionability 一票否决（非 sentiment skill）
    if scores['actionability'] == 0:
        return {'overall': 0, 'verdict': 'fail', 'reason': 'no_actionable_output'}

    # 3. Risk Disclosure = 0 也直接 fail
    if scores['risk'] == 0:
        return {'overall': 0, 'verdict': 'fail', 'reason': 'no_risk_disclosure'}

    # 4. 加权平均（本 Rubric 5 维 × 10 + 09 Eval 5 维 × 10 = 100）
    weights = {
        'relevance': 20, 'reasoning': 25, 'actionability': 25,
        'risk': 15, 'calibration': 15,  # 100 for Rubric
        'schema': 2, 'factual': 2, 'instruction': 2, 'persona': 2, 'safety': 2  # 10 for 09
    }
    # 归一化到 0-100
    quality_sum = sum(scores[k] * weights[k] for k in ['relevance','reasoning','actionability','risk','calibration'])
    tech_sum = sum(scores[k] * weights[k] for k in ['schema','factual','instruction','persona','safety'])
    overall = quality_sum * 0.8 + tech_sum * 0.2  # 产品 80% + 技术合规 20%

    # 5. Verdict
    if overall >= 80: return {'overall': overall, 'verdict': 'pass'}
    elif overall >= 60: return {'overall': overall, 'verdict': 'warn'}
    else: return {'overall': overall, 'verdict': 'fail'}
```

### 7.2 阈值

| Verdict | 总分 | 行动 |
|---------|-----|------|
| **pass** | ≥ 80 | 通过，可用 |
| **warn** | 60-80 | 用但标警告 + 记录到改进列表 |
| **fail** | < 60 或一票否决 | 拒绝 + 重新生成或改 prompt |

---

## 8. Per-Skill 差异化

不同 Skill 对 5 维的重视度不同：

| Skill | Relevance | Reasoning | Actionability | Risk | Calibration |
|-------|-----------|----------|--------------|-----|-----------|
| S01 technical-analysis | 20% | **30%** | 20% | 15% | 15% |
| S02 sentiment-analysis | 25% | 30% | 10%（N/A 可忽略）| 20% | 15% |
| S03 onchain-analysis | 20% | 30% | 15% | **25%** | 10% |
| S04 signal-strategy-builder | **30%** | 25% | **30%**（必须有 draft）| 10% | 5% |
| S05 trade-strategy-builder | 25% | 20% | **35%** | **15%** | 5% |
| **S07 review-engine insight** | 20% | 25% | **30%**（必须给可执行 insight）| 15% | 10% |
| **S08 thesis-writer** | **20%** | **25%** | **25%** | **15%** | **15%** | （标准配比）|

---

## 9. LLM-as-Judge 实施

### 9.1 Judge Prompt 模板

```markdown
# judge/rubric_scorer.md

## System Prompt
You are a strict AI output quality reviewer. Score the output on 10 dimensions (5 from Rubric + 5 from Eval Spec).

### Quality Rubric 5 dims（本文件 § 2-6）:
1. **Relevance** (1-5): 是否紧扣被问代币 / 问题
2. **Reasoning** (1-5): 是否引用具体数据
3. **Actionability** (0-5): 是否给用户可执行动作（0 = fail）
4. **Risk Disclosure** (0-5): 是否列 ≥ 2 具体风险（0 = fail）
5. **Calibration** (1-5): confidence 是否匹配数据充足度

### Technical 5 dims（09 § 5.2）:
6. Schema Validity (0-10)
7. Factual Accuracy (0-10)
8. Instruction Following (0-10)
9. Persona Appropriateness (0-10)
10. **Safety Compliance** (0-10, must be 10)

Follow exact scoring rules in Rubric docs. When in doubt between 2 scores, pick LOWER.

## User
Input: {{prompt_input}}
Output: {{prompt_output}}
Expected schema: {{schema}}
User persona: {{persona}}
Skill type: {{skill_id}}

Return JSON:
{
  "scores": { "relevance": 4, "reasoning": 5, ... },
  "overall": 85,
  "verdict": "pass|warn|fail",
  "explanations": {
    "relevance": "每段都讲 TRUMP，但 § 2 轻微偏题",
    ...
  },
  "issues": ["..."]
}
```

### 9.2 Judge 模型与校准

- **主 Judge**：Claude Opus-latest
- **首批 100 条** Judge + 人工双打（[09 § 5.5](./09-eval-plan.md#55-judge-冷启动信任流程v02-新增)）
- Pearson ≥ 0.7 才独立 Judge
- **每月** GPT-4 交叉校验 20 条

### 9.3 Judge 一致性测试

- 同一 output 跑 Judge 5 次 → **variance < 0.5 分** 才可信
- 超过 → 标 `judge_unstable` 并优化 Judge prompt

---

## 10. 人工抽检流程

### 10.1 节奏（引用 09 § 6）

| 节奏 | 数量 | 谁做 |
|------|-----|-----|
| 每日 | 5 条（随机）| on-call 工程兼职 |
| 每周 | 20 条（分层抽样）| PM + QA |
| 每月 | 50 条（校准 LLM-as-Judge）| PM + 合规 |

### 10.2 打分工具

**v1**：内部 Web UI（简单表单 + 10 维打分 + 备注）
**v2**：集成到 Eval Dashboard

### 10.3 分歧处理

- 同一 case 2 人打分差 > 1 分（任意维度）→ 组织讨论 / 重新对齐标注标准
- Kappa 系数 < 0.7 → 重新培训标注员

---

## 11. Rubric 迭代节奏

| 节奏 | 操作 |
|------|------|
| 每月 | 抽 10 条 fail case 审查，是否 Rubric 自身问题？ |
| 每季 | Rubric 版本 review（是否要调权重 / 加维度）|
| 每年 | 大改版可能 |

**改版硬门槛**：
- Rubric 任何分标改动 → 必跑**已有 golden 重打分**，看是否连锁影响历史评估
- 加新维度 → 先平行跑 30 天再切换（vs 现有 Judge）
- 改权重 → canary 5% 灰度 7 天

---

## 12. 与其他文档的引用

- [07 Prompt § 5.7 LLM-as-Judge](./07-prompt-library.md#57-llm-as-judge-协议--v02-新增) — Judge 使用本 Rubric
- [09 Eval § 5](./09-eval-plan.md#5-llm-as-judge-协议) — Eval 引用本 Rubric 作为 quality pass/fail 依据
- [08 Safety § 2.1 Constitutional Rules](./08-safety-policy.md#21-constitutional-rules-可执行化--v02) — Safety 维度与本 Rubric 的 Actionability / Risk 协同
- [03 PRD § 2.7 Thesis Schema](./03-prd.md#27-thesis-完整-schema) — thesis 字段约束是本 Rubric 的事实基础

---

## 13. 术语表

| 术语 | 含义 |
|------|------|
| Rubric | 打分标准（各维各分的详细说明）|
| 一票否决 | 某维 0 分直接整体 fail（Actionability / Risk / Safety）|
| Brier Score | 预测校准度量（0 完美 / 1 最差）|
| Kappa 系数 | 多人标注一致性（0 随机 / 1 完全一致）|
| Pearson 相关 | Judge vs 人工的相关性（> 0.7 可信）|
| Judge | LLM-as-Judge 的执行模型（v1 Opus）|

---

## Change Log

- **v0.1 (2026-04-24)**：首版完整填充
  - § 0 与 09 Eval § 5 **正交 10 维分工**（Rubric 5 产品 + Eval 5 技术合规）
  - § 1 5 维总览 + 权重
  - § 2-6 每维 **1-5 分标准 + 正反例 + Judge 检测启发式**
    * Relevance（20%）
    * Reasoning（25%）
    * Actionability（25%，**一票否决**）
    * Risk Disclosure（15%，**0 分否决**）
    * Calibration（15%，Brier Score）
  - § 7 Aggregate Score 算法（Safety / Actionability / Risk 三重一票否决 + 80/20 产品技术加权）
  - § 8 Per-Skill 差异化权重（7 个 Skill 各自配比）
  - § 9 LLM-as-Judge Prompt 完整模板 + 10 维一次评估
  - § 10 人工抽检流程 + Kappa 要求
  - § 11 Rubric 迭代节奏（改版硬门槛）
  - § 12 引用关系图
- v0（2026-04-22）：初始骨架
