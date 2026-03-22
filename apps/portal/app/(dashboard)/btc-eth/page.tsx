'use client'

import { useEffect, useState, useCallback } from 'react'
import { Topbar } from '../../components/topbar'
import { RefreshCw, TrendingUp, TrendingDown, AlertTriangle, Activity, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://43.156.207.26'

interface HealthData {
  running: boolean
  btc_price: number
  eth_price: number
  btc_rsi: number
  eth_rsi: number
  collectors: Record<string, {
    name: string
    healthy: boolean
    last_success: number | null
    consecutive_failures: number
    total_successes: number
    total_failures: number
    interval_seconds: number
    last_msg?: number
    streams?: number
    btc_price?: number
    eth_price?: number
  }>
  composite_scores: Record<string, Record<string, number>>
}

interface Signal {
  id: string
  asset: string
  signal_type: string
  entry_price: number
  stop_loss: number
  target_price: number
  risk_reward: number
  confidence: number
  reasoning: string
  status: string
  actual_pnl_pct: number | null
  created_at: string
}

interface Alert {
  id: string
  asset: string
  severity: string
  alert_type: string
  title: string
  message: string
  is_active: boolean
  created_at: string
}

interface Dashboard {
  btc: { price: number; change_24h: number }
  eth: { price: number; change_24h: number }
  indicators: Record<string, any>
  scores: Record<string, number>
}

export default function BtcEthPage() {
  const [health, setHealth] = useState<HealthData | null>(null)
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [signals, setSignals] = useState<Signal[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'BTC' | 'ETH'>('BTC')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [hRes, dRes, sRes, aRes] = await Promise.allSettled([
        fetch(`${API}/api/btc-eth/health`).then(r => r.json()),
        fetch(`${API}/api/btc-eth/dashboard`).then(r => r.json()),
        fetch(`${API}/api/btc-eth/signals?limit=20`).then(r => r.json()),
        fetch(`${API}/api/btc-eth/alerts?limit=10`).then(r => r.json()),
      ])
      if (hRes.status === 'fulfilled') setHealth(hRes.value)
      if (dRes.status === 'fulfilled') setDashboard(dRes.value)
      if (sRes.status === 'fulfilled') {
        const s = sRes.value
        setSignals(Array.isArray(s) ? s : s.signals || [])
      }
      if (aRes.status === 'fulfilled') {
        const a = aRes.value
        setAlerts(Array.isArray(a) ? a : a.alerts || [])
      }
    } catch (e) {
      console.error('BTC/ETH data load error:', e)
    }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [load])

  const scores = health?.composite_scores?.[tab] || { momentum: 50, sentiment: 50, onchain: 50, macro: 50, risk: 50 }
  const price = tab === 'BTC' ? (health?.btc_price || 0) : (health?.eth_price || 0)
  const rsi = tab === 'BTC' ? (health?.btc_rsi || 50) : (health?.eth_rsi || 50)
  const change24h = tab === 'BTC' ? (dashboard?.btc?.change_24h || 0) : (dashboard?.eth?.change_24h || 0)

  const collectors = health?.collectors || {}
  const collectorList = Object.values(collectors)
  const healthyCount = collectorList.filter(c => c.healthy).length
  const totalCount = collectorList.length

  return (
    <>
      <Topbar
        title="BTC/ETH 智能投资"
        subtitle={`${healthyCount}/${totalCount} 采集器正常`}
        action={
          <button
            onClick={load}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs"
            style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
        }
      />

      <div className="p-6 space-y-5">

        {/* === Price Cards === */}
        <div className="flex gap-4">
          {(['BTC', 'ETH'] as const).map(asset => {
            const p = asset === 'BTC' ? (health?.btc_price || 0) : (health?.eth_price || 0)
            const c = asset === 'BTC' ? (dashboard?.btc?.change_24h || 0) : (dashboard?.eth?.change_24h || 0)
            const active = tab === asset
            return (
              <button
                key={asset}
                onClick={() => setTab(asset)}
                className="flex-1 rounded-xl p-4 transition-all"
                style={{
                  background: active ? 'rgba(30,128,255,0.1)' : 'var(--bg-card)',
                  border: active ? '1px solid var(--blue)' : '1px solid var(--border)',
                }}
              >
                <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-dim)' }}>{asset}/USDT</div>
                <div className="text-2xl font-bold" style={{ color: 'var(--text)' }}>
                  ${p.toLocaleString(undefined, { maximumFractionDigits: asset === 'BTC' ? 0 : 2 })}
                </div>
                <div className="text-sm mt-1" style={{ color: c >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {c >= 0 ? '+' : ''}{c.toFixed(2)}%
                </div>
              </button>
            )
          })}
        </div>

        {/* === Composite Scores === */}
        <div className="rounded-xl p-4" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text)' }}>
            {tab} 综合评分
          </div>
          <div className="grid grid-cols-5 gap-3">
            {[
              { key: 'momentum', label: '趋势', icon: TrendingUp },
              { key: 'sentiment', label: '情绪', icon: Activity },
              { key: 'onchain', label: '链上', icon: ArrowUpRight },
              { key: 'macro', label: '宏观', icon: ArrowDownRight },
              { key: 'risk', label: '安全', icon: AlertTriangle },
            ].map(({ key, label, icon: Icon }) => {
              const val = (scores as any)[key] || 50
              const color = val >= 70 ? 'var(--green)' : val >= 40 ? 'var(--yellow)' : 'var(--red)'
              return (
                <div key={key} className="text-center">
                  <Icon size={16} className="mx-auto mb-1" style={{ color }} />
                  <div className="text-lg font-bold" style={{ color }}>{val}</div>
                  <div className="text-xs" style={{ color: 'var(--text-dim)' }}>{label}</div>
                  <div className="mt-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-card2)' }}>
                    <div className="h-full rounded-full" style={{ width: `${val}%`, background: color }} />
                  </div>
                </div>
              )
            })}
          </div>
          <div className="mt-3 flex items-center gap-4 text-xs" style={{ color: 'var(--text-dim)' }}>
            <span>RSI(14): <b style={{ color: rsi > 70 ? 'var(--red)' : rsi < 30 ? 'var(--green)' : 'var(--text)' }}>{rsi}</b></span>
            <span>恐慌指数: <b style={{ color: (dashboard?.indicators?.fear_greed_index || 50) < 25 ? 'var(--red)' : 'var(--text)' }}>{dashboard?.indicators?.fear_greed_index || '-'}</b></span>
            <span>资金费率: <b>{dashboard?.indicators?.funding_rate != null ? (dashboard.indicators.funding_rate * 100).toFixed(4) + '%' : '-'}</b></span>
          </div>
        </div>

        {/* === Alerts === */}
        {alerts.length > 0 && (
          <div className="space-y-2">
            <div className="text-sm font-semibold" style={{ color: 'var(--text)' }}>⚠️ 风险预警</div>
            {alerts.slice(0, 5).map(a => (
              <div
                key={a.id}
                className="rounded-lg p-3 flex items-start gap-2"
                style={{
                  background: a.severity === 'critical' ? 'rgba(246,70,93,0.1)' : 'rgba(255,156,62,0.1)',
                  border: `1px solid ${a.severity === 'critical' ? 'var(--red)' : 'var(--orange)'}`,
                }}
              >
                <AlertTriangle size={14} style={{ color: a.severity === 'critical' ? 'var(--red)' : 'var(--orange)', marginTop: 2 }} />
                <div>
                  <div className="text-xs font-semibold" style={{ color: 'var(--text)' }}>{a.title}</div>
                  <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{a.message}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* === Signals === */}
        <div className="rounded-xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="text-sm font-semibold" style={{ color: 'var(--text)' }}>交易信号</div>
            <div className="text-xs" style={{ color: 'var(--text-dim)' }}>{signals.length} 个信号</div>
          </div>
          {signals.length === 0 ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
              暂无信号，Agent 正在分析市场数据...
            </div>
          ) : (
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {signals.map(s => {
                const isLong = s.signal_type === 'long'
                const pnl = s.actual_pnl_pct
                return (
                  <div key={s.id} className="px-4 py-3 flex items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ background: isLong ? 'rgba(14,203,129,0.15)' : 'rgba(246,70,93,0.15)' }}
                    >
                      {isLong ? <TrendingUp size={14} style={{ color: 'var(--green)' }} /> : <TrendingDown size={14} style={{ color: 'var(--red)' }} />}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold" style={{ color: 'var(--text)' }}>{s.asset}</span>
                        <span
                          className="text-xs px-1.5 py-0.5 rounded"
                          style={{ background: isLong ? 'rgba(14,203,129,0.2)' : 'rgba(246,70,93,0.2)', color: isLong ? 'var(--green)' : 'var(--red)' }}
                        >
                          {isLong ? '做多' : '做空'}
                        </span>
                        <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                          置信度 {s.confidence}%
                        </span>
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>
                        入场 ${s.entry_price.toLocaleString()} → 止盈 ${s.target_price.toLocaleString()} | 止损 ${s.stop_loss.toLocaleString()} | R:R {s.risk_reward?.toFixed(1)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div
                        className="text-xs font-bold"
                        style={{
                          color: s.status === 'active' ? 'var(--blue)' :
                            s.status === 'hit_target' ? 'var(--green)' :
                            s.status === 'hit_stop' ? 'var(--red)' : 'var(--text-dim)'
                        }}
                      >
                        {s.status === 'active' ? '进行中' :
                         s.status === 'hit_target' ? '✅ 止盈' :
                         s.status === 'hit_stop' ? '❌ 止损' :
                         s.status === 'expired' ? '已过期' : s.status}
                      </div>
                      {pnl != null && (
                        <div className="text-xs" style={{ color: pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                          {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%
                        </div>
                      )}
                      <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>
                        {new Date(s.created_at).toLocaleDateString('zh', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* === Collector Health === */}
        <div className="rounded-xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
              数据采集器健康 ({healthyCount}/{totalCount})
            </div>
          </div>
          <div className="grid grid-cols-2 gap-0">
            {collectorList.map(c => {
              const lastTime = c.last_success || c.last_msg || 0
              const ago = lastTime > 0 ? Math.round((Date.now() / 1000 - lastTime) / 60) : -1
              const agoText = ago < 0 ? '从未' : ago === 0 ? '刚刚' : `${ago}min前`
              const freq = c.interval_seconds >= 86400 ? '每日' :
                c.interval_seconds >= 3600 ? `${Math.round(c.interval_seconds / 3600)}h` :
                c.interval_seconds >= 60 ? `${Math.round(c.interval_seconds / 60)}min` : `${c.interval_seconds}s`
              return (
                <div key={c.name} className="px-4 py-2 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ background: c.healthy ? 'var(--green)' : 'var(--red)' }}
                  />
                  <div className="flex-1 text-xs" style={{ color: 'var(--text)' }}>
                    {c.name.replace(/_/g, ' ')}
                  </div>
                  <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
                    {freq}
                  </div>
                  <div className="text-xs" style={{ color: c.healthy ? 'var(--text-dim)' : 'var(--red)' }}>
                    {agoText}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

      </div>
    </>
  )
}
