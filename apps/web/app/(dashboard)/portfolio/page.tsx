import { Topbar } from '@/components/layout/topbar'
export default function PortfolioPage() {
  return (
    <div>
      <Topbar title="持仓管理" subtitle="当前持仓 · P&L统计" />
      <div className="p-6">
        <div className="rounded-xl p-6 border text-sm" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-dim)' }}>
          连接钱包后查看持仓...
        </div>
      </div>
    </div>
  )
}
