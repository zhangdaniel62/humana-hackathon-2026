import type { ReactNode } from 'react'
import { Button, Panel } from '@/components/ui'
import type { OperationsDashboardResponse } from '@/lib/operationsDashboard'
import { DashboardFilters } from './DashboardFilters'
import {
  useOperationsDashboard,
  type OperationsDashboardError,
} from './useOperationsDashboard'

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

function ErrorNotice({ error, onRetry }: { error: OperationsDashboardError; onRetry: () => void }) {
  const title =
    error.kind === 'authentication'
      ? 'Sign-in required'
      : error.kind === 'forbidden'
        ? 'Access denied'
        : error.kind === 'validation'
          ? 'Check the selected range'
          : 'Dashboard unavailable'

  return (
    <Panel className="flex items-center gap-4 border-danger-border bg-danger-bg" role="alert">
      <div className="min-w-0 flex-1">
        <p className="text-small font-medium text-danger">{title}</p>
        <p className="mt-0.5 text-mini text-text-secondary">{error.message}</p>
      </div>
      {error.kind === 'authentication' && (
        <a
          href="/signin"
          className="inline-flex h-7 items-center rounded-md border border-border-primary bg-bg-primary px-2 text-small font-medium text-text-primary"
        >
          Sign in
        </a>
      )}
      {error.retryable && (
        <Button size="sm" onPress={onRetry}>
          Retry
        </Button>
      )}
    </Panel>
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
  const { data, loading, error, retry } = useOperationsDashboard()
  const empty = data !== null && data.summary.completed_sessions === 0 && data.trend.length === 0

  return (
    <div className="flex flex-col gap-6 p-6">
      <DashboardFilters metadata={data?.metadata} />
      {error && <ErrorNotice error={error} onRetry={retry} />}
      {data === null && loading ? (
        <Skeleton />
      ) : data === null ? (
        null
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
