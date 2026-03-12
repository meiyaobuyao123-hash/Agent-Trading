"""
LLM 策略解析器 — Claude Sonnet Tool Use → StrategySpec JSON

接收用户自然语言描述，通过 Claude API 的 Tool Use 功能
将其转化为结构化的 StrategySpec。

仅在策略创建/编辑时调用，每次约 $0.02。
日常规则引擎运行不调用 LLM。

Python 3.9 兼容。
"""
import os
import json
import logging
from typing import Any, Dict, Optional, Tuple

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
SYSTEM_PROMPT = """你是一个加密货币交易策略解析专家。用户会用自然语言描述他们想要的交易策略，
你需要将其转化为结构化的策略规范。

## 可用数据源和字段

### pump_tokens（内盘代币 - pump.fun）
- bc_progress: 进度百分比 0-100（Bonding Curve 进度）
- score: 内盘评分 0-100
- smart_money_count: 聪明钱钱包数
- buyer_count: 买家数
- dev_sold_pct: 开发者卖出比例 0-1
- buy_sell_ratio: 买卖笔数比

### hot_coins（外盘热币 - SOL/BSC/Base/ETH，数据源：OKX DEX Market API）
- score: 外盘评分 0-100
- score_m: 动量分 0-50
- score_q: 质量分 0-30
- score_p: 潜力分 0-20
- price_usd: 当前价格（毫秒级更新）
- price_change_5m: 5分钟涨幅百分比
- price_change_1h: 1小时涨幅百分比
- price_change_4h: 4小时涨幅百分比
- price_change_24h: 24小时涨幅百分比
- holder_count: 持有者数
- market_cap_usd: 市值（美元）
- liquidity_usd: 流动性（美元）
- volume_5m_usd: 5分钟交易量（美元）
- volume_1h_usd: 1小时交易量（美元）
- volume_4h_usd: 4小时交易量（美元）
- volume_24h_usd: 24小时交易量（美元）
- buys_1h: 1小时买入笔数
- sells_1h: 1小时卖出笔数
- buys_24h: 24小时买入笔数
- sells_24h: 24小时卖出笔数
- recommendation: 推荐等级（strong/normal/skip）
- circ_supply: 流通供应量
- chain: 链名（solana/bsc/base/eth）

### kol_mentions（KOL提及）
- mention_count_2h: 2小时内KOL提及次数
- mention_count_24h: 24小时内KOL提及次数
- avg_sentiment: 平均情绪 -1到1
- bullish_ratio: 看多比例 0-1
- mega_mention: 是否有 mega KOL 提及（0/1）

### kol_signals（KOL共振信号）
- signal_strength: 信号强度 0-10
- kol_count: 提及KOL总数
- total_reach: 总触达粉丝数

## 比较运算符
">" | ">=" | "<" | "<=" | "==" | "!=" | "in" | "not_in" | "contains"

## 逻辑运算符
"AND" | "OR"（可嵌套）

## 动作类型
- alert: App 内通知（默认）
- push: 推送通知

## 风控参数（可选，用于交易策略）
当策略包含 buy/sell 动作时，可以设置以下风控参数：
- stop_loss_pct: 止损百分比，默认 0.30（30%），范围 0.05-0.50
- take_profit_pct: 止盈百分比，默认 1.00（100%，即翻倍），范围 0.10-10.0
- max_position_usd: 单笔最大金额（美元），默认 100，范围 10-1000
- trailing_stop: 是否启用追踪止损，默认 true
- priority_fee_sol: Solana 优先费 (SOL)，默认 0.0005
- mev_bribe_sol: MEV 贿赂费 (SOL)，默认 0

## 规则
1. cooldown_minutes 最小 5 分钟
2. 条件必须具体、可量化
3. 模板变量用 {{变量名}}：token_name, chain, score, score_m, score_q, score_p, price_change_5m, price_change_1h, price_change_4h, price_change_24h, volume_5m_usd, market_cap_usd 等
4. 如果用户没指定链，不要添加 chains 过滤
5. 如果用户意图不明确，返回一个合理的默认配置并解释

## 示例：包含风控参数的交易策略
用户："帮我自动买入评分超过 85 的 Solana 热币，每笔不超过 50 美元，止损 20%，止盈 3 倍"
→ 应生成：
  - conditions: hot_coins.score >= 85
  - filters: chains=["solana"]
  - actions: [{type: "buy", amount_usd: 50, max_slippage_pct: 1.0}]
  - risk_params: {stop_loss_pct: 0.20, take_profit_pct: 2.0, max_position_usd: 50, trailing_stop: true}
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
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        解析用户自然语言为策略规范

        Args:
            user_message: 用户输入
            context: 可选的上下文信息

        Returns:
            (strategy_spec_dict, ai_message)
            strategy_spec_dict 可能为 None（如果解析失败或用户意图不明确）
        """
        if not self.api_key:
            return None, "API 密钥未配置，无法解析策略。请设置 ANTHROPIC_API_KEY。"

        try:
            client = self._get_client()

            messages = [
                {"role": "user", "content": user_message},
            ]

            # 如果有上下文，添加到消息前
            if context:
                context_str = json.dumps(context, ensure_ascii=False, indent=2)
                messages.insert(0, {
                    "role": "user",
                    "content": f"上下文信息：\n{context_str}",
                })
                messages.insert(1, {
                    "role": "assistant",
                    "content": "好的，我已了解上下文。请告诉我您想创建什么样的交易策略？",
                })

            response = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=[STRATEGY_TOOL],
                messages=messages,
            )

            # 提取结果
            strategy_spec = None
            ai_message = ""

            for block in response.content:
                if block.type == "tool_use" and block.name == "create_strategy":
                    strategy_spec = self._normalize_spec(block.input)
                elif block.type == "text":
                    ai_message = block.text

            if strategy_spec and not ai_message:
                ai_message = f"已为您创建策略「{strategy_spec.get('name', '')}」，请确认是否启用。"

            if not strategy_spec and not ai_message:
                ai_message = "抱歉，我无法理解您的策略描述。请更具体地描述您想监控什么条件、触发什么动作。"

            return strategy_spec, ai_message

        except anthropic.APIError as e:
            log.error(f"Claude API error: {e}")
            return None, f"AI 服务暂时不可用，请稍后再试。错误：{str(e)[:100]}"
        except Exception as e:
            log.error(f"LLM parser error: {e}")
            return None, f"策略解析出错，请重新描述。"

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
