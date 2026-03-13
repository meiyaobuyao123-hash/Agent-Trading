'use client'

import { useState } from 'react'
import { RefreshCw, Activity, Target, AlertTriangle, TrendingUp, ChevronDown, ChevronUp } from 'lucide-react'
import { Topbar } from '@/components/layout/topbar'
import { usePumpReport, PumpDailyReport } from '@/hooks/usePumpReport'

// ── 漏斗层级定义 ─────────────────────────────────
const FUNNEL_STEPS = [
  { key: 'ws_creates', label: 'pump发射', desc: 'WS 收到的全部 create 事件' },
  { key: 'tokens_saved', label: '我们抓到', desc: '成功入库追踪的代币数' },
  { key: 'rest_success', label: '详情拉取成功', desc: 'REST API 详情成功' },
  { key: 'observed_tokens', label: '进入观察', desc: '通过硬过滤的去重代币' },
  { key: 'picks_count', label: '推荐给用户', desc: '每日 Top 推荐' },
  { key: 'graduated_count', label: '真的毕业了', desc: '完成 Bonding Curve' },
  { key: 'hit_count', label: '推中了', desc: '推荐 ∩ 毕业' },
] as const

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

// ── 主页面 ─────────────────────────────────────
export default function PumpReportPage() {
  const [days, setDays] = useState(7)
  const { data, loading, error, lastUpdated, refresh } = usePumpReport(days)

  const latest = data.length > 0 ? data[0] : null
  const rj = latest?.report_json

  return (
    <div>
      <Topbar title="内盘报表" subtitle="pump.fun 每日数据漏斗 · 自动生成" />
      <div className="p-6 space-y-6">

        {/* ── 控制栏 ──────────────────────────── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                style={{
                  background: days === d ? 'rgba(240,185,11,0.15)' : 'var(--bg-card)',
                  color: days === d ? 'var(--yellow)' : 'var(--text-dim)',
                  border: `1px solid ${days === d ? 'var(--yellow)' : 'var(--border)'}`,
                }}
              >
                {d}天
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            {lastUpdated && (
              <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                更新于 {lastUpdated.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
            <button
              onClick={refresh}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-80 transition-all"
              style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
            >
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
              刷新
            </button>
          </div>
        </div>

        {/* ── Loading / Error ──────────────────── */}
        {loading && !data.length ? (
          <div className="grid grid-cols-4 gap-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-24 rounded-xl animate-pulse" style={{ background: 'var(--bg-card)' }} />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-xl p-8 text-center border" style={{ background: 'var(--bg-card)', borderColor: 'rgba(246,70,93,0.3)' }}>
            <div className="text-sm font-semibold mb-1" style={{ color: 'var(--red)' }}>加载失败</div>
            <div className="text-xs mb-4" style={{ color: 'var(--text-dim)' }}>{error}</div>
            <button onClick={refresh} className="text-xs px-4 py-2 rounded-lg" style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}>
              重试
            </button>
          </div>
        ) : !latest ? (
          <div className="rounded-xl p-8 text-center" style={{ background: 'var(--bg-card)', color: 'var(--text-dim)' }}>
            <div className="text-2xl mb-2">📭</div>
            <div className="text-sm">暂无报表数据</div>
            <div className="text-xs mt-1">报表会在每天 UTC 00:30 自动生成</div>
          </div>
        ) : (
          <>
            {/* ── 最新一天概览卡片 ──────────────── */}
            <div className="grid grid-cols-4 gap-3">
              <StatCard icon={<Activity size={14} />} label="新币出现" value={fmtNum(latest.ws_creates)} color="var(--yellow)" />
              <StatCard icon={<Target size={14} />} label="推荐给用户" value={fmtNum(latest.picks_count)} color="var(--blue)" />
              <StatCard icon={<TrendingUp size={14} />} label="命中率" value={fmtPct(latest.hit_rate)} color="var(--green)" />
              <StatCard icon={<AlertTriangle size={14} />} label="漏选率" value={fmtPct(latest.miss_rate)} color="var(--red)" />
            </div>

            {/* ── 漏斗可视化（最新一天）────────── */}
            <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
              <div className="text-sm font-semibold mb-4" style={{ color: 'var(--text)' }}>
                数据漏斗 · {latest.report_date}
              </div>
              <FunnelBar report={latest} />
            </div>

            {/* ── 质量 & 健康 ──────────────────── */}
            {rj && (
              <div className="grid grid-cols-2 gap-4">
                {/* 准确率 */}
                <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
                  <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text)' }}>准确率</div>
                  <div className="space-y-2">
                    <MetricRow label="推中" value={`${rj.funnel.hit_count} 个`} />
                    <MetricRow label="漏掉" value={`${rj.funnel.miss_count} 个`} />
                    <MetricRow label="命中率" value={fmtPct(rj.accuracy.hit_rate)} highlight="green" />
                    <MetricRow label="漏选率" value={fmtPct(rj.accuracy.miss_rate)} highlight="red" />
                    <MetricRow label="误报" value={`${rj.accuracy.false_positive_count} 个`} />
                  </div>
                </div>
                {/* 健康 */}
                <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
                  <div className="text-sm font-semibold mb-3" style={{ color: 'var(--text)' }}>系统健康</div>
                  <div className="space-y-2">
                    <MetricRow label="REST 成功率" value={fmtPct(rj.health.rest_success_pct)} highlight={rj.health.rest_success_pct >= 0.9 ? 'green' : 'red'} />
                    <MetricRow label="WS 断连" value={`${rj.health.ws_reconnects} 次`} highlight={rj.health.ws_reconnects <= 2 ? 'green' : 'red'} />
                    <MetricRow label="快照/分钟" value={`${rj.health.avg_snapshots_per_min}`} />
                    <MetricRow label="平均毕业耗时" value={rj.quality.avg_grad_hours != null ? `${rj.quality.avg_grad_hours} 小时` : '—'} />
                    <MetricRow
                      label="推荐分布"
                      value={`强${rj.scores.strong} / 普通${rj.scores.normal} / 跳过${rj.scores.skip}`}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* ── 历史趋势表 ──────────────────── */}
            <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
              <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
                <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>历史趋势</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr style={{ background: 'var(--bg-card2)' }}>
                      {['日期', '新币', '抓到', 'REST成功', '观察', '推荐', '毕业', '推中', '漏掉', '命中率', '漏选率', 'REST%', '断连'].map((h) => (
                        <th key={h} className="px-3 py-2 text-left font-medium" style={{ color: 'var(--text-dim)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((r) => (
                      <tr key={r.report_date} className="border-t" style={{ borderColor: 'var(--border)' }}>
                        <td className="px-3 py-2 font-medium" style={{ color: 'var(--text)' }}>{r.report_date}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--text-dim)' }}>{fmtNum(r.ws_creates)}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--text-dim)' }}>{fmtNum(r.tokens_saved)}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--text-dim)' }}>{fmtNum(r.rest_success)}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--text-dim)' }}>{fmtNum(r.observed_tokens)}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--blue)' }}>{r.picks_count}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--yellow)' }}>{r.graduated_count}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--green)' }}>{r.hit_count}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--red)' }}>{r.miss_count}</td>
                        <td className="px-3 py-2 font-medium" style={{ color: r.hit_rate > 0.3 ? 'var(--green)' : 'var(--text-dim)' }}>
                          {fmtPct(r.hit_rate)}
                        </td>
                        <td className="px-3 py-2 font-medium" style={{ color: r.miss_rate < 0.5 ? 'var(--green)' : 'var(--red)' }}>
                          {fmtPct(r.miss_rate)}
                        </td>
                        <td className="px-3 py-2" style={{ color: r.rest_success_pct >= 0.9 ? 'var(--green)' : 'var(--red)' }}>
                          {fmtPct(r.rest_success_pct)}
                        </td>
                        <td className="px-3 py-2" style={{ color: r.ws_reconnects <= 2 ? 'var(--text-dim)' : 'var(--red)' }}>
                          {r.ws_reconnects}
                        </td>
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

// ── 子组件 ─────────────────────────────────────

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) {
  return (
    <div className="rounded-xl px-4 py-3 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-1.5 mb-1">
        <span style={{ color }}>{icon}</span>
        <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{label}</span>
      </div>
      <div className="text-2xl font-black" style={{ color }}>{value}</div>
    </div>
  )
}

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
            <div className="flex-1 h-7 rounded-md overflow-hidden relative" style={{ background: 'var(--bg-card2)' }}>
              <div
                className="h-full rounded-md transition-all duration-500"
                style={{
                  width: `${Math.max(pct, 2)}%`,
                  background: `linear-gradient(90deg, rgba(240,185,11,0.6), rgba(240,185,11,${0.2 + (1 - idx / FUNNEL_STEPS.length) * 0.4}))`,
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
