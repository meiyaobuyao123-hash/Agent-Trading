import { fmtPct, pctColor, pctBg } from '../lib/utils'

interface PctCellProps {
  value?: number | null
  bold?: boolean
}

export function PctCell({ value, bold }: PctCellProps) {
  if (value === null || value === undefined) {
    return (
      <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
        -
      </span>
    )
  }

  return (
    <span
      className="text-xs px-1.5 py-0.5 rounded"
      style={{
        color: pctColor(value),
        background: pctBg(value),
        fontWeight: bold || value >= 100 ? 700 : 500,
      }}
    >
      {fmtPct(value)}
    </span>
  )
}
