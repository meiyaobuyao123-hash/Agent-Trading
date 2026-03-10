'use client'

import { useState, useEffect, useCallback } from 'react'

// =====================================================
// Types
// =====================================================
export interface PortfolioToken {
  id: string
  tokenAddress: string
  chainId: number          // DB存: 1=ETH, 56=BSC, 900=SOL
  symbol: string
  name?: string
  entryPrice: number
  entryAt: string
  reasonTags: string[]
  riskLevel: 'low' | 'medium' | 'high'
  status: 'active' | 'exited'
  exitPrice?: number
  exitAt?: string
  // 客户端富化（实时价格）
  currentPrice?: number
  priceChange24h?: number
  logoUrl?: string
  pnlPercent?: number
  pnlAbs?: number
}

// Binance API 链 ID 转换 (Supabase存整数 → Binance用字符串)
const CHAIN_TO_BINANCE: Record<number, string> = {
  1: '1',
  56: '56',
  900: 'CT_501',
}

async function fetchCurrentPrice(
  address: string,
  chainId: number
): Promise<{ price?: number; change24h?: number; logoUrl?: string }> {
  const binanceChainId = CHAIN_TO_BINANCE[chainId]
  if (!binanceChainId) return {}

  try {
    const res = await fetch(
      `/api/binance/token-dynamic?chainId=${binanceChainId}&address=${address}`,
      { next: { revalidate: 60 } }
    )
    if (!res.ok) return {}
    const json = await res.json()
    // token-dynamic 返回结构: { data: { price, percentChange, logoUrl, ... } }
    const d = json?.data
    if (!d) return {}
    const logo = d.logoUrl ? `https://web3.binance.com${d.logoUrl}` : undefined
    return {
      price: Number(d.price ?? 0) || undefined,
      change24h: Number(d.percentChange ?? 0),
      logoUrl: logo,
    }
  } catch {
    return {}
  }
}

// =====================================================
// Hook
// =====================================================
export function useOfficialPortfolio(refreshInterval = 60_000) {
  const [tokens, setTokens] = useState<PortfolioToken[]>([])
  const [loading, setLoading] = useState(true)
  const [isDemo, setIsDemo] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [enriching, setEnriching] = useState(false)

  const fetchPortfolio = useCallback(async () => {
    try {
      setLoading(true)
      const res = await fetch('/api/portfolio')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const json: {
        tokens: Array<Record<string, unknown>>
        isDemo: boolean
      } = await res.json()

      setIsDemo(json.isDemo)

      // 映射 DB 字段 → 前端类型
      const mapped: PortfolioToken[] = (json.tokens ?? []).map((t) => ({
        id: t.id as string,
        tokenAddress: t.token_address as string,
        chainId: t.chain_id as number,
        symbol: t.symbol as string,
        name: (t.name as string) || undefined,
        entryPrice: Number(t.entry_price ?? 0),
        entryAt: t.entry_at as string,
        reasonTags: (t.reason_tags as string[]) ?? [],
        riskLevel: (t.risk_level as 'low' | 'medium' | 'high') ?? 'medium',
        status: (t.status as 'active' | 'exited') ?? 'active',
        exitPrice: t.exit_price ? Number(t.exit_price) : undefined,
        exitAt: (t.exit_at as string) || undefined,
      }))

      setTokens(mapped)
      setError(null)
      setLastUpdated(new Date())
      setLoading(false)

      // 异步富化：只为 active 代币取当前价格
      const activeTokens = mapped.filter((t) => t.status === 'active')
      if (activeTokens.length > 0) {
        setEnriching(true)
        const priceResults = await Promise.allSettled(
          activeTokens.map((t) => fetchCurrentPrice(t.tokenAddress, t.chainId))
        )

        setTokens((prev) => {
          const priceMap: Record<string, ReturnType<typeof fetchCurrentPrice> extends Promise<infer R> ? R : never> = {}
          activeTokens.forEach((t, i) => {
            const result = priceResults[i]
            if (result.status === 'fulfilled') priceMap[t.id] = result.value
          })

          return prev.map((t) => {
            if (t.status !== 'active' || !priceMap[t.id]) return t
            const { price, change24h, logoUrl } = priceMap[t.id]
            const pnlPercent = price && t.entryPrice
              ? ((price - t.entryPrice) / t.entryPrice) * 100
              : undefined
            const pnlAbs = price && t.entryPrice
              ? price - t.entryPrice
              : undefined
            return { ...t, currentPrice: price, priceChange24h: change24h, logoUrl, pnlPercent, pnlAbs }
          })
        })
        setEnriching(false)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch portfolio')
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPortfolio()
    const timer = setInterval(fetchPortfolio, refreshInterval)
    return () => clearInterval(timer)
  }, [fetchPortfolio, refreshInterval])

  // 统计
  const activeTokens = tokens.filter((t) => t.status === 'active')
  const exitedTokens = tokens.filter((t) => t.status === 'exited')

  const enrichedActive = activeTokens.filter((t) => t.pnlPercent !== undefined)
  const avgPnl = enrichedActive.length > 0
    ? enrichedActive.reduce((sum, t) => sum + (t.pnlPercent ?? 0), 0) / enrichedActive.length
    : undefined

  const exitedWithPnl = exitedTokens.map((t) =>
    t.exitPrice && t.entryPrice
      ? ((t.exitPrice - t.entryPrice) / t.entryPrice) * 100
      : undefined
  ).filter((v): v is number => v !== undefined)

  const avgExitPnl = exitedWithPnl.length > 0
    ? exitedWithPnl.reduce((a, b) => a + b, 0) / exitedWithPnl.length
    : undefined

  return {
    tokens,
    loading,
    enriching,
    isDemo,
    error,
    lastUpdated,
    refresh: fetchPortfolio,
    stats: {
      total: tokens.length,
      activeCount: activeTokens.length,
      exitedCount: exitedTokens.length,
      avgPnl,
      avgExitPnl,
    },
  }
}
