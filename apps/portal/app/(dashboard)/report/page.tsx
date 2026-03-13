'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Loader2 } from 'lucide-react'
import { Topbar } from '../../components/topbar'
import { StatCard } from '../../components/stat-card'
import { fetchPumpDailyReports, type PumpDailyReport } from '../../lib/queries'

function fmtNum(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 10000) return `${(n / 1000).toFixed(1)}k`
  if (n >= 1000) return n.toLocaleString()
  return String(n)
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return '—'
  return `${(n * 100).toFixed(1)}%`
}

const FUNNEL_STEPS: { key: string; label: string; computed?: boolean }[] = [
  { key: 'ws_creates', label: 'pump发射' },
  { key: 'tokens_saved', label: '我们抓到' },
  { key: 'rest_success', label: '详情拉取成功' },
  { key: 'observed_tokens', label: '进入观察' },
  { key: 'picks_count', label: '推荐给用户' },
  { key: 'graduated_count', label: '真的毕业了' },
  { key: 'hit_count', label: '推中了' },
]

export default function PumpReportPage() {
  const [data, setData] = useState<PumpDailyReport[]>([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(7)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await fetchPumpDailyReports(days)
      setData(result)
    } catch (e) {
      console.error('Failed to load pump report:', e)
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => { load() }, [load])

  const latest = data.length > 0 ? data[0] : null
  const rj = latest?.report_json

  return (
    <div>
      <Topbar
        title="内盘数据报表"
        subtitle="pump.fun 每日数据漏斗 · 自动生成"
        action={
          <button
            onClick={load}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium"
            style={{ background: 'var(--bg-card)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
        }
      />
      <div className="p-6 space-y-5">

        {/* 天数选择 */}
        <div className="flex items-center gap-2">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              style={{
                background: days === d ? 'rgba(30,128,255,0.15)' : 'var(--bg-card)',
                color: days === d ? 'var(--blue)' : 'var(--text-dim)',
                border: `1px solid ${days === d ? 'var(--blue)' : 'var(--border)'}`,
              }}
            >
              {d}天
            </button>
          ))}
        </div>

        {loading ? (
          <div className="py-14 flex items-center justify-center gap-3" style={{ color: 'var(--text-dim)' }}>
            <Loader2 size={18} className="animate-spin" />
            <span className="text-sm">加载中...</span>
          </div>
        ) : !latest ? (
          <div className="rounded-xl p-8 text-center" style={{ background: 'var(--bg-card)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}>
            <div className="text-sm">暂无报表数据</div>
            <div className="text-xs mt-1">报表在每天 UTC 00:30 自动生成</div>
          </div>
        ) : (
          <>
            {/* 概览卡片 */}
            <div className="grid grid-cols-5 gap-3">
              <StatCard label="pump发射" value={fmtNum(latest.ws_creates)} color="var(--yellow)" />
              <StatCard label="我们抓到" value={fmtNum(latest.tokens_saved)} color="var(--text)" sub={latest.ws_creates > 0 ? `覆盖率 ${((latest.tokens_saved / latest.ws_creates) * 100).toFixed(1)}%` : undefined} />
              <StatCard label="推荐给用户" value={fmtNum(latest.picks_count)} color="var(--blue)" />
              <StatCard label="命中率" value={fmtPct(latest.hit_rate)} color="var(--green)" />
              <StatCard label="漏选率" value={fmtPct(latest.miss_rate)} color="var(--red)" />
            </div>

            {/* 漏斗 */}
            <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <div className="text-sm font-semibold mb-4" style={{ color: 'var(--text)' }}>
                数据漏斗 · {latest.report_date}
              </div>
              <FunnelBar report={latest} />
            </div>

            {/* 准确率 + 健康 */}
            {rj && rj.funnel && rj.accuracy && rj.health && rj.quality && rj.scores && (
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                  <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text)' }}>准确率</div>
                  <div className="space-y-2">
                    <MetricRow label="推中" value={`${rj.funnel.hit_count ?? 0} 个`} />
                    <MetricRow label="漏掉" value={`${rj.funnel.miss_count ?? 0} 个`} />
                    <MetricRow label="命中率" value={fmtPct(rj.accuracy.hit_rate)} highlight="green" />
                    <MetricRow label="漏选率" value={fmtPct(rj.accuracy.miss_rate)} highlight="red" />
                    <MetricRow label="误报" value={`${rj.accuracy.false_positive_count ?? 0} 个`} />
                  </div>
                </div>
                <div className="rounded-xl p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                  <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text)' }}>系统健康</div>
                  <div className="space-y-2">
                    <MetricRow label="覆盖率" value={latest.ws_creates > 0 ? fmtPct(latest.tokens_saved / latest.ws_creates) : '—'} highlight={latest.ws_creates > 0 && (latest.tokens_saved / latest.ws_creates) >= 0.5 ? 'green' : 'red'} />
                    <MetricRow label="池满丢弃" value={`${fmtNum(rj.funnel.ws_dropped || 0)} 个`} highlight={(rj.funnel.ws_dropped || 0) > 0 ? 'red' : 'green'} />
                    <MetricRow label="REST 成功率" value={fmtPct(rj.health.rest_success_pct)} highlight={(rj.health.rest_success_pct ?? 0) >= 0.9 ? 'green' : 'red'} />
                    <MetricRow label="WS 断连" value={`${rj.health.ws_reconnects ?? 0} 次`} highlight={(rj.health.ws_reconnects ?? 0) <= 2 ? 'green' : 'red'} />
                    <MetricRow label="快照/分钟" value={`${rj.health.avg_snapshots_per_min ?? '—'}`} />
                    <MetricRow label="平均毕业耗时" value={rj.quality.avg_grad_hours != null ? `${rj.quality.avg_grad_hours} 小时` : '—'} />
                    <MetricRow label="推荐分布" value={`强${rj.scores.strong ?? 0} / 普通${rj.scores.normal ?? 0} / 跳过${rj.scores.skip ?? 0}`} />
                  </div>
                </div>
              </div>
            )}

            {/* 历史趋势表 */}
            <div className="rounded-xl overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <div className="px-5 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
                <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>历史趋势</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                      {['日期', '新币', '抓到', 'REST成功', '观察', '推荐', '毕业', '推中', '漏掉', '命中率', '漏选率', 'REST%', '断连'].map((h) => (
                        <th key={h} className="px-3 py-2 text-left font-medium" style={{ color: 'var(--text-dim)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((r) => (
                      <tr key={r.report_date} style={{ borderTop: '1px solid var(--border)' }}>
                        <td className="px-3 py-2 font-medium" style={{ color: 'var(--text)' }}>{r.report_date}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--text-dim)' }}>{fmtNum(r.ws_creates)}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--text-dim)' }}>{fmtNum(r.tokens_saved)}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--text-dim)' }}>{fmtNum(r.rest_success)}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--text-dim)' }}>{fmtNum(r.observed_tokens)}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--blue)' }}>{r.picks_count}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--yellow)' }}>{r.graduated_count}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--green)' }}>{r.hit_count}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--red)' }}>{r.miss_count}</td>
                        <td className="px-3 py-2 font-medium" style={{ color: r.hit_rate > 0.3 ? 'var(--green)' : 'var(--text-dim)' }}>{fmtPct(r.hit_rate)}</td>
                        <td className="px-3 py-2 font-medium" style={{ color: r.miss_rate < 0.5 ? 'var(--green)' : 'var(--red)' }}>{fmtPct(r.miss_rate)}</td>
                        <td className="px-3 py-2" style={{ color: r.rest_success_pct >= 0.9 ? 'var(--green)' : 'var(--red)' }}>{fmtPct(r.rest_success_pct)}</td>
                        <td className="px-3 py-2" style={{ color: r.ws_reconnects <= 2 ? 'var(--text-dim)' : 'var(--red)' }}>{r.ws_reconnects}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── 子组件 ────────────────────────────────

function MetricRow({ label, value, highlight }: { label: string; value: string; highlight?: 'green' | 'red' }) {
  const color = highlight === 'green' ? 'var(--green)' : highlight === 'red' ? 'var(--red)' : 'var(--text)'
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{label}</span>
      <span className="text-sm font-semibold" style={{ color }}>{value}</span>
    </div>
  )
}

function FunnelBar({ report }: { report: PumpDailyReport }) {
  const maxVal = Math.max(...FUNNEL_STEPS.map((s) => (report as unknown as Record<string, number>)[s.key] || 0), 1)

  return (
    <div className="space-y-2">
      {FUNNEL_STEPS.map((step, idx) => {
        const val = (report as unknown as Record<string, number>)[step.key] || 0
        const pct = (val / maxVal) * 100
        const prevVal = idx > 0 ? (report as unknown as Record<string, number>)[FUNNEL_STEPS[idx - 1].key] || 0 : 0
        const convRate = idx > 0 && prevVal > 0 ? ((val / prevVal) * 100).toFixed(1) : null

        return (
          <div key={step.key} className="flex items-center gap-3">
            <div className="w-24 text-xs text-right shrink-0" style={{ color: 'var(--text-dim)' }}>
              {step.label}
            </div>
            <div className="flex-1 h-7 rounded-md overflow-hidden relative" style={{ background: 'rgba(255,255,255,0.04)' }}>
              <div
                className="h-full rounded-md transition-all duration-500"
                style={{
                  width: `${Math.max(pct, 2)}%`,
                  background: `linear-gradient(90deg, rgba(30,128,255,0.6), rgba(30,128,255,${0.15 + (1 - idx / FUNNEL_STEPS.length) * 0.35}))`,
                }}
              />
              <div className="absolute inset-0 flex items-center px-2">
                <span className="text-xs font-bold" style={{ color: 'var(--text)' }}>{fmtNum(val)}</span>
              </div>
            </div>
            <div className="w-16 text-xs shrink-0" style={{ color: convRate ? 'var(--text-dim)' : 'transparent' }}>
              {convRate ? `${convRate}%` : '—'}
            </div>
          </div>
        )
      })}
    </div>
  )
}
