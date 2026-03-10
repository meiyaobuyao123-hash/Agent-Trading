"""
AiTrading Backtester — FastAPI service
Simulates strategy performance against historical signals.

Start:  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Docker: docker run -p 8000:8000 aitrading-backtester

API:
  POST /backtest   — run full backtest
  GET  /health     — health check
  GET  /docs       — Swagger UI
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Any, Literal, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AiTrading Backtester",
    version="1.0.0",
    description="Monte-Carlo backtest engine for AiTrading strategies.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────────────────
class Condition(BaseModel):
    field: str
    op: Literal["eq", "gte", "lte", "in"]
    value: Any

class ConditionTree(BaseModel):
    conditions: list[Condition]
    logic: Literal["AND", "OR"] = "AND"

class ExecConfig(BaseModel):
    amount_usd: float = 100
    slippage: float = 0.5        # percent
    stop_loss_pct: float = 10    # percent
    take_profit_pct: float = 30  # percent
    max_gas_usd: float = 5

class Signal(BaseModel):
    id: Optional[str] = None
    symbol: Optional[str] = "?"
    chain_id: Optional[int] = 56
    direction: Optional[str] = "long"
    confidence_score: Optional[int] = 0
    trigger_price: Optional[float] = None
    risk_level: Optional[str] = "medium"
    created_at: Optional[str] = None

class BacktestRequest(BaseModel):
    condition_tree: ConditionTree
    exec_config: ExecConfig
    signals: list[Signal] = Field(default_factory=list)
    # If no real signals provided, generate synthetic ones
    synthetic_count: int = Field(default=100, ge=10, le=500)
    random_seed: Optional[int] = None

class TradeResult(BaseModel):
    signal_id: str
    symbol: str
    chain_id: int
    direction: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_usd: float
    exit_reason: Literal["take_profit", "stop_loss", "expired"]
    hold_hours: float
    confidence_score: int

class BacktestMetrics(BaseModel):
    total_signals: int
    matched_signals: int
    total_trades: int
    win_rate_pct: float
    total_pnl_pct: float
    total_pnl_usd: float
    avg_win_pct: float
    avg_loss_pct: float
    max_drawdown_pct: float
    profit_factor: float
    sharpe_ratio: float
    avg_hold_hours: float
    take_profit_rate_pct: float
    stop_loss_rate_pct: float
    expired_rate_pct: float

class BacktestResponse(BaseModel):
    ok: bool = True
    elapsed_ms: int
    metrics: BacktestMetrics
    trades: list[TradeResult]
    equity_curve: list[float]   # cumulative P&L at each trade
    monthly_returns: dict[str, float]  # {"2025-01": 12.3, ...}

# ── Condition evaluation ──────────────────────────────────────────────────────
def _matches_condition(signal: Signal, cond: Condition) -> bool:
    field_map: dict[str, Any] = {
        "direction":        signal.direction,
        "confidence_score": signal.confidence_score,
        "chain_id":         str(signal.chain_id),
        "risk_level":       signal.risk_level,
    }
    val = field_map.get(cond.field)
    if val is None:
        return False

    match cond.op:
        case "eq":
            return str(val) == str(cond.value)
        case "gte":
            try:
                return float(val) >= float(cond.value)
            except (ValueError, TypeError):
                return False
        case "lte":
            try:
                return float(val) <= float(cond.value)
            except (ValueError, TypeError):
                return False
        case "in":
            values = cond.value if isinstance(cond.value, list) else [cond.value]
            return str(val) in [str(v) for v in values]
        case _:
            return False

def matches_conditions(signal: Signal, tree: ConditionTree) -> bool:
    if not tree.conditions:
        return True
    results = [_matches_condition(signal, c) for c in tree.conditions]
    return all(results) if tree.logic == "AND" else any(results)

# ── Monte-Carlo trade simulation ──────────────────────────────────────────────
def simulate_trade(
    signal: Signal,
    entry_price: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    rng: random.Random,
) -> TradeResult:
    """
    Simulate price path using geometric Brownian motion.
    Daily vol: 6% (crypto), check every 4h for 30 days max.
    """
    sl_price = entry_price * (1 - stop_loss_pct / 100)
    tp_price = entry_price * (1 + take_profit_pct / 100)

    dt = 4 / 24        # 4-hour steps
    sigma = 0.06       # daily vol 6%
    mu = 0.0008        # slight upward drift (crypto bull bias)
    max_steps = 30 * 6 # 30 days × 6 steps/day

    price = entry_price
    hours = 0.0

    for _ in range(max_steps):
        # GBM step
        z = rng.gauss(0, 1)
        price *= math.exp((mu - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * z)
        hours += 4

        if price <= sl_price:
            exit_price = sl_price
            exit_reason: Literal["take_profit", "stop_loss", "expired"] = "stop_loss"
            break
        if price >= tp_price:
            exit_price = tp_price
            exit_reason = "take_profit"
            break
    else:
        exit_price = price
        exit_reason = "expired"

    pnl_pct = (exit_price - entry_price) / entry_price * 100
    amount = signal.__dict__.get("amount_usd", 100) or 100

    return TradeResult(
        signal_id=signal.id or f"sim-{id(signal)}",
        symbol=signal.symbol or "?",
        chain_id=signal.chain_id or 56,
        direction=signal.direction or "long",
        entry_price=round(entry_price, 8),
        exit_price=round(exit_price, 8),
        pnl_pct=round(pnl_pct, 2),
        pnl_usd=round(amount * pnl_pct / 100, 2),
        exit_reason=exit_reason,
        hold_hours=round(hours, 1),
        confidence_score=signal.confidence_score or 0,
    )

# ── Synthetic signal generator ────────────────────────────────────────────────
def generate_synthetic_signals(n: int, rng: random.Random) -> list[Signal]:
    chains = [1, 56, 137, 42161]
    directions = ["long", "watch", "exit"]
    risks = ["low", "medium", "high"]
    symbols = ["CAKE", "PEPE", "SHIB", "DOGE", "ARB", "OP", "LINK", "UNI", "AAVE", "CRV"]

    signals = []
    base_ts = datetime.now(timezone.utc).timestamp()

    for i in range(n):
        sig_ts = base_ts - rng.uniform(0, 30 * 86400)
        signals.append(Signal(
            id=f"synthetic-{i}",
            symbol=rng.choice(symbols),
            chain_id=rng.choice(chains),
            direction=rng.choices(directions, weights=[0.5, 0.35, 0.15])[0],
            confidence_score=rng.randint(30, 100),
            trigger_price=rng.uniform(0.000001, 100),
            risk_level=rng.choices(risks, weights=[0.3, 0.5, 0.2])[0],
            created_at=datetime.fromtimestamp(sig_ts, tz=timezone.utc).isoformat(),
        ))
    return signals

# ── Metrics calculation ───────────────────────────────────────────────────────
def calc_sharpe(pnls: list[float]) -> float:
    if len(pnls) < 2:
        return 0.0
    arr = np.array(pnls, dtype=float)
    std = float(np.std(arr, ddof=1))
    if std == 0:
        return 0.0
    return float(np.mean(arr) / std * math.sqrt(252))  # annualized

def calc_equity_curve(trades: list[TradeResult]) -> list[float]:
    cumulative = 0.0
    curve = [0.0]
    for t in trades:
        cumulative += t.pnl_pct
        curve.append(round(cumulative, 2))
    return curve

def calc_monthly_returns(trades: list[TradeResult], signals: list[Signal]) -> dict[str, float]:
    monthly: dict[str, float] = {}
    sig_map = {s.id: s for s in signals if s.id}
    for t in trades:
        sig = sig_map.get(t.signal_id)
        if sig and sig.created_at:
            try:
                dt = datetime.fromisoformat(sig.created_at.replace("Z", "+00:00"))
                key = dt.strftime("%Y-%m")
                monthly[key] = round(monthly.get(key, 0.0) + t.pnl_pct, 2)
            except ValueError:
                pass
    return dict(sorted(monthly.items()))

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True, "service": "AiTrading Backtester", "version": "1.0.0"}


@app.post("/backtest", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest):
    import time
    t0 = time.time()

    # Seed RNG
    seed = req.random_seed if req.random_seed is not None else random.randint(0, 999999)
    rng = random.Random(seed)

    # Use provided signals or generate synthetic ones
    signals = req.signals if req.signals else generate_synthetic_signals(req.synthetic_count, rng)

    # Filter signals matching strategy conditions
    matched = [s for s in signals if matches_conditions(s, req.condition_tree)]

    if not matched:
        elapsed = int((time.time() - t0) * 1000)
        return BacktestResponse(
            elapsed_ms=elapsed,
            metrics=BacktestMetrics(
                total_signals=len(signals),
                matched_signals=0,
                total_trades=0,
                win_rate_pct=0,
                total_pnl_pct=0,
                total_pnl_usd=0,
                avg_win_pct=0,
                avg_loss_pct=0,
                max_drawdown_pct=0,
                profit_factor=0,
                sharpe_ratio=0,
                avg_hold_hours=0,
                take_profit_rate_pct=0,
                stop_loss_rate_pct=0,
                expired_rate_pct=0,
            ),
            trades=[],
            equity_curve=[0.0],
            monthly_returns={},
        )

    # Simulate each matched trade
    trades: list[TradeResult] = []
    for sig in matched:
        if sig.direction in ("watch", "exit"):
            continue   # only execute 'long' signals
        entry = sig.trigger_price
        if not entry or entry <= 0:
            entry = rng.uniform(0.000001, 100)
        trades.append(simulate_trade(
            sig, entry,
            req.exec_config.stop_loss_pct,
            req.exec_config.take_profit_pct,
            rng,
        ))

    if not trades:
        elapsed = int((time.time() - t0) * 1000)
        return BacktestResponse(
            elapsed_ms=elapsed,
            metrics=BacktestMetrics(
                total_signals=len(signals), matched_signals=len(matched),
                total_trades=0, win_rate_pct=0, total_pnl_pct=0, total_pnl_usd=0,
                avg_win_pct=0, avg_loss_pct=0, max_drawdown_pct=0, profit_factor=0,
                sharpe_ratio=0, avg_hold_hours=0, take_profit_rate_pct=0,
                stop_loss_rate_pct=0, expired_rate_pct=0,
            ),
            trades=[],
            equity_curve=[0.0],
            monthly_returns={},
        )

    pnls = [t.pnl_pct for t in trades]
    amount = req.exec_config.amount_usd
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    # Max drawdown
    cumulative, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls:
        cumulative += p
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)

    # Exit reason breakdown
    tp_count = sum(1 for t in trades if t.exit_reason == "take_profit")
    sl_count = sum(1 for t in trades if t.exit_reason == "stop_loss")
    ex_count = sum(1 for t in trades if t.exit_reason == "expired")
    n = len(trades)

    metrics = BacktestMetrics(
        total_signals=len(signals),
        matched_signals=len(matched),
        total_trades=n,
        win_rate_pct=round(len(wins) / n * 100, 1),
        total_pnl_pct=round(sum(pnls), 2),
        total_pnl_usd=round(sum(pnls) / 100 * amount * n, 2),
        avg_win_pct=round(sum(wins) / len(wins), 2) if wins else 0.0,
        avg_loss_pct=round(sum(losses) / len(losses), 2) if losses else 0.0,
        max_drawdown_pct=round(max_dd, 2),
        profit_factor=round(abs(sum(wins) / sum(losses)), 2) if losses and sum(losses) != 0 else 9999.0,
        sharpe_ratio=round(calc_sharpe(pnls), 2),
        avg_hold_hours=round(sum(t.hold_hours for t in trades) / n, 1),
        take_profit_rate_pct=round(tp_count / n * 100, 1),
        stop_loss_rate_pct=round(sl_count / n * 100, 1),
        expired_rate_pct=round(ex_count / n * 100, 1),
    )

    elapsed = int((time.time() - t0) * 1000)
    return BacktestResponse(
        elapsed_ms=elapsed,
        metrics=metrics,
        trades=trades[:100],
        equity_curve=calc_equity_curve(trades),
        monthly_returns=calc_monthly_returns(trades, signals),
    )
