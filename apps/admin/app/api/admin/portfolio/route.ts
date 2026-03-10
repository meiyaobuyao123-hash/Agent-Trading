import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key) return null
  return createClient(url, key)
}

// GET — 列出所有官方组合代币
export async function GET() {
  const supabase = getSupabase()
  if (!supabase) {
    return NextResponse.json({ error: 'Supabase not configured', tokens: [] }, { status: 200 })
  }
  const { data, error } = await supabase
    .from('official_portfolio')
    .select('*')
    .order('entry_at', { ascending: false })
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json({ tokens: data })
}

// POST — 添加新代币到官方组合
export async function POST(req: NextRequest) {
  const supabase = getSupabase()
  if (!supabase) {
    return NextResponse.json({ error: 'Supabase not configured' }, { status: 503 })
  }
  try {
    const body = await req.json()
    const { token_address, chain_id, symbol, name, entry_price, reason_tags, risk_level } = body
    if (!token_address || !chain_id || !symbol || !entry_price) {
      return NextResponse.json({ error: 'Missing required fields: token_address, chain_id, symbol, entry_price' }, { status: 400 })
    }
    const { data, error } = await supabase
      .from('official_portfolio')
      .insert([{
        token_address,
        chain_id: Number(chain_id),
        symbol,
        name: name || null,
        entry_price: Number(entry_price),
        reason_tags: reason_tags || [],
        risk_level: risk_level || 'medium',
        status: 'active',
      }])
      .select()
      .single()
    if (error) return NextResponse.json({ error: error.message }, { status: 500 })
    return NextResponse.json({ token: data }, { status: 201 })
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
