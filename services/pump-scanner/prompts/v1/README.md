# Prompt Library v1

引用 [`docs/agent-pm/07-prompt-library.md`](../../../docs/agent-pm/07-prompt-library.md)
引用 [`docs/agent-pm/17-tech-plan.md`](../../../docs/agent-pm/17-tech-plan.md) Phase 2

## 目录约定

```
prompts/v1/
├── P01_chat_clarify/
│   ├── prompt.md          # System Prompt 主体
│   ├── examples.md        # ≥3 条 few-shot(含 persona 各分支)
│   └── frontmatter.yaml   # model / temperature / cache_breakpoints / token_limit
├── P02_thesis_writer/
├── P03_technical_analyst/
├── P04_sentiment_analyst/
├── P05_onchain_analyst/
├── P06_debate_bull/
├── P07_debate_bear/
├── P08_debate_facilitator/
├── P09_decision_agent/
├── P10_risk_reviewer/
├── P11_signal_strategy_builder/
├── P12_trade_strategy_builder/
├── P13_review_engine_daily/
├── P14_review_engine_weekly/
├── P15_review_engine_monthly/
├── P16_reflection/
├── P17_regime_explainer/
└── P18_persona_translator/
```

## frontmatter.yaml schema

```yaml
prompt_id: P02
version: v1.0
model: claude-opus-latest          # opus / sonnet / haiku
temperature: 0.3                    # 0-0.7 梯度
max_input_tokens: 8000
max_output_tokens: 1500
cache_breakpoints:                  # system prompt 末尾硬加 cache marker
  - position: end_of_system
status: draft                       # draft / canary / beta / ga / retired
rollout_pct: 0
owner: pm-lead
description: |
  强关键词描述(用于 progressive disclosure matching)
```

## 灰度流程

| 阶段 | rollout_pct | 持续时间 | 通过门槛 |
|---|---|---|---|
| draft   | 0   | 任意 | 内部测试 |
| canary  | 5   | 48h  | Eval ≥ 90% / Cost in budget |
| beta    | 25  | 7d   | NPS ≥ 30 / Safety AE 零漏 |
| ga      | 100 | -    | 全量 |
| retired | 0   | -    | 旧版本下线 |

## A/B 分桶

`hash(device_id) % 100` < `rollout_pct` → 用该版本(同 device 始终命中同桶)

## Prompt Cache 命中率目标 > 80%

System Prompt 末尾加 cache_control marker → 减 30-40% input cost($300-500/月节省)

## 状态

🔴 v0.1 骨架(W7-W12 实施 18 个 P 完整内容)
