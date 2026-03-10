'use client'

import type { ChainFilter } from '@/hooks/useMarketRank'

const chains: { label: string; value: ChainFilter }[] = [
  { label: 'BSC', value: '56' },
  { label: 'ETH', value: '1' },
  { label: 'SOL', value: 'CT_501' },
]

interface ChainFilterTabsProps {
  value: ChainFilter
  onChange: (v: ChainFilter) => void
}

export function ChainFilterTabs({ value, onChange }: ChainFilterTabsProps) {
  return (
    <div className="flex gap-1.5">
      {chains.map((c) => {
        const active = c.value === value
        return (
          <button
            key={c.value}
            onClick={() => onChange(c.value)}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
            style={{
              background: active ? 'rgba(240,185,11,0.15)' : 'var(--bg-card2)',
              color: active ? 'var(--yellow)' : 'var(--text-dim)',
              border: `1px solid ${active ? 'rgba(240,185,11,0.4)' : 'transparent'}`,
            }}
          >
            {c.label}
          </button>
        )
      })}
    </div>
  )
}
