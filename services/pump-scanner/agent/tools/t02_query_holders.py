"""
T02 query_holders — 查询代币持有人分布(包装 hot_coin_fetcher.fetch_top_holders)

引用 docs/agent-pm/05-tool-catalog.md T02
引用 services/pump-scanner/hot_coin_fetcher.py:fetch_top_holders
  (SOL 走 Helius getTokenLargestAccounts;EVM 走 GoPlus holders)

input:
  chain: "solana" | "eth" | "bsc" | "base"
  token_address: 代币合约
  limit: top N(默认 10,最大 50)

output:
  ok: bool
  top_holders: [{rank, wallet, pct, amount}]
  top10_pct: 前 10 持仓百分比之和
  total_holders: int(可能为 0 — 需配合 query_market 拿)
  concentration_warning: bool(top10_pct > 60% → True,rug 风险高)
  reason: str

side_effects=NONE / idempotent=True / cost=0 / permission=PUBLIC
"""
from __future__ import annotations
import logging
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)

VALID_CHAINS = ("solana", "eth", "bsc", "base")
CONCENTRATION_RED_LINE = 0.60  # top10 > 60% 红线


class QueryHoldersTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="query_holders",
            description=(
                "查询代币持有人分布(SOL 走 Helius / EVM 走 GoPlus)。"
                "返 top N 持仓地址 + 占比 + top10 集中度 + concentration_warning(>60% 红线)。"
                "用于 S03 onchain-analysis 评估 rug 风险。"
            ),
            idempotent=True,
            idempotency_key_fields=["chain", "token_address", "limit"],
            side_effects=SideEffect.NONE,
            p95_latency_ms=3000,
            cost_usd=0.0,
            permission=Permission.PUBLIC,
            failure_modes=[
                "INPUT_SCHEMA_INVALID",
                "HELIUS_API_ERROR",
                "GOPLUS_API_ERROR",
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
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["chain", "token_address"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "top_holders": {"type": "array"},
                "top10_pct": {"type": "number"},
                "total_holders": {"type": "integer"},
                "concentration_warning": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["ok", "top_holders", "top10_pct", "concentration_warning"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        chain = payload["chain"]
        token_address = payload["token_address"]
        limit = int(payload.get("limit", 10))

        try:
            from hot_coin_fetcher import fetch_top_holders
            holders = await fetch_top_holders(chain, token_address, limit=limit)
        except Exception as e:
            log.warning("[T02] fetch_top_holders %s/%s failed: %s",
                        chain, token_address, e)
            return {
                "ok": False, "top_holders": [], "top10_pct": 0.0,
                "total_holders": 0, "concentration_warning": False,
                "reason": f"fetch_failed: {e}",
            }

        if not holders:
            return {
                "ok": False, "top_holders": [], "top10_pct": 0.0,
                "total_holders": 0, "concentration_warning": False,
                "reason": "empty_result",
            }

        # 算 top10 集中度
        top10_pct = sum(float(h.get("pct") or 0) for h in holders[:10])
        # holders 列表的 pct 通常是 0-100;若返 0-1 比例,自动归一化
        if top10_pct <= 1.0 and any((h.get("pct") or 0) > 0 for h in holders):
            top10_pct *= 100  # 防御:某些返 0-1
        warning = top10_pct > (CONCENTRATION_RED_LINE * 100)

        return {
            "ok": True,
            "top_holders": holders,
            "top10_pct": round(top10_pct, 2),
            "total_holders": 0,  # fetch_top_holders 不返 total,留 query_market 拿
            "concentration_warning": warning,
            "reason": "ok",
        }
