import type { HTMLAttributes, ReactNode } from 'react'
import { ArrowDown, ArrowRight, ArrowUp } from 'lucide-react'
import { cn } from '@/lib/cn'
import { Panel } from './Panel'

export interface StatTileDelta {
  /** Already-formatted comparison, e.g. "9.8% lower than baseline" or "+0.8 pp". */
  text: string
  /** Colors the delta: good = success, bad = danger, neutral = quiet text. */
  tone: 'good' | 'bad' | 'neutral'
  /** Actual direction of movement — independent of whether that's good. */
  direction: 'up' | 'down' | 'flat'
}

export interface StatTileProps extends HTMLAttributes<HTMLDivElement> {
  label: string
  /** Already-formatted value; pass "—" for null figures. */
  value: string
  delta?: StatTileDelta
  /** Quiet context line, e.g. "7-day matured cohort · n = 1,266". */
  caption?: ReactNode
  /** Recent per-period values, drawn as a small accent sparkline. */
  sparkline?: number[]
}

const deltaToneClasses: Record<StatTileDelta['tone'], string> = {
  good: 'text-success',
  bad: 'text-danger',
  neutral: 'text-text-tertiary',
}

const deltaIcons = { up: ArrowUp, down: ArrowDown, flat: ArrowRight } as const

function Sparkline({ values }: { values: number[] }) {
  const width = 84
  const height = 28
  const pad = 3
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const x = (i: number) => pad + (i / (values.length - 1)) * (width - pad * 2)
  const y = (v: number) => height - pad - ((v - min) / span) * (height - pad * 2)
  const d = values.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const last = values[values.length - 1]
  return (
    <svg width={width} height={height} aria-hidden="true" className="shrink-0">
      <path d={d} fill="none" stroke="var(--color-accent)" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(values.length - 1)} cy={y(last)} r={2.5} fill="var(--color-accent)" stroke="var(--color-bg-secondary)" strokeWidth={1.5} />
    </svg>
  )
}

/** Dashboard KPI tile: quiet label, prominent value, direction-aware delta. */
export function StatTile({ label, value, delta, caption, sparkline, className, ...props }: StatTileProps) {
  const DeltaIcon = delta ? deltaIcons[delta.direction] : null
  return (
    <Panel {...props} className={cn('flex flex-col gap-1', className)}>
      <div className="text-mini font-medium text-text-tertiary">{label}</div>
      <div className="flex items-end justify-between gap-3">
        <div className="text-title2 text-text-primary">{value}</div>
        {sparkline && sparkline.length > 1 && <Sparkline values={sparkline} />}
      </div>
      {delta && DeltaIcon && (
        <div className={cn('flex items-center gap-1 text-mini font-medium', deltaToneClasses[delta.tone])}>
          <DeltaIcon size={12} strokeWidth={2} aria-hidden="true" />
          {delta.text}
        </div>
      )}
      {caption && <div className="text-micro text-text-quaternary">{caption}</div>}
    </Panel>
  )
}
