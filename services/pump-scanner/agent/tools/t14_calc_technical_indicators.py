"""
T14 calc_technical_indicators — 计算技术指标(RSI/MACD/布林/ATR/MA/支撑阻力)

引用 docs/agent-pm/05-tool-catalog.md T14
引用 docs/agent-pm/17-tech-plan.md Phase 1
复用 btc_eth/indicators/technical.py 现有的纯函数

输入:candles 数组([{open, high, low, close, volume}, ...])+ indicators 数组
输出:{rsi: float, macd: {...}, bollinger: {...}, atr: float, ma_X: float, sr: {support, resistance}}

幂等 / 无副作用 / 公开。
"""
from __future__ import annotations
from typing import Any, Dict, List

from .base import Tool, ToolMetadata, Permission, SideEffect


CANDLE_SCHEMA = {
    "type": "object",
    "properties": {
        "open": {"type": "number"},
        "high": {"type": "number"},
        "low": {"type": "number"},
        "close": {"type": "number"},
        "volume": {"type": "number"},
    },
    "required": ["close"],  # close 是核心(部分指标只需 close);其他可选
}


SUPPORTED_INDICATORS = (
    "rsi", "macd", "bollinger", "atr", "ma", "support_resistance",
)


class CalcTechnicalIndicatorsTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="calc_technical_indicators",
            description=(
                "对 candles 数组计算技术指标。"
                "candles: [{open,high,low,close,volume}] (close 必填,其他可选);"
                "indicators 数组从 [rsi, macd, bollinger, atr, ma, support_resistance] 选;"
                "ma_periods 可选(MA 周期数组,默认 [20, 50])。"
                "返回 {rsi, macd, bollinger, atr, ma: {20:..,50:..}, sr}。"
                "K 线数量不足时该指标返 null,不抛错。"
            ),
            idempotent=True,
            idempotency_key_fields=[],
            side_effects=SideEffect.NONE,
            p95_latency_ms=30,
            cost_usd=0.0,
            permission=Permission.PUBLIC,
            failure_modes=["INPUT_SCHEMA_INVALID", "INSUFFICIENT_CANDLES_OK"],
            owner="agent-team",
            version="1.0",
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "candles": {
                    "type": "array",
                    "items": CANDLE_SCHEMA,
                    "minItems": 1,
                },
                "indicators": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(SUPPORTED_INDICATORS)},
                    "minItems": 1,
                },
                "ma_periods": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 2, "maximum": 200},
                },
                "rsi_period": {"type": "integer", "minimum": 2, "maximum": 100},
                "atr_period": {"type": "integer", "minimum": 2, "maximum": 100},
            },
            "required": ["candles", "indicators"],
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "rsi": {"type": ["number", "null"]},
                "macd": {"type": ["object", "null"]},
                "bollinger": {"type": ["object", "null"]},
                "atr": {"type": ["number", "null"]},
                "ma": {"type": ["object", "null"]},  # {period: value}
                "sr": {"type": ["object", "null"]},  # {support: [], resistance: []}
                "candle_count": {"type": "integer"},
                "indicators_computed": {
                    "type": "array", "items": {"type": "string"},
                },
            },
            "required": ["candle_count", "indicators_computed"],
        }

    async def _execute(self, payload: dict[str, Any]) -> Any:
        from btc_eth.indicators.technical import (
            calc_rsi, calc_macd, calc_bollinger, calc_atr, calc_ma,
            calc_support_resistance,
        )

        candles: List[Dict] = payload["candles"]
        indicators: List[str] = payload["indicators"]
        ma_periods: List[int] = payload.get("ma_periods") or [20, 50]
        rsi_period: int = payload.get("rsi_period") or 14
        atr_period: int = payload.get("atr_period") or 14

        out: Dict[str, Any] = {
            "rsi": None,
            "macd": None,
            "bollinger": None,
            "atr": None,
            "ma": None,
            "sr": None,
            "candle_count": len(candles),
            "indicators_computed": [],
        }

        if "rsi" in indicators:
            out["rsi"] = calc_rsi(candles, period=rsi_period)
            if out["rsi"] is not None:
                out["indicators_computed"].append("rsi")
        if "macd" in indicators:
            out["macd"] = calc_macd(candles)
            if out["macd"] is not None:
                out["indicators_computed"].append("macd")
        if "bollinger" in indicators:
            out["bollinger"] = calc_bollinger(candles)
            if out["bollinger"] is not None:
                out["indicators_computed"].append("bollinger")
        if "atr" in indicators:
            out["atr"] = calc_atr(candles, period=atr_period)
            if out["atr"] is not None:
                out["indicators_computed"].append("atr")
        if "ma" in indicators:
            ma_dict: Dict[str, Any] = {}
            for p in ma_periods:
                v = calc_ma(candles, period=p)
                if v is not None:
                    ma_dict[str(p)] = v
            if ma_dict:
                out["ma"] = ma_dict
                out["indicators_computed"].append("ma")
        if "support_resistance" in indicators:
            sr = calc_support_resistance(candles)
            if sr:
                out["sr"] = sr
                out["indicators_computed"].append("support_resistance")

        return out
