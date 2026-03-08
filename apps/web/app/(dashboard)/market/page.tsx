import { Topbar } from '@/components/layout/topbar'
export default function MarketPage() {
  return (
    <div>
      <Topbar title="行情中心" subtitle="实时代币价格 · 链上分析" />
      <div className="p-6">
        <div className="rounded-xl p-6 border text-sm" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-dim)' }}>
          行情数据接入中...
        </div>
      </div>
    </div>
  )
}
