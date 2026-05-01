"""
Tools — 17 个原子 Tool(JSON Schema + idempotent + 无 LLM 成本)
引用 docs/agent-pm/05-tool-catalog.md §4
引用 docs/agent-pm/17-tech-plan.md Phase 1

17 个 Tool 清单:
  查询(5):  T01 query_market / T02 query_holders / T03 query_onchain_activity
            T04 recall_memory / T10 get_paper_performance
  CRUD(4): T05 list_strategies / T06 update_strategy_status / T11 approve_rule / T12 save_strategy
  执行(3): T07 run_paper_trade / T08 execute_swap / T09 create_approval_request
  计算(3): T14 calc_technical_indicators / T15 calc_risk_metrics / T16 run_backtest
  通知(2): T13 send_push_notification / T17 calc_position_size

强约束:
  - Tool 不调 LLM(否则它该是 Skill)
  - Tool 不调 Skill(Tool 是叶子)
  - Tool 必须幂等(除非显式标 non_idempotent)
  - 所有 Tool 严格 JSON Schema 校验
"""
