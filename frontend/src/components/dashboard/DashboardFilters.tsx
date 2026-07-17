import { useState } from 'react'
import { ToggleButton, ToggleButtonGroup } from 'react-aria-components'
import { Badge, Input } from '@/components/ui'
import { cn } from '@/lib/cn'
import { formatDateRange } from '@/lib/format'
import type { OperationsDashboardResponse } from '@/lib/operationsDashboard'
import { useDashboardFilters } from '@/app/dashboard-filters-context'

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

/**
 * Shared date-range + bucket controls, one row above every dashboard page's
 * content, with the required "Synthetic demo data" disclosure.
 */
export function DashboardFilters({
  metadata,
}: {
  metadata: OperationsDashboardResponse['metadata'] | undefined
}) {
  const { filters, setRange, setBucket } = useDashboardFilters()
  const [startDraft, setStartDraft] = useState<string | null>(null)
  const [endDraft, setEndDraft] = useState<string | null>(null)
  const start = startDraft ?? filters.start ?? metadata?.start ?? ''
  const end = endDraft ?? filters.end ?? metadata?.end ?? ''

  const rangeInvalid = ISO_DATE.test(start) && ISO_DATE.test(end) && start > end

  const commit = (nextStart: string, nextEnd: string) => {
    const validStart = nextStart === '' || ISO_DATE.test(nextStart)
    const validEnd = nextEnd === '' || ISO_DATE.test(nextEnd)
    if (!validStart || !validEnd || (nextStart && nextEnd && nextStart > nextEnd)) return
    setRange(nextStart || undefined, nextEnd || undefined)
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Input
        aria-label="Start date"
        type="date"
        size="sm"
        value={start}
        isInvalid={rangeInvalid}
        onChange={(value) => {
          setStartDraft(value)
          commit(value, end)
        }}
        className="w-36"
      />
      <span className="text-mini text-text-quaternary">–</span>
      <Input
        aria-label="End date"
        type="date"
        size="sm"
        value={end}
        isInvalid={rangeInvalid}
        onChange={(value) => {
          setEndDraft(value)
          commit(start, value)
        }}
        className="w-36"
      />
      <ToggleButtonGroup
        aria-label="Trend bucket"
        selectionMode="single"
        disallowEmptySelection
        selectedKeys={[filters.bucket ?? metadata?.bucket ?? 'week']}
        onSelectionChange={(keys) => {
          const key = [...keys][0]
          if (key === 'week' || key === 'month') setBucket(key)
        }}
        className="flex items-center gap-0.5 rounded-md bg-bg-secondary p-0.5"
      >
        {(['week', 'month'] as const).map((bucket) => (
          <ToggleButton
            key={bucket}
            id={bucket}
            className={cn(
              'flex h-6 cursor-default items-center rounded-[6px] px-2.5 text-mini font-medium transition-colors',
              'text-text-tertiary data-hovered:text-text-secondary',
              'data-selected:bg-bg-primary data-selected:text-text-primary data-selected:shadow-[0_1px_2px_rgb(0_0_0/0.04)]',
            )}
          >
            {bucket === 'week' ? 'Weekly' : 'Monthly'}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      {rangeInvalid && (
        <span className="text-mini text-danger">Start must be on or before end</span>
      )}
      <div className="ml-auto flex items-center gap-2">
        {metadata && (
          <span className="text-mini text-text-tertiary">
            {formatDateRange(metadata.start, metadata.end)}
          </span>
        )}
        <Badge variant="neutral">Synthetic demo data</Badge>
      </div>
    </div>
  )
}
