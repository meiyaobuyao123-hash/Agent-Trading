"""
T12 save_strategy — 保存策略(创建到 agent_strategies)

引用 docs/agent-pm/05-tool-catalog.md T12
引用 docs/agent-pm/17-tech-plan.md Phase 1
复用 agent/strategy_manager.py:create_strategy

输入:user_id + spec(StrategySpec dict)+ source_prompt 可选
输出:strategy row(含 id)

ValidatedError 走 INPUT_SCHEMA_INVALID;DB 失败走 EXECUTE_ERROR。
side_effects=DB_WRITE,permission=DEVICE_ONLY,non-idempotent
(同一用户重复 save 会创多条;Agent 应当先调 T05 list 检查策略数 ≤ 20)
"""
from __future__ import annotations
import logging
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)


# StrategySpec 最小骨架:conditions + actions 必须有
SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 100},
        "description": {"type": "string"},
        "conditions": {
            "type": "object",
            "properties": {
                "rules": {"type": "array", "minItems": 1},
            },
            "required": ["rules"],
        },
        "actions": {"type": "array", "minItems": 1},
        "filters": {"type": "object"},
        "risk_params": {"type": "object"},
        "cooldown_minutes": {"type": "integer", "minimum": 5},
        "mode": {"type": "string", "enum": ["paper", "live"]},
        "template_id": {"type": "string"},
    },
    "required": ["conditions", "actions"],
}


class SaveStrategyTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="save_strategy",
            description=(
                "保存策略到 agent_strategies。"
                "spec 必含 conditions(含 rules 数组)+ actions 数组。"
                "mode 默认 'paper'(强制 paper 起步,30d/30 笔/EV≥1% 后才能 notify→auto)。"
                "cooldown_minutes 强制下限 5min。"
                "返回 created strategy row(含 id)。"
                "Agent 调用前应先 T05 list_strategies 检查 active_count ≤ 20(配额)。"
            ),
            idempotent=False,
            idempotency_key_fields=["user_id", "spec.name"],
            side_effects=SideEffect.DB_WRITE,
            p95_latency_ms=600,
            cost_usd=0.0,
            permission=Permission.DEVICE_ONLY,
            failure_modes=[
                "INPUT_SCHEMA_INVALID",
                "SPEC_VALIDATION_FAILED",
                "DB_WRITE_FAILED",
                "STRATEGY_QUOTA_EXCEEDED",
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
                "spec": SPEC_SCHEMA,
                "source_prompt": {"type": "string"},
                "skip_quota_check": {"type": "boolean"},
            },
            "required": ["user_id", "spec"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "strategy": {"type": ["object", "null"]},
                "reason": {"type": "string"},
            },
            "required": ["ok"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        from agent.strategy_manager import StrategyManager
        mgr = StrategyManager()
        user_id = payload["user_id"]
        spec = payload["spec"]
        source_prompt = payload.get("source_prompt")

        # 配额检查(可跳过):
        if not payload.get("skip_quota_check", False):
            try:
                existing = mgr.list_strategies(user_id, status="active")
                if len(existing) >= 20:
                    return {
                        "ok": False, "strategy": None,
                        "reason": f"strategy_quota_exceeded: {len(existing)} active >= 20",
                    }
            except Exception:
                # 配额查询失败 → 放行(避免 DB 抖动阻塞所有创建)
                pass

        try:
            strategy = mgr.create_strategy(
                user_id=user_id, spec=spec, source_prompt=source_prompt,
            )
        except ValueError as e:
            # spec 验证失败(rules 空 / actions 空 / 字段缺失)
            return {"ok": False, "strategy": None,
                    "reason": f"spec_invalid: {e}"}
        except RuntimeError as e:
            return {"ok": False, "strategy": None,
                    "reason": f"db_write_failed: {e}"}

        return {"ok": True, "strategy": strategy, "reason": "created"}
