'use client'

import type { TokenPerformance } from '../lib/queries'
import { ChainBadge } from './chain-badge'
import { PctCell } from './pct-cell'
import { fmtDate, fmtUsd, fmtSol } from '../lib/utils'

/** 展示的关键天数列 */
const DAY_COLS = [1, 2, 3, 5, 7, 14, 30]

interface PerformanceTableProps {
  data: TokenPerformance[]
  showSource?: boolean
}

export function PerformanceTable({ data, showSource }: PerformanceTableProps) {
  if (data.length === 0) {
    return (
      <div className="py-14 text-center" style={{ color: 'var(--text-dim)' }}>
        <div className="text-3xl mb-3">📊</div>
        <div className="text-sm">暂无追踪数据</div>
        <div className="text-xs mt-1">等待后端 performance_tracker 采集数据</div>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" style={{ minWidth: 900 }}>
        <thead>
          <tr
            className="text-xs font-semibold"
            style={{
              color: 'var(--text-dim)',
              borderBottom: '1px solid var(--border)',
              background: 'var(--bg-card2)',
            }}
          >
            <th className="text-left px-4 py-3">#</th>
            <th className="text-left px-4 py-3">代币</th>
            {showSource && <th className="text-left px-3 py-3">来源</th>}
            <th className="text-left px-3 py-3">日期</th>
            <th className="text-right px-3 py-3">评分</th>
            <th className="text-right px-3 py-3">推荐价</th>
            <th className="text-right px-3 py-3">当前</th>
            {DAY_COLS.map(d => (
              <th key={d} className="text-center px-2 py-3">
                {d}D
              </th>
            ))}
            <th className="text-center px-3 py-3">最佳</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => {
            const highs = row.daily_highs ?? {}
            return (
              <tr
                key={row.id}
                style={{
                  borderBottom: i < data.length - 1 ? '1px solid var(--border)' : 'none',
                }}
              >
                {/* 排名 */}
                <td className="px-4 py-3 text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
                  {row.rank ?? '-'}
                </td>

                {/* 代币信息 */}
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <ChainBadge chain={row.chain} />
                    <div>
                      <div className="font-semibold" style={{ color: 'var(--text)' }}>
                        {row.symbol?.toUpperCase() || '-'}
                      </div>
                      <div className="text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
                        {row.address.slice(0, 6)}...{row.address.slice(-4)}
                      </div>
                    </div>
                  </div>
                </td>

                {/* 来源 */}
                {showSource && (
                  <td className="px-3 py-3">
                    <span
                      className="text-xs font-semibold px-2 py-0.5 rounded-full"
                      style={{
                        color: row.source === 'pump' ? 'var(--orange)' : 'var(--blue)',
                        background: row.source === 'pump' ? 'rgba(255,156,62,0.12)' : 'rgba(30,128,255,0.12)',
                      }}
                    >
                      {row.source === 'pump' ? '内盘' : '热币'}
                    </span>
                  </td>
                )}

                {/* 日期 */}
                <td className="px-3 py-3 text-xs" style={{ color: 'var(--text-dim)' }}>
                  {fmtDate(row.pick_date)}
                </td>

                {/* 评分 */}
                <td className="px-3 py-3 text-right">
                  <span
                    className="text-xs font-bold"
                    style={{
                      color: (row.score ?? 0) >= 72 ? 'var(--green)' : (row.score ?? 0) >= 50 ? 'var(--yellow)' : 'var(--text-dim)',
                    }}
                  >
                    {row.score?.toFixed(0) ?? '-'}
                  </span>
                </td>

                {/* 推荐价 */}
                <td className="px-3 py-3 text-right text-xs font-mono" style={{ color: 'var(--text-dim)' }}>
                  {row.denomination === 'usd' ? fmtUsd(row.price_at_pick) : fmtSol(row.price_at_pick)}
                </td>

                {/* 当前价 */}
                <td className="px-3 py-3 text-right">
                  {row.current_price ? (
                    <div>
                      <div className="text-xs font-mono" style={{ color: 'var(--text)' }}>
                        {row.denomination === 'usd' ? fmtUsd(row.current_price) : fmtSol(row.current_price)}
                      </div>
                      <PctCell value={row.current_pct} />
                    </div>
                  ) : (
                    <span className="text-xs" style={{ color: 'var(--text-dim)' }}>-</span>
                  )}
                </td>

                {/* 各天涨幅 */}
                {DAY_COLS.map(d => {
                  const dayData = highs[String(d)]
                  return (
                    <td key={d} className="px-2 py-3 text-center">
                      <PctCell value={dayData?.pct ?? null} bold={d === 7 || d === 30} />
                    </td>
                  )
                })}

                {/* 最佳 */}
                <td className="px-3 py-3 text-center">
                  {row.best_pct != null ? (
                    <div>
                      <PctCell value={row.best_pct} bold />
                      <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>
                        D{row.best_day}
                      </div>
                    </div>
                  ) : (
                    <span className="text-xs" style={{ color: 'var(--text-dim)' }}>-</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
