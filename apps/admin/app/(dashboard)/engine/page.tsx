'use client'

import { useState, useEffect } from 'react'
import { Play, RefreshCw, Activity, Loader2, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { AdminTopbar } from '../../components/topbar'

// Admin 调用 Web App 的信号引擎（不同 port / 域名）
const WEB_BASE = process.env.NEXT_PUBLIC_WEB_BASE_URL || 'http://localhost:3000'

interface EngineStatus {
  engine: string
  version: string
  supabaseConnected: boolean
  activeSignals: number
  latestSignal: string | null
  chains: string[]
}

interface SyncResult {
  chain: string
  fetched: number
  filtered: number
  upserted: number
  skipped: number
}

interface SyncResponse {
  ok: boolean
  dryRun: boolean
  elapsed: string
  totalUpserted: number
  results: SyncResult[]
  timestamp: string
}

function fmtDate(dateStr?: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export default function EnginePage() {
  const [status, setStatus] = useState<EngineStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [lastSync, setLastSync] = useState<SyncResponse | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)

  const fetchStatus = async () => {
    setStatusLoading(true)
    try {
      const res = await fetch(`${WEB_BASE}/api/engine/sync-signals`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setStatus(data)
    } catch (err) {
      console.error('Engine status error:', err)
    } finally {
      setStatusLoading(false)
    }
  }

  const triggerSync = async () => {
    setSyncing(true)
    setSyncError(null)
    try {
      const res = await fetch(`${WEB_BASE}/api/engine/sync-signals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
      setLastSync(data)
      // Refresh status after sync
      await fetchStatus()
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => { fetchStatus() }, [])

  return (
    <div>
      <AdminTopbar
        title="信号引擎"
        subtitle="手动触发 · 同步状态 · Cron 监控"
        action={
          <div className="flex items-center gap-2">
            <button
              onClick={fetchStatus}
              disabled={statusLoading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium"
              style={{ background: 'var(--bg-card)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
            >
              <RefreshCw size={12} className={statusLoading ? 'animate-spin' : ''} />
              刷新状态
            </button>
            <button
              onClick={triggerSync}
              disabled={syncing}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
              style={{ background: 'var(--green)', color: '#000' }}
            >
              {syncing ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
              {syncing ? '同步中…' : '立即同步'}
            </button>
          </div>
        }
      />

      <div className="p-6 space-y-5">

        {/* Engine Status */}
        <div className="grid grid-cols-4 gap-4">
          {[
            {
              label: '引擎状态',
              value: statusLoading ? '—' : status ? '运行中' : '离线',
              color: status ? 'var(--green)' : 'var(--red)',
              sub: `v${status?.version ?? '—'}`,
            },
            {
              label: 'Supabase',
              value: statusLoading ? '—' : status?.supabaseConnected ? '已连接' : '未配置',
              color: status?.supabaseConnected ? 'var(--green)' : 'var(--yellow)',
              sub: status?.supabaseConnected ? '写入就绪' : '配置 env 后启用',
            },
            {
              label: '活跃信号',
              value: statusLoading ? '—' : String(status?.activeSignals ?? 0),
              color: 'var(--blue)',
              sub: 'Supabase 中',
            },
            {
              label: '最新同步',
              value: statusLoading ? '—' : fmtDate(status?.latestSignal),
              color: 'var(--text-dim)',
              sub: 'Cron: */5 * * * *',
            },
          ].map(({ label, value, color, sub }) => (
            <div
              key={label}
              className="rounded-xl p-4 border"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
            >
              <div className="text-xs mb-1" style={{ color: 'var(--text-dim)' }}>{label}</div>
              <div className="text-lg font-black" style={{ color }}>{value}</div>
              <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{sub}</div>
            </div>
          ))}
        </div>

        {/* Chain Coverage */}
        {status && (
          <div
            className="rounded-xl border p-5"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
          >
            <div className="flex items-center gap-2 mb-4 text-sm font-semibold" style={{ color: 'var(--text)' }}>
              <Activity size={14} color="var(--blue)" />
              覆盖链
            </div>
            <div className="flex gap-3">
              {status.chains.map((chain) => (
                <div
                  key={chain}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg"
                  style={{ background: 'var(--bg-card2)' }}
                >
                  <span className="w-2 h-2 rounded-full" style={{ background: 'var(--green)' }} />
                  <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>{chain}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sync Error */}
        {syncError && (
          <div
            className="rounded-xl border px-5 py-4 flex items-start gap-3"
            style={{ background: 'rgba(246,70,93,0.08)', borderColor: 'rgba(246,70,93,0.3)' }}
          >
            <AlertCircle size={16} color="var(--red)" className="shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-semibold mb-1" style={{ color: 'var(--red)' }}>同步失败</div>
              <div className="text-xs" style={{ color: 'var(--text-dim)' }}>{syncError}</div>
            </div>
          </div>
        )}

        {/* Last Sync Result */}
        {lastSync && (
          <div
            className="rounded-xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
          >
            <div
              className="flex items-center justify-between px-5 py-3"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text)' }}>
                <CheckCircle size={14} color="var(--green)" />
                最近一次同步结果
                {lastSync.dryRun && (
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(240,185,11,0.1)', color: 'var(--yellow)' }}>
                    Dry Run（Supabase 未配置）
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-dim)' }}>
                <Clock size={11} />
                耗时 {lastSync.elapsed} · {fmtDate(lastSync.timestamp)}
              </div>
            </div>

            {/* Result Table */}
            <div
              className="grid px-5 py-2.5 text-xs font-semibold"
              style={{
                gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr',
                color: 'var(--text-dim)',
                borderBottom: '1px solid var(--border)',
                background: 'var(--bg-card2)',
              }}
            >
              <div>链</div>
              <div className="text-right">拉取</div>
              <div className="text-right">有效</div>
              <div className="text-right">写入</div>
              <div className="text-right">跳过</div>
            </div>

            {lastSync.results.map((r) => (
              <div
                key={r.chain}
                className="grid px-5 py-3 text-sm"
                style={{
                  gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                <div className="font-semibold" style={{ color: 'var(--text)' }}>{r.chain}</div>
                <div className="text-right font-mono" style={{ color: 'var(--text-dim)' }}>{r.fetched}</div>
                <div className="text-right font-mono" style={{ color: 'var(--yellow)' }}>{r.filtered}</div>
                <div className="text-right font-mono" style={{ color: 'var(--green)' }}>{r.upserted}</div>
                <div className="text-right font-mono" style={{ color: 'var(--text-dim)' }}>{r.skipped}</div>
              </div>
            ))}

            <div
              className="flex justify-end px-5 py-3 text-sm font-bold"
              style={{ color: 'var(--green)' }}
            >
              总计写入 {lastSync.totalUpserted} 条信号
            </div>
          </div>
        )}

        {/* Usage Guide */}
        <div
          className="rounded-xl border p-5 space-y-3"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
        >
          <div className="text-sm font-semibold" style={{ color: 'var(--text)' }}>使用说明</div>
          <div className="space-y-2 text-xs" style={{ color: 'var(--text-dim)' }}>
            <div>
              <span style={{ color: 'var(--yellow)' }}>● 手动触发：</span>
              {' '}点击"立即同步"按钮，或 curl -X POST {WEB_BASE}/api/engine/sync-signals
            </div>
            <div>
              <span style={{ color: 'var(--green)' }}>● Vercel Cron：</span>
              {' '}vercel.json 已配置 */5 * * * *，部署后自动每5分钟同步
            </div>
            <div>
              <span style={{ color: 'var(--blue)' }}>● 安全保护：</span>
              {' '}设置 CRON_SECRET 环境变量后，需要 Authorization: Bearer token 头
            </div>
            <div>
              <span style={{ color: 'var(--text-dim)' }}>● 去重逻辑：</span>
              {' '}按 (token_address, chain_id) upsert，同一代币更新而非重复插入
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
