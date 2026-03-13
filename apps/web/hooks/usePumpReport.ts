'use client'

import { useState, useEffect, useCallback } from 'react'

export interface PumpDailyReport {
  report_date: string
  ws_creates: number
  tokens_saved: number
  rest_success: number
  rest_fallback: number
  observed_tokens: number
  snapshots_written: number
  picks_count: number
  graduated_count: number
  hit_count: number
  miss_count: number
  hit_rate: number
  miss_rate: number
  avg_grad_hours: number | null
  ws_reconnects: number
  rest_success_pct: number
  report_json: {
    funnel: Record<string, number>
    scores: { strong: number; normal: number; skip: number }
    accuracy: { hit_rate: number; miss_rate: number; false_positive_count: number }
    quality: { avg_grad_hours: number | null }
    health: { ws_reconnects: number; rest_success_pct: number; avg_snapshots_per_min: number }
  } | null
}

export function usePumpReport(days = 7, refreshInterval = 60_000) {
  const [data, setData] = useState<PumpDailyReport[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`/api/pump-report?days=${days}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setData(json.reports || [])
      setError(null)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => {
    setLoading(true)
    fetchData()
    const timer = setInterval(fetchData, refreshInterval)
    return () => clearInterval(timer)
  }, [fetchData, refreshInterval])

  return { data, loading, error, lastUpdated, refresh: fetchData }
}
