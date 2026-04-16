"""
策略模板定义 (PRD-008 M2)

5 个预设策略模板：
  1. meme_sniper    — MEME 早期狙击
  2. hot_breakout   — 热币追涨
  3. smart_money_follow — 聪明钱跟单
  4. kol_sentiment  — KOL 舆情
  5. conservative_dca — 保守定投

支持参数覆盖（v1.1 Q4）：用户可修改金额/止损/止盈等。

Python 3.9 兼容。
"""
import copy
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# 模板定义
# ══════════════════════════════════════════════════════════════

STRATEGY_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "meme_sniper": {
        "name": "MEME 早期狙击",
        "description": "在 pump.fun 代币早期阶段（BC 5-15%）发现聪明钱介入的高分代币",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"data_source": "pump_tokens", "field": "bc_progress", "operator": ">=", "value": 5},
                {"data_source": "pump_tokens", "field": "bc_progress", "operator": "<=", "value": 15},
                {"data_source": "pump_tokens", "field": "smart_money_count", "operator": ">=", "value": 2},
                {"data_source": "pump_tokens", "field": "score", "operator": ">=", "value": 70},
            ],
        },
        "actions": [{"type": "buy", "amount_usd": 50}],
        "filters": {"chains": ["solana"]},
        "risk_params": {"stop_loss_pct": 25, "take_profit_pct": 100},
        "cooldown_minutes": 30,
    },
    "hot_breakout": {
        "name": "热币追涨",
        "description": "捕捉 hot score 高且 24h 涨幅超 30% 的热币",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"data_source": "hot_coins", "field": "score", "operator": ">=", "value": 65},
                {"data_source": "hot_coins", "field": "price_change_24h", "operator": ">", "value": 30},
                {"data_source": "hot_coins", "field": "volume_24h_usd", "operator": ">=", "value": 50000},
            ],
        },
        "actions": [{"type": "buy", "amount_usd": 80}],
        "filters": {"chains": ["solana", "bsc", "base", "eth"]},
        "risk_params": {"stop_loss_pct": 20, "take_profit_pct": 80},
        "cooldown_minutes": 60,
    },
    "smart_money_follow": {
        "name": "聪明钱跟单",
        "description": "跟踪 elite/verified 级聪明钱钱包买入信号，流动性需 > $50K",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"data_source": "smart_money_signals", "field": "wallet_tier", "operator": "in", "value": ["elite", "verified"]},
                {"data_source": "smart_money_signals", "field": "action", "operator": "==", "value": "buy"},
                {"data_source": "smart_money_signals", "field": "liquidity_usd", "operator": ">", "value": 50000},
            ],
        },
        "actions": [{"type": "buy", "amount_usd": 60}],
        "filters": {"chains": ["solana", "bsc", "base", "eth"]},
        "risk_params": {"stop_loss_pct": 30, "take_profit_pct": 150},
        "cooldown_minutes": 30,
    },
    "kol_sentiment": {
        "name": "KOL 舆情",
        "description": "3+ KOL 同时提及、正面情绪、score > 50 时买入",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"data_source": "kol_mentions", "field": "mention_count_2h", "operator": ">=", "value": 3},
                {"data_source": "kol_mentions", "field": "avg_sentiment", "operator": ">", "value": 0.5},
                {"data_source": "kol_mentions", "field": "score", "operator": ">", "value": 50},
            ],
        },
        "actions": [{"type": "buy", "amount_usd": 40}],
        "filters": {"chains": ["solana", "bsc", "base", "eth"]},
        "risk_params": {"stop_loss_pct": 20, "take_profit_pct": 60},
        "cooldown_minutes": 120,
    },
    "conservative_dca": {
        "name": "保守定投",
        "description": "每日 UTC 10:00、BTC 恐慌指数 < 40 时定投买入",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"data_source": "market_indicators", "field": "fear_greed_index", "operator": "<", "value": 40},
                {"data_source": "schedule", "field": "cron", "operator": "==", "value": "0 10 * * *"},
            ],
        },
        "actions": [{"type": "buy", "amount_usd": 20}],
        "filters": {"chains": ["solana"]},
        "risk_params": {"stop_loss_pct": 15, "take_profit_pct": 50},
        "cooldown_minutes": 1440,  # 24h
    },
}

# 允许通过 override 修改的字段白名单
OVERRIDABLE_FIELDS = {
    "amount_usd",
    "stop_loss_pct",
    "take_profit_pct",
    "cooldown_minutes",
    "chains",
}


# ══════════════════════════════════════════════════════════════
# API
# ══════════════════════════════════════════════════════════════

def list_templates() -> List[Dict[str, Any]]:
    """返回所有模板的简要信息"""
    result = []
    for tid, tpl in STRATEGY_TEMPLATES.items():
        result.append({
            "id": tid,
            "name": tpl["name"],
            "description": tpl["description"],
            "risk_params": tpl.get("risk_params", {}),
            "actions": tpl.get("actions", []),
            "filters": tpl.get("filters", {}),
            "cooldown_minutes": tpl.get("cooldown_minutes", 30),
        })
    return result


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """获取单个模板的完整定义"""
    tpl = STRATEGY_TEMPLATES.get(template_id)
    if tpl is None:
        return None
    return {"id": template_id, **copy.deepcopy(tpl)}


def create_from_template(
    template_id: str,
    user_id: str,
    override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    从模板创建策略规范（v1.1 Q4: 支持参数覆盖）

    Args:
        template_id: 模板 ID
        user_id: 用户 UUID
        override: 可选覆盖参数 {amount_usd, stop_loss_pct, take_profit_pct, ...}

    Returns:
        用于 StrategyManager.create_strategy() 的 spec dict

    Raises:
        ValueError: 模板不存在或 override 参数无效
    """
    if template_id not in STRATEGY_TEMPLATES:
        raise ValueError(f"模板不存在: {template_id}")

    template = copy.deepcopy(STRATEGY_TEMPLATES[template_id])

    if override:
        # 验证 override 中的字段在白名单内
        invalid_keys = set(override.keys()) - OVERRIDABLE_FIELDS
        if invalid_keys:
            log.warning(
                "Template override ignored invalid keys: %s", invalid_keys
            )

        if "amount_usd" in override:
            amount = float(override["amount_usd"])
            if amount < 1 or amount > 10000:
                raise ValueError("amount_usd 必须在 $1 ~ $10000 之间")
            template["actions"][0]["amount_usd"] = amount

        if "stop_loss_pct" in override:
            sl = float(override["stop_loss_pct"])
            if sl < 1 or sl > 100:
                raise ValueError("stop_loss_pct 必须在 1% ~ 100% 之间")
            template["risk_params"]["stop_loss_pct"] = sl

        if "take_profit_pct" in override:
            tp = float(override["take_profit_pct"])
            if tp < 1 or tp > 10000:
                raise ValueError("take_profit_pct 必须在 1% ~ 10000% 之间")
            template["risk_params"]["take_profit_pct"] = tp

        if "cooldown_minutes" in override:
            cd = int(override["cooldown_minutes"])
            template["cooldown_minutes"] = max(cd, 5)

        if "chains" in override:
            template["filters"]["chains"] = override["chains"]

    # 默认 paper 模式
    template["mode"] = "paper"
    template["template_id"] = template_id

    # 构造 strategy_manager 需要的 spec 格式
    spec = {
        "name": template["name"],
        "description": template["description"],
        "conditions": template["conditions"],
        "actions": template["actions"],
        "filters": template.get("filters", {}),
        "risk_params": template.get("risk_params", {}),
        "cooldown_minutes": template.get("cooldown_minutes", 30),
    }

    return spec
