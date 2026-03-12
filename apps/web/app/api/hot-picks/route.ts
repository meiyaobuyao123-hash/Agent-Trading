import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

/**
 * GET /api/hot-picks?date=2026-03-12&chain=solana
 *
 * 查询热币日榜 + 当前实时数据
 * - date: 查询日期（默认今天）
 * - chain: 可选链过滤（solana/bsc/base/eth）
 *
 * 返回: { picks: [...], dates: [...] }
 *   picks: 日榜代币列表（含推荐时快照 + 当前实时价格）
 *   dates: 最近30天有数据的日期列表（用于日期选择器）
 */
export async function GET(req: NextRequest) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.json({ error: 'Supabase not configured' }, { status: 500 })
  }

  const { searchParams } = new URL(req.url)
  const date = searchParams.get('date') || new Date().toISOString().slice(0, 10)
  const chain = searchParams.get('chain') || ''

  try {
    const supabase = createClient(supabaseUrl, supabaseKey)

    // 1. 查询指定日期的日榜
    let query = supabase
      .from('hot_daily_picks')
      .select('*')
      .eq('pick_date', date)
      .order('rank', { ascending: true })

    if (chain) {
      query = query.eq('chain', chain)
    }

    const { data: picks, error: picksErr } = await query
    if (picksErr) throw picksErr

    // 2. 查询这些代币的当前实时数据（从 hot_coins 表）
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
          const key = `${row.chain}|${row.address}`
          currentMap[key] = row
        }
      }
    }

    // 3. 合并：日榜快照 + 当前实时数据
    const enrichedPicks = (picks || []).map((pick: Record<string, unknown>) => {
      const snapshot = (pick.snapshot || {}) as Record<string, unknown>
      const key = `${pick.chain}|${pick.address}`
      const current = currentMap[key] || {}

      const pickPrice = Number(snapshot.price_usd || 0)
      const currentPrice = Number(current.price_usd || 0)
      const pnlPct = pickPrice > 0 && currentPrice > 0
        ? ((currentPrice - pickPrice) / pickPrice) * 100
        : null

      return {
        // 基础信息
        pick_date: pick.pick_date,
        chain: pick.chain,
        address: pick.address,
        name: pick.name,
        symbol: pick.symbol,
        rank: pick.rank,

        // 推荐时快照
        pick_score: pick.score,
        pick_recommendation: pick.recommendation,
        pick_price: pickPrice,
        pick_market_cap: Number(pick.market_cap_usd || 0),
        pick_volume_24h: Number(snapshot.volume_24h_usd || 0),
        pick_liquidity: Number(snapshot.liquidity_usd || 0),
        pick_holder_count: Number(snapshot.holder_count || 0),
        pick_score_m: Number(snapshot.score_m || 0),
        pick_score_q: Number(snapshot.score_q || 0),
        pick_score_p: Number(snapshot.score_p || 0),
        pick_has_twitter: Boolean(snapshot.has_twitter),
        pick_has_telegram: Boolean(snapshot.has_telegram),
        pick_has_website: Boolean(snapshot.has_website),

        // 当前实时数据
        current_price: currentPrice || null,
        current_market_cap: Number(current.market_cap_usd || 0) || null,
        current_volume_24h: Number(current.volume_24h_usd || 0) || null,
        current_score: current.score || null,
        current_recommendation: current.recommendation || null,
        current_change_24h: Number(current.price_change_24h || 0),
        current_change_1h: Number(current.price_change_1h || 0),
        current_change_5m: Number(current.price_change_5m || 0),
        current_holder_count: Number(current.holder_count || 0) || null,

        // 计算收益
        pnl_pct: pnlPct !== null ? Math.round(pnlPct * 100) / 100 : null,

        // 图标
        image_url: (current.image_url || current.token_logo_url || '') as string,
        scanned_at: current.scanned_at || null,
      }
    })

    // 4. 查询最近30天有数据的日期（用于日期选择器）
    const { data: dateRows } = await supabase
      .from('hot_daily_picks')
      .select('pick_date')
      .order('pick_date', { ascending: false })
      .limit(200)

    const uniqueDates = [...new Set((dateRows || []).map((r: Record<string, unknown>) => r.pick_date as string))]
      .sort((a, b) => b.localeCompare(a))
      .slice(0, 30)

    return NextResponse.json({
      picks: enrichedPicks,
      date,
      dates: uniqueDates,
    }, {
      headers: { 'Cache-Control': 'public, s-maxage=10, stale-while-revalidate=30' },
    })

  } catch (err) {
    console.error('[/api/hot-picks]', err)
    return NextResponse.json({ error: 'Failed to fetch hot picks' }, { status: 500 })
  }
}
