/** 格式化 USD 价格 */
export function fmtUsd(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`
  if (v >= 1) return `$${v.toFixed(2)}`
  if (v >= 0.01) return `$${v.toFixed(4)}`
  if (v >= 0.0001) return `$${v.toFixed(6)}`
  if (v > 0) return `$${v.toFixed(8)}`
  return '-'
}

/** 格式化 SOL 价格 */
export function fmtSol(v: number): string {
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M SOL`
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K SOL`
  return `${v.toFixed(1)} SOL`
}

/** 格式化日期为 M月D日 */
export function fmtDate(s?: string): string {
  if (!s) return '-'
  const d = new Date(s + 'T00:00:00')
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/** 格式化百分比 */
export function fmtPct(v?: number | null): string {
  if (v === null || v === undefined) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(1)}%`
}

/** 涨跌颜色 */
export function pctColor(v?: number | null): string {
  if (v === null || v === undefined) return 'var(--text-dim)'
  if (v >= 100) return 'var(--green)'
  if (v >= 0) return 'var(--green)'
  return 'var(--red)'
}

/** 涨跌背景色 */
export function pctBg(v?: number | null): string {
  if (v === null || v === undefined) return 'transparent'
  if (v >= 100) return 'rgba(14,203,129,0.15)'
  if (v >= 0) return 'rgba(14,203,129,0.08)'
  return 'rgba(246,70,93,0.08)'
}
