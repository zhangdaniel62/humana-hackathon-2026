import type { ReactNode } from 'react'

export interface TooltipState {
  x: number
  y: number
  content: ReactNode
}

/**
 * Floating readout following the pointer inside a chart. Values lead
 * (high-contrast), series names follow; series keys are short color strokes.
 */
export function ChartTooltip({ state, width }: { state: TooltipState; width: number }) {
  const flip = state.x > width * 0.62
  return (
    <div
      className="pointer-events-none absolute z-10 max-w-64 rounded-md border border-border-primary bg-bg-primary px-2.5 py-2 shadow-float"
      style={{
        left: state.x,
        top: state.y,
        transform: `translate(${flip ? 'calc(-100% - 10px)' : '10px'}, -50%)`,
      }}
    >
      {state.content}
    </div>
  )
}

export function TooltipRow({
  seriesColor,
  dashed,
  label,
  value,
}: {
  seriesColor?: string
  dashed?: boolean
  label: string
  value: string
}) {
  return (
    <div className="flex items-center gap-1.5 whitespace-nowrap text-mini">
      {seriesColor && (
        <svg width={10} height={2} aria-hidden="true" className="shrink-0">
          <line
            x1={0}
            y1={1}
            x2={10}
            y2={1}
            stroke={seriesColor}
            strokeWidth={2}
            strokeDasharray={dashed ? '3 2' : undefined}
          />
        </svg>
      )}
      <span className="font-medium text-text-primary">{value}</span>
      <span className="text-text-tertiary">{label}</span>
    </div>
  )
}

export function TooltipTitle({ children }: { children: ReactNode }) {
  return <div className="mb-1 text-mini font-medium text-text-secondary">{children}</div>
}
