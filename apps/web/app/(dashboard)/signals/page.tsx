import { Topbar } from '@/components/layout/topbar'
export default function SignalsPage() {
  return (
    <div>
      <Topbar title="信号中心" subtitle="AI生成交易信号 · 实时更新" />
      <div className="p-6">
        <div className="rounded-xl p-6 border text-sm" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-dim)' }}>
          信号引擎接入中...
        </div>
      </div>
    </div>
  )
}
