import { NextRequest, NextResponse } from 'next/server'

const BINANCE_HEADERS = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Origin': 'https://web3.binance.com',
  'Referer': 'https://web3.binance.com/',
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

/**
 * GET /api/binance/signals?chainId=56&pageSize=20
 * 代理 Binance Smart Money 信号列表
 * 上游: POST /bapi/defi/v1/public/wallet-direct/buw/wallet/web/signal/smart-money
 */
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const chainId = searchParams.get('chainId') || '56'
  const pageSize = Number(searchParams.get('pageSize') ?? '20')
  const page = Number(searchParams.get('page') ?? '1')

  const upstream = 'https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/web/signal/smart-money'

  try {
    const res = await fetch(upstream, {
      method: 'POST',
      headers: BINANCE_HEADERS,
      body: JSON.stringify({
        chainId,
        page,
        pageSize,
        smartSignalType: '',
      }),
      next: { revalidate: 20 },
    })

    if (!res.ok) {
      return NextResponse.json({ error: `Binance upstream error: ${res.status}` }, { status: res.status })
    }

    const json = await res.json()
    return NextResponse.json(json, {
      headers: { 'Cache-Control': 'public, s-maxage=20, stale-while-revalidate=40' },
    })
  } catch (err) {
    console.error('[/api/binance/signals]', err)
    return NextResponse.json({ error: 'Failed to fetch signals' }, { status: 500 })
  }
}
