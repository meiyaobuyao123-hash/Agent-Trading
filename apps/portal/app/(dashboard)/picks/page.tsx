'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Loader2, ChevronLeft, ChevronRight, Calendar } from 'lucide-react'
import { Topbar } from '../../components/topbar'
import { ChainBadge } from '../../components/chain-badge'
import { PctCell } from '../../components/pct-cell'
import { fmtUsd } from '../../lib/utils'
import { fetchHotDailyPicks, type HotPickItem } from '../../lib/queries'

const CHAIN_TABS = [
  { key: '', label: '全部' },
  { key: 'solana', label: 'SOL' },
  { key: 'bsc', label: 'BSC' },
  { key: 'eth', label: 'ETH' },
  { key: 'base', label: 'BASE' },
]

const REC_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  strong: { bg: 'rgba(14,203,129,0.15)', color: '#0ECB81', label: '强推' },
  normal: { bg: 'rgba(240,185,11,0.15)', color: '#F0B90B', label: '推荐' },
  weak:   { bg: 'rgba(246,70,93,0.15)', color: '#F6465D', label: '观察' },
}

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

function fmtPrice(n: number | undefined | null) {
  if (n == null || isNaN(n) || n === 0) return '—'
  if (n >= 1) return `$${n.toFixed(2)}`
  if (n >= 0.01) return `$${n.toFixed(4)}`
  if (n >= 0.0001) return `$${n.toFixed(6)}`
  return `$${n.toExponential(3)}`
}

export default function HotPicksPage() {
  const [data, setData] = useState<HotPickItem[]>([])
  const [dates, setDates] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [picksDate, setPicksDate] = useState(todayStr())
  const [chainFilter, setChainFilter] = useState('')
  const [showDatePicker, setShowDatePicker] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await fetchHotDailyPicks({
        date: picksDate,
        chain: chainFilter || undefined,
      })
      setData(result.picks)
      setDates(result.dates)
    } catch (e) {
      console.error('Failed to load hot picks:', e)
    } finally {
      setLoading(false)
    }
  }, [picksDate, chainFilter])

  useEffect(() => { load() }, [load])

  // 自动刷新（60秒，避免频繁闪烁）
  useEffect(() => {
    const timer = setInterval(load, 60_000)
    return () => clearInterval(timer)
  }, [load])

  const goPrevDay = () => setPicksDate(shiftDate(picksDate, -1))
  const goNextDay = () => {
    const next = shiftDate(picksDate, 1)
    if (next <= todayStr()) setPicksDate(next)
  }

  return (
    <div>
      <Topbar
        title="热币日榜"
        subtitle="每日 Top20 热币推荐 · 实时追踪收益"
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
            <div className="flex items-center gap-1.5">
              {CHAIN_TABS.map((tab) => {
                const active = tab.key === chainFilter
                return (
                  <button
                    key={tab.key}
                    onClick={() => setChainFilter(tab.key)}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
                    style={{
                      background: active ? 'rgba(30,128,255,0.15)' : 'var(--bg-card)',
                      color: active ? 'var(--blue)' : 'var(--text-dim)',
                      border: active ? '1px solid rgba(30,128,255,0.4)' : '1px solid var(--border)',
                    }}
                  >
                    {tab.label}
                  </button>
                )
              })}
            </div>

            {/* 统计 */}
            <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
              共 {data.length} 个代币
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
              {formatDateLabel(picksDate)}
              <span className="text-[10px] font-normal" style={{ color: 'var(--text-dim)' }}>
                {picksDate}
              </span>
            </button>

            <button
              onClick={goNextDay}
              disabled={shiftDate(picksDate, 1) > todayStr()}
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
                    onClick={() => { setPicksDate(d); setShowDatePicker(false) }}
                    className="w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] transition-colors"
                    style={{
                      color: d === picksDate ? 'var(--blue)' : 'var(--text)',
                      fontWeight: d === picksDate ? 700 : 400,
                    }}
                  >
                    {d} {formatDateLabel(d) !== d.slice(5) ? `(${formatDateLabel(d)})` : ''}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: '数据来源', value: 'OKX + GoPlus + DexScreener', color: 'var(--yellow)' },
            { label: '刷新频率', value: 'OKX 5秒 · 发现 10分钟', color: 'var(--green)' },
            { label: '覆盖链', value: 'SOL · BSC · ETH · BASE', color: 'var(--blue)' },
            { label: '当日入选', value: `${data.length} 个代币`, color: 'var(--yellow)' },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              className="rounded-xl px-4 py-3 border"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
            >
              <div className="text-xs mb-1" style={{ color: 'var(--text-dim)' }}>{label}</div>
              <div className="text-sm font-semibold" style={{ color }}>{value}</div>
            </div>
          ))}
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
          ) : data.length === 0 ? (
            <div className="py-14 text-center" style={{ color: 'var(--text-dim)' }}>
              <div className="text-3xl mb-3">📊</div>
              <div className="text-sm">该日期暂无日榜数据</div>
              <div className="text-xs mt-1">日榜每天 UTC 02:00 自动生成</div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" style={{ minWidth: 1000 }}>
                <thead>
                  <tr
                    className="text-xs font-semibold"
                    style={{
                      color: 'var(--text-dim)',
                      borderBottom: '1px solid var(--border)',
                      background: 'var(--bg-card2)',
                    }}
                  >
                    <th className="text-left px-4 py-3 w-10">#</th>
                    <th className="text-left px-4 py-3">代币</th>
                    <th className="text-center px-3 py-3">推荐</th>
                    <th className="text-right px-3 py-3">发现价</th>
                    <th className="text-right px-3 py-3">现价</th>
                    <th className="text-right px-3 py-3">收益</th>
                    <th className="text-right px-3 py-3">市值</th>
                    <th className="text-right px-3 py-3">流动性</th>
                    <th className="text-right px-3 py-3">24h量</th>
                    <th className="text-center px-3 py-3">5m</th>
                    <th className="text-center px-3 py-3">1h</th>
                    <th className="text-center px-3 py-3">24h</th>
                    <th className="text-right px-3 py-3">评分</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((pick, i) => {
                    const rec = REC_STYLES[pick.pick_recommendation] || REC_STYLES.normal
                    const pnl = pick.pnl_pct
                    const pnlColor = pnl === null ? 'var(--text-dim)'
                      : pnl > 0 ? 'var(--green)'
                      : pnl < 0 ? 'var(--red)'
                      : 'var(--text-dim)'

                    return (
                      <tr
                        key={`${pick.chain}-${pick.address}`}
                        className="hover:bg-white/[0.02] transition-colors"
                        style={{
                          borderBottom: i < data.length - 1 ? '1px solid var(--border)' : 'none',
                        }}
                      >
                        {/* 排名 */}
                        <td className="px-4 py-3 text-xs font-bold" style={{
                          color: pick.rank <= 3 ? 'var(--yellow)' : 'var(--text-dim)',
                        }}>
                          {pick.rank}
                        </td>

                        {/* 代币 */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            {pick.image_url ? (
                              <img
                                src={pick.image_url}
                                alt={pick.symbol}
                                className="w-7 h-7 rounded-full object-cover"
                                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                              />
                            ) : (
                              <div
                                className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                                style={{ background: 'var(--bg-card2)', color: 'var(--text-dim)' }}
                              >
                                {pick.symbol?.[0] ?? '?'}
                              </div>
                            )}
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className="font-semibold text-xs" style={{ color: 'var(--text)' }}>
                                  {pick.symbol}
                                </span>
                                <ChainBadge chain={pick.chain} />
                                <span className="flex gap-0.5 text-[10px]" style={{ color: 'var(--text-dim)' }}>
                                  {pick.pick_has_twitter && <span title="Twitter">𝕏</span>}
                                  {pick.pick_has_telegram && <span title="Telegram">✉</span>}
                                  {pick.pick_has_website && <span title="Website">🌐</span>}
                                </span>
                              </div>
                              <div className="text-xs truncate max-w-[120px]" style={{ color: 'var(--text-dim)' }}>
                                {pick.name || `${pick.address.slice(0, 6)}...${pick.address.slice(-4)}`}
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* 推荐 */}
                        <td className="px-3 py-3 text-center">
                          <span
                            className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                            style={{ background: rec.bg, color: rec.color }}
                          >
                            {rec.label}
                          </span>
                        </td>

                        {/* 发现价 */}
                        <td className="px-3 py-3 text-right font-mono text-xs" style={{ color: 'var(--text-dim)' }}>
                          {fmtPrice(pick.pick_price)}
                        </td>

                        {/* 现价 */}
                        <td className="px-3 py-3 text-right font-mono text-xs" style={{ color: 'var(--text)' }}>
                          {fmtPrice(pick.current_price)}
                        </td>

                        {/* 收益 */}
                        <td className="px-3 py-3 text-right font-mono text-xs font-bold" style={{ color: pnlColor }}>
                          {pnl !== null ? `${pnl > 0 ? '+' : ''}${pnl.toFixed(2)}%` : '—'}
                        </td>

                        {/* 市值 */}
                        <td className="px-3 py-3 text-right text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
                          {fmtUsd(pick.current_market_cap || pick.pick_market_cap || 0)}
                        </td>

                        {/* 流动性 */}
                        <td className="px-3 py-3 text-right text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
                          {fmtUsd(pick.pick_liquidity || 0)}
                        </td>

                        {/* 24h量 */}
                        <td className="px-3 py-3 text-right text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
                          {fmtUsd(pick.current_volume_24h || pick.pick_volume_24h || 0)}
                        </td>

                        {/* 涨跌幅 */}
                        <td className="px-3 py-3 text-center">
                          <PctCell value={pick.current_change_5m || null} />
                        </td>
                        <td className="px-3 py-3 text-center">
                          <PctCell value={pick.current_change_1h || null} />
                        </td>
                        <td className="px-3 py-3 text-center">
                          <PctCell value={pick.current_change_24h || null} />
                        </td>

                        {/* 评分 */}
                        <td className="px-3 py-3 text-right">
                          <div className="text-xs font-bold" style={{ color: 'var(--yellow)' }}>
                            {(pick.current_score ?? pick.pick_score)?.toFixed?.(1) ?? '—'}
                          </div>
                          <div className="text-[10px]" style={{ color: 'var(--text-dim)' }}>
                            M{pick.pick_score_m?.toFixed?.(0) ?? '-'} Q{pick.pick_score_q?.toFixed?.(0) ?? '-'} P{pick.pick_score_p?.toFixed?.(0) ?? '-'}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
