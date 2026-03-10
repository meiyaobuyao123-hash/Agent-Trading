/**
 * POST /api/okx/execute
 * OKX DEX trade execution engine.
 *
 * Two modes:
 *  • Dry-run (default) — gets quote, simulates execution, records to Supabase with status='simulated'
 *  • Real             — requires SERVER_WALLET_PRIVATE_KEY + chain RPC in env
 *                       gets swap tx data from OKX, signs with ethers, broadcasts
 *
 * Body: {
 *   chainIndex: string
 *   toTokenAddress: string     // token to buy
 *   amountUsd: number
 *   slippage?: number          // percent, default 0.5
 *   fromTokenAddress?: string  // override fromToken (default USDT)
 *   strategyId?: string        // Supabase strategy UUID
 *   signal?: object            // signal that triggered this trade
 *   dryRun?: boolean           // force dry-run even if wallet configured
 * }
 */
import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { getOKXQuote, getOKXSwapData, STABLECOINS, usdToTokenAmount } from '@/lib/okx/client'

// Chain RPC endpoints for broadcasting transactions
const CHAIN_RPC: Record<string, string> = {
  '56':    'https://bsc-dataseed1.binance.org',
  '1':     'https://eth.llamarpc.com',
  '137':   'https://polygon-rpc.com',
  '42161': 'https://arb1.arbitrum.io/rpc',
  '8453':  'https://mainnet.base.org',
  '10':    'https://mainnet.optimism.io',
}

function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key) return null
  return createClient(url, key)
}

async function recordTrade(params: {
  strategyId: string | null
  chainId: number
  tokenAddress: string
  symbol: string
  direction: string
  amountIn: number
  amountOut: number | null
  execPrice: number | null
  txHash: string | null
  status: 'pending' | 'confirmed' | 'failed' | 'simulated'
  rawData: object
}) {
  const supabase = getSupabase()
  if (!supabase) return null
  const { data, error } = await supabase.from('trades').insert({
    strategy_id: params.strategyId,
    chain_id: params.chainId,
    token_address: params.tokenAddress,
    direction: params.direction,
    amount_in: params.amountIn,
    amount_out: params.amountOut,
    exec_price: params.execPrice,
    tx_hash: params.txHash,
    status: params.status,
    raw_data: params.rawData,
  }).select().single()
  if (error) console.error('[recordTrade]', error.message)
  return data ?? null
}

export async function POST(req: NextRequest) {
  const t0 = Date.now()
  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 })
  }

  const {
    chainIndex,
    toTokenAddress,
    amountUsd,
    slippage = 0.5,
    fromTokenAddress,
    strategyId = null,
    signal = {},
    dryRun: forceDryRun = false,
  } = body as {
    chainIndex: string
    toTokenAddress: string
    amountUsd: number
    slippage?: number
    fromTokenAddress?: string
    strategyId?: string | null
    signal?: Record<string, unknown>
    dryRun?: boolean
  }

  if (!chainIndex || !toTokenAddress || !amountUsd) {
    return NextResponse.json(
      { error: 'chainIndex, toTokenAddress, amountUsd are required' },
      { status: 400 }
    )
  }

  const stable = STABLECOINS[String(chainIndex)]
  const from = fromTokenAddress ?? stable?.usdt
  if (!from) {
    return NextResponse.json(
      { error: `Unsupported chainIndex "${chainIndex}". Provide fromTokenAddress.` },
      { status: 400 }
    )
  }

  const amount = usdToTokenAmount(Number(amountUsd), String(chainIndex))
  const slippageStr = String(Number(slippage) / 100)

  // ── Step 1: Get Quote ──────────────────────────────────────────────────────
  let quote: Record<string, unknown> | null = null
  try {
    quote = await getOKXQuote({
      chainIndex: String(chainIndex),
      fromTokenAddress: from,
      toTokenAddress: String(toTokenAddress),
      amount,
      slippage: slippageStr,
    }) as Record<string, unknown>
  } catch (err) {
    return NextResponse.json({ error: `Quote failed: ${(err as Error).message}` }, { status: 502 })
  }

  const toToken = quote?.toToken as Record<string, unknown> | undefined
  const estimatedOut = quote?.toTokenAmount
    ? Number(quote.toTokenAmount as string) / Math.pow(10, Number(toToken?.decimal ?? 18))
    : null
  const execPrice = estimatedOut ? Number(amountUsd) / estimatedOut : null
  const symbol = (toToken?.tokenSymbol as string) ?? '?'

  // ── Dry-run mode ───────────────────────────────────────────────────────────
  const walletKey = process.env.SERVER_WALLET_PRIVATE_KEY
  const isDryRun = forceDryRun || !walletKey

  if (isDryRun) {
    const trade = await recordTrade({
      strategyId: strategyId as string | null,
      chainId: Number(chainIndex),
      tokenAddress: String(toTokenAddress),
      symbol,
      direction: 'long',
      amountIn: Number(amountUsd),
      amountOut: estimatedOut,
      execPrice,
      txHash: null,
      status: 'simulated',
      rawData: { quote, signal, dryRun: true },
    })

    return NextResponse.json({
      ok: true,
      dryRun: true,
      reason: walletKey ? 'forced dry-run' : 'SERVER_WALLET_PRIVATE_KEY not configured',
      elapsed: `${Date.now() - t0}ms`,
      chainIndex,
      symbol,
      tokenAddress: toTokenAddress,
      amountUsd,
      estimatedOut: estimatedOut?.toFixed(8),
      execPrice: execPrice?.toFixed(8),
      slippagePct: slippage,
      dexRoute: (quote?.dexRouterList as Record<string, unknown>[])?.[0] ?? null,
      tradeId: trade?.id ?? null,
      message: walletKey
        ? 'Dry-run: trade not executed (forced)'
        : 'Dry-run: configure SERVER_WALLET_PRIVATE_KEY to enable real execution',
    })
  }

  // ── Real execution mode ────────────────────────────────────────────────────
  const walletAddress = process.env.SERVER_WALLET_ADDRESS
  const rpcUrl = CHAIN_RPC[String(chainIndex)] ?? process.env[`CHAIN_RPC_${chainIndex}`]
  if (!walletAddress || !rpcUrl) {
    return NextResponse.json(
      { error: 'SERVER_WALLET_ADDRESS or chain RPC not configured' },
      { status: 503 }
    )
  }

  try {
    // Step 2: Get unsigned swap transaction from OKX
    const swapData = await getOKXSwapData({
      chainIndex: String(chainIndex),
      fromTokenAddress: from,
      toTokenAddress: String(toTokenAddress),
      amount,
      slippage: slippageStr,
      userWalletAddress: walletAddress,
    })

    const tx = swapData?.tx as Record<string, unknown>
    if (!tx) throw new Error('OKX returned no tx data')

    // Step 3: Sign and broadcast via JSON-RPC
    // Dynamic import of ethers to avoid bundling in browser
    const { ethers } = await import('ethers')
    const provider = new ethers.JsonRpcProvider(rpcUrl)
    const wallet = new ethers.Wallet(walletKey, provider)

    const nonce = await provider.getTransactionCount(wallet.address)
    const feeData = await provider.getFeeData()

    const txRequest = {
      from: wallet.address,
      to: tx.to as string,
      data: tx.data as string,
      value: BigInt(tx.value as string ?? '0'),
      gasLimit: BigInt(Math.ceil(Number(tx.gas ?? 500_000) * 1.2)), // 20% buffer
      gasPrice: feeData.gasPrice,
      nonce,
      chainId: Number(chainIndex),
    }

    const sentTx = await wallet.sendTransaction(txRequest)
    console.log(`[execute] Tx sent: ${sentTx.hash}`)

    // Record immediately with 'pending'
    const trade = await recordTrade({
      strategyId: strategyId as string | null,
      chainId: Number(chainIndex),
      tokenAddress: String(toTokenAddress),
      symbol,
      direction: 'long',
      amountIn: Number(amountUsd),
      amountOut: null, // unknown until confirmed
      execPrice: null,
      txHash: sentTx.hash,
      status: 'pending',
      rawData: { tx: txRequest, signal, swapData },
    })

    // Wait for confirmation (max 30s, don't block the response)
    sentTx.wait(1).then(async (receipt: { status: number | null } | null) => {
      const supabase = getSupabase()
      if (!supabase || !trade) return
      const confirmed = receipt?.status === 1
      await supabase.from('trades').update({
        status: confirmed ? 'confirmed' : 'failed',
        amount_out: estimatedOut,
        exec_price: execPrice,
      }).eq('id', trade.id)
    }).catch(console.error)

    return NextResponse.json({
      ok: true,
      dryRun: false,
      txHash: sentTx.hash,
      chainIndex,
      symbol,
      amountUsd,
      estimatedOut: estimatedOut?.toFixed(8),
      tradeId: trade?.id ?? null,
      elapsed: `${Date.now() - t0}ms`,
    })
  } catch (err) {
    const msg = (err as Error).message
    console.error('[execute] Real execution failed:', msg)

    // Record failure
    await recordTrade({
      strategyId: strategyId as string | null,
      chainId: Number(chainIndex),
      tokenAddress: String(toTokenAddress),
      symbol,
      direction: 'long',
      amountIn: Number(amountUsd),
      amountOut: null,
      execPrice: null,
      txHash: null,
      status: 'failed',
      rawData: { error: msg, signal },
    })

    return NextResponse.json({ error: `Execution failed: ${msg}` }, { status: 500 })
  }
}
