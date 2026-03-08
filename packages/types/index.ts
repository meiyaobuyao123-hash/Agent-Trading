// ===== CHAIN & TOKEN =====
export type ChainId = 1 | 56 | 900 // ETH | BSC | SOL (Binance chain IDs)
export type OKXChainIndex = string   // OKX uses string chainIndex

export interface Token {
  address: string
  symbol: string
  name: string
  chainId: ChainId
  decimals: number
  logoUrl?: string
}

// ===== TOKEN DYNAMIC (Binance 100-field response) =====
export interface TokenDynamic {
  // Price
  price: string
  priceChange5m: string
  priceChange1h: string
  priceChange4h: string
  priceChange24h: string
  // Volume
  volume5m: string
  volume1h: string
  volume4h: string
  volume24h: string
  // Holders
  holderCount: number
  top10HolderPercent: string
  // Smart Money
  smartMoneyPercent: string
  smartMoneyCount: number
  kolPercent: string
  institutionPercent: string
  newWalletPercent: string
  sniperPercent: string
  insiderPercent: string
  // Market
  marketCap: string
  liquidity: string
  // Raw
  [key: string]: unknown
}

// ===== SIGNAL =====
export type SignalStatus = 'active' | 'triggered' | 'expired' | 'cancelled'
export type SignalDirection = 'long' | 'watch' | 'exit'
export type RiskLevel = 'low' | 'medium' | 'high'

export interface Signal {
  id: string
  tokenAddress: string
  chainId: ChainId
  symbol: string
  direction: SignalDirection
  confidenceScore: number // 0-100
  triggerPrice: string
  currentPrice: string
  targetGainPct?: string
  status: SignalStatus
  riskLevel: RiskLevel
  smartMoneyCount: number
  rawData?: Record<string, unknown>
  createdAt: string
  expiresAt?: string
}

// ===== OFFICIAL PORTFOLIO =====
export type PortfolioTokenStatus = 'active' | 'exited'

export interface OfficialPortfolioToken {
  id: string
  tokenAddress: string
  chainId: ChainId
  symbol: string
  name: string
  logoUrl?: string
  entryPrice: string
  currentPrice?: string
  gainPct?: number
  entryAt: string
  exitAt?: string
  exitPrice?: string
  reasonTags: string[]
  riskLevel: RiskLevel
  status: PortfolioTokenStatus
}

// ===== STRATEGY =====
export type StrategyStatus = 'draft' | 'active' | 'paused' | 'archived'

export interface StrategyCondition {
  field: string         // e.g. 'smartMoneyPercent'
  operator: '>' | '<' | '>=' | '<=' | '==' | '!='
  value: number | string
  label?: string
}

export interface StrategyExecConfig {
  amountUSD: number
  slippagePct: number
  stopLossPct: number
  takeProfitPct: number
  maxPositions: number
  cooldownMinutes: number
}

export interface Strategy {
  id: string
  userId: string
  name: string
  description?: string
  conditions: StrategyCondition[]
  execConfig: StrategyExecConfig
  generatedScript?: string
  status: StrategyStatus
  isOfficial: boolean
  createdAt: string
  updatedAt: string
}

// ===== TRADE =====
export type TradeStatus = 'pending' | 'confirmed' | 'failed'
export type TradeDirection = 'buy' | 'sell'

export interface Trade {
  id: string
  userId: string
  strategyId?: string
  signalId?: string
  tokenAddress: string
  chainId: ChainId
  txHash?: string
  direction: TradeDirection
  amountIn: string
  amountOut: string
  execPrice: string
  gasUsed?: string
  status: TradeStatus
  createdAt: string
}

// ===== POSITION =====
export interface Position {
  id: string
  userId: string
  tokenAddress: string
  chainId: ChainId
  symbol: string
  amount: string
  avgEntryPrice: string
  currentPrice?: string
  pnlPct?: number
  openedAt: string
}

// ===== API RESPONSE WRAPPER =====
export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: {
    code: string
    message: string
  }
  meta?: {
    page?: number
    total?: number
    limit?: number
  }
  ts: number
}
