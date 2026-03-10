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

// ===== GET SWAP TX DATA (unsigned) =====
// Returns the unsigned transaction that needs to be signed + broadcast
export async function getOKXSwapData(params: {
  chainIndex: string
  fromTokenAddress: string
  toTokenAddress: string
  amount: string        // in fromToken smallest unit (e.g. USDT has 18 decimals on BSC)
  slippage: string      // e.g. '0.005' = 0.5%
  userWalletAddress: string
  referrerAddress?: string
  feePercent?: string
}) {
  const query = new URLSearchParams({
    chainIndex: params.chainIndex,
    fromTokenAddress: params.fromTokenAddress,
    toTokenAddress: params.toTokenAddress,
    amount: params.amount,
    slippage: params.slippage,
    userWalletAddress: params.userWalletAddress,
    ...(params.referrerAddress ? { referrerAddress: params.referrerAddress } : {}),
    ...(params.feePercent ? { feePercent: params.feePercent } : {}),
  })
  const path = `/api/v6/dex/aggregator/swap?${query}`
  const headers = getOKXHeaders('GET', path)
  const res = await fetch(`https://www.okx.com${path}`, { headers })
  const json = await res.json()
  if (json.code !== '0') throw new Error(`OKX swap error ${json.code}: ${json.msg}`)
  return json?.data?.[0] ?? null
}

// ===== STABLECOIN ADDRESSES (fromToken for buys) =====
// Used as the "from" token when buying a new position
export const STABLECOINS: Record<string, { usdt: string; usdc: string; decimals: number }> = {
  '56': {  // BSC
    usdt: '0x55d398326f99059fF775485246999027B3197955', // BSC-USDT (18 decimals)
    usdc: '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d', // BSC-USDC (18 decimals)
    decimals: 18,
  },
  '1': {   // ETH
    usdt: '0xdAC17F958D2ee523a2206206994597C13D831ec7', // ETH-USDT (6 decimals)
    usdc: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', // ETH-USDC (6 decimals)
    decimals: 6,
  },
  '137': { // Polygon
    usdt: '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',
    usdc: '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
    decimals: 6,
  },
  '42161': { // Arbitrum
    usdt: '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9',
    usdc: '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8',
    decimals: 6,
  },
  '8453': { // Base
    usdt: '0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2',
    usdc: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    decimals: 6,
  },
}

// Helper: convert USD amount to token smallest unit
export function usdToTokenAmount(amountUsd: number, chainIndex: string): string {
  const stable = STABLECOINS[chainIndex]
  if (!stable) throw new Error(`Unsupported chain: ${chainIndex}`)
  const decimals = stable.decimals
  return Math.floor(amountUsd * Math.pow(10, decimals)).toString()
}
