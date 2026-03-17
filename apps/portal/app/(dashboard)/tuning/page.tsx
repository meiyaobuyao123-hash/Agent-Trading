'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Loader2, CheckCircle, XCircle, Clock, Bot, ChevronDown, ChevronRight, Play, AlertTriangle } from 'lucide-react'
import { Topbar } from '../../components/topbar'
import {
  fetchOptimizationRuns,
  fetchProposals,
  fetchMetricsHistory,
  approveProposal,
  rejectProposal,
  triggerOptimization,
  type OptimizationRun,
  type OptimizationProposal,
  type MetricsHistory,
} from '../../lib/optimization-queries'

// ═══════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════

function fmtPct(n: number | null | undefined): string {
  if (n == null) return '—'
  return `${(n * 100).toFixed(1)}%`
}

function fmtDate(s: string | null): string {
  if (!s) return '—'
  return new Date(s).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function statusBadge(status: string) {
  const map: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
    running:    { bg: 'rgba(59,130,246,0.15)', text: 'var(--blue)',   icon: <Loader2 size={12} className="animate-spin" /> },
    completed:  { bg: 'rgba(34,197,94,0.15)',  text: 'var(--green)',  icon: <CheckCircle size={12} /> },
    failed:     { bg: 'rgba(239,68,68,0.15)',  text: 'var(--red)',    icon: <XCircle size={12} /> },
    pending:    { bg: 'rgba(234,179,8,0.15)',   text: '#eab308',      icon: <Clock size={12} /> },
    approved:   { bg: 'rgba(34,197,94,0.15)',  text: 'var(--green)',  icon: <CheckCircle size={12} /> },
    applied:    { bg: 'rgba(34,197,94,0.15)',  text: 'var(--green)',  icon: <CheckCircle size={12} /> },
    rejected:   { bg: 'rgba(239,68,68,0.15)',  text: 'var(--red)',    icon: <XCircle size={12} /> },
    rolled_back:{ bg: 'rgba(234,179,8,0.15)',   text: '#eab308',      icon: <AlertTriangle size={12} /> },
  }
  const s = map[status] || map.pending
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ background: s.bg, color: s.text }}>
      {s.icon} {status}
    </span>
  )
}

// ═══════════════════════════════════════════════════
// Main Page
// ═══════════════════════════════════════════════════

export default function TuningPage() {
  const [runs, setRuns] = useState<OptimizationRun[]>([])
  const [proposals, setProposals] = useState<OptimizationProposal[]>([])
  const [metrics, setMetrics] = useState<MetricsHistory[]>([])
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [expandedRun, setExpandedRun] = useState<number | null>(null)
  const [expandedProposal, setExpandedProposal] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [r, p, m] = await Promise.all([
        fetchOptimizationRuns(),
        fetchProposals(),
        fetchMetricsHistory(14),
      ])
      setRuns(r)
      setProposals(p)
      setMetrics(m)
    } catch (e) {
      console.error('Load failed:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleTrigger = async () => {
    if (!confirm('确定手动触发一次 AI 优化？')) return
    setTriggering(true)
    try {
      await triggerOptimization()
      alert('优化已在后台启动，请稍后刷新查看')
    } catch (e) {
      alert(`触发失败: ${e}`)
    } finally {
      setTriggering(false)
    }
  }

  const handleApprove = async (id: number) => {
    const comment = prompt('审批意见（可选）：')
    try {
      await approveProposal(id, comment || undefined)
      alert('方案已批准并应用！需要重启后端服务才能完全生效。')
      load()
    } catch (e) {
      alert(`审批失败: ${e}`)
    }
  }

  const handleReject = async (id: number) => {
    const comment = prompt('拒绝原因：')
    if (!comment) return
    try {
      await rejectProposal(id, comment)
      load()
    } catch (e) {
      alert(`拒绝失败: ${e}`)
    }
  }

  const pendingCount = proposals.filter(p => p.status === 'pending').length

  return (
    <>
      <Topbar title="AI 优化 Agent" subtitle="自动分析监控数据 · 优化推荐算法 · 每3天运行" />

      <div className="p-6 space-y-6">
        {/* Top bar: trigger + summary */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              style={{ background: 'var(--blue)', color: '#fff', opacity: triggering ? 0.6 : 1 }}
            >
              {triggering ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
              手动触发优化
            </button>
            <button onClick={load} className="p-2 rounded-lg transition-colors" style={{ color: 'var(--text-dim)' }}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
            {pendingCount > 0 && (
              <span className="px-3 py-1 rounded-full text-xs font-bold" style={{ background: 'rgba(234,179,8,0.2)', color: '#eab308' }}>
                {pendingCount} 个方案待审批
              </span>
            )}
          </div>
          <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
            模型: Claude Opus 4.6 · 目标: 命中率≥20% 召回率≥15%
          </div>
        </div>

        {/* Pending Proposals (prominent) */}
        {proposals.filter(p => p.status === 'pending').length > 0 && (
          <section>
            <h2 className="text-sm font-bold mb-3" style={{ color: '#eab308' }}>
              ⏳ 待审批方案
            </h2>
            {proposals.filter(p => p.status === 'pending').map(p => (
              <ProposalCard
                key={p.id}
                proposal={p}
                expanded={expandedProposal === p.id}
                onToggle={() => setExpandedProposal(expandedProposal === p.id ? null : p.id)}
                onApprove={() => handleApprove(p.id)}
                onReject={() => handleReject(p.id)}
              />
            ))}
          </section>
        )}

        {/* Metrics Trend */}
        {metrics.length > 0 && (
          <section>
            <h2 className="text-sm font-bold mb-3" style={{ color: 'var(--text)' }}>指标趋势</h2>
            <div className="rounded-xl overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th className="px-3 py-2 text-left" style={{ color: 'var(--text-dim)' }}>日期</th>
                    <th className="px-3 py-2 text-right" style={{ color: 'var(--text-dim)' }}>推荐数</th>
                    <th className="px-3 py-2 text-right" style={{ color: 'var(--text-dim)' }}>毕业数</th>
                    <th className="px-3 py-2 text-right" style={{ color: 'var(--text-dim)' }}>命中</th>
                    <th className="px-3 py-2 text-right" style={{ color: 'var(--text-dim)' }}>命中率</th>
                    <th className="px-3 py-2 text-right" style={{ color: 'var(--text-dim)' }}>召回率</th>
                    <th className="px-3 py-2 text-right" style={{ color: 'var(--text-dim)' }}>F1</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.map(m => (
                    <tr key={m.snapshot_date} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td className="px-3 py-2" style={{ color: 'var(--text)' }}>{m.snapshot_date}</td>
                      <td className="px-3 py-2 text-right" style={{ color: 'var(--text)' }}>{m.pump_picks_count}</td>
                      <td className="px-3 py-2 text-right" style={{ color: 'var(--text)' }}>{m.pump_graduated}</td>
                      <td className="px-3 py-2 text-right" style={{ color: 'var(--text)' }}>{m.pump_hit_count}</td>
                      <td className="px-3 py-2 text-right font-mono" style={{ color: m.pump_hit_rate >= 0.2 ? 'var(--green)' : 'var(--red)' }}>
                        {fmtPct(m.pump_hit_rate)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono" style={{ color: m.pump_recall >= 0.15 ? 'var(--green)' : 'var(--red)' }}>
                        {fmtPct(m.pump_recall)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--text)' }}>
                        {m.pump_f1.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Optimization Runs */}
        <section>
          <h2 className="text-sm font-bold mb-3" style={{ color: 'var(--text)' }}>
            <Bot size={14} className="inline mr-1" />
            优化运行记录
          </h2>
          {runs.length === 0 && !loading && (
            <div className="text-center py-12 text-sm" style={{ color: 'var(--text-dim)' }}>
              暂无优化记录 · 每3天自动运行或手动触发
            </div>
          )}
          {runs.map(run => (
            <RunCard
              key={run.id}
              run={run}
              proposals={proposals.filter(p => p.run_id === run.id)}
              expanded={expandedRun === run.id}
              onToggle={() => setExpandedRun(expandedRun === run.id ? null : run.id)}
              expandedProposal={expandedProposal}
              onToggleProposal={(id) => setExpandedProposal(expandedProposal === id ? null : id)}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
        </section>

        {/* All Proposals History */}
        {proposals.filter(p => p.status !== 'pending').length > 0 && (
          <section>
            <h2 className="text-sm font-bold mb-3" style={{ color: 'var(--text)' }}>历史方案</h2>
            {proposals.filter(p => p.status !== 'pending').map(p => (
              <ProposalCard
                key={p.id}
                proposal={p}
                expanded={expandedProposal === p.id}
                onToggle={() => setExpandedProposal(expandedProposal === p.id ? null : p.id)}
              />
            ))}
          </section>
        )}
      </div>
    </>
  )
}

// ═══════════════════════════════════════════════════
// Components
// ═══════════════════════════════════════════════════

function RunCard({
  run, proposals, expanded, onToggle, expandedProposal, onToggleProposal, onApprove, onReject,
}: {
  run: OptimizationRun
  proposals: OptimizationProposal[]
  expanded: boolean
  onToggle: () => void
  expandedProposal: number | null
  onToggleProposal: (id: number) => void
  onApprove: (id: number) => void
  onReject: (id: number) => void
}) {
  return (
    <div className="mb-3 rounded-xl overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      {/* Header */}
      <button onClick={onToggle} className="w-full flex items-center justify-between px-4 py-3 text-left">
        <div className="flex items-center gap-3">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
            Run #{run.id}
          </span>
          {statusBadge(run.status)}
          <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
            {fmtDate(run.started_at)}
          </span>
          {proposals.length > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(30,128,255,0.1)', color: 'var(--blue)' }}>
              {proposals.length} 个方案
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-dim)' }}>
          <span>{run.tokens_used?.toLocaleString()} tokens</span>
          <span>${run.cost_usd?.toFixed(3)}</span>
        </div>
      </button>

      {/* Expanded: conversation + proposals */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3" style={{ borderTop: '1px solid var(--border)' }}>
          {/* Analysis summary */}
          {run.analysis && (
            <div className="mt-3 p-3 rounded-lg text-xs whitespace-pre-wrap" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
              <div className="font-bold mb-1" style={{ color: 'var(--blue)' }}>Agent 分析结论</div>
              {run.analysis}
            </div>
          )}

          {/* Conversation log */}
          {run.conversation && run.conversation.length > 0 && (
            <div className="space-y-1">
              <div className="text-xs font-bold" style={{ color: 'var(--text-dim)' }}>完整对话记录</div>
              <div className="max-h-96 overflow-y-auto space-y-1 p-2 rounded-lg" style={{ background: 'var(--bg)' }}>
                {run.conversation.map((entry, i) => (
                  <ConversationBubble key={i} entry={entry} />
                ))}
              </div>
            </div>
          )}

          {/* Proposals under this run */}
          {proposals.map(p => (
            <ProposalCard
              key={p.id}
              proposal={p}
              expanded={expandedProposal === p.id}
              onToggle={() => onToggleProposal(p.id)}
              onApprove={p.status === 'pending' ? () => onApprove(p.id) : undefined}
              onReject={p.status === 'pending' ? () => onReject(p.id) : undefined}
            />
          ))}
        </div>
      )}
    </div>
  )
}


function ProposalCard({
  proposal: p, expanded, onToggle, onApprove, onReject,
}: {
  proposal: OptimizationProposal
  expanded: boolean
  onToggle: () => void
  onApprove?: () => void
  onReject?: () => void
}) {
  return (
    <div className="rounded-lg overflow-hidden" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
      <button onClick={onToggle} className="w-full flex items-center justify-between px-3 py-2 text-left">
        <div className="flex items-center gap-2">
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <span className="text-xs font-medium" style={{ color: 'var(--text)' }}>{p.title}</span>
          {statusBadge(p.status)}
          {p.improvement_pct != null && (
            <span className="text-xs font-mono" style={{ color: p.improvement_pct > 0 ? 'var(--green)' : 'var(--red)' }}>
              {p.improvement_pct > 0 ? '+' : ''}{p.improvement_pct.toFixed(1)}%
            </span>
          )}
        </div>
        <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{fmtDate(p.created_at)}</span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-3" style={{ borderTop: '1px solid var(--border)' }}>
          {/* Rationale */}
          <div className="mt-2 text-xs whitespace-pre-wrap" style={{ color: 'var(--text)' }}>
            {p.rationale}
          </div>

          {/* Changes */}
          <div>
            <div className="text-xs font-bold mb-1" style={{ color: 'var(--text-dim)' }}>参数变更</div>
            <table className="w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left px-2 py-1" style={{ color: 'var(--text-dim)' }}>文件</th>
                  <th className="text-left px-2 py-1" style={{ color: 'var(--text-dim)' }}>参数</th>
                  <th className="text-right px-2 py-1" style={{ color: 'var(--text-dim)' }}>旧值</th>
                  <th className="text-right px-2 py-1" style={{ color: 'var(--text-dim)' }}>新值</th>
                  <th className="text-left px-2 py-1" style={{ color: 'var(--text-dim)' }}>原因</th>
                </tr>
              </thead>
              <tbody>
                {p.changes.map((c, i) => (
                  <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                    <td className="px-2 py-1 font-mono" style={{ color: 'var(--blue)' }}>{c.file}</td>
                    <td className="px-2 py-1 font-mono" style={{ color: 'var(--text)' }}>{c.param}</td>
                    <td className="px-2 py-1 text-right font-mono" style={{ color: 'var(--red)' }}>{c.old ?? '—'}</td>
                    <td className="px-2 py-1 text-right font-mono" style={{ color: 'var(--green)' }}>{c.new}</td>
                    <td className="px-2 py-1" style={{ color: 'var(--text-dim)' }}>{c.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Backtest comparison */}
          {p.backtest_before && p.backtest_after && (
            <div>
              <div className="text-xs font-bold mb-1" style={{ color: 'var(--text-dim)' }}>回测对比</div>
              <div className="grid grid-cols-2 gap-2">
                <BacktestBox label="调整前" data={p.backtest_before} />
                <BacktestBox label="调整后" data={p.backtest_after} highlight />
              </div>
            </div>
          )}

          {/* Review info */}
          {p.reviewed_by && (
            <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
              {p.status === 'approved' ? '✅' : '❌'} {p.reviewed_by} 于 {fmtDate(p.reviewed_at)}
              {p.review_comment && ` — "${p.review_comment}"`}
            </div>
          )}

          {/* Approve/Reject buttons */}
          {p.status === 'pending' && onApprove && onReject && (
            <div className="flex gap-2 pt-2">
              <button
                onClick={onApprove}
                className="flex-1 flex items-center justify-center gap-1 py-2 rounded-lg text-xs font-bold transition-colors"
                style={{ background: 'rgba(34,197,94,0.15)', color: 'var(--green)' }}
              >
                <CheckCircle size={14} /> 批准并应用
              </button>
              <button
                onClick={onReject}
                className="flex-1 flex items-center justify-center gap-1 py-2 rounded-lg text-xs font-bold transition-colors"
                style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--red)' }}
              >
                <XCircle size={14} /> 拒绝
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}


function BacktestBox({ label, data, highlight }: {
  label: string
  data: { hit_rate: number; recall: number; f1: number; picks_count?: number; hit_count?: number }
  highlight?: boolean
}) {
  return (
    <div className="p-2 rounded-lg" style={{
      background: highlight ? 'rgba(34,197,94,0.08)' : 'var(--bg-card)',
      border: `1px solid ${highlight ? 'rgba(34,197,94,0.3)' : 'var(--border)'}`,
    }}>
      <div className="text-xs font-bold mb-1" style={{ color: highlight ? 'var(--green)' : 'var(--text-dim)' }}>
        {label}
      </div>
      <div className="space-y-0.5 text-xs font-mono" style={{ color: 'var(--text)' }}>
        <div>命中率: {fmtPct(data.hit_rate)}</div>
        <div>召回率: {fmtPct(data.recall)}</div>
        <div>F1: {data.f1?.toFixed(3)}</div>
        {data.picks_count != null && <div>推荐数: {data.picks_count}</div>}
        {data.hit_count != null && <div>命中数: {data.hit_count}</div>}
      </div>
    </div>
  )
}


function ConversationBubble({ entry }: { entry: { role: string; content?: string; tool_call?: string; input?: Record<string, unknown>; result_preview?: string; timestamp?: string } }) {
  const isAssistant = entry.role === 'assistant'
  const isTool = entry.role === 'tool'

  if (isTool) {
    return (
      <div className="px-2 py-1 rounded text-xs font-mono" style={{ background: 'rgba(30,128,255,0.08)', color: 'var(--blue)' }}>
        🔧 {entry.tool}: {(entry.result_preview || '').slice(0, 200)}...
      </div>
    )
  }

  if (isAssistant && entry.tool_call) {
    return (
      <div className="px-2 py-1 rounded text-xs" style={{ background: 'rgba(139,92,246,0.08)', color: '#8b5cf6' }}>
        🤖 调用 <span className="font-mono font-bold">{entry.tool_call}</span>
        {entry.input && <span className="opacity-60"> ({JSON.stringify(entry.input).slice(0, 100)})</span>}
      </div>
    )
  }

  return (
    <div className={`px-2 py-1 rounded text-xs whitespace-pre-wrap ${isAssistant ? '' : ''}`}
      style={{
        background: isAssistant ? 'rgba(139,92,246,0.08)' : 'rgba(234,179,8,0.08)',
        color: 'var(--text)',
      }}>
      <span className="font-bold" style={{ color: isAssistant ? '#8b5cf6' : '#eab308' }}>
        {isAssistant ? '🤖 Agent' : '📋 System'}:
      </span>{' '}
      {entry.content}
    </div>
  )
}
