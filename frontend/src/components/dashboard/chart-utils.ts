import { useLayoutEffect, useRef, useState, type RefObject } from 'react'
import type { DashboardBucket } from '@/lib/operationsDashboard'
import { formatDay, formatMonth } from '@/lib/format'

/** Series paint — charts only ever use the accent and the muted neutral. */
export const chartColors = {
  accent: 'var(--color-accent)',
  muted: 'var(--color-chart-muted)',
  grid: 'var(--color-border-secondary)',
  axis: 'var(--color-border-primary)',
  baseline: 'var(--color-text-quaternary)',
  tickText: 'var(--color-text-quaternary)',
  /** Panel surface — used for the 2px gaps/rings that separate marks. */
  surface: 'var(--color-bg-secondary)',
} as const

export function periodLabel(iso: string, bucket: DashboardBucket): string {
  return bucket === 'month' ? formatMonth(iso) : `Week of ${formatDay(iso)}`
}

/** Observes the rendered width of a block so SVGs draw at pixel size. */
export function useMeasuredWidth(): { ref: RefObject<HTMLDivElement | null>; width: number } {
  const ref = useRef<HTMLDivElement | null>(null)
  const [width, setWidth] = useState(0)

  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver((entries) => {
      setWidth(entries[0].contentRect.width)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return { ref, width }
}

/** Round tick steps to 1/2/5×10ⁿ and return ~`count` clean ticks covering the domain. */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return []
  if (min === max) {
    max = min + 1
    min = Math.max(0, min - 1)
  }
  const rawStep = (max - min) / count
  const power = 10 ** Math.floor(Math.log10(rawStep))
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= rawStep) ?? 10 * power
  const first = Math.ceil(min / step) * step
  const ticks: number[] = []
  for (let v = first; v <= max + step / 1000; v += step) {
    ticks.push(Math.round(v * 1000) / 1000)
  }
  return ticks
}
