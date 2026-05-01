"""
Skills — Anthropic SKILL.md + tool_use 形式的 Agent 能力封装
引用 docs/agent-pm/05-tool-catalog.md
引用 docs/agent-pm/17-tech-plan.md Phase 2

7 个 Skill(W7-W12 实施):
  S01 technical-analysis     (Always Loaded for Thesis Loop L3)
  S02 sentiment-analysis     (Always Loaded for Thesis Loop L3)
  S03 onchain-analysis       (Always Loaded for Thesis Loop L3)
  S04 signal-strategy-builder ⭐ (Lazy: Chat 提到 "建策略 / strategy" 触发)
  S05 trade-strategy-builder (Lazy: Chat 提到 "加交易 / auto / 执行")
  S07 review-engine          (Always Loaded for Reflect Loop)
  S08 thesis-writer 🆕       (Always Loaded for Thesis Loop;3 面合成)

结构:
  agent/skills/<skill-name>/
    SKILL.md          — frontmatter only(Anthropic Progressive Disclosure)
    prompt.md         — System Prompt + Few-shot
    examples.md       — Golden 示例
    schemas.py        — Input/Output Pydantic schema
    skill.py          — 入口函数 + tool 调用

状态:🔴 v0.1 占位(目录结构准备好,实施 W7-W12)
"""
