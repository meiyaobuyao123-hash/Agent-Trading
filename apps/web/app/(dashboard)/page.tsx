import { Topbar } from '@/components/layout/topbar'
import { TrendingUp, Zap, Star, Briefcase } from 'lucide-react'

const stats = [
  { label: '官方信号', value: '12', sub: '今日活跃', color: 'var(--yellow)', icon: Zap },
  { label: '策略运行中', value: '3', sub: '自动执行', color: 'var(--green)', icon: TrendingUp },
  { label: '官方组合', value: '8', sub: '追踪代币', color: 'var(--blue)', icon: Star },
  { label: '持仓价值', value: '$—', sub: '连接钱包后显示', color: 'var(--orange)', icon: Briefcase },
]

export default function DashboardPage() {
  return (
    <div>
      <Topbar title="总览" subtitle="实时行情 · AI信号 · 策略追踪" />
      <div className="p-6 space-y-6">

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          {stats.map(({ label, value, sub, color, icon: Icon }) => (
            <div
              key={label}
              className="rounded-xl p-4 border"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
            >
              <div className="flex items-center gap-2 mb-3">
                <Icon size={14} color={color} />
                <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{label}</span>
              </div>
              <div className="text-2xl font-black" style={{ color }}>{value}</div>
              <div className="text-xs mt-1" style={{ color: 'var(--text-dim)' }}>{sub}</div>
            </div>
          ))}
        </div>

        {/* Placeholder sections */}
        <div className="grid grid-cols-2 gap-4">
          <div
            className="rounded-xl p-4 border"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', minHeight: 200 }}
          >
            <div className="text-sm font-bold mb-3" style={{ color: 'var(--text)' }}>
              ⚡ 最新信号
            </div>
            <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
              接入数据中...
            </div>
          </div>
          <div
            className="rounded-xl p-4 border"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', minHeight: 200 }}
          >
            <div className="text-sm font-bold mb-3" style={{ color: 'var(--text)' }}>
              🏛️ 官方策略组合
            </div>
            <div className="text-xs" style={{ color: 'var(--text-dim)' }}>
              接入数据中...
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
