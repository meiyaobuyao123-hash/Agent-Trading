'use client'

import { useState, useEffect, useCallback } from 'react'
import type { ChainFilter } from './useMarketRank'

export interface Signal {
  id?: string
  tokenAddress: string
  symbol: string
  name?: string
  chainId: number
  direction: 'BUY' | 'SELL' | 'WATCH'
  confidenceScore?: number    // 0-100
  triggerPrice?: number
  currentPrice?: number
  priceChangePercent?: number
  reason?: string
  tags?: string[]
  status?: 'active' | 'expired' | 'triggered'
  createdAt?: string
  expiresAt?: string
  logoUrl?: string
  // Binance 信号额外字段
  signalType?: string
  smartMoneyAction?: string
  volume24h?: number
}

export function useSignals(chainId: ChainFilter = '', refreshInterval = 20_000) {
  const [data, setData] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (chainId) params.set('chainId', chainId)
      const res = await fetch(`/api/binance/signals${params.size ? `?${params}` : ''}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()

      // Binance Smart Money 信号实际返回结构:
      // data: [ { signalId, ticker, contractAddress, direction:'buy'/'sell',
      //   smartMoneyCount, alertPrice, currentPrice, highestPrice, exitRate,
      //   status:'active'/'exitRate'/'timeout', maxGain, logoUrl, tokenTag, ... } ]
      const raw: Record<string, unknown>[] = Array.isArray(json?.data) ? json.data : []
      const mapped: Signal[] = raw.map((item) => ({
        id: String(item.signalId ?? item.contractAddress ?? ''),
        tokenAddress: (item.contractAddress as string) ?? '',
        symbol: (item.ticker as string) ?? '—',
        chainId: item.chainId === 'CT_501' ? 900 : Number(item.chainId ?? 56),
        direction: parseDirection(item.direction as string),
        confidenceScore: Math.round(Number(item.exitRate ?? 0)),
        triggerPrice: Number(item.alertPrice ?? 0),
        currentPrice: Number(item.currentPrice ?? 0),
        priceChangePercent: 0,
        tags: extractTags(item.tokenTag as Record<string, { tagName: string }[]>),
        status: parseStatus(item.status as string),
        createdAt: item.signalTriggerTime ? new Date(Number(item.signalTriggerTime)).toISOString() : undefined,
        logoUrl: item.logoUrl ? `https://web3.binance.com${item.logoUrl}` : undefined,
        signalType: (item.smartSignalType as string) ?? '',
        smartMoneyAction: `聪明钱 x${item.smartMoneyCount ?? 0}`,
        volume24h: 0,
        // 额外字段
        maxGain: item.maxGain,
        smartMoneyCount: Number(item.smartMoneyCount ?? 0),
      } as Signal & { maxGain: unknown; smartMoneyCount: number }))

      setData(mapped)
      setError(null)
      setLastUpdated(new Date())
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

  return { data, loading, error, lastUpdated, refresh: fetchData }
}

function parseDirection(raw: string): Signal['direction'] {
  if (!raw) return 'WATCH'
  const lower = raw.toLowerCase()
  if (lower === 'buy' || lower.includes('long')) return 'BUY'
  if (lower === 'sell' || lower.includes('short')) return 'SELL'
  return 'WATCH'
}

function parseStatus(raw: string): Signal['status'] {
  if (raw === 'active') return 'active'
  if (raw === 'timeout') return 'expired'
  if (raw === 'exitRate' || raw === 'completed') return 'triggered'
  return 'active'
}

function extractTags(tokenTag?: Record<string, { tagName: string }[]>): string[] {
  if (!tokenTag) return []
  return Object.values(tokenTag)
    .flat()
    .map((t) => t.tagName)
    .filter(Boolean)
    .slice(0, 4)
}
