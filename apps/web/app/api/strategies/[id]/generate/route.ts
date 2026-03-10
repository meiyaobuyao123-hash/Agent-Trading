import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'

// ── helpers ──────────────────────────────────────────────────────────────────
const FIELD_LABELS: Record<string, string> = {
  direction: 'signal direction',
  confidence_score: 'confidence score (0-100)',
  chain_id: 'blockchain chain ID',
  risk_level: 'risk level',
}
const OP_LABELS: Record<string, string> = {
  eq: 'equals',
  gte: 'is greater than or equal to',
  lte: 'is less than or equal to',
  in: 'is one of',
}
const CHAIN_NAMES: Record<string, string> = {
  '56': 'BSC (Binance Smart Chain)',
  '1': 'Ethereum',
  '900': 'Solana',
  'CT_501': 'Solana',
}

function describeConditions(conditionTree: {
  conditions: Array<{ field: string; op: string; value: unknown }>
  logic: string
}): string {
  return conditionTree.conditions
    .map((c) => {
      const field = FIELD_LABELS[c.field] ?? c.field
      const op = OP_LABELS[c.op] ?? c.op
      let val = c.value
      if (c.field === 'chain_id' && Array.isArray(val)) {
        val = (val as string[]).map((v) => CHAIN_NAMES[String(v)] ?? v).join(', ')
      }
      return `  - ${field} ${op} "${val}"`
    })
    .join('\n')
}

// ── fallback template when no API key ────────────────────────────────────────
function buildTemplateScript(
  name: string,
  conditionTree: { conditions: Array<{ field: string; op: string; value: unknown }>; logic: string },
  execConfig: { amount_usd: number; slippage: number; stop_loss_pct: number; take_profit_pct: number; max_gas_usd: number }
): string {
  const checks = conditionTree.conditions.map((c) => {
    if (c.field === 'direction') return `s.direction === '${c.value}'`
    if (c.field === 'confidence_score') {
      return c.op === 'gte'
        ? `s.confidenceScore >= ${c.value}`
        : `s.confidenceScore <= ${c.value}`
    }
    if (c.field === 'chain_id' && Array.isArray(c.value)) {
      const ids = (c.value as string[]).map((v) => `'${v}'`).join(', ')
      return `[${ids}].includes(String(s.chainId))`
    }
    if (c.field === 'risk_level') return `s.riskLevel === '${c.value}'`
    return '/* unknown condition */'
  })

  const logic = conditionTree.logic === 'OR' ? '\n    || ' : '\n    && '
  const condStr = checks.join(logic)

  return `// ═══════════════════════════════════════════════════════════
// Strategy: ${name}
// Generated: ${new Date().toISOString()}
// Conditions: ${conditionTree.conditions.length} rules (${conditionTree.logic}) | Amount: $${execConfig.amount_usd} USD
// ═══════════════════════════════════════════════════════════

/**
 * Signal interface (matches AiTrading signal schema)
 */
export interface SignalInput {
  direction: 'long' | 'watch' | 'exit'
  confidenceScore: number
  chainId: number | string
  riskLevel: 'low' | 'medium' | 'high'
  symbol: string
  tokenAddress: string
  triggerPrice: number
}

/**
 * Evaluate whether a signal satisfies this strategy's conditions.
 * Returns true if the signal should trigger a trade.
 */
export function evaluateSignal(s: SignalInput): boolean {
  return (
    ${condStr}
  )
}

/**
 * Execute a trade via OKX DEX aggregator.
 * Called by the strategy engine when evaluateSignal returns true.
 */
export async function executeTrade(
  signal: SignalInput
): Promise<{ ok: boolean; txHash?: string; error?: string }> {
  const config = {
    amountUsd: ${execConfig.amount_usd},
    slippage: ${execConfig.slippage},        // %
    stopLossPct: ${execConfig.stop_loss_pct}, // %
    takeProfitPct: ${execConfig.take_profit_pct}, // %
    maxGasUsd: ${execConfig.max_gas_usd},
  }

  const stopLoss   = signal.triggerPrice * (1 - config.stopLossPct / 100)
  const takeProfit = signal.triggerPrice * (1 + config.takeProfitPct / 100)

  console.log(\`▶  [\${signal.symbol}] \${signal.direction.toUpperCase()} on chain \${signal.chainId}\`)
  console.log(\`   Entry: $\${signal.triggerPrice} | SL: $\${stopLoss.toFixed(6)} | TP: $\${takeProfit.toFixed(6)}\`)
  console.log(\`   Amount: $\${config.amountUsd} | Slippage: \${config.slippage}%\`)

  try {
    // 1. Get quote from OKX DEX
    const quoteRes = await fetch('/api/okx/quote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chainIndex: String(signal.chainId),
        toTokenAddress: signal.tokenAddress,
        amountUsd: config.amountUsd,
        slippage: String(config.slippage / 100),
      }),
    })
    if (!quoteRes.ok) throw new Error(\`Quote failed: HTTP \${quoteRes.status}\`)
    const quote = await quoteRes.json()

    // 2. Execute swap (stub — real execution handled by OKX execution engine)
    console.log(\`✅  Quote received. Route: \${quote?.routerResult?.dexRouterList?.[0]?.subRouterList?.[0]?.dexProtocol?.[0]?.dexName ?? 'OKX'}\`)

    // TODO: submit signed tx via /api/okx/execute
    return { ok: true }
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error'
    console.error(\`✗  Trade failed: \${msg}\`)
    return { ok: false, error: msg }
  }
}

/**
 * Main entry point — called by the AiTrading strategy engine
 */
export async function run(signal: SignalInput): Promise<void> {
  if (!evaluateSignal(signal)) {
    console.log(\`⏭  [\${signal.symbol}] Signal skipped (conditions not met)\`)
    return
  }
  console.log(\`✅  [\${signal.symbol}] Conditions matched — executing trade\`)
  await executeTrade(signal)
}
`
}

// ── main handler ──────────────────────────────────────────────────────────────
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const body = await req.json()
  const { name, conditionTree, execConfig } = body

  if (!name || !conditionTree || !execConfig) {
    return NextResponse.json({ error: 'name, conditionTree, execConfig are required' }, { status: 400 })
  }

  const apiKey = process.env.ANTHROPIC_API_KEY

  // ── No API key → return template ──────────────────────────────────────────
  if (!apiKey) {
    const script = buildTemplateScript(name, conditionTree, execConfig)
    return NextResponse.json({
      id,
      script,
      source: 'template',
      message: 'ANTHROPIC_API_KEY not configured — template script generated',
    })
  }

  // ── Call Claude ─────────────────────────────────────────────────────────────
  const client = new Anthropic({ apiKey })

  const conditionsText = describeConditions(conditionTree)
  const prompt = `You are an expert DeFi trading bot developer. Generate a clean TypeScript strategy module based on the specification below.

## Strategy Name
${name}

## Signal Conditions (${conditionTree.logic} logic)
${conditionsText}

## Execution Config
- Trade amount: $${execConfig.amount_usd} USD
- Slippage tolerance: ${execConfig.slippage}%
- Stop loss: ${execConfig.stop_loss_pct}%
- Take profit: ${execConfig.take_profit_pct}%
- Max gas: $${execConfig.max_gas_usd} USD

## Requirements
1. Export a \`SignalInput\` interface (fields: direction, confidenceScore, chainId, riskLevel, symbol, tokenAddress, triggerPrice)
2. Export \`evaluateSignal(s: SignalInput): boolean\` that checks ALL conditions
3. Export \`executeTrade(signal: SignalInput): Promise<{ok:boolean; txHash?:string; error?:string}>\` that:
   - Calculates stop-loss and take-profit prices from triggerPrice
   - Logs trade intent with symbol, entry, SL, TP, amount
   - POSTs to \`/api/okx/quote\` with chainIndex, toTokenAddress, amountUsd, slippage
   - Returns \`{ok: true}\` on success, \`{ok: false, error}\` on failure
   - Wraps in try/catch
4. Export \`run(signal: SignalInput): Promise<void>\` — evaluates then executes
5. Add a header comment block with strategy name, conditions summary, exec config summary
6. Use template literals for console.log messages with emojis (▶ ✅ ⏭ ✗)
7. Return ONLY the TypeScript code. No markdown, no explanation.`

  try {
    const message = await client.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 2048,
      messages: [{ role: 'user', content: prompt }],
    })

    const content = message.content[0]
    if (content.type !== 'text') {
      return NextResponse.json({ error: 'Unexpected response from Claude' }, { status: 500 })
    }

    // Strip markdown code fences if Claude wrapped the code
    let script = content.text.trim()
    if (script.startsWith('```')) {
      script = script.replace(/^```(?:typescript|ts)?\n?/, '').replace(/\n?```$/, '').trim()
    }

    return NextResponse.json({ id, script, source: 'claude', model: 'claude-haiku-4-5' })
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error'
    // Fall back to template on API error
    const script = buildTemplateScript(name, conditionTree, execConfig)
    return NextResponse.json({ id, script, source: 'template_fallback', error: msg })
  }
}
