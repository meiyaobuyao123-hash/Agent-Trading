'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  TrendingUp,
  Zap,
  Brain,
  Briefcase,
  Star,
  Settings,
} from 'lucide-react'

const navItems = [
  { href: '/', label: '总览', icon: LayoutDashboard },
  { href: '/market', label: '行情', icon: TrendingUp },
  { href: '/signals', label: '信号', icon: Zap },
  { href: '/strategy', label: '策略', icon: Brain },
  { href: '/portfolio', label: '持仓', icon: Briefcase },
  { href: '/official', label: '官方组合', icon: Star },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="fixed left-0 top-0 h-full w-56 border-r flex flex-col" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      {/* Logo */}
      <div className="px-5 py-6 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="text-lg font-black" style={{ color: 'var(--yellow)' }}>
          AiTrading
        </div>
        <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>
          AI驱动的加密交易
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                active
                  ? 'text-white'
                  : 'hover:text-white'
              )}
              style={{
                background: active ? 'rgba(240,185,11,0.12)' : undefined,
                color: active ? 'var(--yellow)' : 'var(--text-dim)',
                borderLeft: active ? '2px solid var(--yellow)' : '2px solid transparent',
              }}
            >
              <Icon size={16} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Bottom */}
      <div className="px-3 pb-4">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all hover:text-white"
          style={{ color: 'var(--text-dim)' }}
        >
          <Settings size={16} />
          设置
        </Link>
      </div>
    </aside>
  )
}
