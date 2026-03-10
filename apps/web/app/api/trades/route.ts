/**
 * GET /api/trades
 * Returns trade history from Supabase.
 * Supports: ?limit=N&status=pending|confirmed|failed|simulated&chainId=N
 */
import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key) return null
  return createClient(url, key)
}

// Demo trades for when Supabase is not configured
const DEMO_TRADES = [
  {
    id: 'demo-t1',
    strategy_id: null,
    chain_id: 56,
    token_address: '0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82',
    direction: 'long',
    amount_in: 100,
    amount_out: 12543.2,
    exec_price: 0.00797,
    tx_hash: null,
    status: 'simulated',
    created_at: new Date(Date.now() - 3_600_000).toISOString(),
    raw_data: { dryRun: true, symbol: 'CAKE' },
  },
  {
    id: 'demo-t2',
    strategy_id: null,
    chain_id: 1,
    token_address: '0x6982508145454ce325ddbe47a25d4ec3d2311933',
    direction: 'long',
    amount_in: 200,
    amount_out: 5_230_000,
    exec_price: 0.0000382,
    tx_hash: null,
    status: 'simulated',
    created_at: new Date(Date.now() - 7_200_000).toISOString(),
    raw_data: { dryRun: true, symbol: 'PEPE' },
  },
  {
    id: 'demo-t3',
    strategy_id: null,
    chain_id: 56,
    token_address: '0x2170ed0880ac9a755fd29b2688956bd959f933f8',
    direction: 'long',
    amount_in: 150,
    amount_out: 0.0385,
    exec_price: 3896.1,
    tx_hash: null,
    status: 'simulated',
    created_at: new Date(Date.now() - 86_400_000).toISOString(),
    raw_data: { dryRun: true, symbol: 'ETH' },
  },
]

const CHAIN_NAME: Record<number, string> = {
  1: 'ETH', 56: 'BSC', 137: 'Polygon', 42161: 'Arbitrum', 8453: 'Base', 10: 'Optimism',
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const limit = Math.min(Number(searchParams.get('limit') ?? 50), 200)
  const status = searchParams.get('status')
  const chainId = searchParams.get('chainId')

  const supabase = getSupabase()
  if (!supabase) {
    return NextResponse.json({
      trades: DEMO_TRADES.map((t) => ({
        ...t,
        chainName: CHAIN_NAME[t.chain_id] ?? String(t.chain_id),
        symbol: (t.raw_data as Record<string, unknown>).symbol ?? '?',
      })),
      isDemo: true,
    })
  }

  let q = supabase
    .from('trades')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(limit)

  if (status) q = q.eq('status', status)
  if (chainId) q = q.eq('chain_id', Number(chainId))

  const { data, error } = await q

  if (error) {
    // Table may not exist yet
    return NextResponse.json({
      trades: DEMO_TRADES.map((t) => ({
        ...t,
        chainName: CHAIN_NAME[t.chain_id] ?? String(t.chain_id),
        symbol: (t.raw_data as Record<string, unknown>).symbol ?? '?',
      })),
      isDemo: true,
      dbError: error.message,
    })
  }

  const trades = (data ?? []).map((t) => ({
    ...t,
    chainName: CHAIN_NAME[t.chain_id] ?? String(t.chain_id),
    symbol: (t.raw_data as Record<string, unknown>)?.symbol ?? '?',
  }))

  return NextResponse.json({ trades, isDemo: false })
}
