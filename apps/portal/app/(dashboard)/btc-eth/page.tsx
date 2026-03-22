'use client'

import { useEffect, useState, useCallback } from 'react'
import { Topbar } from '../../components/topbar'
import { RefreshCw, TrendingUp, TrendingDown, AlertTriangle, CheckCircle, XCircle, Clock, Target } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://43.156.207.26'

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
  price_1h: number | null
  price_4h: number | null
  price_12h: number | null
  price_24h: number | null
  price_72h: number | null
  created_at: string
  closed_at: string | null
}

interface HealthCollector {
  name: string
  healthy: boolean
  last_success: number | null
  last_msg?: number
  consecutive_failures: number
  interval_seconds: number
}

export default function BtcEthPage() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [health, setHealth] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [sRes, hRes] = await Promise.allSettled([
        fetch(`${API}/api/btc-eth/signals?limit=100`).then(r => r.json()),
        fetch(`${API}/api/btc-eth/health`).then(r => r.json()),
      ])
      if (sRes.status === 'fulfilled') {
        const s = sRes.value
        setSignals(Array.isArray(s) ? s : s.signals || [])
      }
      if (hRes.status === 'fulfilled') setHealth(hRes.value)
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [load])

  // === 统计计算 ===
  const closed = signals.filter(s => s.status !== 'active')
  const active = signals.filter(s => s.status === 'active')
  const wins = closed.filter(s => s.status === 'hit_target')
  const losses = closed.filter(s => s.status === 'hit_stop')
  const winRate = closed.length > 0 ? (wins.length / closed.length * 100) : 0
  const avgWin = wins.length > 0 ? wins.reduce((a, s) => a + (s.actual_pnl_pct || 0), 0) / wins.length : 0
  const avgLoss = losses.length > 0 ? losses.reduce((a, s) => a + Math.abs(s.actual_pnl_pct || 0), 0) / losses.length : 0
  const profitFactor = avgLoss > 0 ? avgWin / avgLoss : 0
  const totalPnl = closed.reduce((a, s) => a + (s.actual_pnl_pct || 0), 0)

  // 按时间窗口统计
  const now = Date.now()
  const d7 = signals.filter(s => now - new Date(s.created_at).getTime() < 7 * 86400000)
  const d30 = signals.filter(s => now - new Date(s.created_at).getTime() < 30 * 86400000)
  const d7Closed = d7.filter(s => s.status !== 'active')
  const d30Closed = d30.filter(s => s.status !== 'active')
  const d7WinRate = d7Closed.length > 0 ? (d7Closed.filter(s => s.status === 'hit_target').length / d7Closed.length * 100) : 0
  const d30WinRate = d30Closed.length > 0 ? (d30Closed.filter(s => s.status === 'hit_target').length / d30Closed.length * 100) : 0
  const d7Pnl = d7Closed.reduce((a, s) => a + (s.actual_pnl_pct || 0), 0)
  const d30Pnl = d30Closed.reduce((a, s) => a + (s.actual_pnl_pct || 0), 0)

  // 采集器
  const collectors: HealthCollector[] = health?.collectors ? Object.values(health.collectors) : []
  const healthyCount = collectors.filter(c => c.healthy).length

  return (
    <>
      <Topbar
        title="BTC/ETH Agent 质量监控"
        subtitle="信号表现追踪 · 策略效果评估"
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

        {/* === 核心 KPI === */}
        <div className="grid grid-cols-6 gap-3">
          {[
            { label: '总信号数', value: `${signals.length}`, sub: `进行中 ${active.length}`, color: 'var(--blue)' },
            { label: '胜率', value: `${winRate.toFixed(1)}%`, sub: `${wins.length}胜 / ${losses.length}负`, color: winRate >= 55 ? 'var(--green)' : winRate >= 40 ? 'var(--yellow)' : 'var(--red)' },
            { label: '累计收益', value: `${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(1)}%`, sub: `已结信号 ${closed.length}`, color: totalPnl >= 0 ? 'var(--green)' : 'var(--red)' },
            { label: '盈亏比', value: profitFactor > 0 ? `${profitFactor.toFixed(1)}:1` : '-', sub: `均盈+${avgWin.toFixed(1)}% / 均亏-${avgLoss.toFixed(1)}%`, color: profitFactor >= 1.5 ? 'var(--green)' : 'var(--yellow)' },
            { label: '7天胜率', value: `${d7WinRate.toFixed(0)}%`, sub: `${d7.length}信号 / ${d7Pnl >= 0 ? '+' : ''}${d7Pnl.toFixed(1)}%`, color: d7WinRate >= 55 ? 'var(--green)' : 'var(--yellow)' },
            { label: '30天胜率', value: `${d30WinRate.toFixed(0)}%`, sub: `${d30.length}信号 / ${d30Pnl >= 0 ? '+' : ''}${d30Pnl.toFixed(1)}%`, color: d30WinRate >= 55 ? 'var(--green)' : 'var(--yellow)' },
          ].map(({ label, value, sub, color }) => (
            <div key={label} className="rounded-xl p-3 text-center" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <div className="text-xs mb-1" style={{ color: 'var(--text-dim)' }}>{label}</div>
              <div className="text-xl font-bold" style={{ color }}>{value}</div>
              <div className="text-xs mt-1" style={{ color: 'var(--text-dim)' }}>{sub}</div>
            </div>
          ))}
        </div>

        {/* === 信号历史列表（核心） === */}
        <div className="rounded-xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
              信号追踪（入场价 vs 实际走势）
            </div>
          </div>

          {/* 表头 */}
          <div className="grid grid-cols-12 gap-2 px-4 py-2 text-xs font-medium" style={{ color: 'var(--text-dim)', borderBottom: '1px solid var(--border)' }}>
            <div className="col-span-1">时间</div>
            <div className="col-span-1">资产</div>
            <div className="col-span-1">方向</div>
            <div className="col-span-1">入场</div>
            <div className="col-span-1">止损</div>
            <div className="col-span-1">止盈</div>
            <div className="col-span-1">1h</div>
            <div className="col-span-1">4h</div>
            <div className="col-span-1">24h</div>
            <div className="col-span-1">72h</div>
            <div className="col-span-1">结果</div>
            <div className="col-span-1">盈亏</div>
          </div>

          {signals.length === 0 ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
              暂无信号数据，Agent 正在积累分析...
            </div>
          ) : (
            <div>
              {signals.map(s => {
                const isLong = s.signal_type === 'long'
                const pnl = s.actual_pnl_pct

                const pctAt = (price: number | null) => {
                  if (price == null || s.entry_price === 0) return null
                  return ((price - s.entry_price) / s.entry_price * 100) * (isLong ? 1 : -1)
                }

                const pct1h = pctAt(s.price_1h)
                const pct4h = pctAt(s.price_4h)
                const pct24h = pctAt(s.price_24h)
                const pct72h = pctAt(s.price_72h)

                const fmtPct = (v: number | null) => {
                  if (v == null) return <span style={{ color: 'var(--text-dim)' }}>-</span>
                  return <span style={{ color: v >= 0 ? 'var(--green)' : 'var(--red)' }}>{v >= 0 ? '+' : ''}{v.toFixed(1)}%</span>
                }

                const statusIcon = s.status === 'active' ? <Clock size={12} style={{ color: 'var(--blue)' }} /> :
                  s.status === 'hit_target' ? <CheckCircle size={12} style={{ color: 'var(--green)' }} /> :
                  s.status === 'hit_stop' ? <XCircle size={12} style={{ color: 'var(--red)' }} /> :
                  <Target size={12} style={{ color: 'var(--text-dim)' }} />

                const statusText = s.status === 'active' ? '进行中' :
                  s.status === 'hit_target' ? '止盈' :
                  s.status === 'hit_stop' ? '止损' :
                  s.status === 'expired' ? '过期' : s.status

                return (
                  <div
                    key={s.id}
                    className="grid grid-cols-12 gap-2 px-4 py-2.5 text-xs items-center hover:bg-white/5 transition-colors"
                    style={{ borderBottom: '1px solid var(--border)' }}
                  >
                    <div className="col-span-1" style={{ color: 'var(--text-dim)' }}>
                      {new Date(s.created_at).toLocaleDateString('zh', { month: 'numeric', day: 'numeric' })}
                      <br />
                      {new Date(s.created_at).toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' })}
                    </div>
                    <div className="col-span-1 font-bold" style={{ color: 'var(--text)' }}>{s.asset}</div>
                    <div className="col-span-1">
                      <span
                        className="px-1.5 py-0.5 rounded text-xs"
                        style={{
                          background: isLong ? 'rgba(14,203,129,0.15)' : 'rgba(246,70,93,0.15)',
                          color: isLong ? 'var(--green)' : 'var(--red)',
                        }}
                      >
                        {isLong ? '做多' : '做空'}
                      </span>
                    </div>
                    <div className="col-span-1" style={{ color: 'var(--text)' }}>${s.entry_price.toLocaleString()}</div>
                    <div className="col-span-1" style={{ color: 'var(--red)' }}>${s.stop_loss.toLocaleString()}</div>
                    <div className="col-span-1" style={{ color: 'var(--green)' }}>${s.target_price.toLocaleString()}</div>
                    <div className="col-span-1">{fmtPct(pct1h)}</div>
                    <div className="col-span-1">{fmtPct(pct4h)}</div>
                    <div className="col-span-1">{fmtPct(pct24h)}</div>
                    <div className="col-span-1">{fmtPct(pct72h)}</div>
                    <div className="col-span-1 flex items-center gap-1">
                      {statusIcon}
                      <span style={{
                        color: s.status === 'active' ? 'var(--blue)' :
                          s.status === 'hit_target' ? 'var(--green)' :
                          s.status === 'hit_stop' ? 'var(--red)' : 'var(--text-dim)'
                      }}>
                        {statusText}
                      </span>
                    </div>
                    <div className="col-span-1 font-bold">
                      {pnl != null ? (
                        <span style={{ color: pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                          {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-dim)' }}>-</span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* === 采集器健康（折叠） === */}
        <details className="rounded-xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <summary className="px-4 py-3 cursor-pointer text-sm font-semibold" style={{ color: 'var(--text)' }}>
            数据采集器 ({healthyCount}/{collectors.length} 正常) — 点击展开
          </summary>
          <div className="px-4 pb-3 grid grid-cols-2 gap-1">
            {collectors.map(c => {
              const lastTime = c.last_success || c.last_msg || 0
              const ago = lastTime > 0 ? Math.round((Date.now() / 1000 - lastTime) / 60) : -1
              const agoText = ago < 0 ? '从未' : ago === 0 ? '刚刚' : ago < 60 ? `${ago}m前` : `${Math.round(ago / 60)}h前`
              return (
                <div key={c.name} className="flex items-center gap-2 py-1 text-xs">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ background: c.healthy ? 'var(--green)' : 'var(--red)' }} />
                  <span style={{ color: 'var(--text)' }}>{c.name.replace(/_/g, ' ')}</span>
                  <span style={{ color: 'var(--text-dim)' }}>{agoText}</span>
                  {c.consecutive_failures > 0 && <span style={{ color: 'var(--red)' }}>失败{c.consecutive_failures}次</span>}
                </div>
              )
            })}
          </div>
        </details>

      </div>
    </>
  )
}
