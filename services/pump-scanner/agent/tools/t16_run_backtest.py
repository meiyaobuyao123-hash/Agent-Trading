"""
T16 run_backtest — 历史回测

引用 docs/agent-pm/05-tool-catalog.md T16
引用 docs/agent-pm/17-tech-plan.md Phase 1
复用 agent/backtester.py:backtest_strategy(已有,接 hot/pump/kol 历史)

输入:strategy_spec(StrategySpec dict)+ days(默认 7,上限 90)
输出:trigger_count / win_rate / avg_return_pct / max_drawdown_pct /
     sample_triggers / warnings(规则化)

W3 D5+ 加 warnings 规则:
  - sample_size < 10 → "样本量过小,胜率不稳定"
  - days < 7 → "回测窗口过短"
  - 触发的代币里有 ≥ 30% 是 CRISIS regime → "CRISIS 期数据稀疏"
  - 模拟收益用 D3 涨幅 → "未考虑滑点和真实成交"

幂等(同 spec + days 多次回测理论上同结果)
side_effects=NONE(只读 DB)
"""
from __future__ import annotations
from typing import Any, Dict, List

from .base import Tool, ToolMetadata, Permission, SideEffect


class RunBacktestTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="run_backtest",
            description=(
                "对策略规范跑历史回测(默认 7 天)。"
                "spec 必含 conditions(含 rules)+ filters。"
                "days 1-90(默认 7);超过 30 自动加 warning。"
                "返回 trigger_count / simulated_win_rate / avg_return_pct / "
                "max_drawdown_pct / sample_triggers + 规则化 warnings 数组。"
            ),
            idempotent=True,
            idempotency_key_fields=["spec.name", "days"],
            side_effects=SideEffect.NONE,
            p95_latency_ms=2000,  # 历史拉取较慢
            cost_usd=0.0,
            permission=Permission.DEVICE_ONLY,
            failure_modes=[
                "INPUT_SCHEMA_INVALID",
                "BACKTESTER_FAILED",
                "INSUFFICIENT_HISTORICAL_DATA",
            ],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "conditions": {
                            "type": "object",
                            "properties": {"rules": {"type": "array"}},
                            "required": ["rules"],
                        },
                        "filters": {"type": "object"},
                    },
                    "required": ["conditions"],
                },
                "days": {"type": "integer", "minimum": 1, "maximum": 90},
            },
            "required": ["spec"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "trigger_count": {"type": "integer"},
                "win_rate": {"type": "number"},
                "avg_return_pct": {"type": "number"},
                "max_drawdown_pct": {"type": "number"},
                "sample_triggers": {"type": "array"},
                "warnings": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "days": {"type": "integer"},
            },
            "required": ["ok", "trigger_count", "win_rate", "warnings", "days"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        from agent.backtester import backtest_strategy

        spec = payload["spec"]
        days = int(payload.get("days", 7))

        try:
            result = await backtest_strategy(spec, days=days)
        except Exception as e:
            raise RuntimeError(f"backtester_failed: {e}")

        # 抽出主要字段(backtest_strategy 返回多个 key)
        trigger_count = int(result.get("trigger_count", 0) or 0)
        win_rate = float(result.get("simulated_win_rate", 0) or 0)
        avg_return = float(result.get("avg_return_pct", 0) or 0)
        max_dd = float(result.get("max_drawdown_pct", 0) or 0)
        samples = result.get("sample_triggers", []) or []

        # 规则化 warnings(对齐 17-tech-plan.md C6 + PRD-003 backtester warnings)
        warnings: List[str] = []
        if trigger_count < 10:
            warnings.append(
                f"sample_size_low: 仅 {trigger_count} 笔触发,胜率不稳定"
            )
        if days < 7:
            warnings.append(f"window_short: {days} 天窗口过短,代表性不足")
        if days > 30:
            warnings.append(
                f"window_long: {days} 天历史包含多个 regime,需结合 regime 拆分看"
            )
        if avg_return == 0 and trigger_count > 0:
            warnings.append("avg_return_zero: token_performance 数据缺失,收益估算 0")
        if max_dd < -20:
            warnings.append(
                f"high_drawdown: 最大回撤 {max_dd:.1f}%,实盘需更严格止损"
            )
        # 通用免责
        warnings.append("disclaimer: 模拟收益基于历史 D3 涨幅,未计滑点 / 真实成交")

        return {
            "ok": True,
            "trigger_count": trigger_count,
            "win_rate": round(win_rate, 4),
            "avg_return_pct": round(avg_return, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "sample_triggers": samples,
            "warnings": warnings,
            "days": days,
        }
