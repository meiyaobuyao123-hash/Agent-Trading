"""
Tool 基类 — 统一 schema 校验 / idempotent 检查 / 调用元数据
引用 docs/agent-pm/05-tool-catalog.md §4.0

每个 Tool 实施:
  - 继承 Tool
  - 定义 input_schema / output_schema (JSON Schema)
  - 实施 _execute(...)
  - 设 idempotent / side_effects / p95_latency_ms / cost_usd / permission

调用方:
  - Skill 通过 Anthropic tool_use API 触发
  - 内部测试可直接 .run(payload)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time
import logging
import jsonschema

log = logging.getLogger(__name__)


class Permission(str, Enum):
    PUBLIC = "public"
    DEVICE_ONLY = "device_only"
    WALLET_REQUIRED = "wallet_required"


class SideEffect(str, Enum):
    NONE = "none"
    DB_WRITE = "db_write"
    EXTERNAL_API = "external_api"
    CHAIN_TX = "chain_tx"
    PUSH = "push"


@dataclass
class ToolMetadata:
    name: str
    description: str
    idempotent: bool = True
    idempotency_key_fields: list[str] = field(default_factory=list)
    side_effects: SideEffect = SideEffect.NONE
    p95_latency_ms: int = 500
    cost_usd: float = 0.0
    permission: Permission = Permission.PUBLIC
    failure_modes: list[str] = field(default_factory=list)
    owner: str = "tbd"
    version: str = "0.1"


@dataclass
class ToolResult:
    ok: bool
    output: Any = None
    error: str | None = None
    failure_mode: str | None = None
    latency_ms: int = 0


class Tool(ABC):
    """Tool 基类。每个 Tool 必须 override metadata + input_schema + output_schema + _execute。"""

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata: ...

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]: ...

    @property
    @abstractmethod
    def output_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    async def _execute(self, payload: dict[str, Any]) -> Any: ...

    async def run(self, payload: dict[str, Any]) -> ToolResult:
        """统一入口:校验 input → 执行 → 校验 output → 返回 ToolResult。"""
        t0 = time.monotonic()
        meta = self.metadata
        try:
            jsonschema.validate(payload, self.input_schema)
        except jsonschema.ValidationError as e:
            return ToolResult(
                ok=False, error=f"input schema 校验失败: {e.message}",
                failure_mode="INPUT_SCHEMA_INVALID",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        try:
            output = await self._execute(payload)
        except Exception as e:
            log.exception("[%s] _execute 异常", meta.name)
            return ToolResult(
                ok=False, error=str(e), failure_mode="EXECUTE_ERROR",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        try:
            jsonschema.validate(output, self.output_schema)
        except jsonschema.ValidationError as e:
            log.error("[%s] output schema 校验失败: %s", meta.name, e.message)
            return ToolResult(
                ok=False, error=f"output schema 校验失败: {e.message}",
                failure_mode="OUTPUT_SCHEMA_INVALID",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        return ToolResult(
            ok=True, output=output,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    def to_anthropic_tool_spec(self) -> dict[str, Any]:
        """生成 Anthropic Messages API tool_use spec。"""
        m = self.metadata
        return {
            "name": m.name,
            "description": m.description,
            "input_schema": self.input_schema,
        }
