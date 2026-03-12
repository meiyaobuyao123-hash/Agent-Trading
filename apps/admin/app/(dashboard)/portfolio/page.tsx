'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Plus,
  Trash2,
  LogOut,
  RefreshCw,
  Loader2,
  Star,
  AlertCircle,
} from 'lucide-react'
import { AdminTopbar } from '../../components/topbar'

// =====================================================
// Types
// =====================================================
interface PortfolioToken {
  id: string
  token_address: string
  chain_id: number
  symbol: string
  name?: string
  entry_price: number
  entry_at: string
  reason_tags: string[]
  risk_level: 'low' | 'medium' | 'high'
  status: 'active' | 'exited'
  exit_price?: number
  exit_at?: string
}

interface AddFormData {
  token_address: string
  chain_id: string
  symbol: string
  name: string
  entry_price: string
  reason_tags: string
  risk_level: 'low' | 'medium' | 'high'
}

// =====================================================
// Utils
// =====================================================
const CHAIN_LABELS: Record<number, string> = { 1: 'ETH', 56: 'BSC', 900: 'SOL', 8453: 'BASE' }
const RISK_COLORS: Record<string, string> = {
  low: 'var(--green)',
  medium: 'var(--yellow)',
  high: 'var(--red)',
}
const RISK_LABELS: Record<string, string> = { low: '低', medium: '中', high: '高' }

function fmtPrice(n: number | undefined): string {
  if (!n || isNaN(n)) return '—'
  if (n >= 1000) return `$${n.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
  if (n >= 1) return `$${n.toFixed(4)}`
  if (n >= 0.001) return `$${n.toFixed(6)}`
  return `$${n.toExponential(3)}`
}

function fmtDate(dateStr?: string): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function calcPnl(entry: number, current: number): string {
  const pct = ((current - entry) / entry) * 100
  return `${pct > 0 ? '+' : ''}${pct.toFixed(2)}%`
}

// =====================================================
// Add Token Modal
// =====================================================
function AddTokenModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void
  onSuccess: () => void
}) {
  const [form, setForm] = useState<AddFormData>({
    token_address: '',
    chain_id: '56',
    symbol: '',
    name: '',
    entry_price: '',
    reason_tags: '',
    risk_level: 'medium',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/admin/portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token_address: form.token_address.trim(),
          chain_id: Number(form.chain_id),
          symbol: form.symbol.trim().toUpperCase(),
          name: form.name.trim() || null,
          entry_price: Number(form.entry_price),
          reason_tags: form.reason_tags.split(',').map((t) => t.trim()).filter(Boolean),
          risk_level: form.risk_level,
        }),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.error || 'Failed')
      onSuccess()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add token')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div
        className="w-full max-w-lg rounded-2xl p-6"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
      >
        <h2 className="text-base font-bold mb-5" style={{ color: 'var(--text)' }}>
          ➕ 添加代币到官方组合
        </h2>

        {error && (
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg mb-4 text-xs"
            style={{ background: 'rgba(246,70,93,0.1)', color: 'var(--red)' }}
          >
            <AlertCircle size={12} />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs mb-1" style={{ color: 'var(--text-dim)' }}>
                代币合约地址 *
              </label>
              <input
                required
                className="w-full px-3 py-2 rounded-lg text-sm font-mono"
                style={{
                  background: 'var(--bg-card2)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  outline: 'none',
                }}
                placeholder="0x..."
                value={form.token_address}
                onChange={(e) => setForm({ ...form, token_address: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--text-dim)' }}>
                链 *
              </label>
              <select
                className="w-full px-3 py-2 rounded-lg text-sm"
                style={{
                  background: 'var(--bg-card2)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  outline: 'none',
                }}
                value={form.chain_id}
                onChange={(e) => setForm({ ...form, chain_id: e.target.value })}
              >
                <option value="56">BSC (56)</option>
                <option value="1">ETH (1)</option>
                <option value="900">SOL (900)</option>
                <option value="8453">BASE (8453)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--text-dim)' }}>
                代码 (Symbol) *
              </label>
              <input
                required
                className="w-full px-3 py-2 rounded-lg text-sm uppercase"
                style={{
                  background: 'var(--bg-card2)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  outline: 'none',
                }}
                placeholder="CAKE"
                value={form.symbol}
                onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--text-dim)' }}>
                代币名称
              </label>
              <input
                className="w-full px-3 py-2 rounded-lg text-sm"
                style={{
                  background: 'var(--bg-card2)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  outline: 'none',
                }}
                placeholder="PancakeSwap"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--text-dim)' }}>
                入选价 (USD) *
              </label>
              <input
                required
                type="number"
                step="any"
                className="w-full px-3 py-2 rounded-lg text-sm font-mono"
                style={{
                  background: 'var(--bg-card2)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  outline: 'none',
                }}
                placeholder="0.00"
                value={form.entry_price}
                onChange={(e) => setForm({ ...form, entry_price: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--text-dim)' }}>
                风险等级
              </label>
              <select
                className="w-full px-3 py-2 rounded-lg text-sm"
                style={{
                  background: 'var(--bg-card2)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  outline: 'none',
                }}
                value={form.risk_level}
                onChange={(e) => setForm({ ...form, risk_level: e.target.value as 'low' | 'medium' | 'high' })}
              >
                <option value="low">低风险</option>
                <option value="medium">中风险</option>
                <option value="high">高风险</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs mb-1" style={{ color: 'var(--text-dim)' }}>
                标签（逗号分隔）
              </label>
              <input
                className="w-full px-3 py-2 rounded-lg text-sm"
                style={{
                  background: 'var(--bg-card2)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  outline: 'none',
                }}
                placeholder="聪明钱驱动, 交易量异动, Meme Rush"
                value={form.reason_tags}
                onChange={(e) => setForm({ ...form, reason_tags: e.target.value })}
              />
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded-lg text-sm font-medium"
              style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 rounded-lg text-sm font-bold flex items-center justify-center gap-2"
              style={{ background: 'var(--yellow)', color: '#000' }}
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : null}
              {loading ? '添加中…' : '确认添加'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// =====================================================
// Exit Modal
// =====================================================
function ExitModal({
  token,
  onClose,
  onSuccess,
}: {
  token: PortfolioToken
  onClose: () => void
  onSuccess: () => void
}) {
  const [exitPrice, setExitPrice] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pnlPct = exitPrice && token.entry_price
    ? ((Number(exitPrice) - token.entry_price) / token.entry_price * 100)
    : null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/admin/portfolio/${token.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exit_price: Number(exitPrice) }),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.error || 'Failed')
      onSuccess()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div
        className="w-full max-w-sm rounded-2xl p-6"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
      >
        <h2 className="text-base font-bold mb-1" style={{ color: 'var(--text)' }}>
          退出持仓 — {token.symbol}
        </h2>
        <p className="text-xs mb-5" style={{ color: 'var(--text-dim)' }}>
          入选价: {fmtPrice(token.entry_price)} · 入选时间: {fmtDate(token.entry_at)}
        </p>

        {error && (
          <div className="text-xs px-3 py-2 rounded-lg mb-4" style={{ background: 'rgba(246,70,93,0.1)', color: 'var(--red)' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--text-dim)' }}>
              退出价格 (USD) *
            </label>
            <input
              required
              type="number"
              step="any"
              className="w-full px-3 py-2 rounded-lg text-sm font-mono"
              style={{
                background: 'var(--bg-card2)',
                border: '1px solid var(--border)',
                color: 'var(--text)',
                outline: 'none',
              }}
              placeholder="0.00"
              value={exitPrice}
              onChange={(e) => setExitPrice(e.target.value)}
            />
          </div>

          {pnlPct !== null && (
            <div
              className="text-center py-2.5 rounded-lg text-sm font-bold"
              style={{
                background: pnlPct >= 0 ? 'rgba(14,203,129,0.1)' : 'rgba(246,70,93,0.1)',
                color: pnlPct >= 0 ? 'var(--green)' : 'var(--red)',
              }}
            >
              P&L: {pnlPct > 0 ? '+' : ''}{pnlPct.toFixed(2)}%
              {' '}({calcPnl(token.entry_price, Number(exitPrice))})
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded-lg text-sm font-medium"
              style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 rounded-lg text-sm font-bold flex items-center justify-center gap-2"
              style={{
                background: pnlPct !== null && pnlPct >= 0 ? 'var(--green)' : 'var(--red)',
                color: '#fff',
              }}
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : null}
              {loading ? '处理中…' : '确认退出'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// =====================================================
// Main Page
// =====================================================
export default function AdminPortfolioPage() {
  const [tokens, setTokens] = useState<PortfolioToken[]>([])
  const [loading, setLoading] = useState(true)
  const [isSupabase, setIsSupabase] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [exitTarget, setExitTarget] = useState<PortfolioToken | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const fetchTokens = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/admin/portfolio')
      const json = await res.json()
      if (json.error && json.tokens?.length === 0) setIsSupabase(false)
      setTokens(json.tokens ?? [])
    } catch {
      setTokens([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTokens() }, [fetchTokens])

  const handleDelete = async (id: string) => {
    setDeleteId(id)
    try {
      await fetch(`/api/admin/portfolio/${id}`, { method: 'DELETE' })
      fetchTokens()
    } finally {
      setDeleteId(null)
    }
  }

  const active = tokens.filter((t) => t.status === 'active')
  const exited = tokens.filter((t) => t.status === 'exited')

  return (
    <div>
      <AdminTopbar
        title="官方组合管理"
        subtitle={`${tokens.length} 个代币 · ${active.length} 持仓中 · ${exited.length} 已退出`}
        action={
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90"
            style={{ background: 'var(--yellow)', color: '#000' }}
          >
            <Plus size={14} />
            添加代币
          </button>
        }
      />

      <div className="p-6 space-y-5">

        {!isSupabase && (
          <div
            className="flex items-center gap-3 px-4 py-3 rounded-xl border text-sm"
            style={{ background: 'rgba(240,185,11,0.08)', borderColor: 'rgba(240,185,11,0.25)', color: 'var(--yellow)' }}
          >
            <Star size={14} />
            Supabase 未配置 — 需设置 NEXT_PUBLIC_SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY 才能管理真实数据
          </div>
        )}

        {/* Token Table */}
        <div
          className="rounded-xl border overflow-hidden"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
        >
          {/* Header */}
          <div
            className="grid px-5 py-3 gap-3 text-xs font-semibold"
            style={{
              gridTemplateColumns: '2.5fr 0.8fr 1fr 1fr 1fr 1fr 1.2fr',
              color: 'var(--text-dim)',
              borderBottom: '1px solid var(--border)',
              background: 'var(--bg-card2)',
            }}
          >
            <div>代币</div>
            <div>链</div>
            <div className="text-right">入选价</div>
            <div className="text-right">退出价</div>
            <div className="text-right">P&amp;L</div>
            <div>入选时间</div>
            <div className="text-right">操作</div>
          </div>

          {/* Loading */}
          {loading && (
            <div className="py-14 flex items-center justify-center gap-3" style={{ color: 'var(--text-dim)' }}>
              <Loader2 size={18} className="animate-spin" />
              <span className="text-sm">加载数据…</span>
            </div>
          )}

          {/* Empty */}
          {!loading && tokens.length === 0 && (
            <div className="py-14 text-center">
              <div className="text-3xl mb-3">📭</div>
              <div className="text-sm mb-4" style={{ color: 'var(--text-dim)' }}>
                官方组合为空
              </div>
              <button
                onClick={() => setShowAdd(true)}
                className="px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ background: 'var(--yellow)', color: '#000' }}
              >
                添加第一个代币
              </button>
            </div>
          )}

          {/* Rows */}
          {!loading &&
            tokens.map((token, i) => {
              const pnl =
                token.status === 'exited' && token.exit_price && token.entry_price
                  ? ((token.exit_price - token.entry_price) / token.entry_price) * 100
                  : null
              return (
                <div
                  key={token.id}
                  className="grid items-center px-5 py-3.5 gap-3 text-sm hover:bg-white/[0.02] transition-colors"
                  style={{
                    gridTemplateColumns: '2.5fr 0.8fr 1fr 1fr 1fr 1fr 1.2fr',
                    borderBottom: i < tokens.length - 1 ? '1px solid var(--border)' : 'none',
                  }}
                >
                  {/* Token info */}
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                        style={{ background: 'var(--bg-card2)', color: 'var(--yellow)' }}
                      >
                        {token.symbol?.[0] ?? '?'}
                      </span>
                      <div>
                        <div className="font-semibold" style={{ color: 'var(--text)' }}>{token.symbol}</div>
                        <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
                          {token.token_address.slice(0, 8)}…
                        </div>
                      </div>
                    </div>
                    {token.reason_tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5 ml-9">
                        {token.reason_tags.slice(0, 2).map((t) => (
                          <span
                            key={t}
                            className="text-xs px-1.5 py-0.5 rounded"
                            style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
                          >
                            {t}
                          </span>
                        ))}
                        <span
                          className="text-xs px-1.5 py-0.5 rounded"
                          style={{
                            color: RISK_COLORS[token.risk_level],
                            background: `${RISK_COLORS[token.risk_level]}18`,
                          }}
                        >
                          {RISK_LABELS[token.risk_level]}险
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Chain */}
                  <div>
                    <span
                      className="text-xs font-bold px-1.5 py-0.5 rounded"
                      style={{ color: 'var(--yellow)', background: 'rgba(240,185,11,0.12)' }}
                    >
                      {CHAIN_LABELS[token.chain_id] ?? token.chain_id}
                    </span>
                  </div>

                  {/* Entry Price */}
                  <div className="font-mono text-right" style={{ color: 'var(--text-dim)' }}>
                    {fmtPrice(token.entry_price)}
                  </div>

                  {/* Exit Price */}
                  <div className="font-mono text-right" style={{ color: 'var(--text-dim)' }}>
                    {token.status === 'exited' ? fmtPrice(token.exit_price) : '—'}
                  </div>

                  {/* P&L */}
                  <div
                    className="font-mono font-semibold text-right text-sm"
                    style={{
                      color:
                        pnl === null
                          ? 'var(--text-dim)'
                          : pnl > 0
                          ? 'var(--green)'
                          : pnl < 0
                          ? 'var(--red)'
                          : 'var(--text-dim)',
                    }}
                  >
                    {pnl !== null ? `${pnl > 0 ? '+' : ''}${pnl.toFixed(2)}%` : '—'}
                  </div>

                  {/* Entry Time */}
                  <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
                    {fmtDate(token.entry_at)}
                    {token.status === 'active' && (
                      <span
                        className="block mt-0.5 text-xs font-semibold"
                        style={{ color: 'var(--green)' }}
                      >
                        持仓中
                      </span>
                    )}
                    {token.status === 'exited' && (
                      <span
                        className="block mt-0.5 text-xs"
                        style={{ color: 'var(--text-dim)' }}
                      >
                        退出 {fmtDate(token.exit_at)}
                      </span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 justify-end">
                    {token.status === 'active' && (
                      <button
                        onClick={() => setExitTarget(token)}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-80"
                        style={{ background: 'rgba(240,185,11,0.1)', color: 'var(--yellow)' }}
                        title="退出仓位"
                      >
                        <LogOut size={11} />
                        退出
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(token.id)}
                      disabled={deleteId === token.id}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-80"
                      style={{ background: 'rgba(246,70,93,0.1)', color: 'var(--red)' }}
                      title="删除记录"
                    >
                      {deleteId === token.id ? (
                        <Loader2 size={11} className="animate-spin" />
                      ) : (
                        <Trash2 size={11} />
                      )}
                    </button>
                  </div>
                </div>
              )
            })}
        </div>

        {/* Refresh footer */}
        {!loading && (
          <div className="flex justify-end">
            <button
              onClick={fetchTokens}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs"
              style={{ color: 'var(--text-dim)', background: 'var(--bg-card)' }}
            >
              <RefreshCw size={11} />
              刷新数据
            </button>
          </div>
        )}
      </div>

      {/* Modals */}
      {showAdd && (
        <AddTokenModal onClose={() => setShowAdd(false)} onSuccess={fetchTokens} />
      )}
      {exitTarget && (
        <ExitModal
          token={exitTarget}
          onClose={() => setExitTarget(null)}
          onSuccess={fetchTokens}
        />
      )}
    </div>
  )
}
