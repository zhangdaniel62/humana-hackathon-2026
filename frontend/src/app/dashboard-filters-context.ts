import { createContext, useContext } from 'react'
import type { DashboardBucket, IsoDate } from '@/lib/operationsDashboard'

export interface DashboardFilters {
  start: IsoDate
  end: IsoDate
  bucket: DashboardBucket
}

export interface DashboardFiltersContextValue {
  filters: DashboardFilters
  setRange: (start: IsoDate, end: IsoDate) => void
  setBucket: (bucket: DashboardBucket) => void
}

export const DashboardFiltersContext = createContext<DashboardFiltersContextValue | null>(null)

/** Shared date-range + bucket selection across all five dashboard tabs. */
export function useDashboardFilters(): DashboardFiltersContextValue {
  const context = useContext(DashboardFiltersContext)
  if (!context) throw new Error('useDashboardFilters must be used within DashboardFiltersProvider')
  return context
}
