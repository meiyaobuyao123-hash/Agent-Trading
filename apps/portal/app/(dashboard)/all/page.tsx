'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Loader2, ChevronLeft, ChevronRight, Calendar } from 'lucide-react'
import { Topbar } from '../../components/topbar'
import { PerformanceTable } from '../../components/performance-table'
import { fetchPerformance, type TokenPerformance } from '../../lib/queries'
import { createClient } from '../../lib/supabase'

const SOURCE_TABS = [
  { key: null, label: '全部' },
  { key: 'hot' as const, label: '热币' },
  { key: 'pump' as const, label: '内盘' },
]

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

function shiftDate(dateStr: string, days: number) {
  const d = new Date(dateStr + 'T00:00:00')
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function formatDateLabel(dateStr: string) {
  const today = todayStr()
  if (dateStr === today) return '今天'
  if (dateStr === shiftDate(today, -1)) return '昨天'
  return dateStr.slice(5)
}

async function fetchAllDates(): Promise<string[]> {
  const supabase = createClient()
  const { data } = await supabase
    .from('token_performance')
    .select('pick_date')
    .order('pick_date', { ascending: false })
    .limit(500)

  const unique = [...new Set((data ?? []).map((r: Record<string, unknown>) => r.pick_date as string))]
    .sort((a, b) => b.localeCompare(a))
    .slice(0, 60)
  return unique
}

export default function AllPerformancePage() {
  const [data, setData] = useState<TokenPerformance[]>([])
  const [loading, setLoading] = useState(true)
  const [sourceIdx, setSourceIdx] = useState(0)
  const [pickDate, setPickDate] = useState(todayStr())
  const [dates, setDates] = useState<string[]>([])
  const [showDatePicker, setShowDatePicker] = useState(false)

  useEffect(() => {
    fetchAllDates()
      .then(setDates)
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (dates.length > 0 && !dates.includes(pickDate)) {
      setPickDate(dates[0])
    }
  }, [dates, pickDate])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const source = SOURCE_TABS[sourceIdx].key
      const result = await fetchPerformance({
        source: source ?? undefined,
        pickDate: pickDate,
        limit: 200,
      })
      setData(result)
    } catch (e) {
      console.error('Failed to load all performance:', e)
    } finally {
      setLoading(false)
    }
  }, [sourceIdx, pickDate])

  useEffect(() => { load() }, [load])

  const goPrevDay = () => {
    const idx = dates.indexOf(pickDate)
    if (idx >= 0 && idx < dates.length - 1) {
      setPickDate(dates[idx + 1])
    } else {
      setPickDate(shiftDate(pickDate, -1))
    }
  }
  const goNextDay = () => {
    const idx = dates.indexOf(pickDate)
    if (idx > 0) {
      setPickDate(dates[idx - 1])
    } else {
      const next = shiftDate(pickDate, 1)
      if (next <= todayStr()) setPickDate(next)
    }
  }

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
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-4 flex-wrap">
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

            <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
              共 {data.length} 条记录
            </span>
          </div>

          {/* 日期导航 */}
          <div className="flex items-center gap-1 relative">
            <button
              onClick={goPrevDay}
              className="p-1.5 rounded-lg transition-all hover:opacity-80"
              style={{ background: 'var(--bg-card)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
            >
              <ChevronLeft size={14} />
            </button>

            <button
              onClick={() => setShowDatePicker(!showDatePicker)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80"
              style={{ background: 'var(--bg-card)', color: 'var(--text)', border: '1px solid var(--border)' }}
            >
              <Calendar size={12} />
              {formatDateLabel(pickDate)}
              <span className="text-[10px] font-normal" style={{ color: 'var(--text-dim)' }}>
                {pickDate}
              </span>
            </button>

            <button
              onClick={goNextDay}
              disabled={pickDate >= todayStr()}
              className="p-1.5 rounded-lg transition-all hover:opacity-80 disabled:opacity-30"
              style={{ background: 'var(--bg-card)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
            >
              <ChevronRight size={14} />
            </button>

            {showDatePicker && dates.length > 0 && (
              <div
                className="absolute top-10 right-0 z-50 rounded-xl border shadow-xl py-1 max-h-60 overflow-y-auto"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', minWidth: 160 }}
              >
                {dates.map((d) => (
                  <button
                    key={d}
                    onClick={() => { setPickDate(d); setShowDatePicker(false) }}
                    className="w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] transition-colors"
                    style={{
                      color: d === pickDate ? 'var(--blue)' : 'var(--text)',
                      fontWeight: d === pickDate ? 700 : 400,
                    }}
                  >
                    {d} {formatDateLabel(d) !== d.slice(5) ? `(${formatDateLabel(d)})` : ''}
                  </button>
                ))}
              </div>
            )}
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
