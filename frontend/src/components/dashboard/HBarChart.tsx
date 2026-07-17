import { useState, type PointerEvent, type ReactNode } from 'react'
import { ChartTooltip, type TooltipState } from './chart-common'
import { chartColors, useMeasuredWidth } from './chart-utils'

export interface HBarItem {
  label: string
  value: number
  /** Formatted value shown at the bar tip. */
  display: string
  /** Tooltip body for this bar. */
  tooltip: ReactNode
  /** 0–1 opacity step for single-hue sequential jobs (funnel stages). */
  opacity?: number
}

export interface HBarChartProps {
  items: HBarItem[]
  /** Bars scale against this; defaults to the max item value. */
  maxValue?: number
  /** Width of the category-label column. */
  labelWidth?: number
}

/**
 * Horizontal magnitude bars in the single accent hue — rep workload, funnel
 * stages. Direct value labels at the tips; hover carries the detail.
 */
export function HBarChart({ items, maxValue, labelWidth = 104 }: HBarChartProps) {
  const { ref, width } = useMeasuredWidth()
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const max = maxValue ?? Math.max(...items.map((item) => item.value), 1)

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>, item: HBarItem) => {
    const rect = event.currentTarget.closest('[data-hbar-root]')?.getBoundingClientRect()
    if (!rect) return
    setTooltip({
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
      content: item.tooltip,
    })
  }

  return (
    <div ref={ref} data-hbar-root className="relative flex flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.label}
          className="flex h-6 items-center gap-2 rounded-sm"
          onPointerMove={(event) => handlePointerMove(event, item)}
          onPointerLeave={() => setTooltip(null)}
        >
          <div
            className="shrink-0 truncate text-mini text-text-secondary"
            style={{ width: labelWidth }}
          >
            {item.label}
          </div>
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <div
              className="h-3.5 rounded-r-[4px]"
              style={{
                width: `${Math.max(0.5, (item.value / max) * 100 * 0.82)}%`,
                background: chartColors.accent,
                opacity: item.opacity ?? 1,
              }}
            />
            <span className="shrink-0 text-mini font-medium text-text-secondary tabular-nums">
              {item.display}
            </span>
          </div>
        </div>
      ))}
      {tooltip && <ChartTooltip state={tooltip} width={width} />}
    </div>
  )
}
