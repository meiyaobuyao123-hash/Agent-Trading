import { createClient } from './supabase'

// ═══════════════════════════════════════════════════
// 热币日榜 (hot_daily_picks + hot_coins 实时数据)
// ═══════════════════════════════════════════════════

export interface HotPickItem {
  pick_date: string
  chain: string
  address: string
  name: string
  symbol: string
  rank: number
  pick_score: number
  pick_recommendation: string
  pick_price: number
  pick_market_cap: number
  pick_volume_24h: number
  pick_liquidity: number
  pick_holder_count: number
  pick_score_m: number
  pick_score_q: number
  pick_score_p: number
  pick_has_twitter: boolean
  pick_has_telegram: boolean
  pick_has_website: boolean
  current_price: number | null
  current_market_cap: number | null
  current_volume_24h: number | null
  current_score: number | null
  current_recommendation: string | null
  current_change_24h: number
  current_change_1h: number
  current_change_5m: number
  current_holder_count: number | null
  pnl_pct: number | null
  image_url: string
  scanned_at: string | null
}

export async function fetchHotDailyPicks(opts: {
  date: string
  chain?: string
}): Promise<{ picks: HotPickItem[]; dates: string[] }> {
  const supabase = createClient()

  // 1. 查询指定日期的日榜
  let query = supabase
    .from('hot_daily_picks')
    .select('*')
    .eq('pick_date', opts.date)
    .order('rank', { ascending: true })

  if (opts.chain) query = query.eq('chain', opts.chain)

  const { data: picks, error: picksErr } = await query
  if (picksErr) throw picksErr

  // 2. 查询这些代币的当前实时数据
  const addresses = (picks || []).map((p: Record<string, unknown>) => p.address as string)
  let currentMap: Record<string, Record<string, unknown>> = {}

  if (addresses.length > 0) {
    const { data: currentData } = await supabase
      .from('hot_coins')
      .select('chain, address, price_usd, market_cap_usd, volume_24h_usd, '
        + 'liquidity_usd, price_change_1h, price_change_24h, price_change_5m, '
        + 'price_change_4h, holder_count, score, score_m, score_q, score_p, '
        + 'recommendation, image_url, token_logo_url, scanned_at')
      .in('address', addresses)

    if (currentData && Array.isArray(currentData)) {
      for (const row of currentData as unknown as Record<string, unknown>[]) {
        currentMap[`${row.chain}|${row.address}`] = row
      }
    }
  }

  // 3. 合并
  const enrichedPicks: HotPickItem[] = (picks || []).map((pick: Record<string, unknown>) => {
    const snap = (pick.snapshot || {}) as Record<string, unknown>
    const cur = currentMap[`${pick.chain}|${pick.address}`] || {}
    const pickPrice = Number(snap.price_usd || 0)
    const curPrice = Number(cur.price_usd || 0)
    const pnl = pickPrice > 0 && curPrice > 0 ? ((curPrice - pickPrice) / pickPrice) * 100 : null

    return {
      pick_date: pick.pick_date as string,
      chain: pick.chain as string,
      address: pick.address as string,
      name: pick.name as string,
      symbol: pick.symbol as string,
      rank: pick.rank as number,
      pick_score: pick.score as number,
      pick_recommendation: pick.recommendation as string,
      pick_price: pickPrice,
      pick_market_cap: Number(pick.market_cap_usd || 0),
      pick_volume_24h: Number(snap.volume_24h_usd || 0),
      pick_liquidity: Number(snap.liquidity_usd || 0),
      pick_holder_count: Number(snap.holder_count || 0),
      pick_score_m: Number(snap.score_m || 0),
      pick_score_q: Number(snap.score_q || 0),
      pick_score_p: Number(snap.score_p || 0),
      pick_has_twitter: Boolean(snap.has_twitter),
      pick_has_telegram: Boolean(snap.has_telegram),
      pick_has_website: Boolean(snap.has_website),
      current_price: curPrice || null,
      current_market_cap: Number(cur.market_cap_usd || 0) || null,
      current_volume_24h: Number(cur.volume_24h_usd || 0) || null,
      current_score: (cur.score as number) || null,
      current_recommendation: (cur.recommendation as string) || null,
      current_change_24h: Number(cur.price_change_24h || 0),
      current_change_1h: Number(cur.price_change_1h || 0),
      current_change_5m: Number(cur.price_change_5m || 0),
      current_holder_count: Number(cur.holder_count || 0) || null,
      pnl_pct: pnl !== null ? Math.round(pnl * 100) / 100 : null,
      image_url: (cur.image_url || cur.token_logo_url || '') as string,
      scanned_at: (cur.scanned_at as string) || null,
    }
  })

  // 4. 最近30天有数据的日期
  const { data: dateRows } = await supabase
    .from('hot_daily_picks')
    .select('pick_date')
    .order('pick_date', { ascending: false })
    .limit(200)

  const uniqueDates = [...new Set((dateRows || []).map((r: Record<string, unknown>) => r.pick_date as string))]
    .sort((a, b) => b.localeCompare(a))
    .slice(0, 30)

  return { picks: enrichedPicks, dates: uniqueDates }
}

// ═══════════════════════════════════════════════════
// 推荐表现追踪 (token_performance)
// ═══════════════════════════════════════════════════

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
  pickDate?: string
  orderBy?: string
  ascending?: boolean
}): Promise<TokenPerformance[]> {
  const supabase = createClient()
  let query = supabase.from('token_performance').select('*')

  if (opts.source) query = query.eq('source', opts.source)
  if (opts.chain) query = query.eq('chain', opts.chain)
  if (opts.pickDate) {
    query = query.eq('pick_date', opts.pickDate)
  } else if (opts.daysBack) {
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

export async function fetchPerformanceDates(source: 'pump' | 'hot'): Promise<string[]> {
  const supabase = createClient()
  const { data } = await supabase
    .from('token_performance')
    .select('pick_date')
    .eq('source', source)
    .order('pick_date', { ascending: false })
    .limit(500)

  const unique = [...new Set((data ?? []).map((r: Record<string, unknown>) => r.pick_date as string))]
    .sort((a, b) => b.localeCompare(a))
    .slice(0, 60)

  return unique
}

// ═══════════════════════════════════════════════════
// 内盘每日数据报表 (pump_daily_report)
// ═══════════════════════════════════════════════════

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

export async function fetchPumpDailyReports(days = 7): Promise<PumpDailyReport[]> {
  const supabase = createClient()
  const { data, error } = await supabase
    .from('pump_daily_report')
    .select('*')
    .order('report_date', { ascending: false })
    .limit(days)

  if (error) throw error
  return (data ?? []) as PumpDailyReport[]
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
    .limit(10000)

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
