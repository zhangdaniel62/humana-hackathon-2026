import { apiFetch } from './api'

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

/** The single data source for all operations-dashboard views. */
export async function fetchOperationsDashboard(
  params: DashboardQuery = {},
  signal?: AbortSignal,
): Promise<OperationsDashboardResponse> {
  const query = new URLSearchParams()
  if (params.start) query.set('start', params.start)
  if (params.end) query.set('end', params.end)
  if (params.bucket) query.set('bucket', params.bucket)

  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return apiFetch<OperationsDashboardResponse>(`/api/operations/dashboard${suffix}`, {
    signal,
  })
}
