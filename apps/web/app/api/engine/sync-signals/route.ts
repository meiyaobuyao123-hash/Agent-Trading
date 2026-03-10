/**
 * Signal Sync Engine — POST /api/engine/sync-signals
 *
 * 功能：
 * 1. 从 Binance Smart Money API 拉取最新信号
 * 2. 过滤并评分（confidence_score / smart_money_count）
 * 3. 写入 Supabase signals 表（upsert，避免重复）
 *
 * 触发方式：
 * - Vercel Cron Job (vercel.json cron 配置) — 每 5 分钟
 * - 手动 POST（Admin 面板 / curl 测试）
 *
 * 安全：
 * - 校验 CRON_SECRET header 防止未授权调用
 * - Supabase 未配置时仅返回 dry-run 结果
 */

import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

const BINANCE_BASE = 'https://web3.binance.com/bapi/defi'
const BINANCE_HEADERS = {
  Accept: 'application/json, text/plain, */*',
  'Content-Type': 'application/json',
  Origin: 'https://web3.binance.com',
  Referer: 'https://web3.binance.com/',
  'User-Agent':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
}

// 支持的链（按优先级）
const CHAINS = [
  { chainId: '56', label: 'BSC' },
  { chainId: '1', label: 'ETH' },
  { chainId: 'CT_501', label: 'SOL' },
]

// Binance chainId → DB chain_id
const CHAIN_DB_ID: Record<string, number> = {
  '56': 56,
  '1': 1,
  CT_501: 900,
}

// =====================================================
// Types
// =====================================================
interface BinanceSignal {
  signalId?: string | number
  contractAddress?: string
  ticker?: string
  chainId?: string | number
  direction?: string // 'buy' | 'sell' | 'watch'
  smartMoneyCount?: number
  alertPrice?: string | number
  currentPrice?: string | number
  exitRate?: string | number  // confidence proxy (0-100)
  status?: string             // 'active' | 'timeout' | 'exitRate'
  signalTriggerTime?: string | number
  logoUrl?: string
  smartSignalType?: string
  maxGain?: string | number
}

interface SyncResult {
  chain: string
  fetched: number
  filtered: number
  upserted: number
  skipped: number
}

// =====================================================
// Fetch signals for one chain
// =====================================================
async function fetchChainSignals(chainId: string, pageSize = 30): Promise<BinanceSignal[]> {
  const body = JSON.stringify({ chainId, page: 1, pageSize, smartSignalType: '' })
  const res = await fetch(
    `${BINANCE_BASE}/v1/public/wallet-direct/buw/wallet/web/signal/smart-money`,
    { method: 'POST', headers: BINANCE_HEADERS, body, next: { revalidate: 0 } }
  )
  if (!res.ok) throw new Error(`Binance HTTP ${res.status} for chain ${chainId}`)
  const json = await res.json()
  const data = json?.data
  return Array.isArray(data) ? data : []
}

// =====================================================
// Map Binance signal → Supabase row
// =====================================================
function mapSignal(raw: BinanceSignal, chainId: string) {
  const dbChainId = CHAIN_DB_ID[chainId] ?? Number(chainId)

  // Parse direction
  let direction: 'long' | 'watch' | 'exit' = 'watch'
  const dir = String(raw.direction ?? '').toLowerCase()
  if (dir === 'buy' || dir === 'long') direction = 'long'
  else if (dir === 'sell' || dir === 'short' || dir === 'exit') direction = 'exit'

  // Parse status
  let status: 'active' | 'triggered' | 'expired' = 'active'
  const st = String(raw.status ?? '').toLowerCase()
  if (st === 'exitrate' || st === 'completed') status = 'triggered'
  else if (st === 'timeout') status = 'expired'

  // Confidence (exitRate is 0-100 from Binance)
  const confidence = Math.min(100, Math.max(0, Math.round(Number(raw.exitRate ?? 0))))

  // Risk level based on smart money count
  const smCount = Number(raw.smartMoneyCount ?? 0)
  const riskLevel: 'low' | 'medium' | 'high' =
    smCount >= 10 ? 'low' : smCount >= 5 ? 'medium' : 'high'

  // Unique ID for upsert (address + chain)
  const tokenAddress = String(raw.contractAddress ?? '').toLowerCase()

  return {
    // Unique key for upsert — we store address+chain as composite identity
    token_address: tokenAddress,
    chain_id: dbChainId,
    symbol: String(raw.ticker ?? ''),
    direction,
    confidence_score: confidence,
    trigger_price: raw.alertPrice ? Number(raw.alertPrice) : null,
    smart_money_count: smCount,
    risk_level: riskLevel,
    status,
    expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
  }
}

// =====================================================
// Quality filter: keep only meaningful signals
// =====================================================
function filterSignal(raw: BinanceSignal): boolean {
  if (!raw.contractAddress) return false          // must have address
  if (!raw.ticker) return false                   // must have symbol
  const smCount = Number(raw.smartMoneyCount ?? 0)
  if (smCount < 1) return false                   // at least 1 smart money wallet
  const st = String(raw.status ?? '').toLowerCase()
  if (st === 'timeout') return false              // skip expired signals
  return true
}

// =====================================================
// Main handler
// =====================================================
export async function POST(req: NextRequest) {
  // Auth check (for Vercel Cron and manual calls)
  const secret = process.env.CRON_SECRET
  if (secret) {
    const authHeader = req.headers.get('authorization')
    if (authHeader !== `Bearer ${secret}`) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
  }

  const startTime = Date.now()

  // Setup Supabase (optional — dry-run if not configured)
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY
  const supabase = supabaseUrl && supabaseKey
    ? createClient(supabaseUrl, supabaseKey)
    : null

  const results: SyncResult[] = []
  let totalUpserted = 0

  // Sync each chain in parallel
  const chainResults = await Promise.allSettled(
    CHAINS.map(async ({ chainId, label }) => {
      let fetched = 0, filtered = 0, upserted = 0, skipped = 0

      const rawSignals = await fetchChainSignals(chainId, 30)
      fetched = rawSignals.length

      const validSignals = rawSignals.filter(filterSignal)
      filtered = validSignals.length

      if (supabase && validSignals.length > 0) {
        const rows = validSignals.map((s) => mapSignal(s, chainId))

        // Upsert by (token_address, chain_id) — update if already exists
        const { data, error } = await supabase
          .from('signals')
          .upsert(rows, {
            onConflict: 'token_address,chain_id',
            ignoreDuplicates: false,
          })
          .select('id')

        if (error) {
          console.error(`[sync-signals] Supabase error (${label}):`, error.message)
          skipped = filtered
        } else {
          upserted = data?.length ?? filtered
        }
      } else {
        // dry-run
        upserted = 0
        skipped = filtered
      }

      return { chain: label, fetched, filtered, upserted, skipped }
    })
  )

  for (const result of chainResults) {
    if (result.status === 'fulfilled') {
      results.push(result.value)
      totalUpserted += result.value.upserted
    } else {
      console.error('[sync-signals] chain error:', result.reason)
      results.push({ chain: '?', fetched: 0, filtered: 0, upserted: 0, skipped: 0 })
    }
  }

  const elapsed = Date.now() - startTime

  return NextResponse.json({
    ok: true,
    dryRun: !supabase,
    elapsed: `${elapsed}ms`,
    totalUpserted,
    results,
    timestamp: new Date().toISOString(),
  })
}

// GET — 查看引擎状态（不触发同步）
export async function GET() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY
  const supabase = supabaseUrl && supabaseKey
    ? createClient(supabaseUrl, supabaseKey)
    : null

  let signalCount = 0
  let latestSignal: string | null = null

  if (supabase) {
    const { count } = await supabase
      .from('signals')
      .select('id', { count: 'exact', head: true })
      .eq('status', 'active')

    const { data } = await supabase
      .from('signals')
      .select('created_at')
      .order('created_at', { ascending: false })
      .limit(1)

    signalCount = count ?? 0
    latestSignal = data?.[0]?.created_at ?? null
  }

  return NextResponse.json({
    engine: 'signal-sync',
    version: '1.0.0',
    supabaseConnected: !!supabase,
    activeSignals: signalCount,
    latestSignal,
    endpoint: 'POST /api/engine/sync-signals',
    cronSchedule: '*/5 * * * *',
    chains: CHAINS.map((c) => c.label),
  })
}
