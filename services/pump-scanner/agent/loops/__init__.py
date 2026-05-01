"""
Loops — 5 个核心 Loop 编排
引用 docs/agent-pm/04-agent-spec.md
引用 docs/agent-pm/17-tech-plan.md Phase 2

5 个 Loop(W7-W12 实施):
  scout_loop.py      EventBus 触发(pump_snapshot/hot_coin_update/kol_signal)→ 规则引擎(0 LLM)→ strategy.triggered
  thesis_loop.py     用户 chat OR strategy.triggered → L1 规则 / L2 单 Opus / L3 3 Haiku 并行 + 5 Sonnet 辩论
  notify_loop.py     strategy.triggered → RiskManager → T17 仓位 → paper/notify/auto 分支 → T13 推送
  reflect_loop.py    cron 20:00 / 10 笔闭仓 / 单笔<-25% → S07 review-engine → 规则提议
  chat_loop.py       用户 message → S04/S05 lazy 加载 → 对话状态机
"""
