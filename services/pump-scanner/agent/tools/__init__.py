"""
Tools — 19 个原子 Tool(JSON Schema + idempotent + 无 LLM 成本)
引用 docs/agent-pm/05-tool-catalog.md §4
引用 docs/agent-pm/17-tech-plan.md Phase 1

19 个 Tool 清单:
  查询(7):  T01 query_market / T02 query_holders / T03 query_onchain_activity
            T04 recall_memory / T10 get_paper_performance / T18 query_top_movers
            T19 query_pump_tokens (R68 加,pump.fun 实时信号专属)
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

from .base import Tool, ToolMetadata, ToolResult, Permission, SideEffect

# R35: 17 Tool 全部实施(T01/T02/T03/T08 包装现有 OKX/Helius/trade_executor)
from .t01_query_market import QueryMarketTool
from .t02_query_holders import QueryHoldersTool
from .t03_query_onchain_activity import QueryOnchainActivityTool
from .t04_recall_memory import RecallMemoryTool
from .t05_list_strategies import ListStrategiesTool
from .t06_update_strategy_status import UpdateStrategyStatusTool
from .t07_run_paper_trade import RunPaperTradeTool
from .t09_create_approval_request import CreateApprovalRequestTool
from .t10_get_paper_performance import GetPaperPerformanceTool
from .t11_approve_rule import ApproveRuleTool
from .t12_save_strategy import SaveStrategyTool
from .t13_send_push_notification import SendPushNotificationTool
from .t14_calc_technical_indicators import CalcTechnicalIndicatorsTool
from .t15_calc_risk_metrics import CalcRiskMetricsTool
from .t16_run_backtest import RunBacktestTool
from .t17_calc_position_size import CalcPositionSizeTool
from .t08_execute_swap import ExecuteSwapTool
from .t18_query_top_movers import QueryTopMoversTool
from .t19_query_pump_tokens import QueryPumpTokensTool


def get_tool_registry() -> dict:
    """返回 {tool_name: Tool 实例} 注册表(R68 后:19/19 全实施 + T19 pump.fun 专属)。"""
    return {
        "query_market": QueryMarketTool(),
        "query_holders": QueryHoldersTool(),
        "query_onchain_activity": QueryOnchainActivityTool(),
        "execute_swap": ExecuteSwapTool(),
        "recall_memory": RecallMemoryTool(),
        "list_strategies": ListStrategiesTool(),
        "update_strategy_status": UpdateStrategyStatusTool(),
        "run_paper_trade": RunPaperTradeTool(),
        "create_approval_request": CreateApprovalRequestTool(),
        "get_paper_performance": GetPaperPerformanceTool(),
        "approve_rule": ApproveRuleTool(),
        "save_strategy": SaveStrategyTool(),
        "send_push_notification": SendPushNotificationTool(),
        "calc_technical_indicators": CalcTechnicalIndicatorsTool(),
        "calc_risk_metrics": CalcRiskMetricsTool(),
        "run_backtest": RunBacktestTool(),
        "calc_position_size": CalcPositionSizeTool(),
        "query_top_movers": QueryTopMoversTool(),
        "query_pump_tokens": QueryPumpTokensTool(),
    }


__all__ = [
    "Tool", "ToolMetadata", "ToolResult", "Permission", "SideEffect",
    "QueryMarketTool",
    "QueryHoldersTool",
    "QueryOnchainActivityTool",
    "ExecuteSwapTool",
    "RecallMemoryTool",
    "ListStrategiesTool",
    "UpdateStrategyStatusTool",
    "RunPaperTradeTool",
    "CreateApprovalRequestTool",
    "GetPaperPerformanceTool",
    "ApproveRuleTool",
    "SaveStrategyTool",
    "SendPushNotificationTool",
    "CalcTechnicalIndicatorsTool",
    "CalcRiskMetricsTool",
    "RunBacktestTool",
    "CalcPositionSizeTool",
    "QueryTopMoversTool",
    "QueryPumpTokensTool",
    "get_tool_registry",
]
