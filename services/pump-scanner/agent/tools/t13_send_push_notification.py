"""
T13 send_push_notification — 发送推送通知(包装 push_service)

引用 docs/agent-pm/05-tool-catalog.md T13
引用 docs/agent-pm/17-tech-plan.md Phase 1
复用 agent/push_service.py:send_push + build_deep_link

输入:user_id + title + body + category + 可选 params(用于 deep_link)
输出:sent_count

幂等性:基于 (user_id, title, body) 短期幂等(同 push 60s 内不重发);
       Tool 层不做 dedupe,假设上层 Loop 已经做了去重。
"""
from __future__ import annotations
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect


VALID_CATEGORIES = (
    "strategy_triggered", "hitl_approval", "review_ready",
    "token_alert", "rule_proposal", "system",
)


class SendPushNotificationTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="send_push_notification",
            description=(
                "发送推送通知到用户活跃设备(FCM/APNs)。"
                "category 必须是: strategy_triggered / hitl_approval / "
                "review_ready / token_alert / rule_proposal / system。"
                "params 可选,用于构造 deep_link(如 strategy_id / approval_id / chain+address)。"
                "返回 sent_count(成功推送的设备数,0 表示用户无活跃设备或 Firebase 未配置)。"
            ),
            idempotent=False,  # push 是有副作用的
            idempotency_key_fields=["user_id", "title", "body"],
            side_effects=SideEffect.PUSH,
            p95_latency_ms=600,
            cost_usd=0.0,  # FCM 免费
            permission=Permission.DEVICE_ONLY,
            failure_modes=[
                "FIREBASE_NOT_INITIALIZED",
                "USER_HAS_NO_DEVICES",
                "FCM_RATE_LIMITED",
                "INVALID_CATEGORY",
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
                "title": {"type": "string", "minLength": 1, "maxLength": 80},
                "body": {"type": "string", "minLength": 1, "maxLength": 240},
                "category": {"type": "string", "enum": list(VALID_CATEGORIES)},
                "params": {
                    "type": "object",
                    "additionalProperties": {"type": ["string", "number", "null"]},
                },
                "extra_data": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["user_id", "title", "body", "category"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sent_count": {"type": "integer"},
                "deep_link": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["sent_count", "deep_link", "category"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        from agent.push_service import send_push, build_deep_link

        user_id = payload["user_id"]
        title = payload["title"]
        body = payload["body"]
        category = payload["category"]
        params = payload.get("params") or {}
        extra = dict(payload.get("extra_data") or {})

        # 构造 deep_link
        deep_link = build_deep_link(category, **params)

        push_data = {
            "type": "tool_t13",
            "category": category,
            "deep_link": deep_link,
            **{k: str(v) for k, v in params.items() if v is not None},
            **extra,
        }

        sent = await send_push(
            user_id=user_id,
            title=title,
            body=body,
            data=push_data,
        )

        return {
            "sent_count": int(sent),
            "deep_link": deep_link,
            "category": category,
        }
