/**
 * POST /api/okx/quote
 * Server-side proxy for OKX DEX aggregator quote endpoint.
 * Called by strategy scripts and the Admin DEX panel.
 *
 * Body: {
 *   chainIndex: string        // '56' BSC | '1' ETH | '137' Polygon ...
 *   toTokenAddress: string    // token we want to BUY
 *   amountUsd: number         // USD amount (converted to stablecoin units internally)
 *   slippage?: number         // percentage, default 0.5
 *   fromTokenAddress?: string // override (default: USDT for that chain)
 * }
 */
import { NextRequest, NextResponse } from 'next/server'
import { getOKXQuote, STABLECOINS, usdToTokenAmount } from '@/lib/okx/client'

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const { chainIndex, toTokenAddress, amountUsd, slippage = 0.5, fromTokenAddress } = body

    if (!chainIndex || !toTokenAddress || !amountUsd) {
      return NextResponse.json(
        { error: 'chainIndex, toTokenAddress, amountUsd are required' },
        { status: 400 }
      )
    }

    // Resolve fromToken (default: USDT for that chain)
    const stable = STABLECOINS[String(chainIndex)]
    if (!stable && !fromTokenAddress) {
      return NextResponse.json(
        { error: `Chain ${chainIndex} not in STABLECOINS map, provide fromTokenAddress` },
        { status: 400 }
      )
    }

    const from = fromTokenAddress ?? stable!.usdt
    const amount = usdToTokenAmount(Number(amountUsd), String(chainIndex))
    const slippageStr = String(slippage / 100) // OKX wants 0.005 not 0.5

    const t0 = Date.now()
    const quote = await getOKXQuote({
      chainIndex: String(chainIndex),
      fromTokenAddress: from,
      toTokenAddress,
      amount,
      slippage: slippageStr,
    })
    const elapsed = Date.now() - t0

    if (!quote) {
      return NextResponse.json({ error: 'OKX returned empty quote' }, { status: 502 })
    }

    // Shape the response for easy consumption
    const fromToken = quote.fromToken
    const toToken = quote.toToken
    const estimatedOutput = quote.toTokenAmount
      ? (Number(quote.toTokenAmount) / Math.pow(10, Number(toToken?.decimal ?? 18))).toFixed(8)
      : null

    const priceImpact = quote.priceImpactPercentage
      ? (Number(quote.priceImpactPercentage) * 100).toFixed(3)
      : null

    const dexName = quote.dexRouterList?.[0]?.subRouterList?.[0]?.dexProtocol?.[0]?.dexName
      ?? 'OKX Aggregator'

    return NextResponse.json({
      ok: true,
      elapsed: `${elapsed}ms`,
      chainIndex,
      amountUsd,
      slippagePct: slippage,
      fromToken: {
        address: from,
        symbol: fromToken?.tokenSymbol ?? 'USDT',
        decimals: fromToken?.decimal ?? 18,
      },
      toToken: {
        address: toTokenAddress,
        symbol: toToken?.tokenSymbol ?? '?',
        decimals: toToken?.decimal ?? 18,
      },
      estimatedOutput,
      estimatedPrice: quote.quoteCompareList?.[0]?.toTokenAmount
        ? (Number(quote.quoteCompareList[0].toTokenAmount) / Math.pow(10, Number(toToken?.decimal ?? 18))).toFixed(8)
        : null,
      priceImpactPct: priceImpact,
      dexRoute: dexName,
      rawQuote: quote,
    })
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error'
    console.error('[/api/okx/quote]', msg)
    return NextResponse.json({ error: msg }, { status: 500 })
  }
}
