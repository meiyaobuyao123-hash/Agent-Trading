import { NextRequest, NextResponse } from 'next/server'

const BINANCE_HEADERS = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Origin': 'https://web3.binance.com',
  'Referer': 'https://web3.binance.com/',
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

/**
 * GET /api/binance/meme-rush?chainId=56&rankType=30&limit=20
 * 代理 Binance Meme Rush 排行榜（pulse rank list）
 * 上游: POST /bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/rank/list
 * rankType: 10=新发 20=即将迁移 30=已迁移(DEX)
 * chainId: CT_501(Solana) 56(BSC)
 */
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const chainId = searchParams.get('chainId') || '56'
  const rankType = Number(searchParams.get('rankType') ?? '30')
  const limit = Number(searchParams.get('limit') ?? '20')

  const upstream = 'https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/rank/list'

  try {
    const res = await fetch(upstream, {
      method: 'POST',
      headers: BINANCE_HEADERS,
      body: JSON.stringify({ chainId, rankType, limit }),
      next: { revalidate: 30 },
    })

    if (!res.ok) {
      return NextResponse.json({ error: `Binance upstream error: ${res.status}` }, { status: res.status })
    }

    const json = await res.json()
    return NextResponse.json(json, {
      headers: { 'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60' },
    })
  } catch (err) {
    console.error('[/api/binance/meme-rush]', err)
    return NextResponse.json({ error: 'Failed to fetch meme rush' }, { status: 500 })
  }
}
