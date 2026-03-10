'use client'

import type { Signal } from '@/hooks/useSignals'

const CHAIN_LABELS: Record<number, string> = { 1: 'ETH', 56: 'BSC', 900: 'SOL' }

function fmtPrice(n: number | undefined) {
  if (!n || isNaN(n)) return '—'
  if (n >= 1) return `$${n.toFixed(2)}`
  if (n >= 0.001) return `$${n.toFixed(5)}`
  return `$${n.toExponential(3)}`
}

function timeAgo(dateStr?: string) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}小时前`
  return `${Math.floor(hrs / 24)}天前`
}

interface SignalCardProps {
  signal: Signal
  rank: number
}

export function SignalCard({ signal, rank }: SignalCardProps) {
  const change = signal.priceChangePercent ?? 0
  const changeColor = change > 0 ? 'var(--green)' : change < 0 ? 'var(--red)' : 'var(--text-dim)'

  const directionConfig = {
    BUY: { label: '做多', color: 'var(--green)', bg: 'rgba(14,203,129,0.1)', border: 'rgba(14,203,129,0.25)' },
    SELL: { label: '做空', color: 'var(--red)', bg: 'rgba(246,70,93,0.1)', border: 'rgba(246,70,93,0.25)' },
    WATCH: { label: '观察', color: 'var(--yellow)', bg: 'rgba(240,185,11,0.1)', border: 'rgba(240,185,11,0.25)' },
  }[signal.direction]

  const confidence = signal.confidenceScore ?? 0

  return (
    <div
      className="rounded-xl p-4 border transition-all hover:border-opacity-60 cursor-pointer"
      style={{
        background: 'var(--bg-card)',
        borderColor: directionConfig.border,
        borderLeft: `3px solid ${directionConfig.color}`,
      }}
    >
      <div className="flex items-start justify-between mb-3">
        {/* Token Info */}
        <div className="flex items-center gap-2.5">
          <span className="text-xs w-5 text-center" style={{ color: 'var(--text-dim)' }}>{rank}</span>
          {signal.logoUrl ? (
            <img src={signal.logoUrl} alt={signal.symbol} className="w-8 h-8 rounded-full object-cover" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
          ) : (
            <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold" style={{ background: 'var(--bg-card2)', color: directionConfig.color }}>
              {signal.symbol?.[0] ?? '?'}
            </div>
          )}
          <div>
            <div className="font-bold text-sm" style={{ color: 'var(--text)' }}>{signal.symbol}</div>
            <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
              {CHAIN_LABELS[signal.chainId] ?? signal.chainId}
              {signal.name ? ` · ${signal.name}` : ''}
            </div>
          </div>
        </div>

        {/* Direction Badge */}
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-bold px-2.5 py-1 rounded-full"
            style={{ color: directionConfig.color, background: directionConfig.bg }}
          >
            {directionConfig.label}
          </span>
        </div>
      </div>

      {/* Price + Change */}
      <div className="flex items-center gap-4 mb-3">
        <div>
          <div className="text-xs mb-0.5" style={{ color: 'var(--text-dim)' }}>触发价</div>
          <div className="font-mono text-sm font-semibold" style={{ color: 'var(--text)' }}>
            {fmtPrice(signal.triggerPrice)}
          </div>
        </div>
        <div>
          <div className="text-xs mb-0.5" style={{ color: 'var(--text-dim)' }}>24h 涨跌</div>
          <div className="font-mono text-sm font-semibold" style={{ color: changeColor }}>
            {change > 0 ? '+' : ''}{change.toFixed(2)}%
          </div>
        </div>
        <div className="flex-1" />
        {/* Confidence Bar */}
        <div className="text-right">
          <div className="text-xs mb-1" style={{ color: 'var(--text-dim)' }}>信心分 {confidence}</div>
          <div className="w-24 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-card2)' }}>
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${confidence}%`,
                background: confidence > 70 ? 'var(--green)' : confidence > 40 ? 'var(--yellow)' : 'var(--red)',
              }}
            />
          </div>
        </div>
      </div>

      {/* Tags */}
      {signal.tags && signal.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {signal.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="text-xs px-2 py-0.5 rounded"
              style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Reason */}
      {signal.reason && (
        <div className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--text-dim)' }}>
          {signal.reason}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
        <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
          {signal.signalType && `${signal.signalType} · `}
          {timeAgo(signal.createdAt)}
        </span>
        <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
          {signal.tokenAddress.slice(0, 6)}...{signal.tokenAddress.slice(-4)}
        </span>
      </div>
    </div>
  )
}
