"""
LLM 策略解析器 — Claude Sonnet Tool Use → StrategySpec JSON

接收用户自然语言描述，通过 Claude API 的 Tool Use 功能
将其转化为结构化的 StrategySpec。

仅在策略创建/编辑时调用，每次约 $0.02。
日常规则引擎运行不调用 LLM。

Python 3.9 兼容。
"""
import asyncio
import os
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
load_dotenv(override=True)

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore

log = logging.getLogger(__name__)

# Claude 模型
MODEL = "claude-sonnet-4-20250514"

# 系统提示词
SYSTEM_PROMPT = """你是加密货币量化交易策略专家。将用户的自然语言描述转化为完整、可执行的策略。

## 核心原则
1. **每条规则必须有 data_source + field + operator + value** — 缺一不可
2. **conditions.rules 至少 1 条** — 空条件树不允许
3. **actions 至少 1 个** — 必须告诉系统触发后做什么
4. 如果用户描述模糊，主动补全合理默认值并在 description 中说明

## 数据源和字段

### hot_coins（外盘热币 SOL/BSC/Base/ETH）
| 字段 | 类型 | 说明 |
|------|------|------|
| _event_type | string | entered=新入榜 / exited=退出 / 空=价格更新 |
| _exit_reason | string | 退出原因（仅 exited 时有值） |
| score | 0-100 | 综合评分 |
| score_m | 0-50 | 动量分 |
| score_q | 0-30 | 质量分 |
| score_p | 0-20 | 潜力分 |
| price_usd | float | 当前价格 |
| price_change_5m | % | 5分钟涨跌幅 |
| price_change_1h | % | 1小时涨跌幅 |
| price_change_4h | % | 4小时涨跌幅 |
| price_change_24h | % | 24小时涨跌幅 |
| volume_1h_usd | float | 1小时交易量(USD) |
| volume_24h_usd | float | 24小时交易量(USD) |
| market_cap_usd | float | 市值(USD) |
| liquidity_usd | float | 流动性(USD) |
| holder_count | int | 持有人数 |
| buys_1h / sells_1h | int | 1小时买/卖笔数 |
| recommendation | string | strong/normal/skip |
| chain | string | solana/bsc/base/eth |

**热币特殊事件条件**：
- `_event_type == "entered"`: 代币刚入榜时触发（可用于"新币入榜自动买入"）
- `_event_type == "exited"`: 代币退出时触发（可用于"退出时卖出"）
- 不设 _event_type: 匹配所有热币更新（价格变动+入榜+退出）

示例："热币新入榜评分>70时买入" →
  条件: [{"field":"_event_type","operator":"==","value":"entered"}, {"field":"score","operator":">","value":70}]

### pump_tokens（内盘 pump.fun）
| 字段 | 类型 | 说明 |
|------|------|------|
| bc_progress | 0-100 | Bonding Curve 进度% |
| score | 0-100 | 内盘评分 |
| smart_money_count | int | 聪明钱钱包数 |
| buyer_count | int | 买家数 |
| dev_sold_pct | 0-1 | 开发者卖出比例 |
| buy_sell_ratio | float | 买卖比 |

### kol_mentions（KOL提及）
- mention_count_2h / mention_count_24h: KOL提及次数
- avg_sentiment: 情绪 -1~1
- bullish_ratio: 看多比例 0~1
- mega_mention: 是否有大V提及 0/1

### btc_eth_indicators（BTC/ETH 实时指标）
| 字段 | 类型 | 说明 |
|------|------|------|
| asset | string | BTC 或 ETH |
| price_usd | float | 当前价格 |
| price_change_1h | % | 1小时涨跌幅 |
| price_change_4h | % | 4小时涨跌幅 |
| price_change_24h | % | 24小时涨跌幅 |
| rsi_14 | 0-100 | RSI指标 |
| funding_rate | float | 资金费率 |
| oi_usd | float | 未平仓量(USD) |
| fear_greed_index | 0-100 | 恐慌贪婪指数 |
| score_momentum | 0-100 | 动量评分 |
| score_sentiment | 0-100 | 情绪评分 |

用户说"BTC策略"/"ETH策略"/"比特币"/"以太坊"时，使用 btc_eth_indicators 数据源。
示例条件：{"data_source":"btc_eth_indicators","field":"rsi_14","operator":"<","value":30}
配合 filters: {"assets": ["BTC"]} 或 {"assets": ["ETH"]}

## 运算符
比较: > >= < <= == != in not_in contains
逻辑: AND OR（可嵌套）

## 动作类型
- alert: App内通知（默认，channels=["app"]，severity=info/warning/critical）
- buy: 自动买入（需 amount_usd + max_slippage_pct）
- sell: 自动卖出

## 风控参数 risk_params（交易策略必填）
- stop_loss_pct: 止损% (0.05-0.50)，默认 0.30
- take_profit_pct: 止盈% (0.10-10.0)，默认 1.00
- max_position_usd: 单笔上限USD (10-1000)，默认 100
- trailing_stop: 追踪止损 bool，默认 true
- priority_fee_sol: SOL优先费，默认 0.0005
- mev_bribe_sol: MEV贿赂费，默认 0

## 完整示例

用户："帮我监控 SOL 链上评分超过 70 的热币，1小时涨幅超过 10%就通知我"
→ 生成：
```json
{
  "name": "SOL高分热币涨幅监控",
  "description": "监控Solana链上评分≥70且1小时涨幅超10%的热币，满足条件时发送App通知",
  "conditions": {
    "operator": "AND",
    "rules": [
      {"data_source": "hot_coins", "field": "score", "operator": ">=", "value": 70},
      {"data_source": "hot_coins", "field": "price_change_1h", "operator": ">", "value": 10}
    ]
  },
  "actions": [{"type": "alert", "channels": ["app"], "severity": "warning",
    "message_template": "{{token_name}} ({{chain}}) 评分{{score}}，1h涨{{price_change_1h}}%"}],
  "filters": {"chains": ["solana"]},
  "cooldown_minutes": 15
}
```

用户："自动买入评分85+的热币，50刀一笔，止损20%，止盈3倍"
→ 生成：
```json
{
  "name": "高分热币自动买入",
  "description": "评分≥85的热币自动买入$50，止损20%止盈200%，追踪止损",
  "conditions": {
    "operator": "AND",
    "rules": [
      {"data_source": "hot_coins", "field": "score", "operator": ">=", "value": 85},
      {"data_source": "hot_coins", "field": "liquidity_usd", "operator": ">=", "value": 10000},
      {"data_source": "hot_coins", "field": "volume_1h_usd", "operator": ">=", "value": 5000}
    ]
  },
  "actions": [{"type": "buy", "amount_usd": 50, "max_slippage_pct": 1.0}],
  "filters": {},
  "cooldown_minutes": 30,
  "risk_params": {"stop_loss_pct": 0.20, "take_profit_pct": 2.0, "max_position_usd": 50, "trailing_stop": true}
}
```

## 你的完整能力(R39 扩展:18 tool 自主 route)

**重要**:你不只是"策略创建器",你是 AiTrading agent,有 14+ 个 tool 可调。
根据用户问的事**自己决定调哪个 tool**,绝不要说"无法 X"。

### 查询类 tools(用户问数据时用)
- `query_top_movers`: **查涨幅榜 top N**(pump.fun / 多链热币 / 全部),回答"哪些币涨得好"/"24h top 30"等
- `query_market`: 单代币行情(price/MC/LP/K线/toplist)
- `query_holders`: 代币 top10 持仓 + 集中度 + 鲸鱼
- `query_onchain_activity`: 链上聪明钱买卖 / 大额转账(window=1h/24h/7d)
- `recall_memory`: 召回历史相似交易案例(episodic + semantic)
- `get_paper_performance`: 用户模拟盘表现统计

### 计算类 tools
- `calc_technical_indicators`: RSI/MACD/MA/ATR/BB(给定 K线)
- `calc_risk_metrics`: 胜率/夏普/最大回撤(给定 trades 列表)
- `calc_position_size`: 仓位大小(fixed/Kelly/ATR-risk)

### 创建/管理类 tools
- `create_strategy` (即此 STRATEGY_TOOL):自然语言 → StrategySpec
- `list_strategies` (LIST_STRATEGIES_TOOL):列用户已有策略
- `run_backtest` (BACKTEST_TOOL):任何策略历史回测
- `update_strategy_status`: paused/active/archived 切换
- `run_paper_trade`: 模拟盘 buy/sell

### 决策路径(必读)
1. 用户说"哪些币涨得好"/"top movers"/"pump.fun 涨幅" → **直接调 `query_top_movers`**,不要说"我无法查"
2. 用户问"分析 TRUMP" → 并行调 `query_market` + `query_holders` + `query_onchain_activity`
3. 用户说"建一个 SOL 跟单策略" → 调 `create_strategy`(用 STRATEGY_TOOL)
4. 用户问"我之前的策略表现" → 调 `list_strategies` + `get_paper_performance`
5. 闲聊 / 模糊问题 → 直接对话,不调 tool

**禁止**:任何时候不能说"系统不支持 X" / "我只能做策略" — 18 工具能做的事都做得到。

### Output Discipline(写给用户看的 final text 必须遵守)

**绝对禁止 narrate tool 调用过程**:
- ❌ "让我使用工具来查询..."
- ❌ "抱歉,让我重新检查工具名"
- ❌ "我发现工具调用有问题"
- ❌ "我尝试使用 X 工具..."
- ❌ "系统当前支持 5m/1h/6h/24h,没有 7d"
- ❌ "需要说明的是..."

**正确做法 — 直接给结果或建议**:
- ✅ 用户问"7天涨幅 top 30" → 静默调 `query_top_movers(window="7d", limit=30)` → 直接返带数据的列表
- ✅ Tool 返 `note: "7d 数据 fallback 24h"` → 在最终回复**简短**提一句"(7d 数据未沉淀,以 24h 为准)" 然后给数据,不展开
- ✅ Tool 返 INPUT_SCHEMA_INVALID → **静默用合理默认值重试**(window=24h, limit=10),不告诉用户尝试过程
- ✅ 真的所有重试都失败 → 才简短说"暂时拿不到数据,稍后再试",不超过 30 字

**记住**:用户看到的 text 是产品体验,不是你的内心独白。
你的"reasoning"应该体现在**调对 tool**,不应该体现在 final text 里。

### 策略创建(STRATEGY_TOOL)
- 将自然语言转化为完整策略(条件+动作+风控)
- 支持热币/内盘/KOL/聪明钱多种数据源
- 所有新策略默认 mode=paper(模拟盘),用户确认后可切换实盘

### 策略模板(用户说"推荐策略"时使用)
- meme_sniper: MEME早期狙击(内盘 BC 5-25%,聪明钱≥2)
- hot_breakout: 热币追涨(评分≥65,1h涨幅>5%)
- smart_money_follow: 聪明钱跟单(elite钱包买入信号)
- kol_sentiment: KOL舆情(2h内≥3个KOL提及)
- conservative_dca: 保守定投(评分≥70,24h量>$50K)

### 回测能力(BACKTEST_TOOL)
- 可以对任何策略进行 7 天历史数据回测
- 返回:触发次数、胜率、平均收益、最大回撤
- 用户说"回测"/"测试一下"/"验证策略"时，直接调用 run_backtest 工具
- 如果用户刚创建了策略又说"回测"，使用上下文中最近创建的策略 ID
- 不要要求用户提供策略 ID，从上下文自动获取

### 模拟盘
- 所有策略先在模拟盘运行（不花真钱）
- 模拟盘自动执行、自动止盈止损
- 用户可查看模拟盘收益后再切换实盘

### 表现分析
- 策略胜率、PNL、夏普率、最大回撤
- 按链/按策略类型/按时间分组分析

### 风险管理（15项自动检查）
- 熔断器、速率限制、每日亏损上限
- 蜜罐检测、税率检查、流动性检查
- BTC大盘趋势、同链集中度检查
- Market Regime 动态调整（CRISIS时暂停新买入）

## 重要规则
- conditions.rules 数组**不能为空**，至少写1条完整规则
- 每条规则**必须**有 data_source, field, operator, value 四个字段
- buy/sell 动作时**必须**生成 risk_params
- 如果用户只说"行情策略"或"止盈止损"等模糊词，自动补全为合理的量化条件
- message_template 用 {{变量名}} 引用字段值
- 用户问"你能做什么"时，完整介绍以上所有能力
"""

# Tool 定义（Claude Tool Use）
STRATEGY_TOOL = {
    "name": "create_strategy",
    "description": "创建交易监控策略",
    "input_schema": {
        "type": "object",
        "required": ["name", "conditions"],
        "properties": {
            "name": {
                "type": "string",
                "description": "策略名称（简洁描述）",
            },
            "description": {
                "type": "string",
                "description": "策略详细描述",
            },
            "conditions": {
                "type": "object",
                "description": "条件树",
                "properties": {
                    "operator": {
                        "type": "string",
                        "enum": ["AND", "OR"],
                    },
                    "rules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "data_source": {"type": "string"},
                                "field": {"type": "string"},
                                "operator": {
                                    "type": "string",
                                    "enum": [">", ">=", "<", "<=", "==", "!=", "in", "not_in", "contains"],
                                },
                                "value": {},
                                # 嵌套用
                                "operator_logic": {
                                    "type": "string",
                                    "enum": ["AND", "OR"],
                                },
                                "rules_nested": {"type": "array"},
                            },
                        },
                    },
                },
            },
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["alert", "push", "buy", "sell"],
                        },
                        "amount_usd": {
                            "type": "number",
                            "description": "交易金额(USD)，buy/sell时必填",
                            "minimum": 1,
                            "maximum": 1000,
                        },
                        "max_slippage_pct": {
                            "type": "number",
                            "description": "最大滑点百分比，默认 1.0",
                            "minimum": 0.1,
                            "maximum": 10.0,
                        },
                        "channels": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "message_template": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["info", "warning", "critical"],
                        },
                    },
                },
            },
            "filters": {
                "type": "object",
                "properties": {
                    "chains": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "min_score": {"type": "number"},
                    "min_score_m": {"type": "number", "description": "最低动量分 (0-50)"},
                    "min_score_q": {"type": "number", "description": "最低质量分 (0-30)"},
                    "min_score_p": {"type": "number", "description": "最低潜力分 (0-20)"},
                    "min_market_cap": {"type": "number"},
                    "max_market_cap": {"type": "number"},
                    "min_liquidity": {"type": "number"},
                    "min_volume_24h": {"type": "number", "description": "最低24h交易量 (USD)"},
                },
            },
            "cooldown_minutes": {
                "type": "integer",
                "minimum": 5,
                "maximum": 1440,
                "default": 30,
            },
            "risk_params": {
                "type": "object",
                "description": "风控参数（交易策略专用）",
                "properties": {
                    "stop_loss_pct": {
                        "type": "number",
                        "description": "止损百分比 0.05-0.50，默认 0.30",
                        "minimum": 0.05,
                        "maximum": 0.50,
                    },
                    "take_profit_pct": {
                        "type": "number",
                        "description": "止盈百分比 0.10-10.0，默认 1.00",
                        "minimum": 0.10,
                        "maximum": 10.0,
                    },
                    "max_position_usd": {
                        "type": "number",
                        "description": "单笔最大金额(USD) 10-1000，默认 100",
                        "minimum": 10,
                        "maximum": 1000,
                    },
                    "trailing_stop": {
                        "type": "boolean",
                        "description": "是否启用追踪止损，默认 true",
                    },
                    "priority_fee_sol": {
                        "type": "number",
                        "description": "Solana 优先费 (SOL)，默认 0.0005",
                        "minimum": 0.0001,
                        "maximum": 0.1,
                    },
                    "mev_bribe_sol": {
                        "type": "number",
                        "description": "MEV 贿赂费 (SOL)，默认 0",
                        "minimum": 0,
                        "maximum": 0.1,
                    },
                },
            },
        },
    },
}


LIST_STRATEGIES_TOOL = {
    "name": "list_strategies",
    "description": "查看用户已创建的所有策略列表，返回策略ID、名称、状态、模式",
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

BACKTEST_TOOL = {
    "name": "run_backtest",
    "description": "对策略进行7天历史数据回测，返回触发次数、胜率、平均收益、最大回撤。需要先用 list_strategies 获取策略ID",
    "input_schema": {
        "type": "object",
        "required": ["strategy_id"],
        "properties": {
            "strategy_id": {
                "type": "string",
                "description": "要回测的策略 ID（UUID），从 list_strategies 结果中获取",
            },
            "days": {
                "type": "integer",
                "description": "回测天数，默认7",
                "minimum": 1,
                "maximum": 30,
            },
        },
    },
}

TOOLS = [STRATEGY_TOOL, LIST_STRATEGIES_TOOL, BACKTEST_TOOL]


# R39 root-cause fix:把 18 个原子 Tool 全部暴露给 LLM,让它自主 route
# 排除冲突的 list_strategies / save_strategy / run_backtest(已有 STRATEGY_TOOL/LIST_STRATEGIES_TOOL/BACKTEST_TOOL 同义)
# 排除真金 execute_swap(必须走 HITL,不能让 chat 直接触发)
_EXCLUDED_FROM_CHAT = {
    "list_strategies",          # 用 LIST_STRATEGIES_TOOL(同义)
    "save_strategy",            # 用 STRATEGY_TOOL.create_strategy(同义)
    "run_backtest",             # 用 BACKTEST_TOOL(同义)
    "execute_swap",             # 真金交易 — 不暴露给 chat
    "send_push_notification",   # 系统级 — 不应由 chat 触发
    "create_approval_request",  # 系统级
    "approve_rule",             # 系统级
}


def _get_extra_tool_specs():
    """从 registry 取 18 - 7 = 11 个适合 chat 暴露的 tool spec。"""
    try:
        from agent.tools import get_tool_registry
        reg = get_tool_registry()
        out = []
        for name, tool in reg.items():
            if name in _EXCLUDED_FROM_CHAT:
                continue
            try:
                out.append(tool.to_anthropic_tool_spec())
            except Exception as e:
                log.warning("tool %s spec fail: %s", name, e)
        return out
    except Exception as e:
        log.warning("get_extra_tool_specs failed: %s", e)
        return []


# 真正暴露给 LLM 的所有 tools(策略创建 + 查询/计算)
ALL_TOOLS = TOOLS + _get_extra_tool_specs()


async def _execute_registry_tool(name: str, payload: dict) -> str:
    """跑 registry tool 并 format 为 LLM 可读 JSON 字符串。"""
    try:
        from agent.tools import get_tool_registry
        reg = get_tool_registry()
        tool = reg.get(name)
        if tool is None:
            return json.dumps({"error": f"tool not in registry: {name}"})
        res = await tool.run(payload)
        if res.ok:
            return json.dumps(res.output, ensure_ascii=False, default=str)
        return json.dumps({
            "error": res.error or "tool_failed",
            "failure_mode": res.failure_mode,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)[:200]}, ensure_ascii=False)


class LLMParser:
    """LLM 策略解析器"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            log.warning("ANTHROPIC_API_KEY not set, LLM parser will not work")
        if anthropic is None:
            log.warning("anthropic SDK not installed, LLM parser disabled")
        self.client = None  # type: Optional[Any]

    def _get_client(self) -> Any:
        """惰性初始化 Anthropic 客户端"""
        if anthropic is None:
            raise RuntimeError("anthropic SDK not installed. Run: pip install anthropic")
        if self.client is None:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        return self.client

    async def parse_strategy(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], str, List[Dict[str, Any]]]:
        """
        多轮 tool use 循环：Claude 可以连续调用多个工具（list→backtest→回复）

        R39 v5: 加 conversation_history 参数。非空时把历史 messages 作为本次 LLM 起点
        (LLM 可以看到 T1 的 tool_result 等)。返回追加完整轮次后的 messages 让 caller 持久化。

        Returns:
            (strategy_spec_dict, ai_message, full_messages)
        """
        if not self.api_key:
            return None, "API 密钥未配置，无法解析策略。请设置 ANTHROPIC_API_KEY。", list(conversation_history or [])

        client = self._get_client()

        if conversation_history:
            # R39 v5: 续接历史。不再注入 context(避免每轮重复污染历史);只追加新 user 消息
            messages = list(conversation_history)
            messages.append({"role": "user", "content": user_message})
        else:
            messages = [{"role": "user", "content": user_message}]
            if context:
                context_str = json.dumps(context, ensure_ascii=False, indent=2)
                messages.insert(0, {"role": "user", "content": f"上下文信息：\n{context_str}"})
                messages.insert(1, {"role": "assistant", "content": "好的，我已了解上下文。请告诉我您想创建什么样的交易策略？"})

        strategy_spec = None
        ai_message = ""
        MAX_TURNS = 5  # 最多 5 轮 tool use 循环

        for turn in range(MAX_TURNS):
            try:
                response = await asyncio.to_thread(
                    client.messages.create,
                    model=MODEL,
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    tools=ALL_TOOLS,
                    messages=messages,
                )
            except (anthropic.RateLimitError, anthropic.InternalServerError) as e:
                log.warning(f"LLM Parser error turn {turn}: {e}")
                await asyncio.sleep(5)
                continue
            except anthropic.APIError as e:
                return None, f"AI 服务暂时不可用：{str(e)[:100]}", messages
            except Exception as e:
                return None, f"策略解析出错，请重新描述。", messages

            # 收集本轮的文本和工具调用
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    ai_message += block.text
                elif block.type == "tool_use":
                    tool_calls.append(block)

            # 没有工具调用 → 对话结束
            if not tool_calls:
                break

            # 处理工具调用，构建 tool_result 消息
            # 先把 assistant 的完整 response 加入 messages
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tc in tool_calls:
                result_text = ""
                if tc.name == "create_strategy":
                    strategy_spec = self._normalize_spec(tc.input)
                    result_text = json.dumps({
                        "success": True,
                        "strategy_id": "pending_confirmation",
                        "name": strategy_spec.get("name", ""),
                        "message": f"策略「{strategy_spec.get('name', '')}」已创建。"
                    }, ensure_ascii=False)
                elif tc.name == "list_strategies":
                    result_text = await self._execute_list_strategies()
                elif tc.name == "run_backtest":
                    result_text = await self._execute_backtest(tc.input)
                else:
                    # R39 root-cause fix:LLM 选了 registry 里某个 tool → 调它
                    result_text = await _execute_registry_tool(tc.name, tc.input or {})

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result_text,
                })

            messages.append({"role": "user", "content": tool_results})

            # 如果 Claude 还想继续调用工具，循环继续
            if response.stop_reason == "end_turn":
                break

        if not ai_message and strategy_spec:
            ai_message = f"已为您创建策略「{strategy_spec.get('name', '')}」，请确认是否启用。"
        if not ai_message and not strategy_spec:
            ai_message = "抱歉，我无法理解您的策略描述。请更具体地描述您想监控什么条件、触发什么动作。"

        # R39 v5: 把本轮 LLM 的 final 文本回复也追加进 messages,
        # 让下一轮 caller 拿到完整 anthropic 历史(含本轮 user + tool 链 + 最终 assistant)
        if ai_message and (not messages or messages[-1].get("role") != "assistant"
                           or isinstance(messages[-1].get("content"), list)):
            messages.append({"role": "assistant", "content": ai_message})

        return strategy_spec, ai_message, messages

    async def parse_strategy_stream(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        流式版本：多轮 tool use + 最终回复流式输出

        策略：先用非流式完成多轮 tool use，然后最后一轮用流式输出文本。
        中间 tool 执行过程通过 delta 事件通知用户"正在执行..."

        R39 v5: 加 conversation_history 参数。流末 yield {"type":"final_messages",...} 让
        caller 拿到完整 messages 持久化。
        """
        if not self.api_key:
            yield {"type": "error", "message": "API 密钥未配置"}
            return

        client = self._get_client()
        if conversation_history:
            messages = list(conversation_history)
            messages.append({"role": "user", "content": user_message})
        else:
            messages = [{"role": "user", "content": user_message}]
            if context:
                context_str = json.dumps(context, ensure_ascii=False, indent=2)
                messages.insert(0, {"role": "user", "content": f"上下文信息：\n{context_str}"})
                messages.insert(1, {"role": "assistant", "content": "好的，我已了解上下文。"})

        yield {"type": "start"}

        strategy_spec = None
        MAX_TURNS = 5
        # R39 v5: 累积本流的纯文本 LLM 回复,用于追加到 messages 末尾(给下轮 caller)
        accumulated_assistant_text = ""

        try:
            for turn in range(MAX_TURNS):
                # 最后一轮或非 tool_use 停止时，用流式输出
                # 先用非流式探测是否有 tool 调用
                response = await asyncio.to_thread(
                    client.messages.create,
                    model=MODEL,
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    tools=ALL_TOOLS,
                    messages=messages,
                )

                tool_calls = []
                text_parts = []
                for block in response.content:
                    if block.type == "text":
                        text_parts.append(block.text)
                    elif block.type == "tool_use":
                        tool_calls.append(block)

                # 有文本 → 逐字推送（模拟打字机效果）
                for text in text_parts:
                    accumulated_assistant_text += text
                    # 分成小块推送，模拟流式
                    chunk_size = 15  # 每次推 15 个字符
                    for i in range(0, len(text), chunk_size):
                        yield {"type": "delta", "text": text[i:i + chunk_size]}
                        await asyncio.sleep(0.02)

                # 没有工具调用 → 结束
                if not tool_calls:
                    break

                # 执行工具调用
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []

                for tc in tool_calls:
                    if tc.name == "create_strategy":
                        strategy_spec = self._normalize_spec(tc.input)
                        yield {"type": "strategy", "data": strategy_spec}
                        result_text = json.dumps({
                            "success": True, "name": strategy_spec.get("name", "")
                        }, ensure_ascii=False)
                    elif tc.name == "list_strategies":
                        yield {"type": "delta", "text": "\n\n正在查询策略列表...\n"}
                        result_text = await self._execute_list_strategies()
                    elif tc.name == "run_backtest":
                        yield {"type": "delta", "text": "\n\n正在执行回测...\n"}
                        result_text = await self._execute_backtest(tc.input)
                        yield {"type": "delta", "text": result_text}
                    else:
                        # R39 v3 fix:registry 里的 tool(query_top_movers / query_market 等)
                        # 必须真调用,否则 LLM 收到 unknown tool 会卡住
                        result_text = await _execute_registry_tool(tc.name, tc.input or {})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result_text,
                    })

                messages.append({"role": "user", "content": tool_results})

                if response.stop_reason == "end_turn":
                    break

            # R39 v5: 把 final text 追加到 messages 末尾,然后 yield 给 caller 持久化
            if accumulated_assistant_text and (
                not messages
                or messages[-1].get("role") != "assistant"
                or isinstance(messages[-1].get("content"), list)
            ):
                messages.append({
                    "role": "assistant",
                    "content": accumulated_assistant_text,
                })
            yield {"type": "final_messages", "messages": messages}
            yield {"type": "done"}

        except Exception as e:
            log.error("Stream error: %s", e)
            yield {"type": "error", "message": str(e)[:200]}
            # 失败也要给 caller 一份 messages(可能用于诊断/不持久化)
            yield {"type": "final_messages", "messages": messages}

    async def _execute_list_strategies(self) -> str:
        """列出所有策略"""
        try:
            from database import get_db
            res = get_db().table("strategies").select(
                "id, name, status, created_at"
            ).order("created_at", desc=True).limit(10).execute()
            strategies = res.data or []
            if not strategies:
                return json.dumps({"strategies": [], "message": "暂无策略，请先创建一个"}, ensure_ascii=False)
            items = []
            for s in strategies:
                items.append({
                    "id": s["id"],
                    "name": s.get("name", ""),
                    "status": s.get("status", ""),
                    "created_at": s.get("created_at", ""),
                })
            return json.dumps({"strategies": items}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)[:100]}, ensure_ascii=False)

    async def _execute_backtest(self, request: Dict[str, Any]) -> str:
        """执行回测并返回格式化结果"""
        try:
            strategy_id = request.get("strategy_id", "")
            days = request.get("days", 7)

            from agent.backtester import Backtester
            bt = Backtester()
            result = await asyncio.to_thread(bt.run, strategy_id, days=days)

            if result and result.get("triggers", 0) > 0:
                return (
                    f"## 📊 回测结果（{days}天）\n"
                    f"- 触发次数：{result.get('triggers', 0)}\n"
                    f"- 胜率：{result.get('win_rate', 0)*100:.1f}%\n"
                    f"- 平均收益：{result.get('avg_pnl', 0)*100:.1f}%\n"
                    f"- 最大回撤：{result.get('max_drawdown', 0)*100:.1f}%\n"
                    f"- 累计PNL：{result.get('total_pnl', 0)*100:.1f}%\n"
                    f"- 夏普率：{result.get('sharpe', 0):.2f}"
                )
            else:
                return f"## 📊 回测结果（{days}天）\n过去{days}天该策略未触发任何交易信号。建议放宽条件或增加回测时间范围。"
        except Exception as e:
            log.warning("Backtest execution error: %s", e)
            return f"回测执行出错：{str(e)[:100]}。请确保策略已创建成功后再进行回测。"

    def _normalize_spec(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        规范化 LLM 输出的策略规范

        处理嵌套条件、默认值等
        """
        spec = {
            "name": raw.get("name", "未命名策略"),
            "description": raw.get("description"),
            "conditions": self._normalize_conditions(
                raw.get("conditions", {})
            ),
            "actions": raw.get("actions", [
                {"type": "alert", "channels": ["app"], "severity": "info"}
            ]),
            "filters": raw.get("filters", {}),
            "cooldown_minutes": max(raw.get("cooldown_minutes", 30), 5),
        }

        # 风控参数（交易策略专用）
        risk_params = raw.get("risk_params")
        if risk_params:
            spec["risk_params"] = {
                "stop_loss_pct": min(max(risk_params.get("stop_loss_pct", 0.30), 0.05), 0.50),
                "take_profit_pct": min(max(risk_params.get("take_profit_pct", 1.00), 0.10), 10.0),
                "max_position_usd": min(max(risk_params.get("max_position_usd", 100), 10), 1000),
                "trailing_stop": risk_params.get("trailing_stop", True),
                "priority_fee_sol": min(max(risk_params.get("priority_fee_sol", 0.0005), 0.0001), 0.1),
                "mev_bribe_sol": min(max(risk_params.get("mev_bribe_sol", 0), 0), 0.1),
            }

        # 确保至少有一个 action
        if not spec["actions"]:
            spec["actions"] = [
                {"type": "alert", "channels": ["app"], "severity": "info"}
            ]

        return spec

    def _normalize_conditions(
        self,
        conditions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """规范化条件树（处理 LLM 可能的格式变体）"""
        if not conditions:
            return {"operator": "AND", "rules": []}

        # 如果是单条规则，包裹成 AND 节点
        if "data_source" in conditions and "field" in conditions:
            return {
                "operator": "AND",
                "rules": [conditions],
            }

        # 处理嵌套规则
        rules = conditions.get("rules", [])
        normalized_rules = []
        for rule in rules:
            if "operator_logic" in rule or "rules_nested" in rule:
                # 嵌套节点
                nested = {
                    "operator": rule.get("operator_logic", "AND"),
                    "rules": rule.get("rules_nested", []),
                }
                normalized_rules.append(
                    self._normalize_conditions(nested)
                )
            else:
                normalized_rules.append(rule)

        return {
            "operator": conditions.get("operator", "AND"),
            "rules": normalized_rules,
        }
