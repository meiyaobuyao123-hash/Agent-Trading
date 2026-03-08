/**
 * Binance Skills API Client
 * Base: https://web3.binance.com/bapi/defi/
 * No auth required. Cache in Redis (TTL 60s) in production.
 * Avg latency: ~1242ms, jitter: 466ms
 */

const BINANCE_BASE = 'https://web3.binance.com/bapi/defi'

// Chain ID mapping (Binance uses numeric chain IDs)
export const BINANCE_CHAINS = {
  ETH: 1,
  BSC: 56,
  SOL: 900,
} as const

export type BinanceChainId = typeof BINANCE_CHAINS[keyof typeof BINANCE_CHAINS]

// ===== TOKEN DYNAMIC INFO (100 fields) =====
export async function getTokenDynamic(chainId: BinanceChainId, address: string) {
  const url = `${BINANCE_BASE}/v1/public/token-dynamic/token/detail?chainId=${chainId}&address=${address}`
  const res = await fetchWithTimeout(url)
  const json = await res.json()
  return json?.data ?? null
}

// ===== TOKEN INFO =====
export async function getTokenInfo(chainId: BinanceChainId, address: string) {
  const url = `${BINANCE_BASE}/v1/public/token/query?chainId=${chainId}&address=${address}`
  const res = await fetchWithTimeout(url)
  const json = await res.json()
  return json?.data ?? null
}

// ===== TRADING SIGNALS =====
export async function getTradingSignals(chainId?: BinanceChainId) {
  const params = chainId ? `?chainId=${chainId}` : ''
  const url = `${BINANCE_BASE}/v1/public/signal/query${params}`
  const res = await fetchWithTimeout(url)
  const json = await res.json()
  return json?.data ?? []
}

// ===== TOKEN AUDIT =====
export async function getTokenAudit(chainId: BinanceChainId, address: string) {
  const requestId = crypto.randomUUID()
  const url = `${BINANCE_BASE}/v1/public/token/audit`
  const res = await fetchWithTimeout(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chainId, address, requestId }),
  })
  const json = await res.json()
  return json?.data ?? null
}

// ===== MARKET RANK =====
export async function getMarketRank(params?: {
  chainId?: BinanceChainId
  page?: number
  size?: number
}) {
  const query = new URLSearchParams()
  if (params?.chainId) query.set('chainId', String(params.chainId))
  if (params?.page) query.set('page', String(params.page))
  if (params?.size) query.set('size', String(params.size))
  const url = `${BINANCE_BASE}/v1/public/market/rank?${query}`
  const res = await fetchWithTimeout(url)
  const json = await res.json()
  return json?.data ?? []
}

// ===== MEME RUSH =====
export async function getMemeRush(chainId?: BinanceChainId) {
  const params = chainId ? `?chainId=${chainId}` : ''
  const url = `${BINANCE_BASE}/v1/public/meme-rush/list${params}`
  const res = await fetchWithTimeout(url)
  const json = await res.json()
  return json?.data ?? []
}

// ===== ADDRESS INFO =====
export async function getAddressInfo(chainId: BinanceChainId, address: string) {
  const url = `${BINANCE_BASE}/v1/public/address/info?chainId=${chainId}&address=${address}`
  const res = await fetchWithTimeout(url)
  const json = await res.json()
  return json?.data ?? null
}

// ===== INTERNAL HELPER =====
async function fetchWithTimeout(url: string, options?: RequestInit, timeoutMs = 5000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0',
        ...options?.headers,
      },
    })
    clearTimeout(timer)
    if (!res.ok) throw new Error(`Binance API error: ${res.status}`)
    return res
  } catch (err) {
    clearTimeout(timer)
    throw err
  }
}
