import type { Metadata } from 'next'
import './globals.css'
import { PortalSidebar } from './components/sidebar'

export const metadata: Metadata = {
  title: 'AiTrading Portal — 推荐表现监控',
  description: '推荐代币表现追踪系统',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <PortalSidebar />
        <main style={{ marginLeft: 'var(--sidebar-w)', minHeight: '100vh', background: 'var(--bg)' }}>
          {children}
        </main>
      </body>
    </html>
  )
}
