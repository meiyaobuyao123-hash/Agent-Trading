import { createClient } from './supabase'

// ═══════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════

export interface OptimizationRun {
  id: number
  run_date: string
  status: 'running' | 'completed' | 'failed'
  metrics_snapshot: Record<string, unknown>
  conversation: ConversationEntry[]
  analysis: string | null
  tokens_used: number
  cost_usd: number
  started_at: string
  completed_at: string | null
}

export interface ConversationEntry {
  role: 'user' | 'assistant' | 'tool'
  content?: string
  tool_call?: string
  input?: Record<string, unknown>
  result_preview?: string
  timestamp: string
}

export interface OptimizationProposal {
  id: number
  run_id: number
  status: 'pending' | 'approved' | 'rejected' | 'applied' | 'rolled_back'
  title: string
  rationale: string
  changes: ProposalChange[]
  backtest_before: BacktestResult | null
  backtest_after: BacktestResult | null
  improvement_pct: number | null
  reviewed_by: string | null
  reviewed_at: string | null
  review_comment: string | null
  applied_at: string | null
  rolled_back_at: string | null
  rollback_reason: string | null
  params_before: Record<string, unknown> | null
  created_at: string
}

export interface ProposalChange {
  file: string
  type: 'weight' | 'threshold' | 'logic'
  param: string
  old?: number
  new: number
  reason: string
}

export interface BacktestResult {
  hit_rate: number
  recall: number
  precision: number
  f1: number
  hit_count: number
  miss_count: number
  false_positive_count: number
  picks_count: number
  sample_size?: number
}

export interface MetricsHistory {
  snapshot_date: string
  pump_picks_count: number
  pump_graduated: number
  pump_hit_count: number
  pump_miss_count: number
  pump_hit_rate: number
  pump_recall: number
  pump_precision: number
  pump_f1: number
  scorer_params: Record<string, unknown> | null
  signal_count: number
  avg_signal_score: number
}

// ═══════════════════════════════════════════════════
// Queries
// ═══════════════════════════════════════════════════

export async function fetchOptimizationRuns(limit = 20): Promise<OptimizationRun[]> {
  const supabase = createClient()
  const { data, error } = await supabase
    .from('optimization_runs')
    .select('*')
    .order('started_at', { ascending: false })
    .limit(limit)

  if (error) throw error
  return (data ?? []) as OptimizationRun[]
}

export async function fetchOptimizationRun(id: number): Promise<OptimizationRun | null> {
  const supabase = createClient()
  const { data, error } = await supabase
    .from('optimization_runs')
    .select('*')
    .eq('id', id)
    .single()

  if (error) return null
  return data as OptimizationRun
}

export async function fetchProposals(status?: string): Promise<OptimizationProposal[]> {
  const supabase = createClient()
  let query = supabase
    .from('optimization_proposals')
    .select('*')
    .order('created_at', { ascending: false })

  if (status) query = query.eq('status', status)

  const { data, error } = await query
  if (error) throw error
  return (data ?? []) as OptimizationProposal[]
}

export async function fetchMetricsHistory(days = 30): Promise<MetricsHistory[]> {
  const supabase = createClient()
  const { data, error } = await supabase
    .from('optimization_metrics_history')
    .select('*')
    .order('snapshot_date', { ascending: false })
    .limit(days)

  if (error) throw error
  return (data ?? []) as MetricsHistory[]
}

// ═══════════════════════════════════════════════════
// Actions (call backend API)
// ═══════════════════════════════════════════════════

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://43.156.207.26'

export async function approveProposal(id: number, comment?: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/optimizer/proposals/${id}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ comment, reviewer: 'portal_user' }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function rejectProposal(id: number, comment?: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/optimizer/proposals/${id}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ comment, reviewer: 'portal_user' }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function triggerOptimization(): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/optimizer/trigger`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
