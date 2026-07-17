import { useMemo, useState, type PointerEvent } from 'react'
import type { DashboardBucket, TrendPoint } from '@/lib/operationsDashboard'
import { formatDay, formatMonth } from '@/lib/format'
import { ChartTooltip, TooltipRow, TooltipTitle } from './chart-common'
import { chartColors, niceTicks, periodLabel, useMeasuredWidth } from './chart-utils'

export interface TrendLineChartProps {
  points: TrendPoint[]
  bucket: DashboardBucket
  /** Display-scaled value for a period (rates already ×100); null = gap. */
  accessor: (point: TrendPoint) => number | null
  seriesLabel: string
  /** Display-scaled constant reference; drawn as a neutral dashed line. */
  baseline: number | null
  baselineLabel: string
  /** Tooltip/direct-label formatting for a display-scaled value. */
  formatValue: (value: number) => string
  /** Axis tick formatting; defaults to the raw number. */
  formatTick?: (value: number) => string
  /** Extra per-period tooltip rows (cohort denominators, sample sizes…). */
  tooltipExtras?: (point: TrendPoint) => Array<{ label: string; value: string }>
  height?: number
}

const MARGIN = { top: 14, right: 14, bottom: 22, left: 40 }

function toMs(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}

/** Single-series accent line over time with a dashed synthetic baseline. */
export function TrendLineChart({
  points,
  bucket,
  accessor,
  seriesLabel,
  baseline,
  baselineLabel,
  formatValue,
  formatTick = (v) => String(v),
  tooltipExtras,
  height = 190,
}: TrendLineChartProps) {
  const { ref, width } = useMeasuredWidth()
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const innerWidth = Math.max(0, width - MARGIN.left - MARGIN.right)
  const innerHeight = height - MARGIN.top - MARGIN.bottom

  const geometry = useMemo(() => {
    const values = points.map(accessor)
    const present = values.filter((v): v is number => v !== null)
    if (present.length === 0 || innerWidth <= 0) return null

    const all = baseline !== null ? [...present, baseline] : present
    let lo = Math.min(...all)
    let hi = Math.max(...all)
    const pad = (hi - lo || Math.abs(hi) || 1) * 0.18
    lo = Math.min(0, lo) === lo && lo >= 0 ? Math.max(0, lo - pad) : lo - pad
    hi = hi + pad
    const ticks = niceTicks(lo, hi, 4)
    const domainLo = Math.min(lo, ticks[0] ?? lo)
    const domainHi = Math.max(hi, ticks[ticks.length - 1] ?? hi)

    const times = points.map((p) => toMs(p.period_start))
    const tMin = Math.min(...times)
    const tMax = Math.max(...times)
    const x = (i: number) =>
      MARGIN.left + (tMax === tMin ? innerWidth / 2 : ((times[i] - tMin) / (tMax - tMin)) * innerWidth)
    const y = (v: number) =>
      MARGIN.top + innerHeight - ((v - domainLo) / (domainHi - domainLo || 1)) * innerHeight

    // Break the path at null values so missing periods stay visible gaps.
    let path = ''
    let pen = false
    values.forEach((v, i) => {
      if (v === null) {
        pen = false
        return
      }
      path += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`
      pen = true
    })

    let lastIndex = -1
    for (let i = values.length - 1; i >= 0; i--) {
      if (values[i] !== null) {
        lastIndex = i
        break
      }
    }

    const tickCount = Math.max(2, Math.min(6, Math.floor(innerWidth / 90)))
    const xTickIndexes = [...new Set(
      Array.from({ length: tickCount }, (_, k) =>
        Math.round((k / (tickCount - 1)) * (points.length - 1)),
      ),
    )]

    return { values, x, y, ticks, path, lastIndex, xTickIndexes }
  }, [points, accessor, baseline, innerWidth, innerHeight])

  if (points.length === 0) return null

  const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (!geometry) return
    const rect = event.currentTarget.getBoundingClientRect()
    const px = event.clientX - rect.left
    let nearest: number | null = null
    let best = Infinity
    geometry.values.forEach((v, i) => {
      if (v === null) return
      const distance = Math.abs(geometry.x(i) - px)
      if (distance < best) {
        best = distance
        nearest = i
      }
    })
    setHoverIndex(nearest)
  }

  const hover =
    geometry && hoverIndex !== null && geometry.values[hoverIndex] !== null
      ? { index: hoverIndex, value: geometry.values[hoverIndex] }
      : null

  return (
    <div ref={ref} className="relative">
      {geometry ? (
        <svg
          width={width}
          height={height}
          className="block touch-none"
          aria-hidden="true"
          onPointerMove={handlePointerMove}
          onPointerLeave={() => setHoverIndex(null)}
        >
          {geometry.ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                x2={width - MARGIN.right}
                y1={geometry.y(tick)}
                y2={geometry.y(tick)}
                stroke={chartColors.grid}
                strokeWidth={1}
              />
              <text
                x={MARGIN.left - 8}
                y={geometry.y(tick)}
                textAnchor="end"
                dominantBaseline="middle"
                className="fill-text-quaternary text-micro tabular-nums"
              >
                {formatTick(tick)}
              </text>
            </g>
          ))}
          {geometry.xTickIndexes.map((i) => (
            <text
              key={points[i].period_start}
              x={geometry.x(i)}
              y={height - 6}
              textAnchor="middle"
              className="fill-text-quaternary text-micro"
            >
              {bucket === 'month' ? formatMonth(points[i].period_start).slice(0, 3) : formatDay(points[i].period_start)}
            </text>
          ))}
          {baseline !== null && (
            <line
              x1={MARGIN.left}
              x2={width - MARGIN.right}
              y1={geometry.y(baseline)}
              y2={geometry.y(baseline)}
              stroke={chartColors.baseline}
              strokeWidth={1}
              strokeDasharray="4 3"
            />
          )}
          <path
            d={geometry.path}
            fill="none"
            stroke={chartColors.accent}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          {hover && (
            <line
              x1={geometry.x(hover.index)}
              x2={geometry.x(hover.index)}
              y1={MARGIN.top}
              y2={height - MARGIN.bottom}
              stroke={chartColors.axis}
              strokeWidth={1}
            />
          )}
          {geometry.lastIndex >= 0 && geometry.values[geometry.lastIndex] !== null && (
            <g>
              <circle
                cx={geometry.x(geometry.lastIndex)}
                cy={geometry.y(geometry.values[geometry.lastIndex] as number)}
                r={4}
                fill={chartColors.accent}
                stroke={chartColors.surface}
                strokeWidth={2}
              />
              <text
                x={geometry.x(geometry.lastIndex)}
                y={geometry.y(geometry.values[geometry.lastIndex] as number) - 10}
                textAnchor="end"
                className="fill-text-secondary text-micro font-medium"
              >
                {formatValue(geometry.values[geometry.lastIndex] as number)}
              </text>
            </g>
          )}
          {hover && (
            <circle
              cx={geometry.x(hover.index)}
              cy={geometry.y(hover.value as number)}
              r={4}
              fill={chartColors.accent}
              stroke={chartColors.surface}
              strokeWidth={2}
            />
          )}
        </svg>
      ) : (
        <div className="flex h-40 items-center justify-center text-mini text-text-quaternary">
          Not enough data to draw
        </div>
      )}
      {hover && geometry && (
        <ChartTooltip
          width={width}
          state={{
            x: geometry.x(hover.index),
            y: geometry.y(hover.value as number),
            content: (
              <>
                <TooltipTitle>{periodLabel(points[hover.index].period_start, bucket)}</TooltipTitle>
                <TooltipRow
                  seriesColor={chartColors.accent}
                  label={seriesLabel}
                  value={formatValue(hover.value as number)}
                />
                {baseline !== null && (
                  <TooltipRow
                    seriesColor={chartColors.baseline}
                    dashed
                    label={baselineLabel}
                    value={formatValue(baseline)}
                  />
                )}
                {tooltipExtras?.(points[hover.index]).map((row) => (
                  <TooltipRow key={row.label} label={row.label} value={row.value} />
                ))}
              </>
            ),
          }}
        />
      )}
    </div>
  )
}
