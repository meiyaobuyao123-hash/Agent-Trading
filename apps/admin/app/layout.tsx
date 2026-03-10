import type { Metadata } from 'next'
import './globals.css'
import { AdminSidebar } from './components/sidebar'

export const metadata: Metadata = {
  title: 'AiTrading Admin',
  description: '官方管理后台',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <AdminSidebar />
        <main style={{ marginLeft: 'var(--sidebar-w)', minHeight: '100vh', background: 'var(--bg)' }}>
          {children}
        </main>
      </body>
    </html>
  )
}
