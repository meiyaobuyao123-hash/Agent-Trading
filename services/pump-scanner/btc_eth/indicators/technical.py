"""技术指标计算 — RSI / MACD / 布林带 / ATR

纯本地计算，不依赖任何外部库。输入为 K线 list，输出为指标值。
"""
from typing import List, Dict, Optional


def calc_rsi(candles: List[Dict], period: int = 14) -> Optional[float]:
    """RSI(14) — 0~100"""
    if len(candles) < period + 1:
        return None
    closes = [c["close"] for c in candles[-(period + 1):]]
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def calc_macd(
    candles: List[Dict], fast: int = 12, slow: int = 26, signal: int = 9
) -> Optional[Dict[str, float]]:
    """MACD — 返回 {macd, signal, histogram}"""
    if len(candles) < slow + signal:
        return None
    closes = [c["close"] for c in candles]

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    if ema_fast is None or ema_slow is None:
        return None

    macd_line = ema_fast[-1] - ema_slow[-1]

    # 计算 MACD 线序列用于信号线
    macd_series = []
    for i in range(len(ema_slow)):
        idx = i + (len(ema_fast) - len(ema_slow))
        if idx >= 0:
            macd_series.append(ema_fast[idx] - ema_slow[i])

    if len(macd_series) < signal:
        return None

    signal_ema = _ema(macd_series, signal)
    if signal_ema is None:
        return None

    signal_val = signal_ema[-1]
    histogram = macd_line - signal_val

    return {
        "macd": round(macd_line, 6),
        "signal": round(signal_val, 6),
        "histogram": round(histogram, 6),
    }


def calc_bollinger(candles: List[Dict], period: int = 20, std_dev: float = 2.0) -> Optional[Dict[str, float]]:
    """布林带 — 返回 {upper, middle, lower, position}
    position: 0=下轨, 0.5=中轨, 1=上轨"""
    if len(candles) < period:
        return None
    closes = [c["close"] for c in candles[-period:]]
    middle = sum(closes) / period
    variance = sum((c - middle) ** 2 for c in closes) / period
    std = variance ** 0.5
    upper = middle + std_dev * std
    lower = middle - std_dev * std

    current = closes[-1]
    band_width = upper - lower
    position = (current - lower) / band_width if band_width > 0 else 0.5

    return {
        "upper": round(upper, 2),
        "middle": round(middle, 2),
        "lower": round(lower, 2),
        "position": round(max(0, min(1, position)), 4),
    }


def calc_atr(candles: List[Dict], period: int = 14) -> Optional[float]:
    """ATR(14) — 平均真实波幅"""
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    return round(sum(trs[-period:]) / period, 4)


def calc_ma(candles: List[Dict], period: int) -> Optional[float]:
    """简单移动平均"""
    if len(candles) < period:
        return None
    closes = [c["close"] for c in candles[-period:]]
    return round(sum(closes) / period, 4)


def calc_support_resistance(candles: List[Dict], lookback: int = 50) -> Dict[str, List[float]]:
    """计算近期支撑阻力位"""
    if len(candles) < 5:
        return {"support": [], "resistance": []}
    recent = candles[-min(lookback, len(candles)):]
    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]
    current = recent[-1]["close"]

    # 找局部高低点
    supports = sorted(set(l for l in lows if l < current))[-3:]
    resistances = sorted(set(h for h in highs if h > current))[:3]

    return {
        "support": [round(s, 2) for s in supports],
        "resistance": [round(r, 2) for r in resistances],
    }


def _ema(values, period: int):
    """EMA 计算，返回序列"""
    if isinstance(values, list) and len(values) < period:
        return None
    data = values if isinstance(values, list) else list(values)
    if len(data) < period:
        return None
    k = 2 / (period + 1)
    ema = [sum(data[:period]) / period]
    for v in data[period:]:
        ema.append(v * k + ema[-1] * (1 - k))
    return ema
