'use client'

import { useState, useEffect, useCallback } from 'react'
import type { ChainFilter } from './useMarketRank'

export interface MemeToken {
  address: string
  symbol: string
  name: string
  chainId: number
  price: number
  priceChangePercent1h?: number
  priceChangePercent24h?: number
  volume1h?: number
  holders?: number
  logoUrl?: string
  rushScore?: number
}

export function useMemeRush(chainId: ChainFilter = '', refreshInterval = 30_000) {
  const [data, setData] = useState<MemeToken[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (chainId) params.set('chainId', chainId)
      const res = await fetch(`/api/binance/meme-rush${params.size ? `?${params}` : ''}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      const list = json?.data?.tokenList ?? json?.data ?? []
      setData(list)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch')
    } finally {
      setLoading(false)
    }
  }, [chainId])

  useEffect(() => {
    setLoading(true)
    fetchData()
    const timer = setInterval(fetchData, refreshInterval)
    return () => clearInterval(timer)
  }, [fetchData, refreshInterval])

  return { data, loading, error }
}
