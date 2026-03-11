"""
Agent 交易系统核心模块

组件：
- schemas: Pydantic 数据模型（StrategySpec, ConditionNode, ActionSpec）
- rule_engine: 递归条件评估器（AND/OR 树）
- evaluator: 数据事件 → 规则匹配
- event_bus: asyncio.Queue 事件总线
- strategy_manager: 策略 CRUD + cooldown 管理
- llm_parser: Claude Sonnet Tool Use → JSON
- action_dispatcher: Alert 写入 + Push 通知
- monitor_job: 30s 轮询评估
"""
