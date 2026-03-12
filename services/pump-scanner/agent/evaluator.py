"""
策略评估器 — 数据事件 → 规则匹配

接收 DataEvent，遍历所有活跃策略，用 rule_engine 评估，
对匹配的策略生成 StrategyTriggeredEvent。

Python 3.9 兼容。
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from agent.schemas import (
    ConditionNode,
    ConditionRule,
    DataEvent,
    StrategyTriggeredEvent,
    StrategyFilters,
)
from agent.rule_engine import evaluate_conditions

log = logging.getLogger(__name__)


class StrategyEvaluator:
    """
    策略评估器

    职责：
    1. 接收数据事件
    2. 过滤匹配的策略（按 data_source + filters）
    3. 评估条件树
    4. 检查冷却时间
    5. 返回触发的策略列表
    """

    def evaluate(
        self,
        event: DataEvent,
        strategies: List[Dict[str, Any]],
    ) -> List[StrategyTriggeredEvent]:
        """
        评估一个数据事件对所有策略的匹配情况。

        Args:
            event: 数据事件
            strategies: 活跃策略列表（从 DB 加载的 dict）

        Returns:
            触发的策略事件列表
        """
        triggered = []  # type: List[StrategyTriggeredEvent]

        for strategy in strategies:
            try:
                result = self._evaluate_single(event, strategy)
                if result is not None:
                    triggered.append(result)
            except Exception as e:
                log.error(
                    f"Error evaluating strategy {strategy.get('id', '?')}: {e}"
                )

        return triggered

    def _evaluate_single(
        self,
        event: DataEvent,
        strategy: Dict[str, Any],
    ) -> Optional[StrategyTriggeredEvent]:
        """评估单个策略"""
        strategy_id = strategy.get("id", "")
        user_id = strategy.get("user_id", "")
        strategy_name = strategy.get("name", "unnamed")

        # 1. 检查策略状态
        if strategy.get("status") != "active":
            return None

        # 2. 检查数据源是否关联
        data_sources = strategy.get("data_sources", [])
        if data_sources and event.source not in data_sources:
            return None

        # 3. 检查过滤器
        filters = strategy.get("filters", {})
        if not self._check_filters(event, filters):
            return None

        # 4. 检查冷却时间
        if not self._check_cooldown(strategy):
            log.debug(f"Strategy {strategy_id} in cooldown")
            return None

        # 5. 构建数据上下文
        data_context = self._build_data_context(event)

        # 6. 解析条件树
        conditions_raw = strategy.get("conditions", {})
        try:
            conditions = self._parse_conditions(conditions_raw)
        except Exception as e:
            log.error(f"Failed to parse conditions for strategy {strategy_id}: {e}")
            return None

        # 7. 评估条件
        if not evaluate_conditions(conditions, data_context):
            return None

        # 8. 条件满足，生成触发事件
        log.info(
            f"Strategy triggered: {strategy_name} (id={strategy_id}) "
            f"by {event.source} event"
        )

        return StrategyTriggeredEvent(
            strategy_id=strategy_id,
            user_id=user_id,
            strategy_name=strategy_name,
            trigger_context=data_context,
            matched_token=event.token_address,
            matched_chain=event.chain,
            token_name=event.token_name,
        )

    def _check_filters(
        self,
        event: DataEvent,
        filters: Dict[str, Any],
    ) -> bool:
        """检查过滤条件"""
        if not filters:
            return True

        # 链过滤
        chains = filters.get("chains")
        if chains and event.chain and event.chain not in chains:
            return False

        # 最低分数
        min_score = filters.get("min_score")
        if min_score is not None:
            score = event.data.get("score", 0)
            if score < min_score:
                return False

        # 市值过滤
        min_mc = filters.get("min_market_cap")
        if min_mc is not None:
            mc = event.data.get("market_cap_usd", 0)
            if mc < min_mc:
                return False

        max_mc = filters.get("max_market_cap")
        if max_mc is not None:
            mc = event.data.get("market_cap_usd", float("inf"))
            if mc > max_mc:
                return False

        # 流动性过滤
        min_liq = filters.get("min_liquidity")
        if min_liq is not None:
            liq = event.data.get("liquidity_usd", 0)
            if liq < min_liq:
                return False

        # 子分过滤（动量/质量/潜力）
        for sub_key, data_key in [
            ("min_score_m", "score_m"),
            ("min_score_q", "score_q"),
            ("min_score_p", "score_p"),
        ]:
            min_val = filters.get(sub_key)
            if min_val is not None:
                val = event.data.get(data_key, 0)
                if val < min_val:
                    return False

        # 24h 交易量过滤
        min_vol = filters.get("min_volume_24h")
        if min_vol is not None:
            vol = event.data.get("volume_24h_usd", 0)
            if vol < min_vol:
                return False

        # 排除代币
        exclude = filters.get("exclude_tokens")
        if exclude and event.token_address in exclude:
            return False

        return True

    def _check_cooldown(self, strategy: Dict[str, Any]) -> bool:
        """检查冷却时间是否已过"""
        last_triggered = strategy.get("last_triggered")
        cooldown_min = strategy.get("cooldown_min", 30)

        if last_triggered is None:
            return True

        if isinstance(last_triggered, str):
            try:
                last_triggered = datetime.fromisoformat(
                    last_triggered.replace("Z", "+00:00")
                )
            except ValueError:
                return True

        now = datetime.utcnow()
        if hasattr(last_triggered, 'tzinfo') and last_triggered.tzinfo is not None:
            # 移除时区信息做简单比较
            last_triggered = last_triggered.replace(tzinfo=None)

        elapsed = now - last_triggered
        return elapsed >= timedelta(minutes=cooldown_min)

    def _build_data_context(self, event: DataEvent) -> Dict[str, Any]:
        """
        构建评估数据上下文

        将事件数据扁平化为 {source.field: value} 和 {field: value} 两种 key
        """
        context = {}  # type: Dict[str, Any]

        for key, value in event.data.items():
            # 带前缀 key
            context[f"{event.source}.{key}"] = value
            # 直接 key（方便简单条件）
            context[key] = value

        # 添加元信息
        context["_chain"] = event.chain
        context["_token_address"] = event.token_address
        context["_token_name"] = event.token_name
        context["_timestamp"] = event.timestamp.isoformat()

        return context

    def _parse_conditions(
        self,
        raw: Dict[str, Any],
    ):
        """将 dict 解析为 ConditionNode/ConditionRule"""
        if "operator" in raw and "rules" in raw:
            # 这是一个 ConditionNode
            rules = []
            for r in raw["rules"]:
                rules.append(self._parse_conditions(r))
            return ConditionNode(operator=raw["operator"], rules=rules)
        elif "data_source" in raw and "field" in raw:
            # 这是一个 ConditionRule
            return ConditionRule(
                data_source=raw["data_source"],
                field=raw["field"],
                operator=raw["operator"],
                value=raw["value"],
            )
        else:
            raise ValueError(f"Invalid condition format: {raw}")
