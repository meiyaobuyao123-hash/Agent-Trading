'use client'

import { useState, useEffect, useCallback } from 'react'

// Binance 支持链: 1=ETH, 56=BSC, CT_501=Solana, 8453=Base
export type ChainFilter = '' | '1' | '56' | 'CT_501' | '8453'

export interface TokenRankItem {
  address: string
  symbol: string
  chainId: string
  price: number
  priceChangePercent24h: number
  priceChangePercent7d: number
  volume24h: number
  marketCap: number
  holders: number
  liquidity: number
  logoUrl?: string
  rank?: number
  score?: string
  tags?: Record<string, { tagName: string }[]>
  protocol?: number
}

interface UseMarketRankOptions {
  chainId?: ChainFilter
  size?: number
  refreshInterval?: number
}

export function useMarketRank({
  chainId = '56',
  size = 20,
  refreshInterval = 30_000,
}: UseMarketRankOptions = {}) {
  const [data, setData] = useState<TokenRankItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const params = new URLSearchParams({ size: String(size) })
      if (chainId) params.set('chainId', chainId)

      const res = await fetch(`/api/binance/market-rank?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const json = await res.json()
      if (json.error) throw new Error(json.error)

      // 实际返回: { data: { tokens: [...] } }
      const raw: Record<string, unknown>[] = json?.data?.tokens ?? []
      const mapped: TokenRankItem[] = raw.map((t) => ({
        address: (t.contractAddress as string) ?? '',
        symbol: (t.symbol as string) ?? '—',
        chainId: (t.chainId as string) ?? '',
        price: Number(t.price ?? 0),
        priceChangePercent24h: Number(t.percentChange ?? 0),
        priceChangePercent7d: Number(t.percentChange7d ?? 0),
        volume24h: Number(t.volume ?? 0),
        marketCap: Number(t.marketCap ?? 0),
        holders: Number(t.holders ?? 0),
        liquidity: Number(t.liquidity ?? 0),
        logoUrl: t.logoUrl ? `https://web3.binance.com${t.logoUrl}` : undefined,
        rank: Number(t.rank ?? 0),
        score: (t.score as string) ?? undefined,
        tags: t.tokenTag as Record<string, { tagName: string }[]>,
        protocol: Number(t.protocol ?? 0),
      }))

      setData(mapped)
      setError(null)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch')
    } finally {
      setLoading(false)
    }
  }, [chainId, size])

  useEffect(() => {
    setLoading(true)
    fetchData()
    const timer = setInterval(fetchData, refreshInterval)
    return () => clearInterval(timer)
  }, [fetchData, refreshInterval])

  return { data, loading, error, lastUpdated, refresh: fetchData }
}
