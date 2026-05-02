"""
T01 query_market — 查询代币行情(包装 okx_market_client)

引用 docs/agent-pm/05-tool-catalog.md T01
引用 services/pump-scanner/okx_market_client.py(已有 OKX DEX API 接通)

input:
  action: "price" | "basic" | "candles" | "toplist"
  chain: "solana" | "eth" | "bsc" | "base"
  token_address: 代币合约地址(price/basic/candles 必填)
  bar: K 线时间帧(candles 用)默认 "1H"
  limit: 返回条数(candles/toplist 用)默认 100
  sort_by: toplist 排序("0"=mcap, "2"=change, "5"=volume)默认 "5"
  time_frame: toplist 时间帧("1"=5m, "2"=1h, "4"=24h)默认 "4"

output:
  ok: bool
  data: dict | list(action 不同结构不同)
  reason: str

side_effects=NONE / idempotent=True / cost=0 / permission=PUBLIC
"""
from __future__ import annotations
import logging
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)

VALID_ACTIONS = ("price", "basic", "candles", "toplist")
VALID_CHAINS = ("solana", "eth", "bsc", "base")


class QueryMarketTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="query_market",
            description=(
                "查询代币行情数据(OKX DEX API)。"
                "action=price:批量行情(lastPriceUsd/marketCap/volume24H/change24H 等);"
                "action=basic:基础信息(symbol/decimals/totalSupply);"
                "action=candles:K 线(默认 1H × 100 根);"
                "action=toplist:某链 token 榜单(默认按 24h 成交量排)。"
                "chain=solana/eth/bsc/base。"
            ),
            idempotent=True,
            idempotency_key_fields=["action", "chain", "token_address", "bar"],
            side_effects=SideEffect.NONE,
            p95_latency_ms=2000,
            cost_usd=0.0,
            permission=Permission.PUBLIC,
            failure_modes=[
                "INPUT_SCHEMA_INVALID",
                "OKX_API_ERROR",
                "CHAIN_UNSUPPORTED",
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
                "action": {"type": "string", "enum": list(VALID_ACTIONS)},
                "chain": {"type": "string", "enum": list(VALID_CHAINS)},
                "token_address": {"type": "string"},
                "bar": {
                    "type": "string",
                    "enum": ["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W", "1M"],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                "sort_by": {"type": "string"},
                "time_frame": {"type": "string"},
            },
            "required": ["action", "chain"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "action": {"type": "string"},
                "chain": {"type": "string"},
                "data": {"type": ["object", "array", "null"]},
                "reason": {"type": "string"},
            },
            "required": ["ok", "action", "chain"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        action = payload["action"]
        chain = payload["chain"]
        token_address = payload.get("token_address", "")

        # 映射 chain → OKX chain_index
        try:
            from config import OKX_CHAIN_INDEX
            chain_index = OKX_CHAIN_INDEX.get(chain)
        except Exception as e:
            return {
                "ok": False, "action": action, "chain": chain,
                "data": None, "reason": f"config import failed: {e}",
            }
        if chain_index is None:
            return {
                "ok": False, "action": action, "chain": chain,
                "data": None, "reason": f"chain_unsupported: {chain}",
            }

        try:
            if action == "price":
                if not token_address:
                    return {"ok": False, "action": action, "chain": chain,
                            "data": None, "reason": "token_address required for price"}
                from okx_market_client import batch_price_info
                result = await batch_price_info(chain_index, [token_address])
                # batch_price_info 返 {addr_lower: dict};单 token 解包
                addr_lower = token_address.lower()
                token_data = result.get(addr_lower)
                if token_data is None:
                    return {"ok": False, "action": action, "chain": chain,
                            "data": None, "reason": "empty_result"}
                return {"ok": True, "action": action, "chain": chain,
                        "data": token_data, "reason": "ok"}

            elif action == "basic":
                if not token_address:
                    return {"ok": False, "action": action, "chain": chain,
                            "data": None, "reason": "token_address required for basic"}
                from okx_market_client import get_basic_info
                result = await get_basic_info(chain_index, [token_address])
                addr_lower = token_address.lower()
                token_data = result.get(addr_lower) if isinstance(result, dict) else None
                if token_data is None:
                    return {"ok": False, "action": action, "chain": chain,
                            "data": None, "reason": "empty_result"}
                return {"ok": True, "action": action, "chain": chain,
                        "data": token_data, "reason": "ok"}

            elif action == "candles":
                if not token_address:
                    return {"ok": False, "action": action, "chain": chain,
                            "data": None, "reason": "token_address required for candles"}
                from okx_market_client import get_candles
                bar = payload.get("bar", "1H")
                limit = int(payload.get("limit", 100))
                candles = await get_candles(chain_index, token_address, bar=bar, limit=limit)
                if not candles:
                    return {"ok": False, "action": action, "chain": chain,
                            "data": [], "reason": "empty_result"}
                return {"ok": True, "action": action, "chain": chain,
                        "data": candles, "reason": "ok"}

            elif action == "toplist":
                from okx_market_client import get_toplist
                sort_by = payload.get("sort_by", "5")    # 5 = 24h volume
                time_frame = payload.get("time_frame", "4")  # 4 = 24h
                limit = int(payload.get("limit", 100))
                items = await get_toplist(
                    chain_index, sort_by=sort_by, time_frame=time_frame,
                )
                items = items[:limit] if limit and items else items
                if not items:
                    return {"ok": False, "action": action, "chain": chain,
                            "data": [], "reason": "empty_result"}
                return {"ok": True, "action": action, "chain": chain,
                        "data": items, "reason": "ok"}

            else:
                return {"ok": False, "action": action, "chain": chain,
                        "data": None, "reason": f"unknown_action: {action}"}

        except Exception as e:
            log.warning("[T01] %s %s failed: %s", action, chain, e)
            return {"ok": False, "action": action, "chain": chain,
                    "data": None, "reason": f"okx_api_error: {e}"}
