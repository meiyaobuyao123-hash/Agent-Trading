"""
T05 list_strategies — 列出用户的策略

引用 docs/agent-pm/05-tool-catalog.md T05
引用 docs/agent-pm/17-tech-plan.md Phase 1
复用 agent/strategy_manager.py:list_strategies

输入:user_id + status 过滤(可选)
输出:strategies 列表(精简:id/name/status/mode/created_at)

幂等 / 无副作用 / device_only。
"""
from __future__ import annotations
from typing import Any, Dict, List

from .base import Tool, ToolMetadata, Permission, SideEffect


VALID_STATUS = ("active", "paused", "archived", "draft", "all")
VALID_MODE = ("paper", "notify", "auto")


class ListStrategiesTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="list_strategies",
            description=(
                "列出用户的策略。"
                "status 过滤:active / paused / archived / draft / all(默认 active)。"
                "返回精简字段(id, name, status, mode, created_at, last_triggered_at, "
                "trigger_count_total)。Agent 用此查策略数(配额检查)。"
            ),
            idempotent=True,
            idempotency_key_fields=[],
            side_effects=SideEffect.NONE,
            p95_latency_ms=300,
            cost_usd=0.0,
            permission=Permission.DEVICE_ONLY,
            failure_modes=["DB_QUERY_FAILED"],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "minLength": 1},
                "status": {"type": "string", "enum": list(VALID_STATUS)},
                "include_archived": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["user_id"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "strategies": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "count": {"type": "integer"},
                "active_count": {"type": "integer"},
            },
            "required": ["strategies", "count", "active_count"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        from agent.strategy_manager import StrategyManager
        mgr = StrategyManager()
        user_id = payload["user_id"]
        status_filter = payload.get("status", "active")
        limit = payload.get("limit", 50)

        # mgr.list_strategies status=None 表全部
        rows = mgr.list_strategies(
            user_id=user_id,
            status=None if status_filter in ("all", None) else status_filter,
        )

        slim = []
        active_count = 0
        for r in rows[:limit]:
            s = r.get("status") or "active"
            if s == "active":
                active_count += 1
            slim.append({
                "id": str(r.get("id", "")),
                "name": r.get("name", ""),
                "status": s,
                "mode": r.get("mode", "paper"),
                "data_sources": r.get("data_sources") or [],
                "created_at": r.get("created_at"),
                "last_triggered_at": r.get("last_triggered_at"),
                "trigger_count_total": int(r.get("trigger_count_total", 0) or 0),
                "cooldown_min": int(r.get("cooldown_min", 30) or 30),
            })
        return {
            "strategies": slim,
            "count": len(slim),
            "active_count": active_count,
        }
