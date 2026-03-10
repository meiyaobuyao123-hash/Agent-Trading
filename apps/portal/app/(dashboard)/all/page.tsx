'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Loader2 } from 'lucide-react'
import { Topbar } from '../../components/topbar'
import { PerformanceTable } from '../../components/performance-table'
import { fetchPerformance, type TokenPerformance } from '../../lib/queries'

const SOURCE_TABS = [
  { key: null, label: '全部' },
  { key: 'hot' as const, label: '热币' },
  { key: 'pump' as const, label: '内盘' },
]

const TIME_TABS = [
  { days: 7, label: '7天' },
  { days: 14, label: '14天' },
  { days: 30, label: '30天' },
  { days: 0, label: '全部' },
]

export default function AllPerformancePage() {
  const [data, setData] = useState<TokenPerformance[]>([])
  const [loading, setLoading] = useState(true)
  const [sourceIdx, setSourceIdx] = useState(0)
  const [timeIdx, setTimeIdx] = useState(2)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const source = SOURCE_TABS[sourceIdx].key
      const days = TIME_TABS[timeIdx].days
      const result = await fetchPerformance({
        source: source ?? undefined,
        daysBack: days || undefined,
        limit: 200,
      })
      setData(result)
    } catch (e) {
      console.error('Failed to load all performance:', e)
    } finally {
      setLoading(false)
    }
  }, [sourceIdx, timeIdx])

  useEffect(() => { load() }, [load])

  return (
    <div>
      <Topbar
        title="综合视图"
        subtitle="所有推荐代币表现 · 内盘 + 热币"
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

      <div className="p-6 space-y-4">
        {/* 过滤栏 */}
        <div className="flex items-center gap-6">
          {/* 来源过滤 */}
          <div className="flex items-center gap-2">
            {SOURCE_TABS.map((tab, i) => (
              <button
                key={tab.label}
                onClick={() => setSourceIdx(i)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                style={{
                  background: sourceIdx === i ? 'var(--blue)' : 'var(--bg-card)',
                  color: sourceIdx === i ? '#fff' : 'var(--text-dim)',
                  border: sourceIdx === i ? 'none' : '1px solid var(--border)',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* 时间过滤 */}
          <div className="flex items-center gap-2">
            {TIME_TABS.map((tab, i) => (
              <button
                key={tab.label}
                onClick={() => setTimeIdx(i)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                style={{
                  background: timeIdx === i ? 'var(--bg-card2)' : 'transparent',
                  color: timeIdx === i ? 'var(--text)' : 'var(--text-dim)',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="ml-auto text-xs" style={{ color: 'var(--text-dim)' }}>
            共 {data.length} 条记录
          </div>
        </div>

        {/* 表格 */}
        <div
          className="rounded-xl border overflow-hidden"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
        >
          {loading ? (
            <div className="py-14 flex items-center justify-center gap-3" style={{ color: 'var(--text-dim)' }}>
              <Loader2 size={18} className="animate-spin" />
              <span className="text-sm">加载中...</span>
            </div>
          ) : (
            <PerformanceTable data={data} showSource />
          )}
        </div>
      </div>
    </div>
  )
}
