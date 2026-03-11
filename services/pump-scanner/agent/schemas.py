"""
Agent 系统 Pydantic 模型

定义策略规范（StrategySpec）、条件节点（ConditionNode）、
动作规范（ActionSpec）等核心数据结构。

Python 3.9 兼容：使用 typing 模块。
"""
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, validator
from datetime import datetime


# ── 枚举类型 ──────────────────────────────────────────────────

class ConditionOperator(str, Enum):
    """逻辑运算符"""
    AND = "AND"
    OR = "OR"


class ComparisonOperator(str, Enum):
    """比较运算符"""
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="
    NEQ = "!="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"


class ActionType(str, Enum):
    """动作类型"""
    ALERT = "alert"
    PUSH = "push"
    WEBHOOK = "webhook"
    BUY = "buy"        # Phase 3
    SELL = "sell"       # Phase 3


class AlertSeverity(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class StrategyStatus(str, Enum):
    """策略状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class DataSourceType(str, Enum):
    """数据源类型"""
    PUMP_TOKENS = "pump_tokens"
    HOT_COINS = "hot_coins"
    KOL_MENTIONS = "kol_mentions"
    KOL_SIGNALS = "kol_signals"
    CUSTOM = "custom"


# ── 条件模型 ──────────────────────────────────────────────────

class ConditionRule(BaseModel):
    """单个条件规则"""
    data_source: str = Field(..., description="数据源名称")
    field: str = Field(..., description="字段名")
    operator: ComparisonOperator = Field(..., description="比较运算符")
    value: Any = Field(..., description="比较值")

    class Config:
        use_enum_values = True


class ConditionNode(BaseModel):
    """
    条件树节点（递归结构）

    支持 AND/OR 嵌套：
    {
        "operator": "AND",
        "rules": [
            {"data_source": "pump_tokens", "field": "bc_progress", "operator": ">", "value": 50},
            {
                "operator": "OR",
                "rules": [
                    {"data_source": "kol_mentions", "field": "mention_count_2h", "operator": ">=", "value": 3},
                    {"data_source": "hot_coins", "field": "score", "operator": ">=", "value": 80}
                ]
            }
        ]
    }
    """
    operator: ConditionOperator = Field(..., description="逻辑运算符 AND/OR")
    rules: List[Union["ConditionNode", ConditionRule]] = Field(
        ..., description="子条件列表（可嵌套）"
    )

    class Config:
        use_enum_values = True


# 递归引用需要 update_forward_refs
ConditionNode.update_forward_refs()


# ── 动作模型 ──────────────────────────────────────────────────

class ActionSpec(BaseModel):
    """动作规范"""
    type: ActionType = Field(..., description="动作类型")
    channels: List[str] = Field(
        default_factory=lambda: ["app"],
        description="通知渠道 ['app', 'push', 'webhook']"
    )
    message_template: str = Field(
        default="{{token_name}} 触发策略 {{strategy_name}}",
        description="消息模板，支持 {{变量}} 替换"
    )
    severity: AlertSeverity = Field(
        default=AlertSeverity.INFO,
        description="告警级别"
    )
    # Phase 3 交易参数
    amount_usd: Optional[float] = Field(None, description="交易金额 (USD)")
    max_slippage_pct: Optional[float] = Field(None, description="最大滑点 %")

    class Config:
        use_enum_values = True


# ── 过滤器 ────────────────────────────────────────────────────

class StrategyFilters(BaseModel):
    """策略过滤器"""
    chains: Optional[List[str]] = Field(None, description="限定链")
    min_score: Optional[float] = Field(None, description="最低分数")
    min_market_cap: Optional[float] = Field(None, description="最低市值")
    max_market_cap: Optional[float] = Field(None, description="最高市值")
    min_liquidity: Optional[float] = Field(None, description="最低流动性")
    exclude_tokens: Optional[List[str]] = Field(None, description="排除的代币地址")


# ── 策略规范（核心） ──────────────────────────────────────────

class StrategySpec(BaseModel):
    """
    完整策略规范

    由 LLM Parser 从自然语言生成，存入 agent_strategies 表。
    """
    name: str = Field(..., description="策略名称", max_length=100)
    description: Optional[str] = Field(None, description="策略描述")
    conditions: ConditionNode = Field(..., description="条件树")
    actions: List[ActionSpec] = Field(
        default_factory=lambda: [ActionSpec(type=ActionType.ALERT)],
        description="触发动作列表"
    )
    filters: StrategyFilters = Field(
        default_factory=StrategyFilters,
        description="过滤条件"
    )
    cooldown_minutes: int = Field(
        default=30, ge=5, le=1440,
        description="冷却时间（分钟），最小5分钟"
    )

    @validator("cooldown_minutes")
    def enforce_min_cooldown(cls, v: int) -> int:
        return max(v, 5)

    def get_data_sources(self) -> List[str]:
        """提取策略中涉及的所有数据源"""
        sources = set()
        self._collect_sources(self.conditions, sources)
        return list(sources)

    def _collect_sources(self, node: Union[ConditionNode, ConditionRule], sources: set):
        if isinstance(node, ConditionRule):
            sources.add(node.data_source)
        elif isinstance(node, ConditionNode):
            for rule in node.rules:
                self._collect_sources(rule, sources)


# ── 事件模型 ──────────────────────────────────────────────────

class DataEvent(BaseModel):
    """数据事件（由数据采集层发射）"""
    source: str = Field(..., description="数据源名")
    data: Dict[str, Any] = Field(..., description="数据载荷")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    chain: Optional[str] = None
    token_address: Optional[str] = None
    token_name: Optional[str] = None


class StrategyTriggeredEvent(BaseModel):
    """策略触发事件"""
    strategy_id: str
    user_id: str
    strategy_name: str
    trigger_context: Dict[str, Any]
    matched_token: Optional[str] = None
    matched_chain: Optional[str] = None
    token_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AlertEvent(BaseModel):
    """告警事件"""
    alert_id: Optional[str] = None
    user_id: str
    strategy_id: str
    title: str
    message: str
    severity: str = "info"
    token_address: Optional[str] = None
    chain: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── API 请求/响应模型 ─────────────────────────────────────────

class ChatRequest(BaseModel):
    """对话请求（用户自然语言 → 策略）"""
    message: str = Field(..., description="用户输入的自然语言", min_length=1)
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")


class ChatResponse(BaseModel):
    """对话响应"""
    strategy: Optional[StrategySpec] = None
    message: str = Field(..., description="AI 回复消息")
    requires_confirmation: bool = Field(
        default=True,
        description="是否需要用户确认"
    )


class StrategyCreateRequest(BaseModel):
    """策略创建请求"""
    spec: StrategySpec
    source_prompt: Optional[str] = None


class StrategyUpdateRequest(BaseModel):
    """策略更新请求"""
    name: Optional[str] = None
    status: Optional[StrategyStatus] = None
    conditions: Optional[ConditionNode] = None
    actions: Optional[List[ActionSpec]] = None
    filters: Optional[StrategyFilters] = None
    cooldown_minutes: Optional[int] = None

    class Config:
        use_enum_values = True


class AlertListResponse(BaseModel):
    """告警列表响应"""
    alerts: List[Dict[str, Any]]
    total: int
    unread_count: int
