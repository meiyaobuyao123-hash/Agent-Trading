'use client'

import { useState } from 'react'
import { RefreshCw, TrendingUp, TrendingDown, Minus, Star, Loader2 } from 'lucide-react'
import { Topbar } from '@/components/layout/topbar'
import { useOfficialPortfolio, type PortfolioToken } from '@/hooks/useOfficialPortfolio'

// =====================================================
// Utils
// =====================================================
const CHAIN_LABELS: Record<number, string> = { 1: 'ETH', 56: 'BSC', 900: 'SOL' }
const CHAIN_COLORS: Record<number, string> = {
  1: 'var(--blue)',
  56: 'var(--yellow)',
  900: 'var(--purple)',
}
const RISK_COLORS: Record<string, string> = {
  low: 'var(--green)',
  medium: 'var(--yellow)',
  high: 'var(--red)',
}
const RISK_LABELS: Record<string, string> = { low: '低风险', medium: '中风险', high: '高风险' }

function fmtPrice(n: number | undefined): string {
  if (n === undefined || n === 0 || isNaN(n)) return '—'
  if (n >= 1000) return `$${n.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
  if (n >= 1) return `$${n.toFixed(4)}`
  if (n >= 0.001) return `$${n.toFixed(6)}`
  return `$${n.toExponential(3)}`
}

function fmtPnl(n: number | undefined): string {
  if (n === undefined || isNaN(n)) return '—'
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}

function fmtDate(dateStr?: string): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

function daysSince(dateStr?: string): number {
  if (!dateStr) return 0
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / (1000 * 60 * 60 * 24))
}

// =====================================================
// Token Avatar
// =====================================================
function TokenAvatar({ token }: { token: PortfolioToken }) {
  const color = CHAIN_COLORS[token.chainId] ?? 'var(--yellow)'
  return token.logoUrl ? (
    <img
      src={token.logoUrl}
      alt={token.symbol}
      className="w-9 h-9 rounded-full object-cover shrink-0"
      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
    />
  ) : (
    <div
      className="w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm shrink-0"
      style={{ background: `${color}22`, color }}
    >
      {token.symbol?.[0] ?? '?'}
    </div>
  )
}

// =====================================================
// P&L Display
// =====================================================
function PnlDisplay({ pct, abs }: { pct?: number; abs?: number }) {
  if (pct === undefined) return <span style={{ color: 'var(--text-dim)' }}>—</span>
  const color = pct > 0 ? 'var(--green)' : pct < 0 ? 'var(--red)' : 'var(--text-dim)'
  const Icon = pct > 0 ? TrendingUp : pct < 0 ? TrendingDown : Minus
  return (
    <div className="flex flex-col items-end">
      <div className="flex items-center gap-1 font-mono font-semibold text-sm" style={{ color }}>
        <Icon size={12} />
        {fmtPnl(pct)}
      </div>
      {abs !== undefined && (
        <div className="text-xs font-mono" style={{ color }}>
          {abs > 0 ? '+' : ''}{fmtPrice(Math.abs(abs))}
        </div>
      )}
    </div>
  )
}

// =====================================================
// Portfolio Token Row
// =====================================================
function PortfolioRow({ token, isEven }: { token: PortfolioToken; isEven: boolean }) {
  const exitPnl =
    token.status === 'exited' && token.exitPrice && token.entryPrice
      ? ((token.exitPrice - token.entryPrice) / token.entryPrice) * 100
      : undefined
  const exitPnlAbs =
    token.status === 'exited' && token.exitPrice && token.entryPrice
      ? token.exitPrice - token.entryPrice
      : undefined

  const chainColor = CHAIN_COLORS[token.chainId] ?? 'var(--text-dim)'

  return (
    <div
      className="grid items-center px-5 py-4 gap-3 text-sm hover:bg-white/[0.02] transition-colors"
      style={{
        gridTemplateColumns: '2.5fr 1fr 1fr 1fr 1.2fr 1fr 1fr',
        background: isEven ? 'transparent' : 'rgba(255,255,255,0.015)',
        borderBottom: '1px solid var(--border)',
      }}
    >
      {/* Token */}
      <div className="flex items-center gap-2.5">
        <TokenAvatar token={token} />
        <div className="min-w-0">
          <div className="font-bold" style={{ color: 'var(--text)' }}>{token.symbol}</div>
          {token.name && (
            <div className="text-xs truncate" style={{ color: 'var(--text-dim)' }}>{token.name}</div>
          )}
        </div>
        <span
          className="text-xs font-bold px-1.5 py-0.5 rounded shrink-0"
          style={{ color: chainColor, background: `${chainColor}22` }}
        >
          {CHAIN_LABELS[token.chainId] ?? token.chainId}
        </span>
        <span
          className="text-xs px-1.5 py-0.5 rounded shrink-0"
          style={{
            color: RISK_COLORS[token.riskLevel],
            background: `${RISK_COLORS[token.riskLevel]}18`,
          }}
        >
          {RISK_LABELS[token.riskLevel]}
        </span>
      </div>

      {/* Entry Date */}
      <div className="text-center">
        <div style={{ color: 'var(--text)' }}>{fmtDate(token.entryAt)}</div>
        <div className="text-xs" style={{ color: 'var(--text-dim)' }}>{daysSince(token.entryAt)}天前</div>
      </div>

      {/* Entry Price */}
      <div className="font-mono text-right" style={{ color: 'var(--text-dim)' }}>
        {fmtPrice(token.entryPrice)}
      </div>

      {/* Current / Exit Price */}
      <div className="font-mono text-right">
        {token.status === 'active' ? (
          token.currentPrice ? (
            <span style={{ color: 'var(--text)' }}>{fmtPrice(token.currentPrice)}</span>
          ) : (
            <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>加载中…</span>
          )
        ) : (
          <span style={{ color: 'var(--text-dim)' }}>{fmtPrice(token.exitPrice)}</span>
        )}
      </div>

      {/* P&L */}
      <div className="text-right">
        {token.status === 'active' ? (
          <PnlDisplay pct={token.pnlPercent} abs={token.pnlAbs} />
        ) : (
          <PnlDisplay pct={exitPnl} abs={exitPnlAbs} />
        )}
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-1">
        {token.reasonTags.slice(0, 2).map((tag) => (
          <span
            key={tag}
            className="text-xs px-1.5 py-0.5 rounded"
            style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
          >
            {tag}
          </span>
        ))}
      </div>

      {/* Status */}
      <div className="text-center">
        {token.status === 'active' ? (
          <span
            className="text-xs font-semibold px-2 py-1 rounded-full"
            style={{ color: 'var(--green)', background: 'rgba(14,203,129,0.12)' }}
          >
            持仓中
          </span>
        ) : (
          <div>
            <span
              className="text-xs font-semibold px-2 py-1 rounded-full"
              style={{ color: 'var(--text-dim)', background: 'var(--bg-card2)' }}
            >
              已退出
            </span>
            {token.exitAt && (
              <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>
                {fmtDate(token.exitAt)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// =====================================================
// Stat Card
// =====================================================
function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string
  value: string
  sub?: string
  color: string
}) {
  return (
    <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <div className="text-xs mb-1" style={{ color: 'var(--text-dim)' }}>{label}</div>
      <div className="text-xl font-black" style={{ color }}>{value}</div>
      {sub && <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{sub}</div>}
    </div>
  )
}

// =====================================================
// Main Page
// =====================================================
type FilterType = 'all' | 'active' | 'exited'

export default function PortfolioPage() {
  const [filter, setFilter] = useState<FilterType>('all')
  const { tokens, loading, enriching, isDemo, error, lastUpdated, refresh, stats } =
    useOfficialPortfolio(60_000)

  const filtered = tokens.filter((t) => {
    if (filter === 'active') return t.status === 'active'
    if (filter === 'exited') return t.status === 'exited'
    return true
  })

  return (
    <div>
      <Topbar title="官方策略组合" subtitle="官方精选代币 · 聪明钱追踪 · 实时 P&L" />
      <div className="p-6 space-y-5">

        {/* Demo Banner */}
        {isDemo && (
          <div
            className="rounded-xl px-5 py-3 border flex items-center gap-3 text-sm"
            style={{
              background: 'rgba(240,185,11,0.08)',
              borderColor: 'rgba(240,185,11,0.25)',
            }}
          >
            <Star size={14} color="var(--yellow)" />
            <span style={{ color: 'var(--yellow)' }}>
              演示模式 — 配置 Supabase 后切换至真实官方组合数据
            </span>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard
            label="追踪代币"
            value={loading ? '—' : String(stats.total)}
            sub="官方精选"
            color="var(--blue)"
          />
          <StatCard
            label="持仓中"
            value={loading ? '—' : String(stats.activeCount)}
            sub="活跃头寸"
            color="var(--green)"
          />
          <StatCard
            label="已退出"
            value={loading ? '—' : String(stats.exitedCount)}
            sub="历史记录"
            color="var(--text-dim)"
          />
          <StatCard
            label="平均浮动 P&L"
            value={
              loading || stats.avgPnl === undefined
                ? '—'
                : `${stats.avgPnl > 0 ? '+' : ''}${stats.avgPnl.toFixed(2)}%`
            }
            sub={enriching ? '实时更新中…' : '持仓中代币'}
            color={
              stats.avgPnl === undefined
                ? 'var(--text-dim)'
                : stats.avgPnl > 0
                ? 'var(--green)'
                : stats.avgPnl < 0
                ? 'var(--red)'
                : 'var(--text-dim)'
            }
          />
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between">
          <div className="flex gap-1 rounded-lg p-1" style={{ background: 'var(--bg-card2)' }}>
            {(['all', 'active', 'exited'] as FilterType[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className="px-4 py-1.5 rounded-md text-xs font-semibold transition-all"
                style={{
                  background: filter === f ? 'var(--bg-card)' : 'transparent',
                  color: filter === f ? 'var(--text)' : 'var(--text-dim)',
                  boxShadow: filter === f ? '0 1px 4px rgba(0,0,0,0.3)' : 'none',
                }}
              >
                {f === 'all'
                  ? `全部 (${stats.total})`
                  : f === 'active'
                  ? `持仓中 (${stats.activeCount})`
                  : `已退出 (${stats.exitedCount})`}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            {enriching && (
              <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-dim)' }}>
                <Loader2 size={12} className="animate-spin" />
                加载实时价格…
              </div>
            )}
            {lastUpdated && !enriching && (
              <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                更新于{' '}
                {lastUpdated.toLocaleTimeString('zh-CN', {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </span>
            )}
            <button
              onClick={refresh}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-80"
              style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
            >
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
              刷新
            </button>
          </div>
        </div>

        {/* Table */}
        <div
          className="rounded-xl border overflow-hidden"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
        >
          {/* Table Header */}
          <div
            className="grid px-5 py-3 gap-3 text-xs font-semibold"
            style={{
              gridTemplateColumns: '2.5fr 1fr 1fr 1fr 1.2fr 1fr 1fr',
              color: 'var(--text-dim)',
              borderBottom: '1px solid var(--border)',
              background: 'var(--bg-card2)',
            }}
          >
            <div>代币</div>
            <div className="text-center">入选日期</div>
            <div className="text-right">入选价</div>
            <div className="text-right">当前/退出价</div>
            <div className="text-right">P&amp;L</div>
            <div>标签</div>
            <div className="text-center">状态</div>
          </div>

          {/* Loading */}
          {loading && (
            <div className="py-16 flex items-center justify-center gap-3" style={{ color: 'var(--text-dim)' }}>
              <Loader2 size={20} className="animate-spin" />
              <span className="text-sm">加载官方组合数据…</span>
            </div>
          )}

          {/* Error */}
          {!loading && error && (
            <div className="py-16 text-center">
              <div className="text-2xl mb-3">⚠️</div>
              <div className="text-sm mb-4" style={{ color: 'var(--text-dim)' }}>{error}</div>
              <button
                onClick={refresh}
                className="px-4 py-2 rounded-lg text-sm font-medium"
                style={{ background: 'var(--yellow)', color: '#000' }}
              >
                重试
              </button>
            </div>
          )}

          {/* Empty */}
          {!loading && !error && filtered.length === 0 && (
            <div className="py-16 text-center" style={{ color: 'var(--text-dim)' }}>
              <div className="text-3xl mb-3">📭</div>
              <div className="text-sm">
                {filter === 'active'
                  ? '暂无持仓代币'
                  : filter === 'exited'
                  ? '暂无退出记录'
                  : '官方组合为空'}
              </div>
            </div>
          )}

          {/* Rows */}
          {!loading &&
            !error &&
            filtered.map((token, i) => (
              <PortfolioRow key={token.id} token={token} isEven={i % 2 === 0} />
            ))}
        </div>

        {/* Footer */}
        {!loading && !error && (
          <div className="flex items-center justify-between text-xs" style={{ color: 'var(--text-dim)' }}>
            <span>价格数据来源：Binance Skills API · 实时价格60秒缓存</span>
            {stats.avgExitPnl !== undefined && (
              <span>
                历史退出平均收益：
                <span
                  style={{
                    color: stats.avgExitPnl >= 0 ? 'var(--green)' : 'var(--red)',
                    fontWeight: 600,
                  }}
                >
                  {stats.avgExitPnl > 0 ? '+' : ''}
                  {stats.avgExitPnl.toFixed(2)}%
                </span>
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
