import { NextRequest, NextResponse } from 'next/server'

const BINANCE_BASE = 'https://web3.binance.com/bapi/defi'

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const chainId = searchParams.get('chainId')
  const address = searchParams.get('address')

  if (!chainId || !address) {
    return NextResponse.json({ error: 'chainId and address are required' }, { status: 400 })
  }

  const upstream = `${BINANCE_BASE}/v1/public/token-dynamic/token/detail?chainId=${chainId}&address=${address}`

  try {
    const res = await fetch(upstream, {
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Origin': 'https://web3.binance.com',
        'Referer': 'https://web3.binance.com/',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      },
      next: { revalidate: 60 },
    })

    if (!res.ok) {
      return NextResponse.json({ error: `Binance upstream error: ${res.status}` }, { status: res.status })
    }

    const data = await res.json()
    return NextResponse.json(data, {
      headers: { 'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120' },
    })
  } catch (err) {
    console.error('[/api/binance/token-dynamic]', err)
    return NextResponse.json({ error: 'Failed to fetch token dynamic' }, { status: 500 })
  }
}
