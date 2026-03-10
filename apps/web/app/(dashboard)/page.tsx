'use client'

import Link from 'next/link'
import { TrendingUp, TrendingDown, Zap, Star, Briefcase, ArrowRight, Loader2 } from 'lucide-react'
import { Topbar } from '@/components/layout/topbar'
import { useSignals, type Signal } from '@/hooks/useSignals'
import { useOfficialPortfolio, type PortfolioToken } from '@/hooks/useOfficialPortfolio'
import { useMarketRank } from '@/hooks/useMarketRank'

// =====================================================
// Utils
// =====================================================
function fmtPrice(n: number | undefined): string {
  if (!n || isNaN(n)) return '—'
  if (n >= 1000) return `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
  if (n >= 1) return `$${n.toFixed(3)}`
  if (n >= 0.001) return `$${n.toFixed(5)}`
  return `$${n.toExponential(2)}`
}

function timeAgo(dateStr?: string): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h`
}

// =====================================================
// Stat Card
// =====================================================
function StatCard({
  label,
  value,
  sub,
  color,
  icon: Icon,
  loading,
  href,
}: {
  label: string
  value: string
  sub: string
  color: string
  icon: React.ComponentType<{ size?: number; color?: string }>
  loading?: boolean
  href?: string
}) {
  const content = (
    <div
      className="rounded-xl p-4 border h-full transition-all"
      style={{
        background: 'var(--bg-card)',
        borderColor: 'var(--border)',
        cursor: href ? 'pointer' : 'default',
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Icon size={14} color={color} />
        <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{label}</span>
      </div>
      {loading ? (
        <div className="flex items-center gap-2">
          <Loader2 size={16} className="animate-spin" style={{ color }} />
        </div>
      ) : (
        <div className="text-2xl font-black" style={{ color }}>{value}</div>
      )}
      <div className="text-xs mt-1" style={{ color: 'var(--text-dim)' }}>{sub}</div>
    </div>
  )
  return href ? <Link href={href} className="block">{content}</Link> : content
}

// =====================================================
// Mini Signal Row
// =====================================================
function SignalRow({ signal }: { signal: Signal }) {
  const dirConfig = {
    BUY: { label: '做多', color: 'var(--green)', bg: 'rgba(14,203,129,0.1)' },
    SELL: { label: '做空', color: 'var(--red)', bg: 'rgba(246,70,93,0.1)' },
    WATCH: { label: '观察', color: 'var(--yellow)', bg: 'rgba(240,185,11,0.1)' },
  }[signal.direction]

  return (
    <div
      className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.02] transition-colors"
      style={{ borderBottom: '1px solid var(--border)' }}
    >
      {signal.logoUrl ? (
        <img src={signal.logoUrl} alt={signal.symbol} className="w-7 h-7 rounded-full object-cover shrink-0" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
      ) : (
        <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0" style={{ background: 'var(--bg-card2)', color: dirConfig.color }}>
          {signal.symbol?.[0] ?? '?'}
        </div>
      )}

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{signal.symbol}</span>
          <span className="text-xs px-1.5 py-0.5 rounded-full font-semibold" style={{ color: dirConfig.color, background: dirConfig.bg }}>
            {dirConfig.label}
          </span>
        </div>
        <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
          触发价 {fmtPrice(signal.triggerPrice)} · {timeAgo(signal.createdAt)}
        </div>
      </div>

      {signal.confidenceScore !== undefined && (
        <div className="text-right shrink-0">
          <div className="text-xs font-mono font-semibold" style={{ color: signal.confidenceScore > 70 ? 'var(--green)' : signal.confidenceScore > 40 ? 'var(--yellow)' : 'var(--red)' }}>
            {signal.confidenceScore}
          </div>
          <div className="text-xs" style={{ color: 'var(--text-dim)' }}>信心</div>
        </div>
      )}
    </div>
  )
}

// =====================================================
// Mini Portfolio Row
// =====================================================
function PortfolioRow({ token }: { token: PortfolioToken }) {
  const pnl = token.pnlPercent
  const pnlColor = pnl === undefined ? 'var(--text-dim)' : pnl > 0 ? 'var(--green)' : pnl < 0 ? 'var(--red)' : 'var(--text-dim)'
  const PnlIcon = pnl && pnl > 0 ? TrendingUp : pnl && pnl < 0 ? TrendingDown : null

  return (
    <div
      className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.02] transition-colors"
      style={{ borderBottom: '1px solid var(--border)' }}
    >
      <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0" style={{ background: 'rgba(240,185,11,0.15)', color: 'var(--yellow)' }}>
        {token.symbol?.[0] ?? '?'}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{token.symbol}</span>
          <span className="text-xs px-1.5 py-0.5 rounded" style={{ color: 'var(--text-dim)', background: 'var(--bg-card2)' }}>
            {token.chainId === 56 ? 'BSC' : token.chainId === 1 ? 'ETH' : 'SOL'}
          </span>
        </div>
        <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
          入选 {fmtPrice(token.entryPrice)}
        </div>
      </div>

      <div className="text-right shrink-0">
        {pnl !== undefined ? (
          <div className="flex items-center gap-1 justify-end font-mono text-sm font-semibold" style={{ color: pnlColor }}>
            {PnlIcon && <PnlIcon size={11} />}
            {pnl > 0 ? '+' : ''}{pnl.toFixed(2)}%
          </div>
        ) : (
          <div className="text-xs" style={{ color: 'var(--text-dim)' }}>—</div>
        )}
        <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
          {token.currentPrice ? fmtPrice(token.currentPrice) : '加载中'}
        </div>
      </div>
    </div>
  )
}

// =====================================================
// Market Summary Bar
// =====================================================
function MarketSummaryBar() {
  const { data, loading } = useMarketRank({ chainId: '56', size: 5, refreshInterval: 60_000 })

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-4 py-2" style={{ background: 'var(--bg-card2)', borderBottom: '1px solid var(--border)' }}>
        <Loader2 size={12} className="animate-spin" style={{ color: 'var(--text-dim)' }} />
        <span className="text-xs" style={{ color: 'var(--text-dim)' }}>加载市场行情…</span>
      </div>
    )
  }

  return (
    <div
      className="flex items-center gap-6 px-5 py-2 overflow-x-auto"
      style={{ background: 'var(--bg-card2)', borderBottom: '1px solid var(--border)' }}
    >
      {data.slice(0, 6).map((token) => {
        const change = token.priceChangePercent24h ?? 0
        const changeColor = change > 0 ? 'var(--green)' : change < 0 ? 'var(--red)' : 'var(--text-dim)'
        return (
          <div key={token.address} className="flex items-center gap-1.5 shrink-0">
            <span className="text-xs font-semibold" style={{ color: 'var(--text)' }}>{token.symbol}</span>
            <span className="text-xs font-mono" style={{ color: 'var(--text-dim)' }}>{fmtPrice(token.price)}</span>
            <span className="text-xs font-mono font-semibold" style={{ color: changeColor }}>
              {change > 0 ? '+' : ''}{change.toFixed(2)}%
            </span>
          </div>
        )
      })}
      <span className="text-xs shrink-0" style={{ color: 'var(--text-dim)' }}>BSC Top 6 · 60s 更新</span>
    </div>
  )
}

// =====================================================
// Dashboard Page
// =====================================================
export default function DashboardPage() {
  const signals = useSignals('56', 30_000)
  const portfolio = useOfficialPortfolio(60_000)

  const activeSignals = signals.data.filter((s) => s.status === 'active' || !s.status)
  const buySignals = activeSignals.filter((s) => s.direction === 'BUY')
  const activePortfolio = portfolio.tokens.filter((t) => t.status === 'active')

  return (
    <div>
      <Topbar title="总览" subtitle="实时行情 · AI信号 · 策略追踪" />

      {/* Market Ticker Bar */}
      <MarketSummaryBar />

      <div className="p-6 space-y-5">

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard
            label="活跃信号"
            value={signals.loading ? '—' : String(activeSignals.length)}
            sub={signals.loading ? '加载中…' : `${buySignals.length} 做多 · 20s 更新`}
            color="var(--yellow)"
            icon={Zap}
            loading={signals.loading}
            href="/signals"
          />
          <StatCard
            label="做多信号"
            value={signals.loading ? '—' : String(buySignals.length)}
            sub="BSC 聪明钱信号"
            color="var(--green)"
            icon={TrendingUp}
            loading={signals.loading}
            href="/signals"
          />
          <StatCard
            label="官方组合"
            value={portfolio.loading ? '—' : String(activePortfolio.length)}
            sub={portfolio.isDemo ? '演示模式' : '追踪中'}
            color="var(--blue)"
            icon={Star}
            loading={portfolio.loading}
            href="/portfolio"
          />
          <StatCard
            label="平均 P&L"
            value={
              portfolio.loading || portfolio.stats.avgPnl === undefined
                ? '—'
                : `${portfolio.stats.avgPnl > 0 ? '+' : ''}${portfolio.stats.avgPnl.toFixed(2)}%`
            }
            sub={portfolio.enriching ? '实时计算中…' : '持仓浮动'}
            color={
              portfolio.stats.avgPnl === undefined
                ? 'var(--text-dim)'
                : portfolio.stats.avgPnl >= 0
                ? 'var(--green)'
                : 'var(--red)'
            }
            icon={Briefcase}
            loading={portfolio.loading}
            href="/portfolio"
          />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-2 gap-5">
          {/* Latest Signals */}
          <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
              <div className="flex items-center gap-2">
                <Zap size={13} color="var(--yellow)" />
                <span className="text-sm font-bold" style={{ color: 'var(--text)' }}>最新信号</span>
                {!signals.loading && (
                  <span className="text-xs px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(240,185,11,0.12)', color: 'var(--yellow)' }}>
                    {activeSignals.length}
                  </span>
                )}
              </div>
              <Link href="/signals" className="flex items-center gap-1 text-xs transition-opacity hover:opacity-70" style={{ color: 'var(--text-dim)' }}>
                查看全部 <ArrowRight size={11} />
              </Link>
            </div>

            {signals.loading && (
              <div className="py-12 flex items-center justify-center gap-2" style={{ color: 'var(--text-dim)' }}>
                <Loader2 size={16} className="animate-spin" />
                <span className="text-sm">加载信号…</span>
              </div>
            )}

            {!signals.loading && signals.error && (
              <div className="py-10 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
                ⚠️ {signals.error}
              </div>
            )}

            {!signals.loading && !signals.error && activeSignals.length === 0 && (
              <div className="py-10 text-center text-sm" style={{ color: 'var(--text-dim)' }}>暂无活跃信号</div>
            )}

            {!signals.loading && !signals.error && activeSignals.slice(0, 6).map((s) => (
              <SignalRow key={s.id ?? s.tokenAddress} signal={s} />
            ))}

            {!signals.loading && activeSignals.length > 6 && (
              <Link
                href="/signals"
                className="flex items-center justify-center gap-1.5 py-3 text-xs transition-opacity hover:opacity-70"
                style={{ color: 'var(--text-dim)' }}
              >
                还有 {activeSignals.length - 6} 个信号 <ArrowRight size={11} />
              </Link>
            )}
          </div>

          {/* Official Portfolio */}
          <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
              <div className="flex items-center gap-2">
                <Star size={13} color="var(--blue)" />
                <span className="text-sm font-bold" style={{ color: 'var(--text)' }}>官方策略组合</span>
                {portfolio.isDemo && (
                  <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(240,185,11,0.1)', color: 'var(--yellow)' }}>
                    演示
                  </span>
                )}
              </div>
              <Link href="/portfolio" className="flex items-center gap-1 text-xs transition-opacity hover:opacity-70" style={{ color: 'var(--text-dim)' }}>
                查看全部 <ArrowRight size={11} />
              </Link>
            </div>

            {portfolio.loading && (
              <div className="py-12 flex items-center justify-center gap-2" style={{ color: 'var(--text-dim)' }}>
                <Loader2 size={16} className="animate-spin" />
                <span className="text-sm">加载组合…</span>
              </div>
            )}

            {!portfolio.loading && !portfolio.error && activePortfolio.slice(0, 6).map((t) => (
              <PortfolioRow key={t.id} token={t} />
            ))}

            {!portfolio.loading && activePortfolio.length === 0 && (
              <div className="py-10 text-center text-sm" style={{ color: 'var(--text-dim)' }}>暂无持仓代币</div>
            )}

            {!portfolio.loading && activePortfolio.length > 6 && (
              <Link
                href="/portfolio"
                className="flex items-center justify-center gap-1.5 py-3 text-xs transition-opacity hover:opacity-70"
                style={{ color: 'var(--text-dim)' }}
              >
                还有 {activePortfolio.length - 6} 个持仓 <ArrowRight size={11} />
              </Link>
            )}
          </div>
        </div>

        {/* Footer Status Bar */}
        <div
          className="rounded-xl px-5 py-3 flex items-center justify-between text-xs"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-5" style={{ color: 'var(--text-dim)' }}>
            <span>
              <span style={{ color: 'var(--green)' }}>●</span> Binance API
            </span>
            <span>信号 20s 自动刷新</span>
            <span>组合 60s 自动刷新</span>
          </div>
          <div style={{ color: 'var(--text-dim)' }}>
            AiTrading v1.0 · Phase 1
          </div>
        </div>
      </div>
    </div>
  )
}
