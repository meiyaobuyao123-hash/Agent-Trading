import { createClient } from './supabase'

export interface TokenPerformance {
  id: number
  source: 'pump' | 'hot'
  pick_date: string
  chain: string
  address: string
  symbol: string | null
  name: string | null
  rank: number | null
  score: number | null
  price_at_pick: number
  denomination: 'usd' | 'sol'
  current_price: number | null
  current_pct: number | null
  current_updated_at: string | null
  daily_highs: Record<string, { high: number; pct: number }>
  best_price: number | null
  best_pct: number | null
  best_day: number | null
  is_active: boolean
  tracking_days: number
  snapshot_data: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export async function fetchPerformance(opts: {
  source?: 'pump' | 'hot'
  chain?: string
  limit?: number
  daysBack?: number
  orderBy?: string
  ascending?: boolean
}): Promise<TokenPerformance[]> {
  const supabase = createClient()
  let query = supabase.from('token_performance').select('*')

  if (opts.source) query = query.eq('source', opts.source)
  if (opts.chain) query = query.eq('chain', opts.chain)
  if (opts.daysBack) {
    const since = new Date()
    since.setDate(since.getDate() - opts.daysBack)
    query = query.gte('pick_date', since.toISOString().split('T')[0])
  }

  query = query
    .order(opts.orderBy ?? 'pick_date', { ascending: opts.ascending ?? false })
    .limit(opts.limit ?? 100)

  const { data, error } = await query
  if (error) throw error
  return (data ?? []) as TokenPerformance[]
}

export interface SummaryStats {
  totalTracked: number
  activeTracking: number
  avgBestReturn: number
  hitRate2x: number
}

export async function fetchSummaryStats(): Promise<SummaryStats> {
  const supabase = createClient()

  const { count: totalTracked } = await supabase
    .from('token_performance')
    .select('*', { count: 'exact', head: true })

  const { count: activeTracking } = await supabase
    .from('token_performance')
    .select('*', { count: 'exact', head: true })
    .eq('is_active', true)

  const { data: all } = await supabase
    .from('token_performance')
    .select('best_pct')
    .not('best_pct', 'is', null)

  const returns = (all ?? []).map(r => r.best_pct as number)
  const avgBestReturn = returns.length > 0
    ? returns.reduce((a, b) => a + b, 0) / returns.length
    : 0
  const hitRate2x = returns.length > 0
    ? (returns.filter(r => r >= 100).length / returns.length) * 100
    : 0

  return {
    totalTracked: totalTracked ?? 0,
    activeTracking: activeTracking ?? 0,
    avgBestReturn: Math.round(avgBestReturn * 10) / 10,
    hitRate2x: Math.round(hitRate2x * 10) / 10,
  }
}
