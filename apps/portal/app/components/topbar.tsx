interface TopbarProps {
  title: string
  subtitle?: string
  action?: React.ReactNode
}

export function Topbar({ title, subtitle, action }: TopbarProps) {
  return (
    <div
      className="flex items-center justify-between px-6 py-4"
      style={{
        borderBottom: '1px solid var(--border)',
        minHeight: 56,
        background: 'var(--bg)',
      }}
    >
      <div>
        <h1 className="text-base font-bold" style={{ color: 'var(--text)' }}>
          {title}
        </h1>
        {subtitle && (
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>
            {subtitle}
          </p>
        )}
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}
