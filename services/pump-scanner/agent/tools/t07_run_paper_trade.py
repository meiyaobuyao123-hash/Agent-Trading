"""
T07 run_paper_trade — 模拟盘开/平仓

引用 docs/agent-pm/05-tool-catalog.md T07
引用 docs/agent-pm/17-tech-plan.md Phase 1
复用 agent/paper_engine.py:open_position / close_position

输入:action(buy/sell) + strategy_id + token + chain + price + amount_usd
     buy 还需:sl_pct + tp_pct(止损止盈百分比)
     sell 需:trade_id(关联开仓)
输出:trade row(含模拟滑点应用后的 entry/exit_price)

side_effects=DB_WRITE,permission=DEVICE_ONLY,non-idempotent
"""
from __future__ import annotations
import logging
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)


class RunPaperTradeTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="run_paper_trade",
            description=(
                "模拟盘开/平仓。"
                "action=buy:需 strategy_id, user_id, token_address, token_symbol, "
                "chain, price, amount_usd, sl_pct, tp_pct;"
                "action=sell:需 trade_id + price + reason。"
                "买入价上浮 1.5%(模拟市价滑点),卖出价下浮 1.5%。"
                "返回 paper_trade row 含模拟成交价。"
            ),
            idempotent=False,
            idempotency_key_fields=["strategy_id", "token_address", "trigger_event_id"],
            side_effects=SideEffect.DB_WRITE,
            p95_latency_ms=400,
            cost_usd=0.0,
            permission=Permission.DEVICE_ONLY,
            failure_modes=[
                "INPUT_SCHEMA_INVALID",
                "TRADE_OPEN_FAILED",
                "TRADE_NOT_FOUND",
                "DB_WRITE_FAILED",
            ],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["buy", "sell"]},
                # Common
                "strategy_id": {"type": "string"},
                "user_id": {"type": "string"},
                "chain": {"type": "string"},
                "price": {"type": "number", "exclusiveMinimum": 0},
                # buy only
                "token_address": {"type": "string"},
                "token_symbol": {"type": "string"},
                "amount_usd": {"type": "number", "exclusiveMinimum": 0},
                "sl_pct": {"type": "number"},
                "tp_pct": {"type": "number"},
                "trigger_context": {"type": "object"},
                # sell only
                "trade_id": {"type": "string"},
                "exit_reason": {"type": "string"},
            },
            "required": ["action", "price"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "trade": {"type": ["object", "null"]},
                "action": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["ok", "action"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        from agent.paper_engine import get_paper_engine
        engine = get_paper_engine()
        action = payload["action"]

        if action == "buy":
            required = ("strategy_id", "user_id", "token_address",
                        "token_symbol", "chain", "amount_usd", "sl_pct", "tp_pct")
            missing = [k for k in required if k not in payload]
            if missing:
                return {"ok": False, "action": action,
                        "reason": f"missing buy params: {missing}"}
            trade = await engine.open_position(
                strategy_id=payload["strategy_id"],
                user_id=payload["user_id"],
                token_address=payload["token_address"],
                token_symbol=payload["token_symbol"],
                chain=payload["chain"],
                price=float(payload["price"]),
                amount_usd=float(payload["amount_usd"]),
                sl_pct=float(payload["sl_pct"]),
                tp_pct=float(payload["tp_pct"]),
                trigger_context=payload.get("trigger_context"),
            )
            if trade is None:
                return {"ok": False, "action": action, "reason": "open_position_failed"}
            return {"ok": True, "trade": trade, "action": "buy", "reason": "opened"}

        # action == sell
        if "trade_id" not in payload:
            return {"ok": False, "action": action, "reason": "trade_id required for sell"}
        trade = await engine.close_position(
            trade_id=payload["trade_id"],
            exit_price=float(payload["price"]),
            exit_reason=payload.get("exit_reason", "manual"),
        )
        if trade is None:
            return {"ok": False, "action": action, "reason": "close_position_failed_or_not_found"}
        return {"ok": True, "trade": trade, "action": "sell", "reason": "closed"}
