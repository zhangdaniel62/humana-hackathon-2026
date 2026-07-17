import { useEffect, useState } from 'react'
import { useDashboardFilters, type DashboardFilters } from '@/app/dashboard-filters-context'
import {
  fetchOperationsDashboard,
  type OperationsDashboardResponse,
} from '@/lib/operationsDashboard'

export interface OperationsDashboardState {
  /** Last loaded payload; null only before the first load completes. */
  data: OperationsDashboardResponse | null
  /** True during any (re)load — first load shows skeletons, refetches dim. */
  loading: boolean
}

interface Loaded {
  data: OperationsDashboardResponse
  /** The filter selection this payload answers — loading is derived from it. */
  forFilters: DashboardFilters
}

/** Loads the dashboard payload for the shared filter selection. */
export function useOperationsDashboard(): OperationsDashboardState {
  const { filters } = useDashboardFilters()
  const [loaded, setLoaded] = useState<Loaded | null>(null)

  useEffect(() => {
    let alive = true
    void fetchOperationsDashboard(filters).then((data) => {
      if (alive) setLoaded({ data, forFilters: filters })
    })
    return () => {
      alive = false
    }
  }, [filters])

  return { data: loaded?.data ?? null, loading: loaded?.forFilters !== filters }
}
