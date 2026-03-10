'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import {
  Brain,
  Plus,
  Play,
  Pause,
  Trash2,
  Code2,
  ChevronRight,
  Loader2,
  AlertCircle,
  Zap,
  RefreshCw,
} from 'lucide-react'
import { Topbar } from '@/components/layout/topbar'

// ── Types ─────────────────────────────────────────────────────────────────────
interface Condition {
  field: string
  op: string
  value: unknown
}
interface ConditionTree {
  conditions: Condition[]
  logic: 'AND' | 'OR'
}
interface ExecConfig {
  amount_usd: number
  slippage: number
  stop_loss_pct: number
  take_profit_pct: number
  max_gas_usd: number
}
interface Strategy {
  id: string
  name: string
  condition_tree: ConditionTree
  exec_config: ExecConfig
  generated_script?: string | null
  status: 'draft' | 'active' | 'paused'
  is_official: boolean
  created_at: string
  updated_at: string
}

// ── Constants ─────────────────────────────────────────────────────────────────
const FIELD_LABELS: Record<string, string> = {
  direction: '方向',
  confidence_score: '信心分',
  chain_id: '链',
  risk_level: '风险',
}
const OP_LABELS: Record<string, string> = { eq: '=', gte: '≥', lte: '≤', in: '∈' }
const CHAIN_NAMES: Record<string, string> = { '56': 'BSC', '1': 'ETH', '900': 'SOL', 'CT_501': 'SOL' }
const DIR_LABELS: Record<string, string> = { long: '做多', watch: '观察', exit: '退出' }
const RISK_LABELS: Record<string, string> = { low: '低', medium: '中', high: '高' }

const STATUS_MAP = {
  active: { label: '运行中', color: 'var(--green)' },
  paused: { label: '已暂停', color: 'var(--yellow)' },
  draft: { label: '草稿', color: 'var(--text-dim)' },
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatConditionValue(field: string, value: unknown): string {
  if (field === 'chain_id' && Array.isArray(value)) {
    return (value as string[]).map((v) => CHAIN_NAMES[v] ?? v).join('/')
  }
  if (field === 'direction') return DIR_LABELS[value as string] ?? String(value)
  if (field === 'risk_level') return RISK_LABELS[value as string] ?? String(value)
  return String(value)
}

function ConditionPill({ c }: { c: Condition }) {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-mono"
      style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
    >
      <span style={{ color: 'var(--blue)' }}>{FIELD_LABELS[c.field] ?? c.field}</span>
      <span>{OP_LABELS[c.op] ?? c.op}</span>
      <span style={{ color: 'var(--yellow)' }}>{formatConditionValue(c.field, c.value)}</span>
    </span>
  )
}

// ── Script Viewer Modal ───────────────────────────────────────────────────────
function ScriptModal({ script, name, onClose }: { script: string; name: string; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(0,0,0,0.7)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl rounded-2xl overflow-hidden"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2">
            <Code2 size={14} color="var(--green)" />
            <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
              AI 生成脚本 · {name}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-xs px-3 py-1 rounded-lg"
            style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
          >
            关闭
          </button>
        </div>
        <pre
          className="overflow-auto text-xs leading-relaxed p-5"
          style={{
            color: 'var(--green)',
            background: 'var(--bg)',
            fontFamily: 'var(--font-mono, monospace)',
            maxHeight: '60vh',
          }}
        >
          {script}
        </pre>
      </div>
    </div>
  )
}

// ── Strategy Card ─────────────────────────────────────────────────────────────
function StrategyCard({
  strategy,
  onStatusChange,
  onDelete,
  onViewScript,
}: {
  strategy: Strategy
  onStatusChange: (id: string, status: string) => void
  onDelete: (id: string) => void
  onViewScript: (s: Strategy) => void
}) {
  const st = STATUS_MAP[strategy.status] ?? STATUS_MAP.draft
  const conditions = strategy.condition_tree?.conditions ?? []
  const cfg = strategy.exec_config

  return (
    <div
      className="rounded-xl border overflow-hidden transition-all hover:border-opacity-60"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
    >
      {/* Header */}
      <div
        className="flex items-start justify-between px-5 py-4"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold truncate" style={{ color: 'var(--text)' }}>
              {strategy.name}
            </span>
            {strategy.is_official && (
              <span
                className="text-xs px-1.5 py-0.5 rounded font-semibold"
                style={{ background: 'rgba(240,185,11,0.12)', color: 'var(--yellow)' }}
              >
                官方
              </span>
            )}
            <span
              className="w-1.5 h-1.5 rounded-full shrink-0"
              style={{ background: st.color }}
            />
            <span className="text-xs" style={{ color: st.color }}>
              {st.label}
            </span>
          </div>
          {/* Condition pills */}
          <div className="flex flex-wrap gap-1.5 mt-2">
            {conditions.slice(0, 3).map((c, i) => (
              <ConditionPill key={i} c={c} />
            ))}
            {conditions.length > 3 && (
              <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                +{conditions.length - 3} 条件
              </span>
            )}
            {conditions.length > 1 && (
              <span
                className="text-xs px-1.5 py-0.5 rounded font-mono"
                style={{ background: 'rgba(114,137,218,0.15)', color: '#7289da' }}
              >
                {strategy.condition_tree.logic}
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1.5 ml-3 shrink-0">
          {strategy.generated_script && (
            <button
              onClick={() => onViewScript(strategy)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium"
              style={{ background: 'rgba(82,196,26,0.1)', color: 'var(--green)' }}
              title="查看 AI 脚本"
            >
              <Code2 size={12} />
              脚本
            </button>
          )}
          {strategy.status === 'active' ? (
            <button
              onClick={() => onStatusChange(strategy.id, 'paused')}
              className="p-2 rounded-lg"
              style={{ background: 'rgba(240,185,11,0.1)', color: 'var(--yellow)' }}
              title="暂停策略"
            >
              <Pause size={13} />
            </button>
          ) : (
            <button
              onClick={() => onStatusChange(strategy.id, 'active')}
              className="p-2 rounded-lg"
              style={{ background: 'rgba(82,196,26,0.1)', color: 'var(--green)' }}
              title="启用策略"
            >
              <Play size={13} />
            </button>
          )}
          <button
            onClick={() => onDelete(strategy.id)}
            className="p-2 rounded-lg"
            style={{ background: 'rgba(246,70,93,0.1)', color: 'var(--red)' }}
            title="删除"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* Exec Config strip */}
      <div
        className="flex items-center gap-4 px-5 py-2.5 text-xs"
        style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
      >
        <span>💵 <strong style={{ color: 'var(--text)' }}>${cfg?.amount_usd ?? '—'}</strong></span>
        <span>📉 SL <strong style={{ color: 'var(--red)' }}>{cfg?.stop_loss_pct ?? '—'}%</strong></span>
        <span>📈 TP <strong style={{ color: 'var(--green)' }}>{cfg?.take_profit_pct ?? '—'}%</strong></span>
        <span>⚡ 滑点 <strong style={{ color: 'var(--text)' }}>{cfg?.slippage ?? '—'}%</strong></span>
        <span className="ml-auto">
          {new Date(strategy.created_at).toLocaleDateString('zh-CN')}
        </span>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function StrategyPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isDemo, setIsDemo] = useState(false)
  const [filter, setFilter] = useState<'all' | 'active' | 'draft' | 'paused'>('all')
  const [scriptModal, setScriptModal] = useState<Strategy | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/strategies')
      const data = await res.json()
      setStrategies(data.strategies ?? [])
      setIsDemo(data.isDemo ?? false)
    } catch {
      setError('加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleStatusChange = async (id: string, status: string) => {
    // Optimistic UI
    setStrategies((prev) => prev.map((s) => s.id === id ? { ...s, status: status as Strategy['status'] } : s))
    try {
      await fetch(`/api/strategies/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
    } catch {
      load() // revert on error
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除该策略？')) return
    setStrategies((prev) => prev.filter((s) => s.id !== id))
    try {
      await fetch(`/api/strategies/${id}`, { method: 'DELETE' })
    } catch {
      load()
    }
  }

  const filtered = filter === 'all' ? strategies : strategies.filter((s) => s.status === filter)

  const counts = {
    all: strategies.length,
    active: strategies.filter((s) => s.status === 'active').length,
    paused: strategies.filter((s) => s.status === 'paused').length,
    draft: strategies.filter((s) => s.status === 'draft').length,
  }

  const TABS = [
    { key: 'all', label: '全部', count: counts.all },
    { key: 'active', label: '运行中', count: counts.active },
    { key: 'paused', label: '已暂停', count: counts.paused },
    { key: 'draft', label: '草稿', count: counts.draft },
  ] as const

  return (
    <div>
      {scriptModal && (
        <ScriptModal
          script={scriptModal.generated_script ?? ''}
          name={scriptModal.name}
          onClose={() => setScriptModal(null)}
        />
      )}

      <Topbar
        title="策略中心"
        subtitle="AI 生成策略 · 条件触发 · OKX 执行"
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={load}
              disabled={loading}
              className="p-2 rounded-lg"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-dim)' }}
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
            <Link
              href="/strategy/create"
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
              style={{ background: 'var(--yellow)', color: '#000' }}
            >
              <Plus size={14} />
              创建策略
            </Link>
          </div>
        }
      />

      <div className="p-6 space-y-5">

        {/* Demo banner */}
        {isDemo && (
          <div
            className="rounded-xl border px-5 py-3 flex items-center gap-3 text-sm"
            style={{ background: 'rgba(240,185,11,0.08)', borderColor: 'rgba(240,185,11,0.3)' }}
          >
            <AlertCircle size={14} color="var(--yellow)" />
            <span style={{ color: 'var(--yellow)' }}>
              演示模式 — 未配置 Supabase，数据不持久化。配置环境变量后刷新即可连接真实数据库。
            </span>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: '全部策略', value: counts.all, color: 'var(--text)' },
            { label: '运行中', value: counts.active, color: 'var(--green)' },
            { label: '已暂停', value: counts.paused, color: 'var(--yellow)' },
            { label: '草稿', value: counts.draft, color: 'var(--text-dim)' },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              className="rounded-xl p-4 border"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
            >
              <div className="text-xs mb-1" style={{ color: 'var(--text-dim)' }}>{label}</div>
              <div className="text-2xl font-black" style={{ color }}>{loading ? '—' : value}</div>
            </div>
          ))}
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-1">
          {TABS.map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all"
              style={{
                background: filter === key ? 'rgba(240,185,11,0.12)' : 'transparent',
                color: filter === key ? 'var(--yellow)' : 'var(--text-dim)',
              }}
            >
              {label}
              <span
                className="px-1.5 py-0.5 rounded text-xs font-mono"
                style={{
                  background: filter === key ? 'rgba(240,185,11,0.2)' : 'var(--bg-card2)',
                }}
              >
                {count}
              </span>
            </button>
          ))}
        </div>

        {/* List */}
        {loading ? (
          <div className="flex items-center justify-center py-16 gap-2" style={{ color: 'var(--text-dim)' }}>
            <Loader2 size={18} className="animate-spin" />
            <span className="text-sm">加载中…</span>
          </div>
        ) : error ? (
          <div
            className="rounded-xl border px-5 py-4 flex items-center gap-3"
            style={{ background: 'rgba(246,70,93,0.08)', borderColor: 'rgba(246,70,93,0.3)' }}
          >
            <AlertCircle size={15} color="var(--red)" />
            <span className="text-sm" style={{ color: 'var(--red)' }}>{error}</span>
          </div>
        ) : filtered.length === 0 ? (
          /* Empty state */
          <div
            className="rounded-2xl border flex flex-col items-center justify-center py-20 gap-4"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
          >
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center"
              style={{ background: 'rgba(240,185,11,0.1)' }}
            >
              <Brain size={28} color="var(--yellow)" />
            </div>
            <div className="text-center">
              <div className="text-sm font-semibold mb-1" style={{ color: 'var(--text)' }}>
                {filter === 'all' ? '还没有策略' : `没有${filter === 'active' ? '运行中' : filter === 'paused' ? '已暂停' : '草稿'}策略`}
              </div>
              <div className="text-xs mb-4" style={{ color: 'var(--text-dim)' }}>
                创建第一个 AI 策略，让机器人帮你自动交易
              </div>
            </div>
            <Link
              href="/strategy/create"
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold"
              style={{ background: 'var(--yellow)', color: '#000' }}
            >
              <Zap size={14} />
              立即创建策略
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((s) => (
              <StrategyCard
                key={s.id}
                strategy={s}
                onStatusChange={handleStatusChange}
                onDelete={handleDelete}
                onViewScript={setScriptModal}
              />
            ))}
          </div>
        )}

        {/* Quick guide */}
        <div
          className="rounded-xl border p-5"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
        >
          <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text)' }}>
            如何使用策略中心
          </div>
          <div className="grid grid-cols-3 gap-4">
            {[
              {
                step: '01',
                title: '设定触发条件',
                desc: '选择信号方向、信心分阈值、目标链、风险等级等条件',
                color: 'var(--blue)',
              },
              {
                step: '02',
                title: 'AI 生成交易脚本',
                desc: 'Claude 根据你的条件自动生成可执行的 TypeScript 策略代码',
                color: 'var(--yellow)',
              },
              {
                step: '03',
                title: '启用自动执行',
                desc: '策略引擎实时监控信号，命中条件时通过 OKX DEX 自动执行',
                color: 'var(--green)',
              },
            ].map(({ step, title, desc, color }) => (
              <div key={step} className="flex items-start gap-3">
                <div
                  className="text-xs font-black shrink-0 mt-0.5 w-6 h-6 rounded flex items-center justify-center"
                  style={{ background: `${color}22`, color }}
                >
                  {step}
                </div>
                <div>
                  <div className="text-xs font-semibold mb-0.5" style={{ color: 'var(--text)' }}>
                    {title}
                  </div>
                  <div className="text-xs leading-relaxed" style={{ color: 'var(--text-dim)' }}>
                    {desc}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <Link
            href="/strategy/create"
            className="flex items-center justify-center gap-2 mt-4 py-2.5 rounded-xl text-sm font-semibold w-full"
            style={{ background: 'rgba(240,185,11,0.1)', color: 'var(--yellow)', border: '1px solid rgba(240,185,11,0.2)' }}
          >
            <Plus size={14} />
            创建新策略
            <ChevronRight size={14} />
          </Link>
        </div>

      </div>
    </div>
  )
}
