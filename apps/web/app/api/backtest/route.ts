/**
 * POST /api/backtest
 * Proxy to Python FastAPI backtester (services/backtester).
 * Falls back to an in-process TypeScript simulation when backtester is offline.
 *
 * Body: BacktestRequest (see services/backtester/main.py for schema)
 */
import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

const BACKTESTER_URL = process.env.BACKTESTER_URL ?? 'http://localhost:8000'

// ── Fallback: TypeScript in-process backtest ──────────────────────────────────
// Simplified simulation for when Python service is offline
interface Condition { field: string; op: string; value: unknown }
interface Signal {
  id?: string; symbol?: string; chain_id?: number; direction?: string
  confidence_score?: number; trigger_price?: number; risk_level?: string; created_at?: string
}

function matchesConditions(
  signal: Signal,
  conditions: Condition[],
  logic: 'AND' | 'OR'
): boolean {
  if (!conditions.length) return true
  const results = conditions.map((c) => {
    const fieldMap: Record<string, unknown> = {
      direction: signal.direction,
      confidence_score: signal.confidence_score,
      chain_id: String(signal.chain_id),
      risk_level: signal.risk_level,
    }
    const val = fieldMap[c.field]
    if (val == null) return false
    switch (c.op) {
      case 'eq': return String(val) === String(c.value)
      case 'gte': return Number(val) >= Number(c.value)
      case 'lte': return Number(val) <= Number(c.value)
      case 'in': return Array.isArray(c.value)
        ? (c.value as string[]).map(String).includes(String(val))
        : String(val) === String(c.value)
      default: return false
    }
  })
  return logic === 'AND' ? results.every(Boolean) : results.some(Boolean)
}

function gaussRandom(rng: () => number): number {
  // Box-Muller
  const u = rng(); const v = rng()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

function simulateTrade(
  signal: Signal,
  entryPrice: number,
  slPct: number,
  tpPct: number,
  rng: () => number
) {
  const slPrice = entryPrice * (1 - slPct / 100)
  const tpPrice = entryPrice * (1 + tpPct / 100)
  const dt = 4 / 24; const sigma = 0.06; const mu = 0.0008; const maxSteps = 180

  let price = entryPrice; let hours = 0
  let exitReason: 'take_profit' | 'stop_loss' | 'expired' = 'expired'

  for (let i = 0; i < maxSteps; i++) {
    const z = gaussRandom(rng)
    price *= Math.exp((mu - 0.5 * sigma * sigma) * dt + sigma * Math.sqrt(dt) * z)
    hours += 4
    if (price <= slPrice) { price = slPrice; exitReason = 'stop_loss'; break }
    if (price >= tpPrice) { price = tpPrice; exitReason = 'take_profit'; break }
  }

  const pnlPct = (price - entryPrice) / entryPrice * 100
  return {
    signal_id: signal.id ?? `ts-${Math.random()}`,
    symbol: signal.symbol ?? '?',
    chain_id: signal.chain_id ?? 56,
    direction: signal.direction ?? 'long',
    entry_price: entryPrice,
    exit_price: price,
    pnl_pct: Math.round(pnlPct * 100) / 100,
    pnl_usd: Math.round(100 * pnlPct / 100 * 100) / 100,
    exit_reason: exitReason,
    hold_hours: hours,
    confidence_score: signal.confidence_score ?? 0,
  }
}

function tsFallbackBacktest(body: Record<string, unknown>) {
  const conditionTree = body.condition_tree as { conditions: Condition[]; logic: 'AND' | 'OR' }
  const execConfig = body.exec_config as { stop_loss_pct: number; take_profit_pct: number; amount_usd: number }
  const inputSignals = (body.signals as Signal[] | undefined) ?? []

  // Mulberry32 — 32-bit safe pseudo-random (no float precision issues)
  let seed = 0x12345678
  const rng = () => {
    seed = (seed + 0x6D2B79F5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }

  const count = Math.min(Number((body.synthetic_count as number | undefined) ?? 100), 500)

  // Generate synthetic if no signals provided
  let signals: Signal[] = inputSignals
  if (!signals.length) {
    const symbols = ['CAKE', 'PEPE', 'SHIB', 'DOGE', 'ARB', 'LINK', 'UNI']
    for (let i = 0; i < count; i++) {
      signals.push({
        id: `syn-${i}`,
        symbol: symbols[i % symbols.length],
        chain_id: [56, 1, 137][i % 3],
        direction: ['long', 'long', 'watch', 'exit'][i % 4],
        confidence_score: 40 + Math.floor(rng() * 60),
        trigger_price: 0.001 + rng() * 50,
        risk_level: ['low', 'medium', 'high'][i % 3],
        created_at: new Date(Date.now() - i * 86400000 / 3).toISOString(),
      })
    }
  }

  const matched = signals.filter((s) =>
    matchesConditions(s, conditionTree.conditions, conditionTree.logic)
  )
  const tradeable = matched.filter((s) => s.direction === 'long')

  const trades = tradeable.map((s) => {
    const entry = (s.trigger_price ?? 0) > 0 ? s.trigger_price! : 0.001 + rng() * 50
    return simulateTrade(s, entry, execConfig.stop_loss_pct, execConfig.take_profit_pct, rng)
  })

  if (!trades.length) {
    return {
      ok: true, elapsed_ms: 5, source: 'ts-fallback',
      metrics: {
        total_signals: signals.length, matched_signals: matched.length, total_trades: 0,
        win_rate_pct: 0, total_pnl_pct: 0, total_pnl_usd: 0, avg_win_pct: 0, avg_loss_pct: 0,
        max_drawdown_pct: 0, profit_factor: 0, sharpe_ratio: 0, avg_hold_hours: 0,
        take_profit_rate_pct: 0, stop_loss_rate_pct: 0, expired_rate_pct: 0,
      },
      trades: [], equity_curve: [0], monthly_returns: {},
    }
  }

  const pnls = trades.map((t) => t.pnl_pct)
  const wins = pnls.filter((p) => p > 0)
  const losses = pnls.filter((p) => p <= 0)
  const n = trades.length

  let cumulative = 0, peak = 0, maxDd = 0
  const equityCurve = [0]
  for (const p of pnls) {
    cumulative += p; peak = Math.max(peak, cumulative)
    maxDd = Math.min(maxDd, cumulative - peak)
    equityCurve.push(Math.round(cumulative * 100) / 100)
  }

  const tp = trades.filter((t) => t.exit_reason === 'take_profit').length
  const sl = trades.filter((t) => t.exit_reason === 'stop_loss').length
  const ex = trades.filter((t) => t.exit_reason === 'expired').length

  return {
    ok: true, elapsed_ms: 5, source: 'ts-fallback',
    metrics: {
      total_signals: signals.length, matched_signals: matched.length, total_trades: n,
      win_rate_pct: Math.round(wins.length / n * 1000) / 10,
      total_pnl_pct: Math.round(pnls.reduce((a, b) => a + b, 0) * 100) / 100,
      total_pnl_usd: Math.round(pnls.reduce((a, b) => a + b, 0) / 100 * execConfig.amount_usd * n * 100) / 100,
      avg_win_pct: wins.length ? Math.round(wins.reduce((a, b) => a + b, 0) / wins.length * 100) / 100 : 0,
      avg_loss_pct: losses.length ? Math.round(losses.reduce((a, b) => a + b, 0) / losses.length * 100) / 100 : 0,
      max_drawdown_pct: Math.round(maxDd * 100) / 100,
      profit_factor: losses.length && losses.reduce((a, b) => a + b, 0) !== 0
        ? Math.round(Math.abs(wins.reduce((a, b) => a + b, 0) / losses.reduce((a, b) => a + b, 0)) * 100) / 100
        : 9999,
      sharpe_ratio: 0,
      avg_hold_hours: Math.round(trades.reduce((s, t) => s + t.hold_hours, 0) / n * 10) / 10,
      take_profit_rate_pct: Math.round(tp / n * 1000) / 10,
      stop_loss_rate_pct: Math.round(sl / n * 1000) / 10,
      expired_rate_pct: Math.round(ex / n * 1000) / 10,
    },
    trades: trades.slice(0, 50),
    equity_curve: equityCurve,
    monthly_returns: {},
  }
}

// ── Route handler ─────────────────────────────────────────────────────────────
export async function POST(req: NextRequest) {
  const body = await req.json()

  // Try Python backtester first
  try {
    const res = await fetch(`${BACKTESTER_URL}/backtest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30_000), // 30s timeout
    })
    if (!res.ok) throw new Error(`Backtester returned HTTP ${res.status}`)
    const data = await res.json()
    return NextResponse.json({ ...data, source: 'python' })
  } catch {
    // Python service offline → use TS fallback
    const result = tsFallbackBacktest(body as Record<string, unknown>)
    return NextResponse.json(result)
  }
}

// GET — health check for backtester service
export async function GET() {
  try {
    const res = await fetch(`${BACKTESTER_URL}/health`, {
      signal: AbortSignal.timeout(3000),
    })
    const data = await res.json()
    return NextResponse.json({ pythonService: data, available: true })
  } catch {
    return NextResponse.json({
      pythonService: null,
      available: false,
      message: 'Python backtester offline — TypeScript fallback active',
    })
  }
}
