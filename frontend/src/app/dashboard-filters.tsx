import { useMemo, useState, type ReactNode } from 'react'
import type { DashboardBucket, IsoDate } from '@/lib/operationsDashboard'
import { DashboardFiltersContext, type DashboardFilters } from './dashboard-filters-context'

/**
 * Holds the dashboard's date-range + bucket selection above the routes, so
 * switching between the five tabs keeps the same slice selected.
 */
export function DashboardFiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<DashboardFilters>({})

  const value = useMemo(
    () => ({
      filters,
      setRange: (start?: IsoDate, end?: IsoDate) =>
        setFilters((current) => {
          if (current.start === start && current.end === end) return current
          return { ...current, start, end }
        }),
      setBucket: (bucket: DashboardBucket) =>
        setFilters((current) => (current.bucket === bucket ? current : { ...current, bucket })),
    }),
    [filters],
  )

  return <DashboardFiltersContext value={value}>{children}</DashboardFiltersContext>
}
