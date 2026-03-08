/**
 * OKX DEX v6 API Client
 * Base: https://www.okx.com/api/v6/dex/aggregator/
 * Requires: API Key + Secret + Passphrase + HMAC SHA256 signature
 * IMPORTANT: v5 deprecated (error 50050), use v6 only
 * IMPORTANT: chainIndex param (NOT chainId like v5)
 * Avg latency: ~1275ms, jitter: 153ms (more stable than Binance)
 */

const OKX_BASE = 'https://www.okx.com/api/v6/dex/aggregator'

// OKX chain index mapping (v6)
export const OKX_CHAINS: Record<string, string> = {
  ETH: '1',
  BSC: '56',
  Solana: '501',
  Polygon: '137',
  Arbitrum: '42161',
  Optimism: '10',
  Avalanche: '43114',
  Base: '8453',
}

// ===== SIGNATURE =====
function signOKX(
  timestamp: string,
  method: string,
  path: string,
  body: string,
  secret: string
): string {
  const message = timestamp + method + path + body
  // In browser environment, use SubtleCrypto
  // In Node.js environment (API routes), use crypto module
  if (typeof window === 'undefined') {
    // Node.js
    const crypto = require('crypto')
    return crypto.createHmac('sha256', secret).update(message).digest('base64')
  }
  // Browser: should proxy through API route - don't expose secret in browser
  throw new Error('OKX API must be called from server-side only (API routes)')
}

function getOKXHeaders(method: string, path: string, body = '') {
  const apiKey = process.env.OKX_API_KEY!
  const secret = process.env.OKX_SECRET_KEY!
  const passphrase = process.env.OKX_PASSPHRASE!
  const timestamp = new Date().toISOString()

  return {
    'OK-ACCESS-KEY': apiKey,
    'OK-ACCESS-SIGN': signOKX(timestamp, method, path, body, secret),
    'OK-ACCESS-TIMESTAMP': timestamp,
    'OK-ACCESS-PASSPHRASE': passphrase,
    'Content-Type': 'application/json',
  }
}

// ===== GET SUPPORTED TOKENS =====
export async function getOKXTokens(chainIndex: string) {
  const path = `/api/v6/dex/aggregator/all-tokens?chainIndex=${chainIndex}`
  const headers = getOKXHeaders('GET', path)
  const res = await fetch(`https://www.okx.com${path}`, { headers })
  const json = await res.json()
  return json?.data ?? []
}

// ===== GET QUOTE =====
export async function getOKXQuote(params: {
  chainIndex: string
  fromTokenAddress: string
  toTokenAddress: string
  amount: string
  slippage?: string
}) {
  const query = new URLSearchParams({
    chainIndex: params.chainIndex,
    fromTokenAddress: params.fromTokenAddress,
    toTokenAddress: params.toTokenAddress,
    amount: params.amount,
    slippage: params.slippage ?? '0.005',
  })
  const path = `/api/v6/dex/aggregator/quote?${query}`
  const headers = getOKXHeaders('GET', path)
  const res = await fetch(`https://www.okx.com${path}`, { headers })
  const json = await res.json()
  return json?.data?.[0] ?? null
}

// ===== GET SUPPORTED CHAINS =====
export async function getOKXChains() {
  const path = `/api/v6/dex/aggregator/supported/chain`
  const headers = getOKXHeaders('GET', path)
  const res = await fetch(`https://www.okx.com${path}`, { headers })
  const json = await res.json()
  return json?.data ?? []
}
