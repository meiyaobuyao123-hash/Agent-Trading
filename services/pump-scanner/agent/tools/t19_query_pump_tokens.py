"""
T19 query_pump_tokens — pump.fun 实时新币信号池专属深度查询(R68 加)
引用 docs/agent-pm/05-tool-catalog.md §4.19

回答 chat 类问题:
  - "pump.fun 最新有什么"
  - "pump 新币榜"
  - "毕业进度 10-20% 的"
  - "刚冒头评分 > 70 的"
  - "BC 3-35% 的早期信号"

跟 T18 query_top_movers 区别:
  - T18 是**综合 top movers**(hot_coins + pump_signals union,按涨幅排序为主)
  - T19 是 **pump.fun 专属深度**:暴露 pump 特有元数据(bonding_curve_pct / score /
    detected_at / age_minutes),只在 SOL 链,过滤 BC 范围,按 score 或 BC 进度排序
  - 数据源:跟 routes_pump.py /api/pump/signals 同一份(scanner in-memory → Redis →
    文件兜底),5-60s 新鲜

input:
  min_score: int 0-100               默认 55(pump_scanner 默认筛选阈值)
  bc_min: float 0-100                默认 3   (毕业曲线下界 %)
  bc_max: float 0-100                默认 35  (毕业曲线上界 %)
  min_volume_usd: number             默认 1000
  limit: int 1-50                    默认 20
  sort_by: "score" | "bc_pct" | "volume" | "detected_age"   默认 "score"

output:
  ok: bool
  items: [{
    rank, symbol, name, address,
    score (0-100),
    bonding_curve_pct,
    price_usd,
    mcap_usd,
    volume_24h_usd,
    price_change_24h_pct,
    detected_at,
    age_minutes,
  }]
  total: int
  source_used: "scanner" | "redis" | "file" | "empty"
  is_history: bool        # True = 当前实时池空,展示最近 1h 历史回顾
  reason?: str

side_effects=NONE / idempotent=True / cost=0 / permission=PUBLIC
"""
from __future__ import annotations
import logging
import json
import os
from datetime import datetime, timezone
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)

VALID_SORT = ("score", "bc_pct", "volume", "detected_age")


class QueryPumpTokensTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="query_pump_tokens",
            description=(
                "查询 pump.fun 实时新币信号池(SOL only)— 暴露 pump.fun 专属元数据:"
                "毕业曲线进度 / 评分 / 检测时间 / 信号年龄。"
                "回答 'pump.fun 最新 / 毕业进度 X% / 刚冒头评分 > N / BC 早期信号' 等问题。"
                "默认筛选:score≥55, BC 3-35%(pump_scanner 早期信号定义)。"
                "数据 5-60s 新鲜(scanner in-memory → Redis → 文件兜底)。"
                "跟 query_top_movers 区别:本工具 pump-only,暴露 bonding_curve_pct / "
                "detected_at;query_top_movers 是综合多链 top movers。"
            ),
            idempotent=True,
            idempotency_key_fields=["min_score", "bc_min", "bc_max", "limit", "sort_by"],
            side_effects=SideEffect.NONE,
            p95_latency_ms=200,
            cost_usd=0.0,
            permission=Permission.PUBLIC,
            failure_modes=[
                "INPUT_SCHEMA_INVALID",
                "DATA_SOURCE_UNAVAILABLE",
                "EMPTY_RESULT",
            ],
            owner="agent-pm",
            version="0.1",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "min_score": {"type": "integer", "minimum": 0, "maximum": 100, "default": 55},
                "bc_min": {"type": "number", "minimum": 0, "maximum": 100, "default": 3},
                "bc_max": {"type": "number", "minimum": 0, "maximum": 100, "default": 35},
                "min_volume_usd": {"type": "number", "minimum": 0, "default": 1000},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                "sort_by": {"type": "string", "enum": list(VALID_SORT), "default": "score"},
            },
            "additionalProperties": False,
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rank": {"type": "integer"},
                            "symbol": {"type": ["string", "null"]},
                            "name": {"type": ["string", "null"]},
                            "address": {"type": ["string", "null"]},
                            "score": {"type": "number"},
                            "bonding_curve_pct": {"type": "number"},
                            "price_usd": {"type": "number"},
                            "mcap_usd": {"type": "number"},
                            "volume_24h_usd": {"type": "number"},
                            "price_change_24h_pct": {"type": "number"},
                            "detected_at": {"type": ["string", "null"]},
                            "age_minutes": {"type": ["number", "null"]},
                        },
                    },
                },
                "total": {"type": "integer"},
                "source_used": {"type": "string"},
                "is_history": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["ok", "items", "total", "source_used", "is_history"],
        }

    async def _execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        min_score = int(payload.get("min_score", 55))
        bc_min = float(payload.get("bc_min", 3))
        bc_max = float(payload.get("bc_max", 35))
        min_vol = float(payload.get("min_volume_usd", 1000))
        limit = int(payload.get("limit", 20))
        sort_by = payload.get("sort_by", "score")

        # ── 数据源:scanner in-memory → Redis → 文件 ─────────────────
        raw_signals, source, is_history = await self._fetch_signal_pool()

        if not raw_signals:
            return {
                "ok": True,
                "items": [],
                "total": 0,
                "source_used": source or "empty",
                "is_history": False,
                "reason": "pump.fun 当前无实时信号(可能市场偏冷 / 数据同步延迟)",
            }

        # ── filter + normalize ─────────────────────────────────────
        now = datetime.now(timezone.utc)
        filtered: list[dict[str, Any]] = []
        for s in raw_signals:
            score = float(s.get("score") or 0)
            bc_pct = float(s.get("bonding_curve_pct") or s.get("bc_pct") or 0)
            vol = float(s.get("volume_24h_usd") or s.get("vol_24h") or 0)
            if score < min_score:
                continue
            if bc_pct < bc_min or bc_pct > bc_max:
                continue
            if vol < min_vol:
                continue

            detected_at = s.get("detected_at") or s.get("created_at")
            age_min: float | None = None
            if detected_at:
                try:
                    ts = datetime.fromisoformat(str(detected_at).replace("Z", "+00:00"))
                    age_min = (now - ts).total_seconds() / 60.0
                except Exception:
                    age_min = None

            filtered.append({
                "symbol": s.get("symbol"),
                "name": s.get("name"),
                "address": s.get("address") or s.get("mint"),
                "score": score,
                "bonding_curve_pct": bc_pct,
                "price_usd": float(s.get("price_usd") or 0),
                "mcap_usd": float(s.get("market_cap_usd") or s.get("mcap_usd") or 0),
                "volume_24h_usd": vol,
                "price_change_24h_pct": float(s.get("price_change_24h") or 0),
                "detected_at": detected_at,
                "age_minutes": age_min,
            })

        # ── sort ───────────────────────────────────────────────────
        if sort_by == "score":
            filtered.sort(key=lambda x: x["score"], reverse=True)
        elif sort_by == "bc_pct":
            filtered.sort(key=lambda x: x["bonding_curve_pct"], reverse=True)
        elif sort_by == "volume":
            filtered.sort(key=lambda x: x["volume_24h_usd"], reverse=True)
        elif sort_by == "detected_age":
            # 最新检测(age 最小)排前
            filtered.sort(key=lambda x: x.get("age_minutes") or 1e9)

        filtered = filtered[:limit]
        for i, it in enumerate(filtered, start=1):
            it["rank"] = i

        return {
            "ok": True,
            "items": filtered,
            "total": len(filtered),
            "source_used": source,
            "is_history": is_history,
        }

    # ── 数据源读取(参考 routes_pump.py 路径)────────────────────
    async def _fetch_signal_pool(self) -> tuple[list[dict], str, bool]:
        """返回 (signals, source, is_history)。"""
        # 1. 同进程 scanner
        try:
            from scanner_ref import get_scanner
            scanner = get_scanner()
            if scanner is not None:
                signals = scanner.get_signals() or []
                is_hist = bool(signals and signals[0].get("is_history"))
                return signals, "scanner", is_hist
        except Exception as e:
            log.debug("[T19] scanner 不可用,降级 redis: %s", e)

        # 2. Redis
        try:
            from agent.redis_client import safe_get_async, KEY_PUMP_SIGNAL_POOL
            raw = await safe_get_async(KEY_PUMP_SIGNAL_POOL)
            if raw:
                data = json.loads(raw)
                signals = data.get("signals", []) or []
                is_hist = bool(data.get("is_history", False))
                return signals, "redis", is_hist
        except Exception as e:
            log.debug("[T19] redis 不可用,降级文件: %s", e)

        # 3. 文件兜底
        DUMP_PATH = "/tmp/pump_signal_pool.json"
        try:
            if os.path.exists(DUMP_PATH):
                with open(DUMP_PATH, "r") as f:
                    data = json.load(f)
                signals = data.get("signals", []) or []
                is_hist = bool(data.get("is_history", False))
                return signals, "file", is_hist
        except Exception as e:
            log.debug("[T19] 文件兜底失败: %s", e)

        return [], "empty", False
