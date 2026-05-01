"""
T06 update_strategy_status — 改策略状态(pause / activate / archive)

引用 docs/agent-pm/05-tool-catalog.md T06
引用 docs/agent-pm/17-tech-plan.md Phase 1
复用 agent/strategy_manager.py:update_strategy

输入:strategy_id + new_status
输出:ok + previous_status + new_status

幂等(同状态再切返 noop=True)/ db_write / device_only。
"""
from __future__ import annotations
import logging
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)

VALID_TRANSITIONS = {
    "active": ("paused", "archived"),
    "paused": ("active", "archived"),
    "archived": (),  # archived 是 terminal
    "draft": ("active", "archived"),
}


class UpdateStrategyStatusTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="update_strategy_status",
            description=(
                "改策略状态。允许的转移:"
                "active ↔ paused / active → archived / paused → archived / "
                "draft → active|archived。archived 是 terminal,不能再切。"
                "同状态再切返 noop=True(幂等)。"
            ),
            idempotent=True,
            idempotency_key_fields=["strategy_id", "new_status"],
            side_effects=SideEffect.DB_WRITE,
            p95_latency_ms=400,
            cost_usd=0.0,
            permission=Permission.DEVICE_ONLY,
            failure_modes=[
                "STRATEGY_NOT_FOUND",
                "INVALID_TRANSITION",
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
                "strategy_id": {"type": "string", "minLength": 1},
                "new_status": {
                    "type": "string",
                    "enum": ["active", "paused", "archived"],
                },
                "user_id": {"type": "string"},
            },
            "required": ["strategy_id", "new_status"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "strategy_id": {"type": "string"},
                "previous_status": {"type": ["string", "null"]},
                "new_status": {"type": "string"},
                "noop": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["ok", "strategy_id", "new_status", "noop"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        from agent.strategy_manager import StrategyManager
        from database import get_db

        sid = payload["strategy_id"]
        new_status = payload["new_status"]

        # 1. 拉当前 status
        try:
            cur = get_db().table("agent_strategies").select(
                "id, status, user_id"
            ).eq("id", sid).limit(1).execute()
        except Exception as e:
            log.warning("[T06] DB query failed: %s", e)
            return {
                "ok": False, "strategy_id": sid,
                "previous_status": None, "new_status": new_status,
                "noop": False, "reason": f"db_query_failed: {e}",
            }

        if not cur.data:
            return {
                "ok": False, "strategy_id": sid,
                "previous_status": None, "new_status": new_status,
                "noop": False, "reason": "strategy_not_found",
            }
        row = cur.data[0]
        prev = row.get("status", "active")

        # 2. 幂等
        if prev == new_status:
            return {
                "ok": True, "strategy_id": sid,
                "previous_status": prev, "new_status": new_status,
                "noop": True, "reason": "already_in_target_status",
            }

        # 3. 校验转移合法性
        allowed = VALID_TRANSITIONS.get(prev, ())
        if new_status not in allowed:
            return {
                "ok": False, "strategy_id": sid,
                "previous_status": prev, "new_status": new_status,
                "noop": False,
                "reason": f"invalid_transition: {prev} -> {new_status}",
            }

        # 4. 写入
        mgr = StrategyManager()
        result = mgr.update_strategy(sid, {"status": new_status})
        if result is None:
            return {
                "ok": False, "strategy_id": sid,
                "previous_status": prev, "new_status": new_status,
                "noop": False, "reason": "db_write_failed",
            }
        return {
            "ok": True, "strategy_id": sid,
            "previous_status": prev, "new_status": new_status,
            "noop": False, "reason": "updated",
        }
