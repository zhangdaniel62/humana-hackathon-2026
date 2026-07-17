import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './api'
import {
  fetchOperationsDashboard,
  type OperationsDashboardResponse,
} from './operationsDashboard'
import { toOperationsDashboardError } from '@/components/dashboard/useOperationsDashboard'

const response: OperationsDashboardResponse = {
  metadata: {
    data_label: 'synthetic_demo',
    start: '2026-01-12',
    end: '2026-07-12',
    bucket: 'week',
    repeat_window_days: 7,
    observation_cutoff: '2026-07-13T17:10:00Z',
  },
  baseline: {
    aht_minutes: 8.5,
    fcr_rate: 0.72,
    repeat_contact_rate: 0.18,
    source_note: 'Synthetic assumptions',
    data_label: 'synthetic_demo_assumption',
  },
  summary: {
    completed_sessions: 0,
    average_handle_time_minutes: null,
    mature_initial_contacts: 0,
    first_contact_resolution_rate: null,
    repeat_contact_rate: null,
    automated_calls: 0,
    manual_review_calls: 0,
  },
  trend: [],
  interventions: {
    identified_claims: 0,
    recommended_claims: 0,
    recorded_claims: 0,
    recorded_coverage_rate: null,
  },
  manual_by_rep: [],
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchOperationsDashboard', () => {
  it('lets the backend apply every default when filters are unset', async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(response))
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchOperationsDashboard()).resolves.toEqual(response)

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/operations/dashboard')
    expect(options.credentials).toBe('include')
  })

  it('encodes only selected filters and forwards the abort signal', async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(response))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()

    await fetchOperationsDashboard(
      { start: '2026-01-12', end: '2026-07-12', bucket: 'month' },
      controller.signal,
    )

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(
      '/api/operations/dashboard?start=2026-01-12&end=2026-07-12&bucket=month',
    )
    expect(options.signal).toBe(controller.signal)
  })

  it('does not manufacture missing date parameters', async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(response))
    vi.stubGlobal('fetch', fetchMock)

    await fetchOperationsDashboard({ bucket: 'month' })

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/operations/dashboard?bucket=month')
  })
})

describe('toOperationsDashboardError', () => {
  it.each([
    [401, 'authentication', true],
    [403, 'forbidden', false],
    [422, 'validation', false],
  ] as const)('maps HTTP %i to a visible dashboard state', (status, kind, retryable) => {
    expect(toOperationsDashboardError(new ApiError(status, 'Backend detail'))).toMatchObject({
      status,
      kind,
      retryable,
    })
  })

  it('maps fetch failures to a retryable network state', () => {
    expect(toOperationsDashboardError(new TypeError('Failed to fetch'))).toMatchObject({
      kind: 'network',
      status: null,
      retryable: true,
    })
  })
})
