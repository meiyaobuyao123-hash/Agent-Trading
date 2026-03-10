'use client'

import { useState } from 'react'
import { RefreshCw, Zap } from 'lucide-react'
import { Topbar } from '@/components/layout/topbar'
import { ChainFilterTabs } from '@/components/market/ChainFilter'
import { SignalCard } from '@/components/signals/SignalCard'
import { useSignals } from '@/hooks/useSignals'
import type { ChainFilter } from '@/hooks/useMarketRank'

type DirectionFilter = 'all' | 'BUY' | 'SELL' | 'WATCH'

const DIR_COLORS: Record<DirectionFilter, string> = {
  all: 'var(--yellow)',
  BUY: 'var(--green)',
  SELL: 'var(--red)',
  WATCH: 'var(--blue)',
}

export default function SignalsPage() {
  const [chain, setChain] = useState<ChainFilter>('')
  const [direction, setDirection] = useState<DirectionFilter>('all')
  const { data, loading, error, lastUpdated, refresh } = useSignals(chain, 20_000)

  const filtered = direction === 'all' ? data : data.filter((s) => s.direction === direction)

  const stats = {
    total: data.length,
    buy: data.filter((s) => s.direction === 'BUY').length,
    sell: data.filter((s) => s.direction === 'SELL').length,
    watch: data.filter((s) => s.direction === 'WATCH').length,
  }

  const statCards: { label: string; value: number; key: DirectionFilter }[] = [
    { label: '全部信号', value: stats.total, key: 'all' },
    { label: '做多信号', value: stats.buy, key: 'BUY' },
    { label: '做空信号', value: stats.sell, key: 'SELL' },
    { label: '观察信号', value: stats.watch, key: 'WATCH' },
  ]

  return (
    <div>
      <Topbar title="信号中心" subtitle="AI 生成交易信号 · 实时更新" />
      <div className="p-6 space-y-4">

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3">
          {statCards.map(({ label, value, key }) => {
            const color = DIR_COLORS[key]
            const active = direction === key
            return (
              <button
                key={key}
                onClick={() => setDirection(key)}
                className="rounded-xl px-4 py-3 border text-left transition-all"
                style={{
                  background: active ? 'var(--bg-card2)' : 'var(--bg-card)',
                  borderColor: active ? color : 'var(--border)',
                }}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <Zap size={12} color={color} />
                  <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{label}</span>
                </div>
                <div className="text-2xl font-black" style={{ color }}>
                  {loading ? '—' : value}
                </div>
              </button>
            )
          })}
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between">
          <ChainFilterTabs value={chain} onChange={setChain} />
          <div className="flex items-center gap-3">
            {lastUpdated && (
              <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                更新于 {lastUpdated.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
            <button
              onClick={refresh}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-80 transition-all"
              style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
            >
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
              刷新
            </button>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="grid grid-cols-2 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-44 rounded-xl animate-pulse" style={{ background: 'var(--bg-card)' }} />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-xl p-8 text-center border" style={{ background: 'var(--bg-card)', borderColor: 'rgba(246,70,93,0.3)' }}>
            <div className="text-sm font-semibold mb-1" style={{ color: 'var(--red)' }}>⚠️ 信号加载失败</div>
            <div className="text-xs mb-4" style={{ color: 'var(--text-dim)' }}>{error}</div>
            <button onClick={refresh} className="text-xs px-4 py-2 rounded-lg" style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}>
              重试
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-xl p-8 text-center" style={{ background: 'var(--bg-card)', color: 'var(--text-dim)' }}>
            <div className="text-2xl mb-2">📭</div>
            <div className="text-sm">暂无{direction !== 'all' ? `「${direction}」` : ''}信号</div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {filtered.map((signal, idx) => (
              <SignalCard key={signal.id ?? (signal.tokenAddress + idx)} signal={signal} rank={idx + 1} />
            ))}
          </div>
        )}

      </div>
    </div>
  )
}
