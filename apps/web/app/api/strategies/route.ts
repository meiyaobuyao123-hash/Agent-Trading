import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key) return null
  return createClient(url, key)
}

const DEMO_STRATEGIES = [
  {
    id: 'demo-1',
    name: '聪明钱跟单 BSC',
    condition_tree: {
      conditions: [
        { field: 'direction', op: 'eq', value: 'long' },
        { field: 'confidence_score', op: 'gte', value: 70 },
        { field: 'chain_id', op: 'in', value: ['56'] },
      ],
      logic: 'AND',
    },
    exec_config: {
      amount_usd: 100,
      slippage: 0.5,
      stop_loss_pct: 10,
      take_profit_pct: 30,
      max_gas_usd: 5,
    },
    generated_script: `// Strategy: 聪明钱跟单 BSC
export function evaluateSignal(s) {
  return s.direction === 'long'
    && s.confidenceScore >= 70
    && String(s.chainId) === '56';
}
export async function executeTrade(signal, config) {
  console.log(\`▶ Executing \${signal.symbol} on BSC\`);
  // OKX DEX execution stub
  return { ok: true };
}`,
    status: 'active',
    is_official: true,
    created_at: new Date(Date.now() - 2 * 86_400_000).toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'demo-2',
    name: '低风险 ETH 精选',
    condition_tree: {
      conditions: [
        { field: 'direction', op: 'eq', value: 'long' },
        { field: 'confidence_score', op: 'gte', value: 80 },
        { field: 'risk_level', op: 'eq', value: 'low' },
        { field: 'chain_id', op: 'in', value: ['1'] },
      ],
      logic: 'AND',
    },
    exec_config: {
      amount_usd: 200,
      slippage: 0.3,
      stop_loss_pct: 8,
      take_profit_pct: 25,
      max_gas_usd: 15,
    },
    generated_script: null,
    status: 'draft',
    is_official: false,
    created_at: new Date(Date.now() - 86_400_000).toISOString(),
    updated_at: new Date().toISOString(),
  },
]

export async function GET() {
  const supabase = getSupabase()
  if (!supabase) {
    return NextResponse.json({ strategies: DEMO_STRATEGIES, isDemo: true })
  }
  const { data, error } = await supabase
    .from('strategies')
    .select('*')
    .order('created_at', { ascending: false })
  // Table may not exist yet (migration not run) → fall back to demo
  if (error) {
    return NextResponse.json({ strategies: DEMO_STRATEGIES, isDemo: true, dbError: error.message })
  }
  return NextResponse.json({ strategies: data ?? [], isDemo: false })
}

export async function POST(req: NextRequest) {
  const supabase = getSupabase()
  if (!supabase) return NextResponse.json({ error: 'Supabase not configured' }, { status: 503 })

  const body = await req.json()
  const { name, condition_tree, exec_config } = body
  if (!name || !condition_tree || !exec_config) {
    return NextResponse.json({ error: 'name, condition_tree, exec_config are required' }, { status: 400 })
  }

  const { data, error } = await supabase
    .from('strategies')
    .insert({ name, condition_tree, exec_config, status: 'draft', is_official: false })
    .select()
    .single()
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json({ strategy: data })
}
