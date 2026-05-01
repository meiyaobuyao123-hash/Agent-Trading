"""
T10 get_paper_performance — 拉取策略模拟盘表现统计

引用 docs/agent-pm/05-tool-catalog.md T10
引用 docs/agent-pm/17-tech-plan.md Phase 1
复用 agent/paper_engine.py:get_stats / get_comparison

输入:strategy_id (+ include_comparison 是否拉模拟 vs 实盘对比)
输出:stats(win_rate, pnl, trade_count 等) + 可选 comparison

只读 / 幂等 / device_only。
"""
from __future__ import annotations
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect


class GetPaperPerformanceTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="get_paper_performance",
            description=(
                "拉取策略的模拟盘表现统计:win_rate / total_pnl_usd / total_pnl_pct / "
                "trade_count / closed_count / open_count / avg_pnl_pct / max_win/loss_pct。"
                "include_comparison=true 时还返回模拟盘 vs 实盘对比(若有实盘数据)。"
                "用于:模式晋升判定(paper→notify→auto 30d/30笔/EV>=+1%)+ 复盘报告 + UI 展示。"
            ),
            idempotent=True,
            idempotency_key_fields=[],
            side_effects=SideEffect.NONE,
            p95_latency_ms=400,
            cost_usd=0.0,
            permission=Permission.DEVICE_ONLY,
            failure_modes=["DB_QUERY_FAILED", "STRATEGY_NOT_FOUND_OK"],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string", "minLength": 1},
                "include_comparison": {"type": "boolean"},
            },
            "required": ["strategy_id"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "stats": {"type": "object"},
                "comparison": {"type": ["object", "null"]},
                "promotion_eligible": {"type": "boolean"},
                "promotion_blockers": {
                    "type": "array", "items": {"type": "string"},
                },
            },
            "required": ["ok", "stats", "promotion_eligible", "promotion_blockers"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        from agent.paper_engine import get_paper_engine
        engine = get_paper_engine()
        sid = payload["strategy_id"]
        include_comp = bool(payload.get("include_comparison", False))

        try:
            stats = await engine.get_stats(sid)
        except Exception as e:
            return {
                "ok": False,
                "stats": {},
                "comparison": None,
                "promotion_eligible": False,
                "promotion_blockers": [f"db_query_failed: {e}"],
            }

        comparison = None
        if include_comp:
            try:
                comparison = await engine.get_comparison(sid)
            except Exception:
                comparison = None

        # 模式晋升判定(对齐 17-tech-plan.md C5):
        #   30d 跑过 + 30 笔以上 + EV ≥ +1% 才能从 paper → notify → auto
        # 这里只暴露候选条件,真实晋升需 routes 层 + agent_strategies.mode_locked_until 检查
        blockers = []
        closed = stats.get("closed_count", 0) or 0
        if closed < 30:
            blockers.append(f"closed_trades_lt_30 (current {closed})")
        avg_pnl = stats.get("avg_pnl_pct", 0) or 0
        if avg_pnl < 1.0:
            blockers.append(f"avg_pnl_pct_lt_1 (current {avg_pnl})")
        eligible = len(blockers) == 0

        return {
            "ok": True,
            "stats": stats,
            "comparison": comparison,
            "promotion_eligible": eligible,
            "promotion_blockers": blockers,
        }
