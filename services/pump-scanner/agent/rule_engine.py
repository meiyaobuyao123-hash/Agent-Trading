"""
规则引擎 — 递归条件评估器

纯逻辑运算，CPU 耗时 <1ms。
支持 AND/OR 嵌套条件树。

用法：
    from agent.rule_engine import evaluate_conditions
    from agent.schemas import ConditionNode

    conditions = ConditionNode(operator="AND", rules=[...])
    data = {"bc_progress": 60, "score": 85}
    result = evaluate_conditions(conditions, data)
    # result = True/False

Python 3.9 兼容。
"""
import logging
from typing import Any, Dict, List, Optional, Union

from agent.schemas import (
    ConditionNode,
    ConditionRule,
    ComparisonOperator,
    ConditionOperator,
)

log = logging.getLogger(__name__)


def evaluate_conditions(
    node: Union[ConditionNode, ConditionRule],
    data: Dict[str, Any],
) -> bool:
    """
    递归评估条件树。

    Args:
        node: 条件树节点（ConditionNode 或 ConditionRule）
        data: 扁平化数据字典，key 格式为 "{data_source}.{field}" 或直接 "{field}"

    Returns:
        True if 条件满足，False otherwise
    """
    if isinstance(node, ConditionRule):
        return _evaluate_rule(node, data)
    elif isinstance(node, ConditionNode):
        return _evaluate_node(node, data)
    else:
        log.warning(f"Unknown node type: {type(node)}")
        return False


def _evaluate_node(node: ConditionNode, data: Dict[str, Any]) -> bool:
    """评估逻辑节点 (AND/OR)"""
    if not node.rules:
        return True  # 空规则视为通过

    results = [evaluate_conditions(rule, data) for rule in node.rules]

    if node.operator == ConditionOperator.AND or node.operator == "AND":
        return all(results)
    elif node.operator == ConditionOperator.OR or node.operator == "OR":
        return any(results)
    else:
        log.warning(f"Unknown operator: {node.operator}")
        return False


def _evaluate_rule(rule: ConditionRule, data: Dict[str, Any]) -> bool:
    """评估单条规则"""
    # 构建查找 key：先尝试 "source.field"，再尝试直接 "field"
    full_key = f"{rule.data_source}.{rule.field}"
    actual_value = data.get(full_key)
    if actual_value is None:
        actual_value = data.get(rule.field)
    if actual_value is None:
        # 数据中没有此字段，条件不满足
        log.debug(f"Field not found: {full_key} or {rule.field}")
        return False

    return _compare(actual_value, rule.operator, rule.value)


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    """执行比较运算"""
    try:
        op = operator if isinstance(operator, str) else operator.value

        if op == ">" or op == ComparisonOperator.GT:
            return float(actual) > float(expected)
        elif op == ">=" or op == ComparisonOperator.GTE:
            return float(actual) >= float(expected)
        elif op == "<" or op == ComparisonOperator.LT:
            return float(actual) < float(expected)
        elif op == "<=" or op == ComparisonOperator.LTE:
            return float(actual) <= float(expected)
        elif op == "==" or op == ComparisonOperator.EQ:
            return _eq_compare(actual, expected)
        elif op == "!=" or op == ComparisonOperator.NEQ:
            return not _eq_compare(actual, expected)
        elif op == "in" or op == ComparisonOperator.IN:
            if isinstance(expected, (list, tuple, set)):
                return actual in expected
            return str(actual) in str(expected)
        elif op == "not_in" or op == ComparisonOperator.NOT_IN:
            if isinstance(expected, (list, tuple, set)):
                return actual not in expected
            return str(actual) not in str(expected)
        elif op == "contains" or op == ComparisonOperator.CONTAINS:
            return str(expected).lower() in str(actual).lower()
        else:
            log.warning(f"Unknown operator: {op}")
            return False
    except (ValueError, TypeError) as e:
        log.debug(f"Compare error: {actual} {operator} {expected} → {e}")
        return False


def _eq_compare(a: Any, b: Any) -> bool:
    """相等比较（支持类型宽容）"""
    # 尝试数值比较
    try:
        return float(a) == float(b)
    except (ValueError, TypeError):
        pass
    # 字符串比较
    return str(a).lower() == str(b).lower()


def extract_data_sources(node: Union[ConditionNode, ConditionRule]) -> List[str]:
    """提取条件树中的所有数据源名"""
    sources = set()
    _collect_sources(node, sources)
    return list(sources)


def _collect_sources(
    node: Union[ConditionNode, ConditionRule],
    sources: set
):
    """递归收集数据源"""
    if isinstance(node, ConditionRule):
        sources.add(node.data_source)
    elif isinstance(node, ConditionNode):
        for rule in node.rules:
            _collect_sources(rule, sources)


def validate_conditions(node: Union[ConditionNode, ConditionRule]) -> List[str]:
    """
    验证条件树的合法性。

    Returns:
        错误信息列表，空列表表示验证通过
    """
    errors = []  # type: List[str]
    _validate_node(node, errors, depth=0)
    return errors


def _validate_node(
    node: Union[ConditionNode, ConditionRule],
    errors: List[str],
    depth: int,
):
    """递归验证条件节点"""
    if depth > 10:
        errors.append("Condition tree too deep (max 10 levels)")
        return

    if isinstance(node, ConditionRule):
        if not node.data_source:
            errors.append("Rule missing data_source")
        if not node.field:
            errors.append("Rule missing field")
        # 验证数据源是否已知
        known_sources = {"pump_tokens", "hot_coins", "kol_mentions", "kol_signals", "custom"}
        if node.data_source not in known_sources:
            errors.append(f"Unknown data_source: {node.data_source}")

    elif isinstance(node, ConditionNode):
        if not node.rules:
            errors.append("ConditionNode has no rules")
        for rule in node.rules:
            _validate_node(rule, errors, depth + 1)
