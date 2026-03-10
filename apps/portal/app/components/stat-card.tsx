interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  color?: string
}

export function StatCard({ label, value, sub, color }: StatCardProps) {
  return (
    <div
      className="rounded-xl p-4"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="text-xs font-medium mb-2" style={{ color: 'var(--text-dim)' }}>
        {label}
      </div>
      <div
        className="text-2xl font-bold"
        style={{ color: color ?? 'var(--text)' }}
      >
        {value}
      </div>
      {sub && (
        <div className="text-xs mt-1" style={{ color: 'var(--text-dim)' }}>
          {sub}
        </div>
      )}
    </div>
  )
}
