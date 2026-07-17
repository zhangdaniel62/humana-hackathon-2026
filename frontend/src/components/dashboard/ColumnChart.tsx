import { useMemo, useState, type PointerEvent } from 'react'
import type { DashboardBucket, TrendPoint } from '@/lib/operationsDashboard'
import { formatDay, formatInt, formatMonth } from '@/lib/format'
import { ChartTooltip, TooltipRow, TooltipTitle } from './chart-common'
import { chartColors, niceTicks, periodLabel, useMeasuredWidth } from './chart-utils'

export interface ColumnSeries {
  label: string
  color: string
  accessor: (point: TrendPoint) => number
}

export interface ColumnChartProps {
  points: TrendPoint[]
  bucket: DashboardBucket
  /** Bottom-up stack order; one entry renders a plain column chart. */
  series: ColumnSeries[]
  /** Extra un-keyed tooltip row, e.g. completed sessions for the stack. */
  totalRow?: { label: string; accessor: (point: TrendPoint) => number }
  height?: number
}

const MARGIN = { top: 10, right: 14, bottom: 22, left: 40 }
const SEGMENT_GAP = 2
const CORNER = 4

/** Column cap: 4px rounded top corners, square at the baseline. */
function roundedTopRect(x: number, y: number, w: number, h: number): string {
  const r = Math.min(CORNER, w / 2, h)
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`
}

/**
 * Volume columns over time. Stacked segments are separated by a 2px
 * surface gap; identity comes from the legend in the containing ChartCard.
 */
export function ColumnChart({ points, bucket, series, totalRow, height = 190 }: ColumnChartProps) {
  const { ref, width } = useMeasuredWidth()
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const innerWidth = Math.max(0, width - MARGIN.left - MARGIN.right)
  const innerHeight = height - MARGIN.top - MARGIN.bottom

  const geometry = useMemo(() => {
    if (points.length === 0 || innerWidth <= 0) return null
    const totals = points.map((p) => series.reduce((sum, s) => sum + s.accessor(p), 0))
    const hi = Math.max(...totals, 1) * 1.08
    const ticks = niceTicks(0, hi, 4)
    const domainHi = Math.max(hi, ticks[ticks.length - 1] ?? 0)

    const slot = innerWidth / points.length
    const columnWidth = Math.min(24, Math.max(6, slot * 0.55))
    const x = (i: number) => MARGIN.left + slot * i + (slot - columnWidth) / 2
    const y = (v: number) => MARGIN.top + innerHeight - (v / domainHi) * innerHeight

    const tickCount = Math.max(2, Math.min(6, Math.floor(innerWidth / 90)))
    const xTickIndexes = [...new Set(
      Array.from({ length: tickCount }, (_, k) =>
        Math.round((k / (tickCount - 1)) * (points.length - 1)),
      ),
    )]

    return { x, y, ticks, slot, columnWidth, xTickIndexes }
  }, [points, series, innerWidth, innerHeight])

  const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (!geometry) return
    const rect = event.currentTarget.getBoundingClientRect()
    const px = event.clientX - rect.left - MARGIN.left
    const index = Math.floor(px / geometry.slot)
    setHoverIndex(index >= 0 && index < points.length ? index : null)
  }

  if (points.length === 0) return null

  return (
    <div ref={ref} className="relative">
      {geometry && (
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
                {formatInt(tick)}
              </text>
            </g>
          ))}
          {points.map((point, i) => {
            const values = series.map((s) => s.accessor(point))
            const visible = values
              .map((value, k) => ({ value, k }))
              .filter((segment) => segment.value > 0)
            const topVisibleK = visible.length > 0 ? visible[visible.length - 1].k : -1
            const dim = hoverIndex !== null && hoverIndex !== i
            let cumulative = 0
            return (
              <g key={point.period_start} opacity={dim ? 0.55 : 1}>
                {values.map((value, k) => {
                  const bottomValue = cumulative
                  cumulative += value
                  if (value <= 0) return null
                  const isBottom = bottomValue === 0
                  const bottomY = geometry.y(bottomValue) - (isBottom ? 0 : SEGMENT_GAP)
                  const topY = geometry.y(cumulative)
                  const h = Math.max(1, bottomY - topY)
                  const xPos = geometry.x(i)
                  return k === topVisibleK ? (
                    <path
                      key={series[k].label}
                      d={roundedTopRect(xPos, topY, geometry.columnWidth, h)}
                      fill={series[k].color}
                    />
                  ) : (
                    <rect
                      key={series[k].label}
                      x={xPos}
                      y={topY}
                      width={geometry.columnWidth}
                      height={h}
                      fill={series[k].color}
                    />
                  )
                })}
              </g>
            )
          })}
          {geometry.xTickIndexes.map((i) => (
            <text
              key={points[i].period_start}
              x={geometry.x(i) + geometry.columnWidth / 2}
              y={height - 6}
              textAnchor="middle"
              className="fill-text-quaternary text-micro"
            >
              {bucket === 'month' ? formatMonth(points[i].period_start).slice(0, 3) : formatDay(points[i].period_start)}
            </text>
          ))}
        </svg>
      )}
      {geometry && hoverIndex !== null && points[hoverIndex] && (
        <ChartTooltip
          width={width}
          state={{
            x: geometry.x(hoverIndex) + geometry.columnWidth / 2,
            y: geometry.y(series.reduce((sum, s) => sum + s.accessor(points[hoverIndex]), 0)),
            content: (
              <>
                <TooltipTitle>{periodLabel(points[hoverIndex].period_start, bucket)}</TooltipTitle>
                {series.map((s) => (
                  <TooltipRow
                    key={s.label}
                    seriesColor={s.color}
                    label={s.label}
                    value={formatInt(s.accessor(points[hoverIndex]))}
                  />
                ))}
                {totalRow && (
                  <TooltipRow
                    label={totalRow.label}
                    value={formatInt(totalRow.accessor(points[hoverIndex]))}
                  />
                )}
              </>
            ),
          }}
        />
      )}
    </div>
  )
}
