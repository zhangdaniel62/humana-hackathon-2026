import { useMemo, useState, type ReactNode } from 'react'
import type { DashboardBucket, IsoDate } from '@/lib/operationsDashboard'
import { MOCK_RANGE } from '@/lib/mockOperationsDashboard'
import { DashboardFiltersContext, type DashboardFilters } from './dashboard-filters-context'

/**
 * Holds the dashboard's date-range + bucket selection above the routes, so
 * switching between the five tabs keeps the same slice selected.
 */
export function DashboardFiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<DashboardFilters>({
    start: MOCK_RANGE.start,
    end: MOCK_RANGE.end,
    bucket: 'week',
  })

  const value = useMemo(
    () => ({
      filters,
      setRange: (start: IsoDate, end: IsoDate) =>
        setFilters((current) => ({ ...current, start, end })),
      setBucket: (bucket: DashboardBucket) => setFilters((current) => ({ ...current, bucket })),
    }),
    [filters],
  )

  return <DashboardFiltersContext value={value}>{children}</DashboardFiltersContext>
}
