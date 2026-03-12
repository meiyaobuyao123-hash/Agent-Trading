'use client'

import { useState } from 'react'
import { RefreshCw, ChevronLeft, ChevronRight, Calendar } from 'lucide-react'
import { Topbar } from '@/components/layout/topbar'
import { ChainFilterTabs } from '@/components/market/ChainFilter'
import { TokenTable } from '@/components/market/TokenTable'
import { HotPicksTable } from '@/components/market/HotPicksTable'
import { useMarketRank, type ChainFilter } from '@/hooks/useMarketRank'
import { useMemeRush } from '@/hooks/useMemeRush'
import { useHotDailyPicks } from '@/hooks/useHotDailyPicks'

type TabType = 'rank' | 'meme' | 'picks'

// 热币日榜的链过滤值
type PicksChainFilter = '' | 'solana' | 'bsc' | 'base' | 'eth'

const PICKS_CHAINS: { label: string; value: PicksChainFilter }[] = [
  { label: '全部', value: '' },
  { label: 'SOL', value: 'solana' },
  { label: 'BSC', value: 'bsc' },
  { label: 'ETH', value: 'eth' },
  { label: 'BASE', value: 'base' },
]

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

function shiftDate(dateStr: string, days: number) {
  const d = new Date(dateStr + 'T00:00:00')
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function formatDateLabel(dateStr: string) {
  const today = todayStr()
  const yesterday = shiftDate(today, -1)
  if (dateStr === today) return '今天'
  if (dateStr === yesterday) return '昨天'
  // 显示 MM-DD
  return dateStr.slice(5)
}

export default function MarketPage() {
  const [chain, setChain] = useState<ChainFilter>('56') // Binance 链
  const [tab, setTab] = useState<TabType>('rank')

  // 热币日榜状态
  const [picksDate, setPicksDate] = useState(todayStr())
  const [picksChain, setPicksChain] = useState<PicksChainFilter>('')
  const [showDatePicker, setShowDatePicker] = useState(false)

  // Binance hooks
  const rank = useMarketRank({ chainId: chain, size: 30, refreshInterval: 30_000 })
  const meme = useMemeRush(chain, 30_000)

  // 热币日榜 hook
  const picks = useHotDailyPicks({ date: picksDate, chain: picksChain, refreshInterval: 10_000 })

  // 日期导航
  const goPrevDay = () => setPicksDate(shiftDate(picksDate, -1))
  const goNextDay = () => {
    const next = shiftDate(picksDate, 1)
    if (next <= todayStr()) setPicksDate(next)
  }

  // 统一数据格式传给 TokenTable（MemeToken → TokenRankItem 适配）
  const tableData =
    tab === 'rank'
      ? rank.data
      : meme.data.map((m) => ({
          address: m.address,
          symbol: m.symbol,
          chainId: String(m.chainId),
          price: m.price,
          priceChangePercent24h: m.priceChangePercent24h ?? 0,
          priceChangePercent7d: 0,
          volume24h: m.volume1h ?? 0,
          marketCap: 0,
          holders: m.holders ?? 0,
          liquidity: 0,
          logoUrl: m.logoUrl,
          rank: 0,
          score: m.rushScore !== undefined ? String(m.rushScore) : undefined,
          tags: undefined,
          protocol: 0,
        }))

  const activeLoading = tab === 'rank' ? rank.loading : tab === 'meme' ? meme.loading : picks.loading
  const activeError = tab === 'rank' ? rank.error : tab === 'meme' ? meme.error : picks.error
  const lastUpdated = tab === 'picks' ? picks.lastUpdated : rank.lastUpdated
  const activeRefresh = tab === 'picks' ? picks.refresh : rank.refresh

  return (
    <div>
      <Topbar title="行情中心" subtitle="实时代币价格 · 链上排名 · 热币日榜" />
      <div className="p-6 space-y-4">

        {/* Controls */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-4 flex-wrap">
            {/* Tabs */}
            <div className="flex gap-1 rounded-lg p-1" style={{ background: 'var(--bg-card2)' }}>
              {([
                { key: 'rank' as TabType, label: '🏆 市场排名' },
                { key: 'meme' as TabType, label: '🔥 Meme Rush' },
                { key: 'picks' as TabType, label: '📊 热币日榜' },
              ]).map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className="px-4 py-1.5 rounded-md text-xs font-semibold transition-all"
                  style={{
                    background: tab === t.key ? 'var(--bg-card)' : 'transparent',
                    color: tab === t.key ? 'var(--text)' : 'var(--text-dim)',
                    boxShadow: tab === t.key ? '0 1px 4px rgba(0,0,0,0.3)' : 'none',
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Chain Filter - Binance tabs for rank/meme, custom for picks */}
            {tab !== 'picks' ? (
              <ChainFilterTabs value={chain} onChange={setChain} />
            ) : (
              <div className="flex gap-1.5">
                {PICKS_CHAINS.map((c) => {
                  const active = c.value === picksChain
                  return (
                    <button
                      key={c.value}
                      onClick={() => setPicksChain(c.value)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                      style={{
                        background: active ? 'rgba(240,185,11,0.15)' : 'var(--bg-card2)',
                        color: active ? 'var(--yellow)' : 'var(--text-dim)',
                        border: `1px solid ${active ? 'rgba(240,185,11,0.4)' : 'transparent'}`,
                      }}
                    >
                      {c.label}
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Date Navigator (only for picks tab) */}
            {tab === 'picks' && (
              <div className="flex items-center gap-1 relative">
                <button
                  onClick={goPrevDay}
                  className="p-1.5 rounded-lg transition-all hover:opacity-80"
                  style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
                >
                  <ChevronLeft size={14} />
                </button>

                <button
                  onClick={() => setShowDatePicker(!showDatePicker)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80"
                  style={{ background: 'var(--bg-card2)', color: 'var(--text)' }}
                >
                  <Calendar size={12} />
                  {formatDateLabel(picksDate)}
                  <span className="text-[10px] font-normal" style={{ color: 'var(--text-dim)' }}>
                    {picksDate}
                  </span>
                </button>

                <button
                  onClick={goNextDay}
                  disabled={shiftDate(picksDate, 1) > todayStr()}
                  className="p-1.5 rounded-lg transition-all hover:opacity-80 disabled:opacity-30"
                  style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
                >
                  <ChevronRight size={14} />
                </button>

                {/* Date dropdown */}
                {showDatePicker && picks.dates.length > 0 && (
                  <div
                    className="absolute top-10 right-0 z-50 rounded-xl border shadow-xl py-1 max-h-60 overflow-y-auto"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', minWidth: 140 }}
                  >
                    {picks.dates.map((d) => (
                      <button
                        key={d}
                        onClick={() => { setPicksDate(d); setShowDatePicker(false) }}
                        className="w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] transition-colors"
                        style={{
                          color: d === picksDate ? 'var(--yellow)' : 'var(--text)',
                          fontWeight: d === picksDate ? 700 : 400,
                        }}
                      >
                        {d} {formatDateLabel(d) !== d.slice(5) ? `(${formatDateLabel(d)})` : ''}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Last Updated + Refresh */}
            {lastUpdated && (
              <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                更新于 {lastUpdated.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
            <button
              onClick={activeRefresh}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-80"
              style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
            >
              <RefreshCw size={12} className={activeLoading ? 'animate-spin' : ''} />
              刷新
            </button>
          </div>
        </div>

        {/* Stats Bar */}
        {tab !== 'picks' ? (
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: '数据来源', value: 'Binance Skills API', color: 'var(--yellow)' },
              { label: '自动刷新', value: '每 30 秒', color: 'var(--green)' },
              { label: '覆盖链', value: 'ETH · BSC · SOL · BASE', color: 'var(--blue)' },
            ].map(({ label, value, color }) => (
              <div
                key={label}
                className="rounded-xl px-4 py-3 border"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
              >
                <div className="text-xs mb-1" style={{ color: 'var(--text-dim)' }}>{label}</div>
                <div className="text-sm font-semibold" style={{ color }}>{value}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: '数据来源', value: 'OKX + GoPlus + DexScreener', color: 'var(--yellow)' },
              { label: '刷新频率', value: 'OKX 5秒 · 发现 10分钟', color: 'var(--green)' },
              { label: '覆盖链', value: 'SOL · BSC · ETH · BASE', color: 'var(--blue)' },
              { label: '当日入选', value: `${picks.data.length} 个代币`, color: 'var(--yellow)' },
            ].map(({ label, value, color }) => (
              <div
                key={label}
                className="rounded-xl px-4 py-3 border"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
              >
                <div className="text-xs mb-1" style={{ color: 'var(--text-dim)' }}>{label}</div>
                <div className="text-sm font-semibold" style={{ color }}>{value}</div>
              </div>
            ))}
          </div>
        )}

        {/* Table */}
        {tab === 'picks' ? (
          <HotPicksTable
            data={picks.data}
            loading={picks.loading}
            error={picks.error}
          />
        ) : (
          <TokenTable
            data={tableData}
            loading={activeLoading}
            error={activeError}
          />
        )}

      </div>
    </div>
  )
}
