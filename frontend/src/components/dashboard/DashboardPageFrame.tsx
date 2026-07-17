import type { ReactNode } from 'react'
import { Panel } from '@/components/ui'
import type { OperationsDashboardResponse } from '@/lib/operationsDashboard'
import { DashboardFilters } from './DashboardFilters'
import { useOperationsDashboard } from './useOperationsDashboard'

function Skeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-6" aria-hidden="true">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Panel key={i} className="h-28" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Panel className="h-64" />
        <Panel className="h-64" />
      </div>
    </div>
  )
}

function EmptyRange() {
  return (
    <div className="flex flex-col items-center justify-center gap-1 py-24 text-center">
      <p className="text-regular text-text-secondary">No synthetic activity in this date range.</p>
      <p className="text-mini text-text-quaternary">
        Synthetic demo activity starts Jan 12, 2026 — widen the range to see data.
      </p>
    </div>
  )
}

export interface DashboardPageFrameProps {
  children: (data: OperationsDashboardResponse) => ReactNode
}

/**
 * Shared scaffolding for all five dashboard tabs: the filter row + disclosure
 * badge, the loading skeleton (filters stay put), the empty-range state, and
 * dimming the previous render during a refetch.
 */
export function DashboardPageFrame({ children }: DashboardPageFrameProps) {
  const { data, loading } = useOperationsDashboard()
  const empty = data !== null && data.summary.completed_sessions === 0 && data.trend.length === 0

  return (
    <div className="flex flex-col gap-6 p-6">
      <DashboardFilters metadata={data?.metadata} />
      {data === null ? (
        <Skeleton />
      ) : empty ? (
        <EmptyRange />
      ) : (
        <div className={loading ? 'opacity-50 transition-opacity' : 'transition-opacity'}>
          {children(data)}
        </div>
      )}
    </div>
  )
}
