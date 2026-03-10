'use client'

import { useState, useEffect, useCallback } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { AdminTopbar } from '../../components/topbar'

interface Signal {
  id: string
  token_address: string
  chain_id: number
  symbol?: string
  direction: 'long' | 'watch' | 'exit'
  confidence_score: number
  trigger_price?: number
  smart_money_count?: number
  risk_level: 'low' | 'medium' | 'high'
  status: 'active' | 'triggered' | 'expired' | 'cancelled'
  created_at: string
  expires_at?: string
}

const CHAIN_LABELS: Record<number, string> = { 1: 'ETH', 56: 'BSC', 900: 'SOL' }
const DIR_CONFIG: Record<string, { label: string; color: string }> = {
  long: { label: '做多', color: 'var(--green)' },
  watch: { label: '观察', color: 'var(--yellow)' },
  exit: { label: '退出', color: 'var(--red)' },
}
const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  active: { label: '活跃', color: 'var(--green)' },
  triggered: { label: '触发', color: 'var(--blue)' },
  expired: { label: '过期', color: 'var(--text-dim)' },
  cancelled: { label: '取消', color: 'var(--red)' },
}

function fmtDate(s?: string) {
  if (!s) return '—'
  return new Date(s).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function AdminSignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const [noSupabase, setNoSupabase] = useState(false)

  const fetchSignals = useCallback(async () => {
    setLoading(true)
    try {
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
      if (!supabaseUrl) { setNoSupabase(true); setLoading(false); return }
      // Phase 1: direct Supabase REST call
      const res = await fetch(`${supabaseUrl}/rest/v1/signals?order=created_at.desc&limit=50`, {
        headers: {
          'apikey': process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? '',
          'Authorization': `Bearer ${process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? ''}`,
        },
      })
      if (!res.ok) { setNoSupabase(true); setLoading(false); return }
      const data = await res.json()
      setSignals(Array.isArray(data) ? data : [])
    } catch {
      setNoSupabase(true)
      setSignals([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchSignals() }, [fetchSignals])

  return (
    <div>
      <AdminTopbar
        title="信号管理"
        subtitle="Supabase signals 表 · 只读查看"
        action={
          <button
            onClick={fetchSignals}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium"
            style={{ background: 'var(--bg-card)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
        }
      />

      <div className="p-6">
        {noSupabase && (
          <div
            className="mb-5 px-4 py-3 rounded-xl border text-sm"
            style={{ background: 'rgba(240,185,11,0.08)', borderColor: 'rgba(240,185,11,0.25)', color: 'var(--yellow)' }}
          >
            ⚠️ Supabase 未配置 — 信号数据需要配置数据库后才能查看
          </div>
        )}

        <div
          className="rounded-xl border overflow-hidden"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
        >
          {/* Header */}
          <div
            className="grid px-5 py-3 gap-3 text-xs font-semibold"
            style={{
              gridTemplateColumns: '1.5fr 0.8fr 0.8fr 0.8fr 1fr 1fr 0.8fr',
              color: 'var(--text-dim)',
              borderBottom: '1px solid var(--border)',
              background: 'var(--bg-card2)',
            }}
          >
            <div>代币</div>
            <div>链</div>
            <div>方向</div>
            <div className="text-right">信心分</div>
            <div className="text-right">触发价</div>
            <div>创建时间</div>
            <div className="text-center">状态</div>
          </div>

          {loading && (
            <div className="py-14 flex items-center justify-center gap-3" style={{ color: 'var(--text-dim)' }}>
              <Loader2 size={18} className="animate-spin" />
              <span className="text-sm">加载信号…</span>
            </div>
          )}

          {!loading && signals.length === 0 && (
            <div className="py-14 text-center" style={{ color: 'var(--text-dim)' }}>
              <div className="text-3xl mb-3">⚡</div>
              <div className="text-sm">暂无信号数据</div>
              <div className="text-xs mt-1">配置 Supabase 并运行信号引擎后数据会显示在这里</div>
            </div>
          )}

          {!loading &&
            signals.map((signal, i) => {
              const dir = DIR_CONFIG[signal.direction] ?? { label: signal.direction, color: 'var(--text-dim)' }
              const sts = STATUS_CONFIG[signal.status] ?? { label: signal.status, color: 'var(--text-dim)' }
              return (
                <div
                  key={signal.id}
                  className="grid items-center px-5 py-3 gap-3 text-sm"
                  style={{
                    gridTemplateColumns: '1.5fr 0.8fr 0.8fr 0.8fr 1fr 1fr 0.8fr',
                    borderBottom: i < signals.length - 1 ? '1px solid var(--border)' : 'none',
                  }}
                >
                  <div>
                    <div className="font-semibold" style={{ color: 'var(--text)' }}>
                      {signal.symbol ?? '—'}
                    </div>
                    <div className="text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
                      {signal.token_address.slice(0, 8)}…
                    </div>
                  </div>
                  <div>
                    <span
                      className="text-xs font-bold px-1.5 py-0.5 rounded"
                      style={{ color: 'var(--yellow)', background: 'rgba(240,185,11,0.12)' }}
                    >
                      {CHAIN_LABELS[signal.chain_id] ?? signal.chain_id}
                    </span>
                  </div>
                  <div>
                    <span
                      className="text-xs font-semibold px-2 py-0.5 rounded-full"
                      style={{ color: dir.color, background: `${dir.color}18` }}
                    >
                      {dir.label}
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-semibold" style={{ color: signal.confidence_score > 70 ? 'var(--green)' : signal.confidence_score > 40 ? 'var(--yellow)' : 'var(--red)' }}>
                      {signal.confidence_score}
                    </div>
                    <div className="mt-1 h-1 w-12 rounded-full ml-auto overflow-hidden" style={{ background: 'var(--bg-card2)' }}>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${signal.confidence_score}%`,
                          background: signal.confidence_score > 70 ? 'var(--green)' : signal.confidence_score > 40 ? 'var(--yellow)' : 'var(--red)',
                        }}
                      />
                    </div>
                  </div>
                  <div className="text-right font-mono text-xs" style={{ color: 'var(--text-dim)' }}>
                    {signal.trigger_price ? `$${signal.trigger_price}` : '—'}
                  </div>
                  <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
                    {fmtDate(signal.created_at)}
                  </div>
                  <div className="text-center">
                    <span
                      className="text-xs font-semibold px-2 py-0.5 rounded-full"
                      style={{ color: sts.color, background: `${sts.color}18` }}
                    >
                      {sts.label}
                    </span>
                  </div>
                </div>
              )
            })}
        </div>
      </div>
    </div>
  )
}
