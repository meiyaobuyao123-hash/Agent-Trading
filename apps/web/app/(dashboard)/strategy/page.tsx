import { Topbar } from '@/components/layout/topbar'
export default function StrategyPage() {
  return (
    <div>
      <Topbar title="策略中心" subtitle="AI生成策略 · 自动执行" />
      <div className="p-6">
        <div className="rounded-xl p-6 border text-sm" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-dim)' }}>
          策略引擎开发中...
        </div>
      </div>
    </div>
  )
}
