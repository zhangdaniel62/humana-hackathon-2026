import { useState, type ReactNode } from 'react'
import { ChartLine, Table2 } from 'lucide-react'
import { Button, Panel } from '@/components/ui'
import { cn } from '@/lib/cn'

export interface LegendEntry {
  label: string
  color: string
  /** Mirror the mark: line for lines, rect for bars/columns. */
  kind: 'line' | 'dashed' | 'rect'
}

export interface ChartTable {
  columns: Array<{ header: string; align?: 'left' | 'right' }>
  rows: ReactNode[][]
}

export interface ChartCardProps {
  title: string
  subtitle?: string
  /** Present whenever the chart draws ≥ 2 series; omitted for one. */
  legend?: LegendEntry[]
  /** Accessible equivalent of the chart — every chart must provide one. */
  table: ChartTable
  /** Quiet footnote under the plot, e.g. the 7-day matured-cohort caveat. */
  caption?: ReactNode
  /** Dim during a refetch — the previous render holds, no layout jump. */
  dimmed?: boolean
  className?: string
  children: ReactNode
}

function LegendKey({ entry }: { entry: LegendEntry }) {
  return (
    <span className="flex items-center gap-1.5 text-mini text-text-tertiary">
      {entry.kind === 'rect' ? (
        <span className="size-2.5 rounded-[3px]" style={{ background: entry.color }} aria-hidden="true" />
      ) : (
        <svg width={14} height={2} aria-hidden="true">
          <line
            x1={0}
            y1={1}
            x2={14}
            y2={1}
            stroke={entry.color}
            strokeWidth={2}
            strokeDasharray={entry.kind === 'dashed' ? '3 2' : undefined}
          />
        </svg>
      )}
      {entry.label}
    </span>
  )
}

/** Dashboard chart container: quiet header, legend, and a table-view toggle. */
export function ChartCard({
  title,
  subtitle,
  legend,
  table,
  caption,
  dimmed = false,
  className,
  children,
}: ChartCardProps) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const showingChart = view === 'chart'

  return (
    <Panel className={cn('flex flex-col gap-3', className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-small font-medium text-text-primary">{title}</h3>
          {subtitle && <p className="mt-0.5 text-mini text-text-tertiary">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {legend && legend.length > 0 && (
            <div className="flex items-center gap-3">
              {legend.map((entry) => (
                <LegendKey key={entry.label} entry={entry} />
              ))}
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            iconOnly
            aria-label={showingChart ? `Show ${title} as a table` : `Show ${title} as a chart`}
            onPress={() => setView(showingChart ? 'table' : 'chart')}
          >
            {showingChart ? (
              <Table2 size={14} strokeWidth={1.5} aria-hidden="true" />
            ) : (
              <ChartLine size={14} strokeWidth={1.5} aria-hidden="true" />
            )}
          </Button>
        </div>
      </div>
      <div className={cn('transition-opacity', dimmed && 'opacity-50')}>
        {showingChart ? (
          children
        ) : (
          <table className="w-full border-separate border-spacing-0">
            <thead>
              <tr>
                {table.columns.map((column) => (
                  <th
                    key={column.header}
                    scope="col"
                    className={cn(
                      'border-b border-border-primary px-2 py-1.5 text-mini font-medium text-text-tertiary',
                      column.align === 'right' ? 'text-right' : 'text-left',
                    )}
                  >
                    {column.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td
                      key={cellIndex}
                      className={cn(
                        'border-b border-border-secondary px-2 py-1.5 text-mini text-text-secondary tabular-nums',
                        table.columns[cellIndex]?.align === 'right' ? 'text-right' : 'text-left',
                      )}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {caption && <p className="text-micro text-text-quaternary">{caption}</p>}
    </Panel>
  )
}
