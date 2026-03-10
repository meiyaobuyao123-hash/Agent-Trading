'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Loader2 } from 'lucide-react'
import { Topbar } from '../../components/topbar'
import { StatCard } from '../../components/stat-card'
import { PerformanceTable } from '../../components/performance-table'
import { fetchSummaryStats, fetchPerformance, type SummaryStats, type TokenPerformance } from '../../lib/queries'

export default function OverviewPage() {
  const [stats, setStats] = useState<SummaryStats | null>(null)
  const [recentPump, setRecentPump] = useState<TokenPerformance[]>([])
  const [recentHot, setRecentHot] = useState<TokenPerformance[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, pump, hot] = await Promise.all([
        fetchSummaryStats(),
        fetchPerformance({ source: 'pump', limit: 5 }),
        fetchPerformance({ source: 'hot', limit: 5 }),
      ])
      setStats(s)
      setRecentPump(pump)
      setRecentHot(hot)
    } catch (e) {
      console.error('Failed to load overview:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div>
      <Topbar
        title="总览"
        subtitle="推荐代币表现监控 · 每 4 小时更新"
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

      <div className="p-6 space-y-6">
        {/* 统计卡片 */}
        {loading && !stats ? (
          <div className="py-14 flex items-center justify-center gap-3" style={{ color: 'var(--text-dim)' }}>
            <Loader2 size={18} className="animate-spin" />
            <span className="text-sm">加载中...</span>
          </div>
        ) : stats ? (
          <>
            <div className="grid grid-cols-4 gap-4">
              <StatCard label="总追踪数" value={stats.totalTracked} sub="累计推荐代币" />
              <StatCard label="活跃追踪" value={stats.activeTracking} sub="30天窗口内" color="var(--blue)" />
              <StatCard
                label="平均最佳收益"
                value={`${stats.avgBestReturn > 0 ? '+' : ''}${stats.avgBestReturn}%`}
                sub="所有已追踪代币"
                color={stats.avgBestReturn >= 0 ? 'var(--green)' : 'var(--red)'}
              />
              <StatCard
                label="2x 命中率"
                value={`${stats.hitRate2x}%`}
                sub="最佳收益 ≥ 100%"
                color="var(--yellow)"
              />
            </div>

            {/* 最近热币推荐 */}
            <div>
              <h2
                className="text-sm font-bold mb-3 flex items-center gap-2"
                style={{ color: 'var(--text)' }}
              >
                <span style={{ color: 'var(--blue)' }}>🔥</span>
                最近热币推荐
              </h2>
              <div
                className="rounded-xl border overflow-hidden"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
              >
                <PerformanceTable data={recentHot} />
              </div>
            </div>

            {/* 最近内盘推荐 */}
            <div>
              <h2
                className="text-sm font-bold mb-3 flex items-center gap-2"
                style={{ color: 'var(--text)' }}
              >
                <span style={{ color: 'var(--orange)' }}>⚡</span>
                最近内盘推荐
              </h2>
              <div
                className="rounded-xl border overflow-hidden"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
              >
                <PerformanceTable data={recentPump} />
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
