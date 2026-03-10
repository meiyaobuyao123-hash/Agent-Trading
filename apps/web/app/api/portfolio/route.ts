import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

// =====================================================
// 官方组合演示数据（Supabase 未配置时使用）
// =====================================================
const DEMO_TOKENS = [
  {
    id: 'demo-1',
    token_address: '0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82',
    chain_id: 56,
    symbol: 'CAKE',
    name: 'PancakeSwap',
    entry_price: 2.15,
    entry_at: new Date(Date.now() - 9 * 24 * 60 * 60 * 1000).toISOString(),
    reason_tags: ['聪明钱驱动', 'DEX龙头', '交易量异动'],
    risk_level: 'low',
    status: 'active',
    exit_price: null,
    exit_at: null,
  },
  {
    id: 'demo-2',
    token_address: '0x6982508145454ce325ddbe47a25d4ec3d2311933',
    chain_id: 1,
    symbol: 'PEPE',
    name: 'Pepe',
    entry_price: 0.0000138,
    entry_at: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString(),
    reason_tags: ['社区热度', 'Meme Rush', '大资金流入'],
    risk_level: 'high',
    status: 'active',
    exit_price: null,
    exit_at: null,
  },
  {
    id: 'demo-3',
    token_address: '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
    chain_id: 1,
    symbol: 'SHIB',
    name: 'Shiba Inu',
    entry_price: 0.0000219,
    entry_at: new Date(Date.now() - 12 * 24 * 60 * 60 * 1000).toISOString(),
    reason_tags: ['持有人激增', '链上活跃', '做多信号'],
    risk_level: 'medium',
    status: 'active',
    exit_price: null,
    exit_at: null,
  },
  {
    id: 'demo-4',
    token_address: '0x7083609fce4d1d8dc0c979aab8c869ea2c873402',
    chain_id: 56,
    symbol: 'DOT',
    name: 'Polkadot (BSC)',
    entry_price: 5.82,
    entry_at: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
    reason_tags: ['基本面强', '聪明钱流入', '低风险'],
    risk_level: 'low',
    status: 'active',
    exit_price: null,
    exit_at: null,
  },
  {
    id: 'demo-5',
    token_address: '0xba2ae424d960c26247dd6c32edc70b295c744c43',
    chain_id: 56,
    symbol: 'DOGE',
    name: 'Dogecoin (BSC)',
    entry_price: 0.172,
    entry_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    reason_tags: ['社区热度', 'Meme Rush', '短线机会'],
    risk_level: 'high',
    status: 'active',
    exit_price: null,
    exit_at: null,
  },
  {
    id: 'demo-6',
    token_address: '0x2170ed0880ac9a755fd29b2688956bd959f933f8',
    chain_id: 56,
    symbol: 'ETH',
    name: 'Ethereum (BSC)',
    entry_price: 2310.0,
    entry_at: new Date(Date.now() - 21 * 24 * 60 * 60 * 1000).toISOString(),
    reason_tags: ['蓝筹资产', '趋势向上'],
    risk_level: 'low',
    status: 'exited',
    exit_price: 2680.0,
    exit_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'demo-7',
    token_address: '0xbf5140a22578168fd562dccf235e5d43a02ce9b1',
    chain_id: 56,
    symbol: 'UNI',
    name: 'Uniswap (BSC)',
    entry_price: 8.45,
    entry_at: new Date(Date.now() - 18 * 24 * 60 * 60 * 1000).toISOString(),
    reason_tags: ['DEX热度', '做多信号', '基本面'],
    risk_level: 'medium',
    status: 'exited',
    exit_price: 7.20,
    exit_at: new Date(Date.now() - 8 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'demo-8',
    token_address: '0x3ee2200efb3400fabb9aacf31297cbdd1d435d47',
    chain_id: 56,
    symbol: 'ADA',
    name: 'Cardano (BSC)',
    entry_price: 0.415,
    entry_at: new Date(Date.now() - 25 * 24 * 60 * 60 * 1000).toISOString(),
    reason_tags: ['生态发展', '聪明钱加仓', '长期布局'],
    risk_level: 'medium',
    status: 'exited',
    exit_price: 0.563,
    exit_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
  },
]

export async function GET() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  // Supabase 未配置时返回演示数据
  if (!supabaseUrl || supabaseUrl === '' || !supabaseKey || supabaseKey === '') {
    return NextResponse.json({
      tokens: DEMO_TOKENS,
      isDemo: true,
    })
  }

  try {
    const supabase = createClient(supabaseUrl, supabaseKey)
    const { data, error } = await supabase
      .from('official_portfolio')
      .select('*')
      .order('entry_at', { ascending: false })

    if (error) throw error

    return NextResponse.json({
      tokens: data ?? [],
      isDemo: false,
    })
  } catch (err) {
    console.error('[/api/portfolio]', err)
    // Supabase 出错时也返回演示数据
    return NextResponse.json({
      tokens: DEMO_TOKENS,
      isDemo: true,
    })
  }
}
