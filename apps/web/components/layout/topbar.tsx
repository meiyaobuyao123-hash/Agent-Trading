'use client'

import { cn } from '@/lib/utils'

interface TopbarProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}

export function Topbar({ title, subtitle, actions }: TopbarProps) {
  return (
    <div
      className="flex items-center justify-between px-6 py-4 border-b sticky top-0 z-10"
      style={{ background: 'var(--bg)', borderColor: 'var(--border)' }}
    >
      <div>
        <h1 className="text-base font-bold" style={{ color: 'var(--text)' }}>{title}</h1>
        {subtitle && (
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  )
}
