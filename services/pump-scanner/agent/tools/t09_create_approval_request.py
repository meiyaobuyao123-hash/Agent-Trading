"""
T09 create_approval_request — 写 HITL 队列(本地 PG pending_approvals 表)

引用 docs/agent-pm/05-tool-catalog.md T09
引用 docs/agent-pm/17-tech-plan.md Phase 0
引用 services/pump-scanner/migrations/local_pg/036_pending_approvals_wal.sql

输入:device_id + strategy_id + trigger_conditions + thesis_id + amount_usd +
     timeout_seconds(默认 5min)+ idempotency_key(防 retry 重复)
输出:approval_id + expires_at + idempotent_hit (若已存在)

side=DB_WRITE / permission=DEVICE_ONLY / 幂等(idempotency_key 唯一约束)
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5 * 60   # 5min 默认超时
MAX_TIMEOUT_SECONDS = 60 * 60      # 上限 60min


class CreateApprovalRequestTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="create_approval_request",
            description=(
                "创建 HITL(human-in-the-loop)审批请求 — 写 pending_approvals 表 + 推送。"
                "默认 5min 超时;15min 降级 notify_only;60min 自动 reject(由 reflect_loop 处理)。"
                "idempotency_key(strategy_id + signal_event_id + amount_usd 拼接)防 retry 重复创建。"
                "返回 approval_id + expires_at;若 idempotency_key 已存在,返已有的 approval_id 并标 idempotent_hit=true。"
            ),
            idempotent=True,
            idempotency_key_fields=["idempotency_key"],
            side_effects=SideEffect.DB_WRITE,
            p95_latency_ms=300,
            cost_usd=0.0,
            permission=Permission.DEVICE_ONLY,
            failure_modes=[
                "INPUT_SCHEMA_INVALID",
                "DB_WRITE_FAILED",
                "DUPLICATE_IDEMPOTENCY_KEY_OK",  # 不是错,返已有
            ],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "minLength": 1},
                "strategy_id": {"type": "string", "minLength": 1},
                "trigger_conditions_matched": {"type": "object"},
                "thesis_id": {"type": ["string", "null"]},
                "token_address": {"type": ["string", "null"]},
                "chain": {"type": ["string", "null"]},
                "amount_usd": {"type": ["number", "null"]},
                "timeout_seconds": {
                    "type": "integer",
                    "minimum": 60,
                    "maximum": MAX_TIMEOUT_SECONDS,
                },
                "idempotency_key": {"type": "string"},
            },
            "required": ["device_id", "strategy_id", "trigger_conditions_matched"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "approval_id": {"type": "string"},
                "expires_at": {"type": "string"},
                "idempotent_hit": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["ok", "approval_id", "expires_at", "idempotent_hit"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        device_id = payload["device_id"]
        strategy_id = payload["strategy_id"]
        trigger = payload["trigger_conditions_matched"]
        thesis_id = payload.get("thesis_id")
        token_address = payload.get("token_address")
        chain = payload.get("chain")
        amount_usd = payload.get("amount_usd")
        timeout_s = payload.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        idem_key = payload.get("idempotency_key")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=timeout_s)

        try:
            from local_db import _get_conn
            conn = _get_conn()
        except Exception as e:
            log.warning("[T09] local_db conn failed: %s", e)
            raise

        # 幂等检查
        if idem_key:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT approval_id, expires_at FROM pending_approvals "
                        "WHERE idempotency_key = %s LIMIT 1",
                        (idem_key,),
                    )
                    row = cur.fetchone()
                    if row:
                        return {
                            "ok": True,
                            "approval_id": str(row[0]),
                            "expires_at": row[1].isoformat() if row[1] else "",
                            "idempotent_hit": True,
                            "reason": "duplicate_idempotency_key",
                        }
            except Exception as e:
                log.warning("[T09] idempotency check failed: %s", e)

        new_id = str(uuid.uuid4())
        try:
            import json as _json
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pending_approvals
                    (approval_id, device_id, strategy_id, trigger_conditions_matched,
                     thesis_id, token_address, chain, amount_usd,
                     expires_at, idempotency_key)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
                    RETURNING approval_id, expires_at
                    """,
                    (
                        new_id, device_id, strategy_id, _json.dumps(trigger),
                        thesis_id, token_address, chain, amount_usd,
                        expires_at, idem_key,
                    ),
                )
                row = cur.fetchone()
            return {
                "ok": True,
                "approval_id": str(row[0]),
                "expires_at": row[1].isoformat() if row[1] else expires_at.isoformat(),
                "idempotent_hit": False,
                "reason": "created",
            }
        except Exception as e:
            log.warning("[T09] insert failed: %s", e)
            raise
