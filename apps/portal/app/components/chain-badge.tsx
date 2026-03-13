const CHAIN_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  solana: { label: 'SOL', color: '#9945FF', bg: 'rgba(153,69,255,0.1)' },
  bsc: { label: 'BSC', color: '#F3BA2F', bg: 'rgba(243,186,47,0.1)' },
  base: { label: 'BASE', color: '#0052FF', bg: 'rgba(0,82,255,0.1)' },
  eth: { label: 'ETH', color: '#627EEA', bg: 'rgba(98,126,234,0.1)' },
}

interface ChainBadgeProps {
  chain: string
}

export function ChainBadge({ chain }: ChainBadgeProps) {
  const cfg = CHAIN_CONFIG[chain] ?? { label: chain.toUpperCase(), color: 'var(--text-dim)', bg: 'rgba(128,128,128,0.1)' }

  return (
    <span
      className="text-xs font-bold px-1.5 py-0.5 rounded"
      style={{ color: cfg.color, background: cfg.bg }}
    >
      {cfg.label}
    </span>
  )
}
