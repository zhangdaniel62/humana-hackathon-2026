import { useCallback, useEffect, useRef, useState } from 'react'
import { useDashboardFilters } from '@/app/dashboard-filters-context'
import { ApiError } from '@/lib/api'
import {
  fetchOperationsDashboard,
  type OperationsDashboardResponse,
} from '@/lib/operationsDashboard'

export interface OperationsDashboardError {
  kind: 'authentication' | 'forbidden' | 'validation' | 'network' | 'unknown'
  status: number | null
  message: string
  retryable: boolean
}

export interface OperationsDashboardState {
  /** Last loaded payload; null only before the first load completes. */
  data: OperationsDashboardResponse | null
  /** True during any (re)load — first load shows skeletons, refetches dim. */
  loading: boolean
  error: OperationsDashboardError | null
  retry: () => void
}

interface LoadState {
  data: OperationsDashboardResponse | null
  error: OperationsDashboardError | null
  settledRequest: string | null
}

export function toOperationsDashboardError(error: unknown): OperationsDashboardError {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return {
        kind: 'authentication',
        status: 401,
        message: 'Your session has expired. Sign in again to view the manager dashboard.',
        retryable: true,
      }
    }
    if (error.status === 403) {
      return {
        kind: 'forbidden',
        status: 403,
        message: error.message || 'You do not have access to the manager dashboard.',
        retryable: false,
      }
    }
    if (error.status === 422) {
      return {
        kind: 'validation',
        status: 422,
        message: error.message,
        retryable: false,
      }
    }
    return {
      kind: 'unknown',
      status: error.status,
      message: error.message,
      retryable: true,
    }
  }

  if (error instanceof TypeError) {
    return {
      kind: 'network',
      status: null,
      message: 'The dashboard could not reach the server. Check your connection and try again.',
      retryable: true,
    }
  }

  return {
    kind: 'unknown',
    status: null,
    message: error instanceof Error ? error.message : 'The dashboard could not be loaded.',
    retryable: true,
  }
}

/** Loads the dashboard payload for the shared filter selection. */
export function useOperationsDashboard(): OperationsDashboardState {
  const { filters } = useDashboardFilters()
  const [reloadKey, setReloadKey] = useState(0)
  const latestRequest = useRef(0)
  const requestKey = `${filters.start ?? ''}|${filters.end ?? ''}|${filters.bucket ?? ''}|${reloadKey}`
  const [state, setState] = useState<LoadState>({
    data: null,
    error: null,
    settledRequest: null,
  })

  useEffect(() => {
    const requestId = latestRequest.current + 1
    latestRequest.current = requestId
    const controller = new AbortController()

    void fetchOperationsDashboard(filters, controller.signal)
      .then((data) => {
        if (latestRequest.current !== requestId || controller.signal.aborted) return
        setState({ data, error: null, settledRequest: requestKey })
      })
      .catch((error: unknown) => {
        if (latestRequest.current !== requestId || controller.signal.aborted) return
        setState((current) => ({
          ...current,
          error: toOperationsDashboardError(error),
          settledRequest: requestKey,
        }))
      })

    return () => {
      controller.abort()
    }
  }, [filters, requestKey])

  const retry = useCallback(() => setReloadKey((current) => current + 1), [])

  const loading = state.settledRequest !== requestKey
  const error = loading ? null : state.error
  return { data: state.data, loading, error, retry }
}
