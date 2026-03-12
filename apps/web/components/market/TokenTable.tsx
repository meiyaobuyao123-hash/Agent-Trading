'use client'

import type { TokenRankItem } from '@/hooks/useMarketRank'

function fmt(n: number | undefined | null, prefix = '') {
  if (n == null || isNaN(n)) return '—'
  if (n >= 1e9) return `${prefix}${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `${prefix}${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `${prefix}${(n / 1e3).toFixed(2)}K`
  return `${prefix}${n.toFixed(2)}`
}

function fmtPrice(n: number | undefined | null) {
  if (n == null || isNaN(n)) return '—'
  if (n >= 1) return `$${n.toFixed(2)}`
  if (n >= 0.01) return `$${n.toFixed(4)}`
  if (n >= 0.0001) return `$${n.toFixed(6)}`
  return `$${n.toExponential(3)}`
}

const CHAIN_LABELS: Record<string, string> = {
  '1': 'ETH',
  '56': 'BSC',
  'CT_501': 'SOL',
  '8453': 'BASE',
}

interface TokenTableProps {
  data: TokenRankItem[]
  loading: boolean
  error: string | null
}

export function TokenTable({ data, loading, error }: TokenTableProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="h-14 rounded-xl animate-pulse"
            style={{ background: 'var(--bg-card2)', opacity: 1 - i * 0.08 }}
          />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-xl p-6 text-center border" style={{ background: 'var(--bg-card)', borderColor: 'rgba(246,70,93,0.3)', color: 'var(--red)' }}>
        <div className="text-sm font-semibold mb-1">⚠️ 数据加载失败</div>
        <div className="text-xs" style={{ color: 'var(--text-dim)' }}>{error}</div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="rounded-xl p-6 text-center text-sm" style={{ background: 'var(--bg-card)', color: 'var(--text-dim)' }}>
        暂无数据
      </div>
    )
  }

  return (
    <div className="rounded-xl overflow-hidden border" style={{ borderColor: 'var(--border)' }}>
      {/* Header */}
      <div
        className="grid text-xs font-semibold px-4 py-3"
        style={{
          gridTemplateColumns: '2rem 2fr 1fr 1.2fr 1.2fr 1fr 0.8fr',
          color: 'var(--text-dim)',
          background: 'var(--bg-card2)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <span>#</span>
        <span>代币</span>
        <span className="text-right">价格</span>
        <span className="text-right">24h 涨跌</span>
        <span className="text-right">24h 成交量</span>
        <span className="text-right">市值</span>
        <span className="text-right">链</span>
      </div>

      {/* Rows */}
      {data.map((token, idx) => {
        const change = token.priceChangePercent24h ?? 0
        const changeColor = change > 0 ? 'var(--green)' : change < 0 ? 'var(--red)' : 'var(--text-dim)'
        return (
          <div
            key={token.address + token.chainId}
            className="grid items-center px-4 py-3 text-sm transition-colors hover:bg-white/[0.02] cursor-pointer"
            style={{
              gridTemplateColumns: '2rem 2fr 1fr 1.2fr 1.2fr 1fr 0.8fr',
              borderBottom: '1px solid var(--border)',
              background: 'var(--bg-card)',
            }}
          >
            {/* Rank */}
            <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{idx + 1}</span>

            {/* Token */}
            <div className="flex items-center gap-2">
              {token.logoUrl ? (
                <img src={token.logoUrl} alt={token.symbol} className="w-7 h-7 rounded-full object-cover" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
              ) : (
                <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold" style={{ background: 'var(--bg-card2)', color: 'var(--yellow)' }}>
                  {token.symbol?.[0] ?? '?'}
                </div>
              )}
              <div>
                <div className="font-semibold text-xs" style={{ color: 'var(--text)' }}>{token.symbol}</div>
                <div className="text-xs truncate max-w-[100px]" style={{ color: 'var(--text-dim)' }}>
                  {token.address ? `${token.address.slice(0, 6)}...` : ''}
                </div>
              </div>
            </div>

            {/* Price */}
            <div className="text-right font-mono text-xs" style={{ color: 'var(--text)' }}>
              {fmtPrice(token.price)}
            </div>

            {/* 24h Change */}
            <div className="text-right font-mono text-xs font-semibold" style={{ color: changeColor }}>
              {change > 0 ? '+' : ''}{change.toFixed(2)}%
            </div>

            {/* Volume */}
            <div className="text-right text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
              {fmt(token.volume24h, '$')}
            </div>

            {/* Market Cap */}
            <div className="text-right text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
              {fmt(token.marketCap, '$')}
            </div>

            {/* Chain */}
            <div className="text-right">
              <span
                className="text-xs px-1.5 py-0.5 rounded font-medium"
                style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
              >
                {CHAIN_LABELS[String(token.chainId)] ?? token.chainId}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
