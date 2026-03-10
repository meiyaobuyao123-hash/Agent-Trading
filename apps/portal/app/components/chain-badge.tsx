const CHAIN_CONFIG: Record<string, { label: string; color: string }> = {
  solana: { label: 'SOL', color: 'var(--purple)' },
  bsc: { label: 'BSC', color: 'var(--yellow)' },
  base: { label: 'BASE', color: 'var(--blue)' },
}

interface ChainBadgeProps {
  chain: string
}

export function ChainBadge({ chain }: ChainBadgeProps) {
  const cfg = CHAIN_CONFIG[chain] ?? { label: chain.toUpperCase(), color: 'var(--text-dim)' }

  return (
    <span
      className="text-xs font-bold px-1.5 py-0.5 rounded"
      style={{ color: cfg.color, background: `${cfg.color}18` }}
    >
      {cfg.label}
    </span>
  )
}
