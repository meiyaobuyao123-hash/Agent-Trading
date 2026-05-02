"""
T03 query_onchain_activity — 查询代币链上活动(读 smart_money_signals 表)

引用 docs/agent-pm/05-tool-catalog.md T03
引用 services/pump-scanner/smart_money_tracker.py(SOL 5222 + EVM 10540 钱包追踪写入此表)

input:
  chain: "solana" | "eth" | "bsc" | "base"
  token_address: 代币合约
  window_hours: 24(后端聚合窗口已是 6h,这里仅做返参标识,不影响查询)

output:
  ok: bool
  smart_money_net_usd: net_flow(buy_volume - sell_volume,USD)
  elite_buy_count / elite_sell_count
  buy_count / sell_count / unique_buyers
  signal_strength: "weak" | "medium" | "strong"
  heat_score: int
  big_buy_warning: bool(elite_buy_count >= 3 AND net_flow > 0)
  reason

side_effects=DB_QUERY / idempotent=True / cost=0 / permission=PUBLIC
"""
from __future__ import annotations
import logging
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)

VALID_CHAINS = ("solana", "eth", "bsc", "base")


class QueryOnchainActivityTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="query_onchain_activity",
            description=(
                "查询代币 24h 链上活动(读 smart_money_signals 表,SOL 5222 + EVM 10540 "
                "聪明钱钱包写入)。"
                "返 net_flow(USD)/ elite_buy_count / unique_buyers / signal_strength /"
                " big_buy_warning(elite_buy >= 3 + net+ → True)。"
                "用于 S03 onchain-analysis 评估资金动向。"
            ),
            idempotent=True,
            idempotency_key_fields=["chain", "token_address"],
            side_effects=SideEffect.NONE,
            p95_latency_ms=500,
            cost_usd=0.0,
            permission=Permission.PUBLIC,
            failure_modes=[
                "INPUT_SCHEMA_INVALID",
                "DB_QUERY_FAILED",
                "EMPTY_RESULT",
            ],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "enum": list(VALID_CHAINS)},
                "token_address": {"type": "string", "minLength": 1},
                "window_hours": {"type": "integer", "minimum": 1, "maximum": 168},
            },
            "required": ["chain", "token_address"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "smart_money_net_usd": {"type": "number"},
                "elite_buy_count": {"type": "integer"},
                "elite_sell_count": {"type": "integer"},
                "buy_count": {"type": "integer"},
                "sell_count": {"type": "integer"},
                "unique_buyers": {"type": "integer"},
                "signal_strength": {"type": "string"},
                "heat_score": {"type": "integer"},
                "big_buy_warning": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["ok", "smart_money_net_usd", "signal_strength", "big_buy_warning"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        chain = payload["chain"]
        token_address = payload["token_address"]

        try:
            from database import get_db
            db = get_db()
            r = db.table("smart_money_signals").select("*") \
                .eq("chain", chain).eq("token_address", token_address) \
                .limit(1).execute()
            rows = r.data or []
        except Exception as e:
            log.warning("[T03] DB query %s/%s failed: %s",
                        chain, token_address, e)
            return self._empty(chain, token_address, f"db_query_failed: {e}")

        if not rows:
            return self._empty(chain, token_address, "empty_result")

        row = rows[0]
        net_flow = float(row.get("net_flow") or 0)
        elite_buy = int(row.get("elite_buy_count") or 0)
        elite_sell = int(row.get("elite_sell_count") or 0)
        # big_buy_warning:elite_buy ≥ 3 且净流入为正
        big_buy = (elite_buy >= 3) and (net_flow > 0)

        return {
            "ok": True,
            "smart_money_net_usd": net_flow,
            "elite_buy_count": elite_buy,
            "elite_sell_count": elite_sell,
            "buy_count": int(row.get("buy_count") or 0),
            "sell_count": int(row.get("sell_count") or 0),
            "unique_buyers": int(row.get("unique_buyers") or 0),
            "signal_strength": row.get("signal_strength") or "weak",
            "heat_score": int(row.get("heat_score") or 0),
            "big_buy_warning": big_buy,
            "reason": "ok",
        }

    @staticmethod
    def _empty(chain: str, token_address: str, reason: str) -> dict:
        return {
            "ok": False,
            "smart_money_net_usd": 0.0,
            "elite_buy_count": 0, "elite_sell_count": 0,
            "buy_count": 0, "sell_count": 0, "unique_buyers": 0,
            "signal_strength": "weak", "heat_score": 0,
            "big_buy_warning": False,
            "reason": reason,
        }
