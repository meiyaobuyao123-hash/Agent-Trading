'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Loader2, ChevronLeft, ChevronRight, Calendar } from 'lucide-react'
import { Topbar } from '../../components/topbar'
import { PerformanceTable } from '../../components/performance-table'
import { fetchPerformance, fetchPerformanceDates, type TokenPerformance } from '../../lib/queries'

const CHAIN_TABS = [
  { key: null, label: '全部' },
  { key: 'solana', label: 'SOL' },
  { key: 'bsc', label: 'BSC' },
  { key: 'eth', label: 'ETH' },
  { key: 'base', label: 'BASE' },
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
  return dateStr.slice(5) // MM-DD
}

export default function HotPerformancePage() {
  const [data, setData] = useState<TokenPerformance[]>([])
  const [loading, setLoading] = useState(true)
  const [chainIdx, setChainIdx] = useState(0)
  const [pickDate, setPickDate] = useState(todayStr())
  const [dates, setDates] = useState<string[]>([])
  const [showDatePicker, setShowDatePicker] = useState(false)

  // 加载可用日期列表
  useEffect(() => {
    fetchPerformanceDates('hot')
      .then(setDates)
      .catch(() => {})
  }, [])

  // 加载日期数据后，自动跳转到最近有数据的日期
  useEffect(() => {
    if (dates.length > 0 && !dates.includes(pickDate)) {
      setPickDate(dates[0])
    }
  }, [dates, pickDate])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const chain = CHAIN_TABS[chainIdx].key
      const result = await fetchPerformance({
        source: 'hot',
        chain: chain ?? undefined,
        pickDate: pickDate,
        limit: 200,
      })
      setData(result)
    } catch (e) {
      console.error('Failed to load hot performance:', e)
    } finally {
      setLoading(false)
    }
  }, [chainIdx, pickDate])

  useEffect(() => { load() }, [load])

  // 日期导航：跳到 dates 列表中的上一个/下一个
  const goPrevDay = () => {
    const idx = dates.indexOf(pickDate)
    if (idx >= 0 && idx < dates.length - 1) {
      setPickDate(dates[idx + 1]) // dates 降序，+1 是更早的日期
    } else {
      setPickDate(shiftDate(pickDate, -1))
    }
  }
  const goNextDay = () => {
    const idx = dates.indexOf(pickDate)
    if (idx > 0) {
      setPickDate(dates[idx - 1]) // dates 降序，-1 是更新的日期
    } else {
      const next = shiftDate(pickDate, 1)
      if (next <= todayStr()) setPickDate(next)
    }
  }

  return (
    <div>
      <Topbar
        title="热币榜推荐表现"
        subtitle="多链 Top20 推荐追踪 · SOL / BSC / ETH / BASE"
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
            {/* 链过滤 */}
            <div className="flex items-center gap-2">
              {CHAIN_TABS.map((tab, i) => (
                <button
                  key={tab.label}
                  onClick={() => setChainIdx(i)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                  style={{
                    background: chainIdx === i ? 'var(--blue)' : 'var(--bg-card)',
                    color: chainIdx === i ? '#fff' : 'var(--text-dim)',
                    border: chainIdx === i ? 'none' : '1px solid var(--border)',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* 计数 */}
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

            {/* 日期下拉 */}
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
            <PerformanceTable data={data} />
          )}
        </div>
      </div>
    </div>
  )
}
