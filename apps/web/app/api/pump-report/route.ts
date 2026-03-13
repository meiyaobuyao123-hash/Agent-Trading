import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

/**
 * GET /api/pump-report?days=7
 *
 * 查询内盘每日报表
 * - days: 最近N天（默认7）
 */
export async function GET(req: NextRequest) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.json({ error: 'Supabase not configured' }, { status: 500 })
  }

  const { searchParams } = new URL(req.url)
  const days = Math.min(Number(searchParams.get('days') || 7), 90)

  try {
    const supabase = createClient(supabaseUrl, supabaseKey)

    const { data, error } = await supabase
      .from('pump_daily_report')
      .select('*')
      .order('report_date', { ascending: false })
      .limit(days)

    if (error) throw error

    return NextResponse.json({ reports: data || [] }, {
      headers: { 'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120' },
    })
  } catch (err) {
    console.error('[/api/pump-report]', err)
    return NextResponse.json({ error: 'Failed to fetch pump report' }, { status: 500 })
  }
}
