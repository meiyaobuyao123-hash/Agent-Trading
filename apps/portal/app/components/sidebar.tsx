'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Flame,
  Zap,
  BarChart3,
} from 'lucide-react'

const NAV_ITEMS = [
  { href: '/overview', icon: LayoutDashboard, label: '总览' },
  { href: '/hot', icon: Flame, label: '热币表现' },
  { href: '/pump', icon: Zap, label: '内盘表现' },
  { href: '/all', icon: BarChart3, label: '综合视图' },
]

export function PortalSidebar() {
  const pathname = usePathname()

  return (
    <aside
      className="fixed top-0 left-0 h-screen flex flex-col z-10"
      style={{
        width: 'var(--sidebar-w)',
        background: 'var(--bg-card)',
        borderRight: '1px solid var(--border)',
      }}
    >
      {/* Logo */}
      <div
        className="flex items-center gap-2.5 px-5 py-4"
        style={{ borderBottom: '1px solid var(--border)', minHeight: 56 }}
      >
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black"
          style={{ background: 'var(--blue)', color: '#fff' }}
        >
          P
        </div>
        <div>
          <div className="text-sm font-bold" style={{ color: 'var(--text)' }}>
            AiTrading
          </div>
          <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
            Performance Portal
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const active = pathname === href
          return (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors"
              style={{
                background: active ? 'rgba(30,128,255,0.12)' : 'transparent',
                color: active ? 'var(--blue)' : 'var(--text-dim)',
                fontWeight: active ? 600 : 400,
              }}
            >
              <Icon size={15} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div
        className="px-5 py-3 text-xs"
        style={{ borderTop: '1px solid var(--border)', color: 'var(--text-dim)' }}
      >
        v1.0.0 · 推荐表现追踪
      </div>
    </aside>
  )
}
