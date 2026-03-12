'use client'

import type { HotPickItem } from '@/hooks/useHotDailyPicks'

function fmt(n: number | undefined | null, prefix = '') {
  if (n == null || isNaN(n) || n === 0) return '—'
  if (n >= 1e9) return `${prefix}${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `${prefix}${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `${prefix}${(n / 1e3).toFixed(1)}K`
  return `${prefix}${n.toFixed(2)}`
}

function fmtPrice(n: number | undefined | null) {
  if (n == null || isNaN(n) || n === 0) return '—'
  if (n >= 1) return `$${n.toFixed(2)}`
  if (n >= 0.01) return `$${n.toFixed(4)}`
  if (n >= 0.0001) return `$${n.toFixed(6)}`
  return `$${n.toExponential(3)}`
}

const CHAIN_COLORS: Record<string, string> = {
  solana: '#9945FF',
  bsc: '#F0B90B',
  base: '#0052FF',
  eth: '#627EEA',
}

const CHAIN_LABELS: Record<string, string> = {
  solana: 'SOL',
  bsc: 'BSC',
  base: 'BASE',
  eth: 'ETH',
}

const REC_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  strong: { bg: 'rgba(14,203,129,0.15)', color: '#0ECB81', label: '强推' },
  normal: { bg: 'rgba(240,185,11,0.15)', color: '#F0B90B', label: '推荐' },
  weak: { bg: 'rgba(246,70,93,0.15)', color: '#F6465D', label: '观察' },
}

interface HotPicksTableProps {
  data: HotPickItem[]
  loading: boolean
  error: string | null
}

export function HotPicksTable({ data, loading, error }: HotPicksTableProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="h-16 rounded-xl animate-pulse"
            style={{ background: 'var(--bg-card2)', opacity: 1 - i * 0.08 }}
          />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-xl p-6 text-center border" style={{ background: 'var(--bg-card)', borderColor: 'rgba(246,70,93,0.3)', color: 'var(--red)' }}>
        <div className="text-sm font-semibold mb-1">&#9888;&#65039; 数据加载失败</div>
        <div className="text-xs" style={{ color: 'var(--text-dim)' }}>{error}</div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="rounded-xl p-8 text-center" style={{ background: 'var(--bg-card)' }}>
        <div className="text-2xl mb-2">&#128196;</div>
        <div className="text-sm font-medium" style={{ color: 'var(--text-dim)' }}>
          该日期暂无日榜数据
        </div>
        <div className="text-xs mt-1" style={{ color: 'var(--text-dim)', opacity: 0.7 }}>
          日榜每天 UTC 02:00 自动生成
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl overflow-hidden border" style={{ borderColor: 'var(--border)' }}>
      {/* Header */}
      <div
        className="grid text-xs font-semibold px-4 py-3"
        style={{
          gridTemplateColumns: '2rem 2fr 0.8fr 1fr 1fr 1fr 1fr 1fr',
          color: 'var(--text-dim)',
          background: 'var(--bg-card2)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <span>#</span>
        <span>代币</span>
        <span className="text-center">推荐</span>
        <span className="text-right">发现价</span>
        <span className="text-right">现价</span>
        <span className="text-right">收益</span>
        <span className="text-right">市值</span>
        <span className="text-right">评分</span>
      </div>

      {/* Rows */}
      {data.map((pick) => {
        const pnl = pick.pnl_pct
        const pnlColor = pnl === null ? 'var(--text-dim)'
          : pnl > 0 ? 'var(--green)'
          : pnl < 0 ? 'var(--red)'
          : 'var(--text-dim)'

        const rec = REC_STYLES[pick.pick_recommendation] || REC_STYLES.normal
        const chainColor = CHAIN_COLORS[pick.chain] || 'var(--text-dim)'
        const chainLabel = CHAIN_LABELS[pick.chain] || pick.chain

        return (
          <div
            key={`${pick.chain}-${pick.address}`}
            className="grid items-center px-4 py-3 text-sm transition-colors hover:bg-white/[0.02] cursor-pointer"
            style={{
              gridTemplateColumns: '2rem 2fr 0.8fr 1fr 1fr 1fr 1fr 1fr',
              borderBottom: '1px solid var(--border)',
              background: 'var(--bg-card)',
            }}
          >
            {/* Rank */}
            <span className="text-xs font-bold" style={{
              color: pick.rank <= 3 ? 'var(--yellow)' : 'var(--text-dim)',
            }}>
              {pick.rank}
            </span>

            {/* Token */}
            <div className="flex items-center gap-2">
              {pick.image_url ? (
                <img
                  src={pick.image_url}
                  alt={pick.symbol}
                  className="w-8 h-8 rounded-full object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
              ) : (
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                  style={{ background: `${chainColor}22`, color: chainColor }}
                >
                  {pick.symbol?.[0] ?? '?'}
                </div>
              )}
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-xs" style={{ color: 'var(--text)' }}>
                    {pick.symbol}
                  </span>
                  <span
                    className="text-[10px] px-1 py-0.5 rounded font-medium"
                    style={{ background: `${chainColor}22`, color: chainColor }}
                  >
                    {chainLabel}
                  </span>
                  {/* Social icons */}
                  <span className="flex gap-0.5 text-[10px]" style={{ color: 'var(--text-dim)' }}>
                    {pick.pick_has_twitter && <span title="Twitter">&#120143;</span>}
                    {pick.pick_has_telegram && <span title="Telegram">&#9993;</span>}
                    {pick.pick_has_website && <span title="Website">&#127760;</span>}
                  </span>
                </div>
                <div className="text-xs truncate" style={{ color: 'var(--text-dim)' }}>
                  {pick.name || `${pick.address.slice(0, 6)}...${pick.address.slice(-4)}`}
                </div>
              </div>
            </div>

            {/* Recommendation */}
            <div className="text-center">
              <span
                className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                style={{ background: rec.bg, color: rec.color }}
              >
                {rec.label}
              </span>
            </div>

            {/* Pick Price */}
            <div className="text-right font-mono text-xs" style={{ color: 'var(--text-dim)' }}>
              {fmtPrice(pick.pick_price)}
            </div>

            {/* Current Price */}
            <div className="text-right font-mono text-xs" style={{ color: 'var(--text)' }}>
              {fmtPrice(pick.current_price)}
            </div>

            {/* P&L */}
            <div className="text-right font-mono text-xs font-semibold" style={{ color: pnlColor }}>
              {pnl !== null ? (
                <>
                  {pnl > 0 ? '+' : ''}{pnl.toFixed(2)}%
                </>
              ) : '—'}
            </div>

            {/* Market Cap */}
            <div className="text-right text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
              {fmt(pick.current_market_cap || pick.pick_market_cap, '$')}
            </div>

            {/* Score */}
            <div className="text-right">
              <div className="text-xs font-bold" style={{ color: 'var(--yellow)' }}>
                {(pick.current_score ?? pick.pick_score)?.toFixed?.(1) ?? '—'}
              </div>
              <div className="text-[10px]" style={{ color: 'var(--text-dim)' }}>
                M{pick.pick_score_m?.toFixed?.(0) ?? '-'} Q{pick.pick_score_q?.toFixed?.(0) ?? '-'} P{pick.pick_score_p?.toFixed?.(0) ?? '-'}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
