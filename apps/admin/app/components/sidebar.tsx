'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Star,
  Zap,
  Users,
  Settings,
  Activity,
  Cpu,
  ArrowRightLeft,
  Brain,
} from 'lucide-react'

const NAV_ITEMS = [
  { href: '/', icon: LayoutDashboard, label: '总览' },
  { href: '/portfolio', icon: Star, label: '官方组合' },
  { href: '/signals', icon: Zap, label: '信号管理' },
  { href: '/engine', icon: Cpu, label: '信号引擎' },
  { href: '/execute', icon: ArrowRightLeft, label: 'DEX 执行器' },
  { href: '/strategies', icon: Brain, label: '策略管理' },
  { href: '/users', icon: Users, label: '用户管理' },
  { href: '/health', icon: Activity, label: '系统健康' },
  { href: '/settings', icon: Settings, label: '配置' },
]

export function AdminSidebar() {
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
          style={{ background: 'var(--yellow)', color: '#000' }}
        >
          A
        </div>
        <div>
          <div className="text-sm font-bold" style={{ color: 'var(--text)' }}>
            AiTrading
          </div>
          <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
            Admin Panel
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
                background: active ? 'rgba(240,185,11,0.12)' : 'transparent',
                color: active ? 'var(--yellow)' : 'var(--text-dim)',
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
        style={{
          borderTop: '1px solid var(--border)',
          color: 'var(--text-dim)',
        }}
      >
        v1.0.0 · 仅内部使用
      </div>
    </aside>
  )
}
