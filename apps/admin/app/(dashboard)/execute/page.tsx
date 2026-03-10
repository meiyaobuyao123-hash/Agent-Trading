'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Zap, AlertCircle, CheckCircle, Loader2, RefreshCw,
  ArrowRightLeft, Clock, Search, ExternalLink,
} from 'lucide-react'
import { AdminTopbar } from '../../components/topbar'

const WEB_BASE = process.env.NEXT_PUBLIC_WEB_BASE_URL || 'http://localhost:3000'

// ── Types ─────────────────────────────────────────────────────────────────────
interface QuoteResult {
  ok: boolean
  elapsed: string
  chainIndex: string
  amountUsd: number
  slippagePct: number
  fromToken: { symbol: string; address: string; decimals: number }
  toToken: { symbol: string; address: string; decimals: number }
  estimatedOutput: string | null
  priceImpactPct: string | null
  dexRoute: string
}

interface ExecuteResult {
  ok: boolean
  dryRun: boolean
  txHash?: string
  symbol: string
  amountUsd: number
  estimatedOut?: string
  tradeId?: string
  elapsed: string
  reason?: string
  message?: string
}

interface Trade {
  id: string
  chain_id: number
  chainName: string
  symbol: string
  token_address: string
  direction: string
  amount_in: number
  amount_out: number | null
  exec_price: number | null
  tx_hash: string | null
  status: string
  created_at: string
}

// ── Constants ─────────────────────────────────────────────────────────────────
const CHAINS = [
  { index: '56',    name: 'BSC',      color: '#F0B90B' },
  { index: '1',     name: 'ETH',      color: '#627EEA' },
  { index: '137',   name: 'Polygon',  color: '#8247E5' },
  { index: '42161', name: 'Arbitrum', color: '#28A0F0' },
  { index: '8453',  name: 'Base',     color: '#0052FF' },
]

const STATUS_STYLE: Record<string, { label: string; color: string }> = {
  simulated: { label: '模拟',   color: 'var(--yellow)' },
  pending:   { label: '待确认', color: 'var(--blue)' },
  confirmed: { label: '已确认', color: 'var(--green)' },
  failed:    { label: '失败',   color: 'var(--red)' },
}

const EXPLORER: Record<string, string> = {
  '56':    'https://bscscan.com/tx/',
  '1':     'https://etherscan.io/tx/',
  '137':   'https://polygonscan.com/tx/',
  '42161': 'https://arbiscan.io/tx/',
  '8453':  'https://basescan.org/tx/',
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtDate(d: string) {
  return new Date(d).toLocaleString('zh-CN', {
    month: 'numeric', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}
function fmtNum(n: number | null | undefined, decimals = 2) {
  if (n == null) return '—'
  return n.toLocaleString('en-US', { maximumFractionDigits: decimals, minimumFractionDigits: decimals })
}

// ── Stat Card ─────────────────────────────────────────────────────────────────
function Stat({ label, value, color = 'var(--text)' }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl border p-4" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <div className="text-xs mb-1" style={{ color: 'var(--text-dim)' }}>{label}</div>
      <div className="text-xl font-black" style={{ color }}>{value}</div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function ExecutePage() {
  // Quote form
  const [chainIndex, setChainIndex] = useState('56')
  const [toToken, setToToken] = useState('')
  const [amountUsd, setAmountUsd] = useState(100)
  const [slippage, setSlippage] = useState(0.5)
  const [quoting, setQuoting] = useState(false)
  const [quote, setQuote] = useState<QuoteResult | null>(null)
  const [quoteError, setQuoteError] = useState<string | null>(null)

  // Execute
  const [executing, setExecuting] = useState(false)
  const [execResult, setExecResult] = useState<ExecuteResult | null>(null)
  const [execError, setExecError] = useState<string | null>(null)
  const [forceDryRun, setForceDryRun] = useState(true)

  // Trade history
  const [trades, setTrades] = useState<Trade[]>([])
  const [tradesLoading, setTradesLoading] = useState(true)
  const [isDemo, setIsDemo] = useState(false)

  const loadTrades = useCallback(async () => {
    setTradesLoading(true)
    try {
      const res = await fetch(`${WEB_BASE}/api/trades?limit=20`)
      const data = await res.json()
      setTrades(data.trades ?? [])
      setIsDemo(data.isDemo ?? false)
    } catch (err) {
      console.error(err)
    } finally {
      setTradesLoading(false)
    }
  }, [])

  useEffect(() => { loadTrades() }, [loadTrades])

  const handleGetQuote = async () => {
    if (!toToken.trim()) { setQuoteError('请输入代币合约地址'); return }
    setQuoting(true)
    setQuoteError(null)
    setQuote(null)
    try {
      const res = await fetch(`${WEB_BASE}/api/okx/quote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chainIndex, toTokenAddress: toToken.trim(), amountUsd, slippage }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`)
      setQuote(data)
    } catch (err) {
      setQuoteError(err instanceof Error ? err.message : '获取报价失败')
    } finally {
      setQuoting(false)
    }
  }

  const handleExecute = async () => {
    if (!toToken.trim() || !quote) return
    setExecuting(true)
    setExecError(null)
    setExecResult(null)
    try {
      const res = await fetch(`${WEB_BASE}/api/okx/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chainIndex,
          toTokenAddress: toToken.trim(),
          amountUsd,
          slippage,
          dryRun: forceDryRun,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`)
      setExecResult(data)
      // Refresh trades
      setTimeout(loadTrades, 1500)
    } catch (err) {
      setExecError(err instanceof Error ? err.message : '执行失败')
    } finally {
      setExecuting(false)
    }
  }

  // Stats from trades
  const simCount   = trades.filter((t) => t.status === 'simulated').length
  const realCount  = trades.filter((t) => t.status === 'confirmed').length
  const failCount  = trades.filter((t) => t.status === 'failed').length
  const totalVol   = trades.reduce((s, t) => s + (t.amount_in ?? 0), 0)

  return (
    <div>
      <AdminTopbar
        title="DEX 执行引擎"
        subtitle="OKX DEX 报价 · 模拟/真实执行 · 交易历史"
        action={
          <button
            onClick={loadTrades}
            disabled={tradesLoading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium"
            style={{ background: 'var(--bg-card)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
          >
            <RefreshCw size={12} className={tradesLoading ? 'animate-spin' : ''} />
            刷新
          </button>
        }
      />

      <div className="p-6 space-y-5">

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <Stat label="模拟交易" value={String(simCount)}  color="var(--yellow)" />
          <Stat label="成功交易" value={String(realCount)} color="var(--green)" />
          <Stat label="失败交易" value={String(failCount)} color="var(--red)" />
          <Stat label="总交易量" value={`$${fmtNum(totalVol)}`} />
        </div>

        <div className="grid grid-cols-2 gap-5">

          {/* ── Quote Form ──────────────────────────────────────────────── */}
          <div
            className="rounded-xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
          >
            <div
              className="flex items-center gap-2 px-5 py-3.5 text-sm font-semibold"
              style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-card2)', color: 'var(--text)' }}
            >
              <Search size={14} color="var(--blue)" />
              获取 OKX 报价
            </div>
            <div className="p-5 space-y-4">
              {/* Chain */}
              <div className="space-y-1.5">
                <label className="text-xs" style={{ color: 'var(--text-dim)' }}>目标链</label>
                <div className="flex gap-2 flex-wrap">
                  {CHAINS.map((c) => (
                    <button
                      key={c.index}
                      onClick={() => setChainIndex(c.index)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                      style={{
                        background: chainIndex === c.index ? `${c.color}22` : 'var(--bg-card2)',
                        color: chainIndex === c.index ? c.color : 'var(--text-dim)',
                        border: `1px solid ${chainIndex === c.index ? c.color + '55' : 'var(--border)'}`,
                      }}
                    >
                      {c.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Token address */}
              <div className="space-y-1.5">
                <label className="text-xs" style={{ color: 'var(--text-dim)' }}>代币合约地址（买入目标）</label>
                <input
                  type="text"
                  placeholder="0x... 或 SOL 地址"
                  value={toToken}
                  onChange={(e) => setToToken(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg text-xs font-mono"
                  style={{
                    background: 'var(--bg-card2)',
                    border: `1px solid ${toToken ? 'var(--blue)' : 'var(--border)'}`,
                    color: 'var(--text)',
                    outline: 'none',
                  }}
                />
              </div>

              {/* Amount + Slippage */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs" style={{ color: 'var(--text-dim)' }}>金额 (USD)</label>
                  <input
                    type="number"
                    min={10} max={100000} step={10}
                    value={amountUsd}
                    onChange={(e) => setAmountUsd(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg text-sm font-mono font-bold"
                    style={{ background: 'var(--bg-card2)', border: '1px solid var(--border)', color: 'var(--yellow)', outline: 'none' }}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs" style={{ color: 'var(--text-dim)' }}>滑点 (%)</label>
                  <input
                    type="number"
                    min={0.1} max={5} step={0.1}
                    value={slippage}
                    onChange={(e) => setSlippage(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg text-sm font-mono font-bold"
                    style={{ background: 'var(--bg-card2)', border: '1px solid var(--border)', color: 'var(--blue)', outline: 'none' }}
                  />
                </div>
              </div>

              {quoteError && (
                <div className="text-xs flex items-center gap-1.5 px-3 py-2 rounded-lg"
                  style={{ background: 'rgba(246,70,93,0.08)', color: 'var(--red)' }}>
                  <AlertCircle size={12} />
                  {quoteError}
                </div>
              )}

              <button
                onClick={handleGetQuote}
                disabled={quoting || !toToken.trim()}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold"
                style={{
                  background: toToken.trim() ? 'rgba(22,155,213,0.15)' : 'var(--bg-card2)',
                  color: toToken.trim() ? 'var(--blue)' : 'var(--text-dim)',
                  border: `1px solid ${toToken.trim() ? 'rgba(22,155,213,0.3)' : 'var(--border)'}`,
                  opacity: quoting ? 0.7 : 1,
                }}
              >
                {quoting ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
                {quoting ? 'OKX 查询中…' : '获取报价'}
              </button>

              {/* Quote Result */}
              {quote && (
                <div
                  className="rounded-xl p-4 space-y-2.5"
                  style={{ background: 'rgba(82,196,26,0.05)', border: '1px solid rgba(82,196,26,0.2)' }}
                >
                  <div className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: 'var(--green)' }}>
                    <CheckCircle size={12} />
                    报价获取成功 · {quote.elapsed}
                  </div>
                  <div className="space-y-1.5 text-xs" style={{ color: 'var(--text-dim)' }}>
                    <div className="flex justify-between">
                      <span>路由</span>
                      <span style={{ color: 'var(--text)' }}>{quote.dexRoute}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>支付</span>
                      <span style={{ color: 'var(--yellow)' }}>${quote.amountUsd} → {quote.fromToken.symbol}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>预计获得</span>
                      <span style={{ color: 'var(--green)' }}>
                        {quote.estimatedOutput} {quote.toToken.symbol}
                      </span>
                    </div>
                    {quote.priceImpactPct && (
                      <div className="flex justify-between">
                        <span>价格影响</span>
                        <span style={{ color: Number(quote.priceImpactPct) > 1 ? 'var(--red)' : 'var(--text)' }}>
                          {quote.priceImpactPct}%
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── Execute Panel ──────────────────────────────────────────── */}
          <div
            className="rounded-xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
          >
            <div
              className="flex items-center gap-2 px-5 py-3.5 text-sm font-semibold"
              style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-card2)', color: 'var(--text)' }}
            >
              <ArrowRightLeft size={14} color="var(--green)" />
              执行交易
            </div>
            <div className="p-5 space-y-4">

              {/* Mode toggle */}
              <div
                className="rounded-xl p-4 space-y-3"
                style={{ background: 'var(--bg-card2)', border: '1px solid var(--border)' }}
              >
                <div className="text-xs font-semibold" style={{ color: 'var(--text)' }}>执行模式</div>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { dry: true,  label: '模拟执行',  desc: '不消耗 Gas，记录意图',  color: 'var(--yellow)' },
                    { dry: false, label: '真实执行',   desc: '需配置钱包私钥',        color: 'var(--green)' },
                  ].map(({ dry, label, desc, color }) => (
                    <button
                      key={String(dry)}
                      onClick={() => setForceDryRun(dry)}
                      className="p-3 rounded-xl text-left transition-all"
                      style={{
                        background: forceDryRun === dry ? `${color}15` : 'transparent',
                        border: `1px solid ${forceDryRun === dry ? color + '55' : 'var(--border)'}`,
                      }}
                    >
                      <div className="text-xs font-bold" style={{ color: forceDryRun === dry ? color : 'var(--text-dim)' }}>
                        {label}
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{desc}</div>
                    </button>
                  ))}
                </div>
                {!forceDryRun && (
                  <div
                    className="text-xs px-3 py-2 rounded-lg flex items-center gap-1.5"
                    style={{ background: 'rgba(240,185,11,0.08)', color: 'var(--yellow)' }}
                  >
                    <AlertCircle size={11} />
                    需在 .env 配置 SERVER_WALLET_PRIVATE_KEY + SERVER_WALLET_ADDRESS
                  </div>
                )}
              </div>

              {/* Error / Success */}
              {execError && (
                <div className="text-xs flex items-start gap-1.5 px-3 py-3 rounded-lg"
                  style={{ background: 'rgba(246,70,93,0.08)', color: 'var(--red)' }}>
                  <AlertCircle size={12} className="mt-0.5 shrink-0" />
                  {execError}
                </div>
              )}
              {execResult && (
                <div
                  className="rounded-xl p-4 space-y-2"
                  style={{
                    background: execResult.dryRun ? 'rgba(240,185,11,0.05)' : 'rgba(82,196,26,0.05)',
                    border: `1px solid ${execResult.dryRun ? 'rgba(240,185,11,0.2)' : 'rgba(82,196,26,0.2)'}`,
                  }}
                >
                  <div className="flex items-center gap-1.5 text-xs font-semibold"
                    style={{ color: execResult.dryRun ? 'var(--yellow)' : 'var(--green)' }}>
                    <CheckCircle size={12} />
                    {execResult.dryRun ? '模拟成功' : '交易已广播'} · {execResult.elapsed}
                  </div>
                  <div className="space-y-1 text-xs" style={{ color: 'var(--text-dim)' }}>
                    {execResult.txHash && (
                      <div className="flex justify-between">
                        <span>Tx Hash</span>
                        <a
                          href={`${EXPLORER[chainIndex] ?? '#'}${execResult.txHash}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 font-mono"
                          style={{ color: 'var(--blue)' }}
                        >
                          {execResult.txHash.slice(0, 10)}…{execResult.txHash.slice(-6)}
                          <ExternalLink size={10} />
                        </a>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span>预计获得</span>
                      <span style={{ color: 'var(--green)' }}>{execResult.estimatedOut} {execResult.symbol}</span>
                    </div>
                    {execResult.message && (
                      <div className="pt-1 italic" style={{ color: 'var(--text-dim)' }}>{execResult.message}</div>
                    )}
                  </div>
                </div>
              )}

              <button
                onClick={handleExecute}
                disabled={executing || !quote}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold"
                style={{
                  background: quote
                    ? forceDryRun ? 'rgba(240,185,11,0.15)' : 'var(--green)'
                    : 'var(--bg-card2)',
                  color: quote ? (forceDryRun ? 'var(--yellow)' : '#000') : 'var(--text-dim)',
                  opacity: executing || !quote ? 0.6 : 1,
                  cursor: !quote || executing ? 'not-allowed' : 'pointer',
                }}
              >
                {executing ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Zap size={15} />
                )}
                {executing
                  ? '执行中…'
                  : !quote
                  ? '请先获取报价'
                  : forceDryRun
                  ? '模拟执行'
                  : '真实执行（消耗 Gas）'}
              </button>

              <div className="text-xs leading-relaxed space-y-1" style={{ color: 'var(--text-dim)' }}>
                <div>● 模拟模式：调用 OKX 报价 API，不发送交易，结果记录为 simulated</div>
                <div>● 真实模式：OKX 返回 unsigned tx → 服务端钱包签名 → 广播上链</div>
                <div>● 所有执行结果写入 Supabase trades 表</div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Trade History ──────────────────────────────────────────────────── */}
        <div
          className="rounded-xl border overflow-hidden"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
        >
          <div
            className="flex items-center justify-between px-5 py-3.5"
            style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-card2)' }}
          >
            <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text)' }}>
              <Clock size={14} color="var(--text-dim)" />
              交易历史（最近 20 条）
            </div>
            {isDemo && (
              <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(240,185,11,0.1)', color: 'var(--yellow)' }}>
                演示数据
              </span>
            )}
          </div>

          {/* Header */}
          <div
            className="grid text-xs font-semibold px-5 py-2.5"
            style={{
              gridTemplateColumns: '80px 80px 100px 1fr 100px 100px 120px 80px',
              color: 'var(--text-dim)',
              background: 'var(--bg-card2)',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <div>链</div>
            <div>代币</div>
            <div>金额</div>
            <div>地址</div>
            <div className="text-right">获得</div>
            <div className="text-right">价格</div>
            <div className="text-right">时间</div>
            <div className="text-right">状态</div>
          </div>

          {tradesLoading ? (
            <div className="flex items-center justify-center py-12 gap-2" style={{ color: 'var(--text-dim)' }}>
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm">加载中…</span>
            </div>
          ) : trades.length === 0 ? (
            <div className="py-12 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
              暂无交易记录，点击上方执行一笔模拟交易
            </div>
          ) : (
            trades.map((t) => {
              const st = STATUS_STYLE[t.status] ?? { label: t.status, color: 'var(--text-dim)' }
              return (
                <div
                  key={t.id}
                  className="grid px-5 py-3 text-sm"
                  style={{
                    gridTemplateColumns: '80px 80px 100px 1fr 100px 100px 120px 80px',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  <div className="text-xs font-semibold" style={{ color: 'var(--text-dim)' }}>{t.chainName}</div>
                  <div className="text-xs font-bold" style={{ color: 'var(--text)' }}>{t.symbol}</div>
                  <div className="text-xs font-mono" style={{ color: 'var(--yellow)' }}>${fmtNum(t.amount_in)}</div>
                  <div
                    className="text-xs font-mono truncate pr-4"
                    style={{ color: 'var(--text-dim)' }}
                    title={t.token_address}
                  >
                    {t.token_address.slice(0, 8)}…{t.token_address.slice(-6)}
                  </div>
                  <div className="text-right text-xs font-mono" style={{ color: 'var(--green)' }}>
                    {t.amount_out ? fmtNum(t.amount_out, 4) : '—'}
                  </div>
                  <div className="text-right text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
                    {t.exec_price ? `$${fmtNum(t.exec_price, 6)}` : '—'}
                  </div>
                  <div className="text-right text-xs" style={{ color: 'var(--text-dim)' }}>
                    {fmtDate(t.created_at)}
                  </div>
                  <div className="text-right">
                    <span
                      className="text-xs px-2 py-0.5 rounded font-semibold"
                      style={{ background: `${st.color}18`, color: st.color }}
                    >
                      {st.label}
                    </span>
                  </div>
                </div>
              )
            })
          )}
        </div>

      </div>
    </div>
  )
}
