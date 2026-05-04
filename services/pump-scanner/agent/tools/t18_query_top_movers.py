"""
T18 query_top_movers — 查询某窗口内涨幅 Top N 代币
引用 docs/agent-pm/05-tool-catalog.md §4.18(R39 加)

回答 chat 类问题:
  - "pump.fun 上近期表现优异的代币"
  - "哪些币涨得好"
  - "24h top gainers"
  - "热币榜单"

数据源:
  - hot_coins 表(多链热币 + price_change_5m/1h/6h/24h/4h)
  - pump_signals 表(pump.fun BC 3-35% 信号)
  - source=all 时 union 两边

input:
  source: "pump" | "hot" | "all"      默认 "all"
  chain:  "solana" | "eth" | "bsc" | "base" | "all"   默认 "all"
  window: "5m" | "1h" | "6h" | "24h"  默认 "24h"
  limit:  整数 1-50                    默认 10
  min_volume_usd: 数值                 默认 1000
  sort_by: "pct_change" | "volume" | "score"  默认 "pct_change"

output:
  ok: bool
  items: [{ rank, symbol, name, address, chain, source,
            pct_change, volume_usd, mcap_usd, liquidity_usd, score }]
  window: str
  total: int
  source_used: str
  reason?: str

side_effects=NONE / idempotent=True / cost=0 / permission=PUBLIC
"""
from __future__ import annotations
import logging
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)

VALID_SOURCES = ("pump", "hot", "all")
VALID_CHAINS = ("solana", "eth", "bsc", "base", "all")
VALID_WINDOWS = ("5m", "1h", "6h", "24h")
VALID_SORT = ("pct_change", "volume", "score")

# window → hot_coins 字段名映射
WINDOW_TO_PCT_FIELD = {
    "5m": "price_change_5m",
    "1h": "price_change_1h",
    "6h": "price_change_6h",
    "24h": "price_change_24h",
}
WINDOW_TO_VOL_FIELD = {
    "5m": "volume_5m_usd",
    "1h": "volume_1h_usd",
    "6h": None,            # hot_coins 无 6h volume,fallback 24h
    "24h": "volume_24h_usd",
}


class QueryTopMoversTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="query_top_movers",
            description=(
                "查询某窗口内涨幅 Top N 代币(支持 pump.fun BC 信号 / 多链热币 / 全部)。"
                "回答 '哪些币涨得好' / 'pump.fun top movers' / '近期表现优异的代币' 等问题。"
                "source=pump:pump.fun BC 3-35% 信号;"
                "source=hot:多链热币(SOL/ETH/BSC/Base);"
                "source=all:union 两边;"
                "window=5m/1h/6h/24h;"
                "sort_by=pct_change(默认)|volume|score。"
            ),
            idempotent=True,
            idempotency_key_fields=["source", "chain", "window", "limit", "sort_by"],
            side_effects=SideEffect.NONE,
            p95_latency_ms=400,
            cost_usd=0.0,
            permission=Permission.PUBLIC,
            failure_modes=[
                "INPUT_SCHEMA_INVALID",
                "DB_ERROR",
                "EMPTY_RESULT",
            ],
            owner="agent-team",
            version="0.1",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"enum": list(VALID_SOURCES), "default": "all"},
                "chain": {"enum": list(VALID_CHAINS), "default": "all"},
                "window": {"enum": list(VALID_WINDOWS), "default": "24h"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                "min_volume_usd": {"type": "number", "minimum": 0, "default": 1000},
                "sort_by": {"enum": list(VALID_SORT), "default": "pct_change"},
            },
            "additionalProperties": False,
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "items": {"type": "array"},
                "window": {"type": "string"},
                "total": {"type": "integer"},
                "source_used": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["ok", "items", "window", "total", "source_used"],
        }

    async def _execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        source = payload.get("source", "all")
        chain = payload.get("chain", "all")
        window = payload.get("window", "24h")
        limit = payload.get("limit", 10)
        min_vol = float(payload.get("min_volume_usd", 1000))
        sort_by = payload.get("sort_by", "pct_change")

        items: list[dict[str, Any]] = []

        # ── 查 hot_coins(支持 source=hot 或 all)─────
        if source in ("hot", "all"):
            try:
                items.extend(self._query_hot_coins(chain, window, min_vol, sort_by))
            except Exception as e:
                log.warning("[T18] hot_coins query fail: %s", e)

        # ── 查 pump_signals(支持 source=pump 或 all)──
        if source in ("pump", "all"):
            try:
                items.extend(self._query_pump_signals(chain, window, min_vol))
            except Exception as e:
                log.warning("[T18] pump_signals query fail: %s", e)

        if not items:
            return {
                "ok": True,
                "items": [],
                "window": window,
                "total": 0,
                "source_used": source,
                "reason": "no data in window/source/chain filter",
            }

        # 全局排序
        sort_key = self._build_sort_key(sort_by, window)
        items.sort(key=sort_key, reverse=True)

        # 限量 + 加 rank
        items = items[:limit]
        for i, it in enumerate(items, start=1):
            it["rank"] = i

        return {
            "ok": True,
            "items": items,
            "window": window,
            "total": len(items),
            "source_used": source,
        }

    # ── helpers ────────────────────────────────────

    def _query_hot_coins(
        self, chain: str, window: str, min_vol: float, sort_by: str,
    ) -> list[dict[str, Any]]:
        """从 hot_coins 表读多链热币,filter + project。"""
        from database import get_db
        db = get_db()

        pct_field = WINDOW_TO_PCT_FIELD[window]
        vol_field = WINDOW_TO_VOL_FIELD.get(window) or "volume_24h_usd"

        # 每链各取 top,然后 union
        chains = ["solana", "eth", "bsc", "base"] if chain == "all" else [chain]
        all_rows: list[dict[str, Any]] = []
        for c in chains:
            try:
                q = (
                    db.table("hot_coins")
                    .select(
                        "chain,address,symbol,name,score,price_usd,"
                        "market_cap_usd,liquidity_usd,"
                        "price_change_5m,price_change_1h,price_change_6h,price_change_24h,"
                        "volume_5m_usd,volume_1h_usd,volume_24h_usd,"
                        "goplus_risk,is_honeypot"
                    )
                    .eq("chain", c)
                    .eq("goplus_risk", False)
                    .eq("is_honeypot", False)
                    .gte(vol_field, min_vol)
                    .not_.is_(pct_field, "null")
                    .order(pct_field if sort_by == "pct_change" else "score", desc=True)
                    .limit(30)
                    .execute()
                )
                all_rows.extend(q.data or [])
            except Exception as e:
                log.debug("[T18] hot chain=%s fail: %s", c, e)

        # project 成统一 schema
        out = []
        for r in all_rows:
            pct = r.get(pct_field)
            if pct is None:
                continue
            out.append({
                "symbol": r.get("symbol"),
                "name": r.get("name"),
                "address": r.get("address"),
                "chain": r.get("chain"),
                "source": "hot",
                "pct_change": float(pct),
                "volume_usd": float(r.get(vol_field) or 0),
                "mcap_usd": float(r.get("market_cap_usd") or 0),
                "liquidity_usd": float(r.get("liquidity_usd") or 0),
                "score": float(r.get("score") or 0),
                "price_usd": float(r.get("price_usd") or 0),
            })
        return out

    def _query_pump_signals(
        self, chain: str, window: str, min_vol: float,
    ) -> list[dict[str, Any]]:
        """从 pump_signals 表读 pump.fun 信号。
        注:pump_signals 是 SOL only(pump.fun 不存在其他链),chain=eth/bsc/base 时返空。
        """
        if chain not in ("solana", "all"):
            return []
        from database import get_db
        db = get_db()
        try:
            q = (
                db.table("pump_signals")
                .select(
                    "address,symbol,name,score,price_usd,market_cap_usd,"
                    "volume_24h_usd,price_change_24h,bonding_curve_pct,detected_at"
                )
                .order("score", desc=True)
                .limit(30)
                .execute()
            )
            rows = q.data or []
        except Exception as e:
            log.debug("[T18] pump query fail: %s", e)
            return []

        # window 不 filter pump_signals(它是实时 BC 3-35% 信号,固有时效 minutes 级)
        out = []
        for r in rows:
            vol = float(r.get("volume_24h_usd") or 0)
            if vol < min_vol:
                continue
            out.append({
                "symbol": r.get("symbol"),
                "name": r.get("name"),
                "address": r.get("address"),
                "chain": "solana",
                "source": "pump",
                "pct_change": float(r.get("price_change_24h") or 0),
                "volume_usd": vol,
                "mcap_usd": float(r.get("market_cap_usd") or 0),
                "liquidity_usd": 0,  # pump_signals 不带 liquidity
                "score": float(r.get("score") or 0),
                "price_usd": float(r.get("price_usd") or 0),
                "bonding_curve_pct": float(r.get("bonding_curve_pct") or 0),
                "detected_at": r.get("detected_at"),
            })
        return out

    @staticmethod
    def _build_sort_key(sort_by: str, _window: str):
        if sort_by == "volume":
            return lambda x: x.get("volume_usd") or 0
        if sort_by == "score":
            return lambda x: x.get("score") or 0
        # default pct_change
        return lambda x: x.get("pct_change") or 0
