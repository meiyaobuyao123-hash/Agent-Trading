"""
T15 calc_risk_metrics — 计算风险指标(纯函数,无 LLM)

引用 docs/agent-pm/05-tool-catalog.md T15
引用 docs/agent-pm/17-tech-plan.md Phase 1
复用 agent/review_engine.py:_compute_metrics

输入:trades 列表(配对后的 buy/sell pairs)
输出:win_rate / ev_pct / sharpe / max_drawdown_pct / profit_factor /
     kelly_fraction / wilson_ci_lower

幂等 / 无副作用 / 公开。
"""
from __future__ import annotations
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect


_TRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_closed": {"type": "boolean"},
        "pnl_ratio": {"type": ["number", "null"]},
        "d3_pct": {"type": ["number", "null"]},
        "chain": {"type": "string"},
        "token_address": {"type": "string"},
    },
    "required": ["is_closed"],
}


class CalcRiskMetricsTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="calc_risk_metrics",
            description=(
                "对一组配对后的 trade 计算风险与表现指标:win_rate / EV / Sharpe / "
                "max_drawdown / profit_factor / kelly / Wilson CI lower。"
                "trade 至少含 is_closed (bool) 和 pnl_ratio (sell/buy 比率,closed 时必填)。"
                "输入空数组返零值;开仓中可用 d3_pct 估算(D3≥20% 视为 win)。"
            ),
            idempotent=True,
            idempotency_key_fields=[],
            side_effects=SideEffect.NONE,
            p95_latency_ms=20,
            cost_usd=0.0,
            permission=Permission.PUBLIC,
            failure_modes=["INPUT_SCHEMA_INVALID", "EMPTY_TRADES_OK"],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "trades": {
                    "type": "array",
                    "items": _TRADE_SCHEMA,
                },
            },
            "required": ["trades"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "trade_count": {"type": "integer"},
                "win_rate": {"type": "number"},
                "ev_pct": {"type": "number"},
                "sharpe": {"type": "number"},
                "max_drawdown_pct": {"type": "number"},
                "profit_factor": {"type": "number"},
                "kelly_fraction": {"type": ["number", "null"]},
                "wilson_ci_lower": {"type": ["number", "null"]},
            },
            "required": [
                "trade_count", "win_rate", "ev_pct", "sharpe",
                "max_drawdown_pct", "profit_factor",
            ],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        from agent.review_engine import _compute_metrics, _wilson_lower
        trades = payload["trades"]
        # 补齐 review_engine 期望的字段(_compute_metrics 内会用 t["pnl_ratio"]/t["d3_pct"]/t["is_closed"])
        normalized = []
        for t in trades:
            normalized.append({
                "is_closed": bool(t.get("is_closed", False)),
                "pnl_ratio": t.get("pnl_ratio"),
                "d3_pct": t.get("d3_pct", 0.0) or 0.0,
            })
        m = _compute_metrics(normalized)

        # Wilson CI:基于 closed trades 的 win_rate
        closed = [t for t in normalized if t["is_closed"] and t["pnl_ratio"]]
        if closed:
            wr = m["win_rate"]
            wci = _wilson_lower(wr, len(closed))
        else:
            wci = None

        return {
            "trade_count": m["trade_count"],
            "win_rate": m["win_rate"],
            "ev_pct": m["ev_pct"],
            "sharpe": m["sharpe"],
            "max_drawdown_pct": m["max_drawdown_pct"],
            "profit_factor": m["profit_factor"],
            "kelly_fraction": m["kelly_fraction"],
            "wilson_ci_lower": wci,
        }
