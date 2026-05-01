"""
T04 recall_memory — 检索 Working / Episodic / Semantic Memory(合并返回)

引用 docs/agent-pm/05-tool-catalog.md T04
引用 docs/agent-pm/06-memory-spec.md
引用 docs/agent-pm/17-tech-plan.md Phase 1
复用 agent/memory/{working,episodic,semantic}_memory.py

输入:device_id + query_context(可选)+ layer 选择
输出:{working: [], episodic: [], semantic: []}

幂等 / 无副作用(只读)/ device_only。
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List

from .base import Tool, ToolMetadata, Permission, SideEffect

log = logging.getLogger(__name__)

VALID_LAYERS = ("working", "episodic", "semantic")


class RecallMemoryTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="recall_memory",
            description=(
                "检索用户记忆 — 三层(working/episodic/semantic)合并返回。"
                "layers 数组从 [working, episodic, semantic] 选(默认全部)。"
                "可传 chain / trigger_source 过滤 episodic+semantic。"
                "limit_per_layer 默认 10。"
                "DB 失败时该 layer 返空数组,不阻断其他 layer。"
            ),
            idempotent=True,
            idempotency_key_fields=[],
            side_effects=SideEffect.NONE,  # 只读
            p95_latency_ms=300,
            cost_usd=0.0,
            permission=Permission.DEVICE_ONLY,
            failure_modes=["MEMORY_MANAGER_INIT_FAILED", "PARTIAL_LAYER_FAILURE_OK"],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "minLength": 1},
                "layers": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(VALID_LAYERS)},
                },
                "chain": {"type": ["string", "null"]},
                "trigger_source": {"type": "string"},
                "limit_per_layer": {
                    "type": "integer", "minimum": 1, "maximum": 50,
                },
            },
            "required": ["device_id"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "working": {"type": "array"},
                "episodic": {"type": "array"},
                "semantic": {"type": "array"},
                "layers_returned": {
                    "type": "array", "items": {"type": "string"},
                },
                "errors": {"type": "object"},
            },
            "required": ["working", "episodic", "semantic", "layers_returned"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        layers = payload.get("layers") or list(VALID_LAYERS)
        chain = payload.get("chain")
        trigger = payload.get("trigger_source")
        limit = payload.get("limit_per_layer", 10)

        out: Dict[str, Any] = {
            "working": [],
            "episodic": [],
            "semantic": [],
            "layers_returned": [],
            "errors": {},
        }

        try:
            from agent.memory import get_memory_manager
            mem = get_memory_manager()
        except Exception as e:
            log.warning("[T04] get_memory_manager failed: %s", e)
            return out  # 全部空,不抛错(failure_mode=MEMORY_MANAGER_INIT_FAILED 由 base 包)

        if "working" in layers:
            try:
                events = mem.working.get_recent(limit)
                out["working"] = [
                    {
                        "type": e.get("type", ""),
                        "summary": (e.get("summary") or str(e))[:200],
                        "ts": e.get("_ts", 0),
                    }
                    for e in (events or [])
                ]
                out["layers_returned"].append("working")
            except Exception as e:
                log.warning("[T04] working failed: %s", e)
                out["errors"]["working"] = str(e)[:120]

        if "episodic" in layers:
            try:
                # episodic 的 get_relevant 需要 chain + trigger_source
                if hasattr(mem, "episodic"):
                    eps = mem.episodic.get_relevant(
                        chain=chain, trigger_source=trigger, limit=limit,
                    ) if hasattr(mem.episodic, "get_relevant") else []
                    out["episodic"] = [
                        {
                            "id": str(e.get("id", "")),
                            "summary": (e.get("content") or "")[:200],
                            "regime": (e.get("structured_data") or {}).get("regime", ""),
                            "score": e.get("_score"),
                        }
                        for e in (eps or [])
                    ]
                    out["layers_returned"].append("episodic")
            except Exception as e:
                log.warning("[T04] episodic failed: %s", e)
                out["errors"]["episodic"] = str(e)[:120]

        if "semantic" in layers:
            try:
                rules = mem.semantic.get_relevant(
                    chain=chain, trigger_source=trigger, limit=limit,
                )
                out["semantic"] = [
                    {
                        "id": str(r.get("id", "")),
                        "content": (r.get("content") or "")[:200],
                        "condition": (
                            (r.get("structured_data") or {}).get("condition", "")
                        ),
                        "action": (
                            (r.get("structured_data") or {}).get("action", "")
                        ),
                        "importance": r.get("importance", 0),
                        "match_count": r.get("match_count", r.get("usage_count", 0)),
                    }
                    for r in (rules or [])
                ]
                out["layers_returned"].append("semantic")
            except Exception as e:
                log.warning("[T04] semantic failed: %s", e)
                out["errors"]["semantic"] = str(e)[:120]

        return out
