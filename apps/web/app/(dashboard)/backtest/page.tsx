'use client'

import { useState } from 'react'
import {
  FlaskConical, Play, Loader2, AlertCircle, CheckCircle,
  TrendingUp, TrendingDown, BarChart3, Zap, Clock, Target,
} from 'lucide-react'
import { Topbar } from '@/components/layout/topbar'

// ── Types ─────────────────────────────────────────────────────────────────────
interface Condition {
  field: 'direction' | 'confidence_score' | 'chain_id' | 'risk_level'
  op: 'eq' | 'gte' | 'lte' | 'in'
  value: string | number | string[]
}

interface BacktestMetrics {
  total_signals: number
  matched_signals: number
  total_trades: number
  win_rate_pct: number
  total_pnl_pct: number
  total_pnl_usd: number
  avg_win_pct: number
  avg_loss_pct: number
  max_drawdown_pct: number
  profit_factor: number
  sharpe_ratio: number
  avg_hold_hours: number
  take_profit_rate_pct: number
  stop_loss_rate_pct: number
  expired_rate_pct: number
}

interface TradeResult {
  signal_id: string
  symbol: string
  chain_id: number
  direction: string
  entry_price: number
  exit_price: number
  pnl_pct: number
  pnl_usd: number
  exit_reason: 'take_profit' | 'stop_loss' | 'expired'
  hold_hours: number
  confidence_score: number
}

interface BacktestResult {
  ok: boolean
  elapsed_ms: number
  source: string
  metrics: BacktestMetrics
  trades: TradeResult[]
  equity_curve: number[]
}

// ── Preset strategies ─────────────────────────────────────────────────────────
const PRESETS = [
  {
    name: '聪明钱 BSC 高信心',
    conditions: [
      { field: 'direction' as const, op: 'eq' as const, value: 'long' },
      { field: 'confidence_score' as const, op: 'gte' as const, value: 70 },
      { field: 'chain_id' as const, op: 'in' as const, value: ['56'] },
    ],
  },
  {
    name: '全链低风险信号',
    conditions: [
      { field: 'direction' as const, op: 'eq' as const, value: 'long' },
      { field: 'confidence_score' as const, op: 'gte' as const, value: 80 },
      { field: 'risk_level' as const, op: 'eq' as const, value: 'low' },
    ],
  },
  {
    name: 'ETH 链高信心',
    conditions: [
      { field: 'direction' as const, op: 'eq' as const, value: 'long' },
      { field: 'confidence_score' as const, op: 'gte' as const, value: 65 },
      { field: 'chain_id' as const, op: 'in' as const, value: ['1'] },
    ],
  },
]

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtNum(n: number, dec = 2) {
  return n.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}

function ExitBadge({ reason }: { reason: string }) {
  const map = {
    take_profit: { label: '止盈', color: 'var(--green)' },
    stop_loss:   { label: '止损', color: 'var(--red)' },
    expired:     { label: '到期', color: 'var(--text-dim)' },
  }
  const s = map[reason as keyof typeof map] ?? { label: reason, color: 'var(--text-dim)' }
  return (
    <span className="text-xs px-1.5 py-0.5 rounded font-semibold"
      style={{ background: s.color + '18', color: s.color }}>
      {s.label}
    </span>
  )
}

// Mini equity curve SVG
function EquityCurve({ data }: { data: number[] }) {
  if (data.length < 2) return null
  const w = 400; const h = 60; const pad = 4
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (w - pad * 2)
    const y = pad + ((max - v) / range) * (h - pad * 2)
    return `${x},${y}`
  }).join(' ')
  const isPositive = data[data.length - 1] >= 0
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: 60 }}>
      <polyline
        points={pts}
        fill="none"
        stroke={isPositive ? 'var(--green)' : 'var(--red)'}
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function BacktestPage() {
  const [conditions, setConditions] = useState<Condition[]>([
    { field: 'direction', op: 'eq', value: 'long' },
    { field: 'confidence_score', op: 'gte', value: 70 },
    { field: 'chain_id', op: 'in', value: ['56'] },
  ])
  const [logic, setLogic] = useState<'AND' | 'OR'>('AND')
  const [stopLoss, setStopLoss] = useState(10)
  const [takeProfit, setTakeProfit] = useState(30)
  const [amountUsd, setAmountUsd] = useState(100)
  const [syntheticCount, setSyntheticCount] = useState(200)

  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [source, setSource] = useState<string>('')

  const loadPreset = (preset: typeof PRESETS[0]) => {
    setConditions(preset.conditions)
  }

  const handleRun = async () => {
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          condition_tree: { conditions, logic },
          exec_config: { amount_usd: amountUsd, slippage: 0.5, stop_loss_pct: stopLoss, take_profit_pct: takeProfit, max_gas_usd: 5 },
          signals: [],
          synthetic_count: syntheticCount,
        }),
      })
      const data = await res.json()
      if (!data.ok) throw new Error(data.detail ?? 'Backtest failed')
      setResult(data)
      setSource(data.source ?? '')
    } catch (err) {
      setError(err instanceof Error ? err.message : '运行失败')
    } finally {
      setRunning(false)
    }
  }

  const m = result?.metrics

  return (
    <div>
      <Topbar
        title="回测引擎"
        subtitle="Monte-Carlo 模拟 · 策略历史验证"
        actions={
          <button
            onClick={handleRun}
            disabled={running}
            className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-semibold"
            style={{ background: 'var(--yellow)', color: '#000', opacity: running ? 0.7 : 1 }}
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {running ? '运行中…' : '运行回测'}
          </button>
        }
      />

      <div className="p-6 space-y-5">

        <div className="grid grid-cols-2 gap-5">
          {/* ── Config ──────────────────────────────────────────────────── */}
          <div className="space-y-4">

            {/* Presets */}
            <div className="rounded-xl border p-4 space-y-3" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
              <div className="text-xs font-semibold" style={{ color: 'var(--text-dim)' }}>快速预设</div>
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p) => (
                  <button
                    key={p.name}
                    onClick={() => loadPreset(p)}
                    className="text-xs px-3 py-1.5 rounded-lg font-medium"
                    style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Conditions */}
            <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
              <div className="flex items-center justify-between px-4 py-3"
                style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-card2)' }}>
                <span className="text-xs font-semibold" style={{ color: 'var(--text)' }}>触发条件</span>
                <div className="flex gap-1">
                  {(['AND', 'OR'] as const).map((l) => (
                    <button key={l} onClick={() => setLogic(l)}
                      className="text-xs px-2 py-0.5 rounded"
                      style={{
                        background: logic === l ? 'rgba(114,137,218,0.2)' : 'var(--bg-card)',
                        color: logic === l ? '#7289da' : 'var(--text-dim)',
                      }}>
                      {l}
                    </button>
                  ))}
                </div>
              </div>
              <div className="p-4 space-y-2">
                {conditions.map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs p-2 rounded-lg"
                    style={{ background: 'var(--bg-card2)' }}>
                    <span style={{ color: 'var(--blue)' }}>{c.field}</span>
                    <span style={{ color: 'var(--text-dim)' }}>{c.op}</span>
                    <span style={{ color: 'var(--yellow)' }}>
                      {Array.isArray(c.value) ? (c.value as string[]).join('/') : String(c.value)}
                    </span>
                    <button onClick={() => setConditions(prev => prev.filter((_, idx) => idx !== i))}
                      className="ml-auto text-xs" style={{ color: 'var(--red)' }}>✕</button>
                  </div>
                ))}
                <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
                  使用策略创建页配置条件后可在此验证历史表现
                </p>
              </div>
            </div>

            {/* Exec config */}
            <div className="rounded-xl border p-4 space-y-4" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
              <div className="text-xs font-semibold" style={{ color: 'var(--text-dim)' }}>执行参数</div>
              {[
                { label: '单次金额 ($)', val: amountUsd, set: setAmountUsd, min: 10, max: 10000, step: 10, color: 'var(--yellow)' },
                { label: '止损 (%)', val: stopLoss, set: setStopLoss, min: 1, max: 50, step: 1, color: 'var(--red)' },
                { label: '止盈 (%)', val: takeProfit, set: setTakeProfit, min: 5, max: 200, step: 1, color: 'var(--green)' },
                { label: '合成信号数', val: syntheticCount, set: setSyntheticCount, min: 50, max: 500, step: 50, color: 'var(--blue)' },
              ].map(({ label, val, set, min, max, step, color }) => (
                <div key={label} className="flex items-center gap-3">
                  <span className="text-xs w-24 shrink-0" style={{ color: 'var(--text-dim)' }}>{label}</span>
                  <input type="range" min={min} max={max} step={step} value={val}
                    onChange={(e) => set(Number(e.target.value))}
                    className="flex-1 h-1.5 appearance-none rounded-full" style={{ accentColor: color }} />
                  <input type="number" min={min} max={max} step={step} value={val}
                    onChange={(e) => set(Number(e.target.value))}
                    className="w-16 text-right text-xs font-mono font-bold px-2 py-1 rounded-lg"
                    style={{ background: 'var(--bg-card2)', border: '1px solid var(--border)', color, outline: 'none' }} />
                </div>
              ))}
            </div>
          </div>

          {/* ── Results ─────────────────────────────────────────────────── */}
          <div className="space-y-4">
            {error && (
              <div className="rounded-xl border px-4 py-3 flex items-center gap-2 text-xs"
                style={{ background: 'rgba(246,70,93,0.08)', borderColor: 'rgba(246,70,93,0.3)', color: 'var(--red)' }}>
                <AlertCircle size={13} />{error}
              </div>
            )}

            {!result && !running && !error && (
              <div className="rounded-xl border flex flex-col items-center justify-center py-20 gap-3"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
                  style={{ background: 'rgba(240,185,11,0.1)' }}>
                  <FlaskConical size={28} color="var(--yellow)" />
                </div>
                <div className="text-sm font-semibold" style={{ color: 'var(--text)' }}>配置策略后点击运行回测</div>
                <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
                  基于 Monte-Carlo 模拟验证策略历史表现
                </div>
              </div>
            )}

            {running && (
              <div className="rounded-xl border flex flex-col items-center justify-center py-20 gap-3"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
                <Loader2 size={32} className="animate-spin" color="var(--yellow)" />
                <div className="text-sm" style={{ color: 'var(--text-dim)' }}>正在运行 Monte-Carlo 模拟…</div>
              </div>
            )}

            {result && m && (
              <div className="space-y-4">
                {/* Source badge */}
                <div className="flex items-center gap-2">
                  <CheckCircle size={14} color="var(--green)" />
                  <span className="text-xs" style={{ color: 'var(--green)' }}>
                    回测完成 · {result.elapsed_ms}ms
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--bg-card)', color: 'var(--text-dim)' }}>
                    {source === 'python' ? 'Python FastAPI' : 'TypeScript (备用引擎)'}
                  </span>
                </div>

                {/* Key metrics 2×3 */}
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { icon: TrendingUp, label: '总收益', value: `${m.total_pnl_pct > 0 ? '+' : ''}${fmtNum(m.total_pnl_pct)}%`, color: m.total_pnl_pct >= 0 ? 'var(--green)' : 'var(--red)' },
                    { icon: Target, label: '胜率', value: `${fmtNum(m.win_rate_pct)}%`, color: m.win_rate_pct >= 50 ? 'var(--green)' : 'var(--yellow)' },
                    { icon: BarChart3, label: '盈亏比', value: m.profit_factor >= 9000 ? '∞' : fmtNum(m.profit_factor), color: m.profit_factor >= 1.5 ? 'var(--green)' : 'var(--text-dim)' },
                    { icon: TrendingDown, label: '最大回撤', value: `${fmtNum(m.max_drawdown_pct)}%`, color: 'var(--red)' },
                    { icon: Zap, label: '匹配信号', value: `${m.matched_signals}/${m.total_signals}`, color: 'var(--blue)' },
                    { icon: Clock, label: '平均持仓', value: `${fmtNum(m.avg_hold_hours, 1)}h`, color: 'var(--text-dim)' },
                  ].map(({ icon: Icon, label, value, color }) => (
                    <div key={label} className="rounded-xl p-3 border"
                      style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
                      <div className="flex items-center gap-1.5 mb-1">
                        <Icon size={11} color={color} />
                        <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{label}</span>
                      </div>
                      <div className="text-lg font-black" style={{ color }}>{value}</div>
                    </div>
                  ))}
                </div>

                {/* Equity curve */}
                {result.equity_curve.length > 1 && (
                  <div className="rounded-xl border p-4" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
                    <div className="text-xs font-semibold mb-2" style={{ color: 'var(--text-dim)' }}>资金曲线 (累计 P&L %)</div>
                    <EquityCurve data={result.equity_curve} />
                    <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--text-dim)' }}>
                      <span>开始: 0%</span>
                      <span style={{ color: result.equity_curve[result.equity_curve.length - 1] >= 0 ? 'var(--green)' : 'var(--red)' }}>
                        结束: {fmtNum(result.equity_curve[result.equity_curve.length - 1])}%
                      </span>
                    </div>
                  </div>
                )}

                {/* Exit breakdown */}
                <div className="rounded-xl border p-4" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
                  <div className="text-xs font-semibold mb-2" style={{ color: 'var(--text-dim)' }}>退出原因分布</div>
                  <div className="flex gap-4 text-xs">
                    {[
                      { label: '止盈', val: m.take_profit_rate_pct, color: 'var(--green)' },
                      { label: '止损', val: m.stop_loss_rate_pct,   color: 'var(--red)' },
                      { label: '到期', val: m.expired_rate_pct,     color: 'var(--text-dim)' },
                    ].map(({ label, val, color }) => (
                      <div key={label} className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                        <span style={{ color: 'var(--text-dim)' }}>{label}</span>
                        <span className="font-bold" style={{ color }}>{fmtNum(val)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Trade list ──────────────────────────────────────────────────── */}
        {result && result.trades.length > 0 && (
          <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
            <div className="px-5 py-3 text-xs font-semibold"
              style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-card2)', color: 'var(--text)' }}>
              模拟交易记录（前 {Math.min(result.trades.length, 50)} 条）
            </div>
            <div className="grid text-xs font-semibold px-5 py-2"
              style={{
                gridTemplateColumns: '60px 60px 90px 90px 70px 80px 60px 70px',
                color: 'var(--text-dim)', borderBottom: '1px solid var(--border)', background: 'var(--bg-card2)',
              }}>
              <div>代币</div><div>链</div><div>入场价</div><div>出场价</div>
              <div className="text-right">P&L%</div><div className="text-right">持仓(h)</div>
              <div className="text-right">信心</div><div className="text-right">结果</div>
            </div>
            {result.trades.map((t, i) => (
              <div key={i} className="grid px-5 py-2.5 text-xs"
                style={{
                  gridTemplateColumns: '60px 60px 90px 90px 70px 80px 60px 70px',
                  borderBottom: '1px solid var(--border)',
                }}>
                <div className="font-bold" style={{ color: 'var(--text)' }}>{t.symbol}</div>
                <div style={{ color: 'var(--text-dim)' }}>{t.chain_id}</div>
                <div className="font-mono" style={{ color: 'var(--text-dim)' }}>{t.entry_price.toFixed(6)}</div>
                <div className="font-mono" style={{ color: 'var(--text-dim)' }}>{t.exit_price.toFixed(6)}</div>
                <div className="text-right font-mono font-bold"
                  style={{ color: t.pnl_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {t.pnl_pct >= 0 ? '+' : ''}{fmtNum(t.pnl_pct)}%
                </div>
                <div className="text-right font-mono" style={{ color: 'var(--text-dim)' }}>{t.hold_hours}h</div>
                <div className="text-right font-mono" style={{ color: 'var(--blue)' }}>{t.confidence_score}</div>
                <div className="text-right"><ExitBadge reason={t.exit_reason} /></div>
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  )
}
