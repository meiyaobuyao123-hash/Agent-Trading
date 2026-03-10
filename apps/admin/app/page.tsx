import { AdminTopbar } from './components/topbar'
import {
  Star,
  Zap,
  Activity,
  Database,
  Globe,
  Shield,
  CheckCircle,
  AlertCircle,
} from 'lucide-react'

const STATS = [
  { label: '官方组合代币', value: '—', sub: '接入 Supabase 后更新', color: 'var(--yellow)', icon: Star },
  { label: '活跃信号', value: '—', sub: '聪明钱信号', color: 'var(--green)', icon: Zap },
  { label: 'API 状态', value: '正常', sub: 'Binance + OKX', color: 'var(--green)', icon: Activity },
  { label: '数据库', value: 'Supabase', sub: '免费版 · 未配置', color: 'var(--text-dim)', icon: Database },
]

const SERVICES = [
  {
    name: 'Binance Skills API',
    url: 'https://web3.binance.com/bapi/defi/v1/public/',
    status: 'active',
    note: '非官方 · 无需认证 · Cloudflare保护',
    latency: '~1242ms',
  },
  {
    name: 'OKX DEX v6 API',
    url: 'https://www.okx.com/api/v6/dex/aggregator/',
    status: 'active',
    note: '需签名 · HMAC SHA256 · 仅服务端调用',
    latency: '~1275ms',
  },
  {
    name: 'Supabase',
    url: 'https://supabase.com',
    status: 'pending',
    note: '需配置 SUPABASE_URL + SERVICE_ROLE_KEY',
    latency: '—',
  },
  {
    name: 'Upstash Redis',
    url: 'https://upstash.com',
    status: 'pending',
    note: '需配置 UPSTASH_REDIS_REST_URL',
    latency: '—',
  },
]

const ENV_VARS = [
  { key: 'NEXT_PUBLIC_SUPABASE_URL', required: true },
  { key: 'NEXT_PUBLIC_SUPABASE_ANON_KEY', required: true },
  { key: 'SUPABASE_SERVICE_ROLE_KEY', required: true },
  { key: 'UPSTASH_REDIS_REST_URL', required: false },
  { key: 'UPSTASH_REDIS_REST_TOKEN', required: false },
  { key: 'OKX_API_KEY', required: false },
  { key: 'OKX_SECRET_KEY', required: false },
  { key: 'OKX_PASSPHRASE', required: false },
  { key: 'ANTHROPIC_API_KEY', required: false },
]

export default function AdminDashboard() {
  return (
    <div>
      <AdminTopbar title="管理总览" subtitle="系统状态 · 服务健康 · 环境配置" />
      <div className="p-6 space-y-6">

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          {STATS.map(({ label, value, sub, color, icon: Icon }) => (
            <div
              key={label}
              className="rounded-xl p-4 border"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
            >
              <div className="flex items-center gap-2 mb-3">
                <Icon size={13} color={color} />
                <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{label}</span>
              </div>
              <div className="text-xl font-black" style={{ color }}>{value}</div>
              <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{sub}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-5">
          {/* Service Status */}
          <div
            className="rounded-xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
          >
            <div
              className="px-5 py-3 text-sm font-semibold flex items-center gap-2"
              style={{ borderBottom: '1px solid var(--border)', color: 'var(--text)' }}
            >
              <Globe size={14} color="var(--blue)" />
              外部服务状态
            </div>
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {SERVICES.map((s) => (
                <div key={s.name} className="px-5 py-3.5 flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    {s.status === 'active' ? (
                      <CheckCircle size={14} color="var(--green)" />
                    ) : (
                      <AlertCircle size={14} color="var(--yellow)" />
                    )}
                    <div>
                      <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>{s.name}</div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{s.note}</div>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div
                      className="text-xs font-semibold"
                      style={{ color: s.status === 'active' ? 'var(--green)' : 'var(--yellow)' }}
                    >
                      {s.status === 'active' ? '运行中' : '待配置'}
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{s.latency}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Env Vars */}
          <div
            className="rounded-xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
          >
            <div
              className="px-5 py-3 text-sm font-semibold flex items-center gap-2"
              style={{ borderBottom: '1px solid var(--border)', color: 'var(--text)' }}
            >
              <Shield size={14} color="var(--orange)" />
              环境变量清单
            </div>
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {ENV_VARS.map(({ key, required }) => (
                <div key={key} className="px-5 py-2.5 flex items-center justify-between">
                  <code
                    className="text-xs font-mono"
                    style={{ color: 'var(--text)' }}
                  >
                    {key}
                  </code>
                  <span
                    className="text-xs px-2 py-0.5 rounded"
                    style={{
                      color: required ? 'var(--red)' : 'var(--text-dim)',
                      background: required ? 'rgba(246,70,93,0.1)' : 'var(--bg-card2)',
                    }}
                  >
                    {required ? '必填' : '可选'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Quick Links */}
        <div
          className="rounded-xl border p-5"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
        >
          <div className="text-sm font-semibold mb-4" style={{ color: 'var(--text)' }}>
            快速导航
          </div>
          <div className="grid grid-cols-3 gap-3 text-sm">
            {[
              { href: '/portfolio', label: '📋 官方组合管理', sub: '添加/移除/退出代币' },
              { href: '/signals', label: '⚡ 信号管理', sub: '查看聪明钱信号' },
              { href: '/health', label: '📡 系统健康', sub: 'API 实时延迟监控' },
            ].map(({ href, label, sub }) => (
              <a
                key={href}
                href={href}
                className="flex flex-col gap-1 px-4 py-3 rounded-lg transition-colors hover:bg-white/[0.04] cursor-pointer"
                style={{ background: 'var(--bg-card2)' }}
              >
                <span style={{ color: 'var(--text)' }}>{label}</span>
                <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{sub}</span>
              </a>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}
