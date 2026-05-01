"""
T11 approve_rule — 用户采纳规则提议 → 进入 14 天 Shadow Mode

引用 docs/agent-pm/05-tool-catalog.md T11
引用 docs/agent-pm/17-tech-plan.md Phase 1
引用 docs/agent-pm/06-memory-spec.md §3.3 Semantic 5 条硬晋升

设计:
  1. 写一条新 row 到 agent_memory(type=semantic, is_active=true,
     shadow_mode_until = now + 14d)
  2. 把 source proposal_id 记到 metadata.source_proposal_id
  3. 返回 promoted_rule_id

不调 reflection 表(reflection 真实施在 W7-W12);仅根据传入的
formal_condition + human_readable + active_regimes 直接写规则。

权限:device_only(用户主动采纳,不能跨用户)
副作用:DB 写入 agent_memory
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)

SHADOW_MODE_DAYS = 14


class ApproveRuleTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="approve_rule",
            description=(
                "用户采纳一条规则提议,把它写入 Semantic Memory 并进入 14 天 "
                "Shadow Mode(只观察不影响决策)。"
                "输入:proposal_id + human_readable + formal_condition "
                "(condition + action JSON)+ active_regimes(数组)。"
                "返回:promoted_rule_id + shadow_mode_until。"
            ),
            idempotent=True,  # 同 proposal_id 不重复写
            idempotency_key_fields=["proposal_id", "user_id"],
            side_effects=SideEffect.DB_WRITE,
            p95_latency_ms=300,
            cost_usd=0.0,
            permission=Permission.DEVICE_ONLY,
            failure_modes=[
                "PROPOSAL_ALREADY_PROMOTED",
                "DB_WRITE_FAILED",
                "DUPLICATE_CONDITION",
            ],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "minLength": 1},
                "proposal_id": {"type": "string", "minLength": 1},
                "human_readable": {
                    "type": "string", "minLength": 5, "maxLength": 500,
                },
                "formal_condition": {
                    "type": "object",
                    "properties": {
                        "condition": {"type": "string"},
                        "action": {"type": "string"},
                    },
                    "required": ["condition", "action"],
                },
                "active_regimes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "evidence": {
                    "type": "object",
                    "properties": {
                        "sample_size": {"type": "integer", "minimum": 0},
                        "win_rate_diff": {"type": "number"},
                        "wilson_ci_lower": {"type": ["number", "null"]},
                    },
                },
            },
            "required": [
                "user_id", "proposal_id", "human_readable", "formal_condition",
            ],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "promoted_rule_id": {"type": "string"},
                "shadow_mode_until": {"type": "string"},
                "shadow_mode_days": {"type": "integer"},
                "duplicate": {"type": "boolean"},
            },
            "required": ["ok", "promoted_rule_id", "shadow_mode_until", "shadow_mode_days"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        user_id = payload["user_id"]
        proposal_id = payload["proposal_id"]
        human_readable = payload["human_readable"]
        formal = payload["formal_condition"]
        active_regimes = payload.get("active_regimes", [])
        evidence = payload.get("evidence", {})

        now = datetime.now(timezone.utc)
        shadow_until = now + timedelta(days=SHADOW_MODE_DAYS)

        try:
            from database import get_db
            db = get_db()

            # 幂等检查:同 user + proposal_id 已写过则返 duplicate
            try:
                existing = (
                    db.table("agent_memory")
                    .select("id, shadow_mode_until")
                    .eq("user_id", user_id)
                    .eq("structured_data->>source_proposal_id", proposal_id)
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    row = existing.data[0]
                    return {
                        "ok": True,
                        "promoted_rule_id": str(row.get("id", "")),
                        "shadow_mode_until": str(row.get("shadow_mode_until") or shadow_until.isoformat()),
                        "shadow_mode_days": SHADOW_MODE_DAYS,
                        "duplicate": True,
                    }
            except Exception as e:
                # 幂等查询失败不阻断写入,只 warning
                log.debug("[T11] 幂等检查失败(忽略): %s", e)

            new_id = str(uuid.uuid4())
            row = {
                "id": new_id,
                "user_id": user_id,
                "type": "semantic",
                "content": human_readable,
                "structured_data": {
                    "condition": formal["condition"],
                    "action": formal["action"],
                    "active_regimes": active_regimes,
                    "source_proposal_id": proposal_id,
                    "regimes_observed": active_regimes,
                },
                "is_active": True,
                "importance": 5,
                "shadow_mode_until": shadow_until.isoformat(),
                "wilson_ci_lower": evidence.get("wilson_ci_lower"),
                "match_count": 0,
                "propose_count_so_far": 1,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            db.table("agent_memory").insert(row).execute()

            # 让 SemanticMemory 缓存立即 invalidate
            try:
                from agent.memory import get_memory_manager
                get_memory_manager().semantic.force_refresh()
            except Exception:
                pass

            return {
                "ok": True,
                "promoted_rule_id": new_id,
                "shadow_mode_until": shadow_until.isoformat(),
                "shadow_mode_days": SHADOW_MODE_DAYS,
                "duplicate": False,
            }
        except Exception as e:
            log.warning("[T11] approve_rule failed: %s", e)
            raise  # base.run 会 catch 成 EXECUTE_ERROR
