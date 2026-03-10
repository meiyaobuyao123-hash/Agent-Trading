import { NextRequest, NextResponse } from 'next/server'

const BINANCE_HEADERS = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Origin': 'https://web3.binance.com',
  'Referer': 'https://web3.binance.com/',
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

/**
 * GET /api/binance/market-rank?chainId=56&size=20
 * 代理 Binance exclusive rank（综合排名）
 * 上游: GET /bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/exclusive/rank/list?chainId=56
 */
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const chainId = searchParams.get('chainId') || '56' // 默认 BSC
  const size = Number(searchParams.get('size') ?? '20')

  // Binance exclusive rank 是 GET 请求，chainId 作为 query 参数
  const upstream = `https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/exclusive/rank/list?chainId=${chainId}`

  try {
    const res = await fetch(upstream, {
      headers: BINANCE_HEADERS,
      next: { revalidate: 30 },
    })

    if (!res.ok) {
      return NextResponse.json({ error: `Binance upstream error: ${res.status}` }, { status: res.status })
    }

    const json = await res.json()

    // 统一返回结构
    const tokens = (json?.data?.tokens ?? []).slice(0, size)
    return NextResponse.json({ code: '000000', data: { tokens } }, {
      headers: { 'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60' },
    })
  } catch (err) {
    console.error('[/api/binance/market-rank]', err)
    return NextResponse.json({ error: 'Failed to fetch market rank' }, { status: 500 })
  }
}
