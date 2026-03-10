'use client'

import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Topbar } from '@/components/layout/topbar'
import { ChainFilterTabs } from '@/components/market/ChainFilter'
import { TokenTable } from '@/components/market/TokenTable'
import { useMarketRank, type ChainFilter } from '@/hooks/useMarketRank'
import { useMemeRush } from '@/hooks/useMemeRush'

type TabType = 'rank' | 'meme'

export default function MarketPage() {
  const [chain, setChain] = useState<ChainFilter>('56') // 默认 BSC
  const [tab, setTab] = useState<TabType>('rank')

  const rank = useMarketRank({ chainId: chain, size: 30, refreshInterval: 30_000 })
  const meme = useMemeRush(chain, 30_000)

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
  const activeLoading = tab === 'rank' ? rank.loading : meme.loading
  const activeError = tab === 'rank' ? rank.error : meme.error
  const lastUpdated = rank.lastUpdated

  return (
    <div>
      <Topbar title="行情中心" subtitle="实时代币价格 · 链上排名 · Meme 快讯" />
      <div className="p-6 space-y-4">

        {/* Controls */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Tabs */}
            <div className="flex gap-1 rounded-lg p-1" style={{ background: 'var(--bg-card2)' }}>
              {(['rank', 'meme'] as TabType[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className="px-4 py-1.5 rounded-md text-xs font-semibold transition-all"
                  style={{
                    background: tab === t ? 'var(--bg-card)' : 'transparent',
                    color: tab === t ? 'var(--text)' : 'var(--text-dim)',
                    boxShadow: tab === t ? '0 1px 4px rgba(0,0,0,0.3)' : 'none',
                  }}
                >
                  {t === 'rank' ? '🏆 市场排名' : '🔥 Meme Rush'}
                </button>
              ))}
            </div>

            {/* Chain Filter */}
            <ChainFilterTabs value={chain} onChange={setChain} />
          </div>

          {/* Last Updated + Refresh */}
          <div className="flex items-center gap-3">
            {lastUpdated && (
              <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                更新于 {lastUpdated.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
            <button
              onClick={rank.refresh}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-80"
              style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
            >
              <RefreshCw size={12} className={rank.loading ? 'animate-spin' : ''} />
              刷新
            </button>
          </div>
        </div>

        {/* Stats Bar */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: '数据来源', value: 'Binance Skills API', color: 'var(--yellow)' },
            { label: '自动刷新', value: '每 30 秒', color: 'var(--green)' },
            { label: '覆盖链', value: 'ETH · BSC · SOL', color: 'var(--blue)' },
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

        {/* Token Table */}
        <TokenTable
          data={tableData}
          loading={activeLoading}
          error={activeError}
        />

      </div>
    </div>
  )
}
