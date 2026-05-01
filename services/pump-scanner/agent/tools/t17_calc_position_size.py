"""
T17 calc_position_size — 计算建议仓位(Kelly + 固定百分比 + ATR 止损)

引用 docs/agent-pm/05-tool-catalog.md T17
引用 docs/agent-pm/17-tech-plan.md Phase 1
引用 docs/agent-pm/03-prd.md §仓位管理

设计:
  3 种仓位模式(可叠加风控)
  - fixed_pct(固定百分比 of 账户余额)
  - kelly(Kelly fraction × 账户余额,clipped 到 max_pct)
  - atr_risk(基于 ATR 止损 + 固定风险金额倒推仓位)

并应用全局风控上限:
  - max_position_usd
  - max_pct_of_balance
  - HR01: 单笔 ≤ $500(safety_engine 之外的二次保险)
  - HR04: 单策略 ≤ 总余额 10%

输入:account_balance_usd, mode, params(因 mode 而异)
输出:position_usd, position_pct_of_balance, capped_by, reasoning

幂等 / 无副作用 / 公开。
"""
from __future__ import annotations
from typing import Any

from .base import Tool, ToolMetadata, Permission, SideEffect


SUPPORTED_MODES = ("fixed_pct", "kelly", "atr_risk")


# 安全上限(对齐 safety_policy.yaml HR01/HR04)
HR01_MAX_PER_TRADE_USD = 500.0
HR04_MAX_PCT_PER_STRATEGY = 0.10  # 单策略 ≤ 总余额 10%


class CalcPositionSizeTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="calc_position_size",
            description=(
                "计算建议仓位金额(USD)。3 种 mode:"
                "fixed_pct(固定 % 余额)/ kelly(Kelly fraction)/ atr_risk(ATR 止损反推)。"
                "应用 HR01(单笔 ≤ $500)+ HR04(单策略 ≤ 10% 余额)风控硬上限。"
                "返回 position_usd / position_pct_of_balance / capped_by(列出生效的风控)/ reasoning。"
            ),
            idempotent=True,
            idempotency_key_fields=[],
            side_effects=SideEffect.NONE,
            p95_latency_ms=10,
            cost_usd=0.0,
            permission=Permission.PUBLIC,
            failure_modes=["INPUT_SCHEMA_INVALID", "MODE_PARAMS_INSUFFICIENT"],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "account_balance_usd": {"type": "number", "exclusiveMinimum": 0},
                "mode": {"type": "string", "enum": list(SUPPORTED_MODES)},
                # fixed_pct
                "fixed_pct": {
                    "type": "number", "exclusiveMinimum": 0, "maximum": 1,
                    "description": "fixed_pct mode 用,0.0-1.0",
                },
                # kelly
                "win_rate": {"type": "number", "minimum": 0, "maximum": 1},
                "win_loss_ratio": {"type": "number", "exclusiveMinimum": 0,
                                   "description": "kelly 用:平均赢/平均亏 比"},
                "kelly_safety_factor": {"type": "number", "minimum": 0, "maximum": 1,
                                         "description": "kelly fraction 缩减系数,默认 0.5(half-kelly)"},
                # atr_risk
                "entry_price": {"type": "number", "exclusiveMinimum": 0},
                "stop_loss_price": {"type": "number", "exclusiveMinimum": 0},
                "risk_per_trade_usd": {"type": "number", "exclusiveMinimum": 0},
                # 全局风控覆盖(可选,不传则用 HR01/HR04 默认)
                "max_position_usd": {"type": "number", "exclusiveMinimum": 0},
                "max_pct_of_balance": {"type": "number", "exclusiveMinimum": 0,
                                        "maximum": 1},
            },
            "required": ["account_balance_usd", "mode"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "position_usd": {"type": "number"},
                "position_pct_of_balance": {"type": "number"},
                "raw_position_usd": {"type": "number"},
                "capped_by": {
                    "type": "array", "items": {"type": "string"},
                },
                "reasoning": {"type": "string"},
            },
            "required": [
                "position_usd", "position_pct_of_balance",
                "raw_position_usd", "capped_by", "reasoning",
            ],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        balance = float(payload["account_balance_usd"])
        mode = payload["mode"]

        # 1. 计算 raw position(未应用风控上限)
        raw_pct = 0.0
        reasoning_parts = []

        if mode == "fixed_pct":
            pct = payload.get("fixed_pct")
            if pct is None:
                raise ValueError("fixed_pct mode requires 'fixed_pct' param")
            raw_pct = float(pct)
            reasoning_parts.append(f"fixed_pct={raw_pct:.2%}")

        elif mode == "kelly":
            wr = payload.get("win_rate")
            wlr = payload.get("win_loss_ratio")
            if wr is None or wlr is None:
                raise ValueError("kelly mode requires 'win_rate' and 'win_loss_ratio'")
            # Kelly: f* = (W/L * p - q) / (W/L) = p - (1-p)/(W/L)
            wr = float(wr)
            wlr = float(wlr)
            if wlr <= 0:
                kelly_f = 0.0
            else:
                kelly_f = wr - (1.0 - wr) / wlr
            kelly_f = max(0.0, kelly_f)  # 不做空仓位
            safety = float(payload.get("kelly_safety_factor", 0.5))
            raw_pct = kelly_f * safety
            reasoning_parts.append(
                f"kelly_f={kelly_f:.3f} × safety={safety:.2f} → {raw_pct:.2%}"
            )

        elif mode == "atr_risk":
            entry = payload.get("entry_price")
            stop = payload.get("stop_loss_price")
            risk_usd = payload.get("risk_per_trade_usd")
            if not all(x is not None for x in (entry, stop, risk_usd)):
                raise ValueError(
                    "atr_risk mode requires entry_price + stop_loss_price + risk_per_trade_usd"
                )
            entry = float(entry); stop = float(stop); risk_usd = float(risk_usd)
            if entry == stop:
                raise ValueError("entry_price == stop_loss_price (zero risk)")
            # 仓位 = risk_usd / |entry - stop| × entry
            risk_per_unit = abs(entry - stop)
            units = risk_usd / risk_per_unit if risk_per_unit > 0 else 0
            raw_position_usd = units * entry
            raw_pct = raw_position_usd / balance if balance > 0 else 0
            reasoning_parts.append(
                f"atr_risk: ${risk_usd:.0f} risk ÷ ${risk_per_unit:.4f} per unit "
                f"× ${entry:.4f} entry = ${raw_position_usd:.2f}"
            )

        raw_position_usd = raw_pct * balance

        # 2. 应用风控上限
        capped_by = []
        position_usd = raw_position_usd

        # HR01: 单笔 ≤ $500
        if position_usd > HR01_MAX_PER_TRADE_USD:
            position_usd = HR01_MAX_PER_TRADE_USD
            capped_by.append("HR01_max_per_trade_500usd")

        # HR04: 单策略 ≤ 总余额 10%
        max_pct = float(payload.get("max_pct_of_balance", HR04_MAX_PCT_PER_STRATEGY))
        max_pct_usd = max_pct * balance
        if position_usd > max_pct_usd:
            position_usd = max_pct_usd
            capped_by.append(f"max_pct_of_balance_{max_pct:.0%}")

        # 用户自定义 max_position_usd
        if "max_position_usd" in payload:
            user_max = float(payload["max_position_usd"])
            if position_usd > user_max:
                position_usd = user_max
                capped_by.append("user_max_position_usd")

        position_pct = position_usd / balance if balance > 0 else 0

        reasoning = (
            "; ".join(reasoning_parts)
            + f" → raw ${raw_position_usd:.2f} ({raw_pct:.2%})"
            + (f"; capped by {', '.join(capped_by)}" if capped_by else "")
            + f" → final ${position_usd:.2f} ({position_pct:.2%})"
        )

        return {
            "position_usd": round(position_usd, 2),
            "position_pct_of_balance": round(position_pct, 4),
            "raw_position_usd": round(raw_position_usd, 2),
            "capped_by": capped_by,
            "reasoning": reasoning,
        }
