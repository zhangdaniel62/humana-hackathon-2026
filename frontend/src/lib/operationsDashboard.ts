import { buildMockDashboardResponse } from './mockOperationsDashboard'

/**
 * Types and data access for the manager operations dashboard, mirroring
 * assets/docs/dashboard_frontend_contract.md exactly.
 */

export type IsoDate = string
export type IsoDateTime = string
export type DashboardBucket = 'week' | 'month'

export interface MetricSummary {
  completed_sessions: number
  average_handle_time_minutes: number | null
  mature_initial_contacts: number
  first_contact_resolution_rate: number | null
  repeat_contact_rate: number | null
  automated_calls: number
  manual_review_calls: number
}

export interface TrendPoint extends MetricSummary {
  period_start: IsoDate
}

export interface OperationsDashboardResponse {
  metadata: {
    data_label: 'synthetic_demo'
    start: IsoDate
    end: IsoDate
    bucket: DashboardBucket
    repeat_window_days: 7
    observation_cutoff: IsoDateTime | null
  }
  baseline: {
    aht_minutes: number | null
    fcr_rate: number | null
    repeat_contact_rate: number | null
    source_note: string
    data_label: 'synthetic_demo_assumption'
  }
  summary: MetricSummary
  trend: TrendPoint[]
  interventions: {
    identified_claims: number
    recommended_claims: number
    recorded_claims: number
    recorded_coverage_rate: number | null
  }
  manual_by_rep: Array<{
    username: string
    manual_review_calls: number
  }>
}

export interface DashboardQuery {
  start?: IsoDate
  end?: IsoDate
  bucket?: DashboardBucket
}

/**
 * SWAP POINT — the only place the dashboard reads data from.
 *
 * Currently served by the local synthetic mock so the surface renders
 * without the backend. To wire the real API, replace the body with:
 *
 *   return apiFetch<OperationsDashboardResponse>(
 *     `/api/operations/dashboard?${new URLSearchParams(params)}`,
 *     { credentials: 'include' },
 *   )
 *
 * plus the 401/403/422/network handling in the contract's
 * "Loading, errors, empty states" section. Nothing else changes.
 */
export async function fetchOperationsDashboard(
  params: DashboardQuery = {},
): Promise<OperationsDashboardResponse> {
  // Brief artificial latency so the loading skeleton is a real state.
  await new Promise((resolve) => setTimeout(resolve, 250))
  return buildMockDashboardResponse(params)
}
