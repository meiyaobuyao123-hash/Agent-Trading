'use client'

import { useState, useEffect, useCallback } from 'react'

export interface HotPickItem {
  pick_date: string
  chain: string
  address: string
  name: string
  symbol: string
  rank: number

  // 推荐时快照
  pick_score: number
  pick_recommendation: string
  pick_price: number
  pick_market_cap: number
  pick_volume_24h: number
  pick_liquidity: number
  pick_holder_count: number
  pick_score_m: number
  pick_score_q: number
  pick_score_p: number
  pick_has_twitter: boolean
  pick_has_telegram: boolean
  pick_has_website: boolean

  // 当前实时数据
  current_price: number | null
  current_market_cap: number | null
  current_volume_24h: number | null
  current_score: number | null
  current_recommendation: string | null
  current_change_24h: number
  current_change_1h: number
  current_change_5m: number
  current_holder_count: number | null

  // 收益
  pnl_pct: number | null

  // 图标
  image_url: string
  scanned_at: string | null
}

interface UseHotDailyPicksOptions {
  date?: string
  chain?: string
  refreshInterval?: number
}

export function useHotDailyPicks({
  date,
  chain = '',
  refreshInterval = 10_000,
}: UseHotDailyPicksOptions = {}) {
  const [data, setData] = useState<HotPickItem[]>([])
  const [dates, setDates] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (date) params.set('date', date)
      if (chain) params.set('chain', chain)

      const res = await fetch(`/api/hot-picks?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const json = await res.json()
      if (json.error) throw new Error(json.error)

      setData(json.picks ?? [])
      setDates(json.dates ?? [])
      setError(null)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch')
    } finally {
      setLoading(false)
    }
  }, [date, chain])

  useEffect(() => {
    setLoading(true)
    fetchData()
    const timer = setInterval(fetchData, refreshInterval)
    return () => clearInterval(timer)
  }, [fetchData, refreshInterval])

  return { data, dates, loading, error, lastUpdated, refresh: fetchData }
}
