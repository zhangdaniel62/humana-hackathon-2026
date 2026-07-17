import { StatTile } from '@/components/ui'
import { formatInt, formatMinutes, formatRate } from '@/lib/format'
import type { OperationsDashboardResponse } from '@/lib/operationsDashboard'
import { AhtTrendCard, CohortColumnCard, FcrTrendCard, FunnelCard, RepeatTrendCard, VolumeCard } from './cards'
import { ahtDelta, fcrDelta, repeatDelta } from './kpis'

/** Quiet note for breakdowns the endpoint does not measure — never invented. */
function NotMeasured({ children }: { children: string }) {
  return <p className="text-micro text-text-quaternary">Not measured by this endpoint: {children}</p>
}

function cohortCaption(data: OperationsDashboardResponse): string {
  return data.summary.first_contact_resolution_rate === null &&
    data.summary.repeat_contact_rate === null
    ? 'Not enough matured contacts'
    : `7-day matured cohort · n = ${formatInt(data.summary.mature_initial_contacts)}`
}

export function AhtTab({ data }: { data: OperationsDashboardResponse }) {
  const { summary, baseline } = data
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatTile
          label="Average handle time"
          value={formatMinutes(summary.average_handle_time_minutes)}
          delta={ahtDelta(summary.average_handle_time_minutes, baseline.aht_minutes)}
          caption={
            summary.average_handle_time_minutes === null
              ? 'No calls in range'
              : 'Average call-session duration'
          }
        />
        <StatTile
          label="Completed sessions"
          value={formatInt(summary.completed_sessions)}
          caption="Sample size — all selected calls, including follow-ups"
        />
      </div>
      <AhtTrendCard data={data} height={230} />
      <VolumeCard data={data} height={180} />
      <NotMeasured>
        median or percentile handle time, duration histogram, or AHT split by routing mode or
        outcome.
      </NotMeasured>
    </div>
  )
}

export function FcrTab({ data }: { data: OperationsDashboardResponse }) {
  const { summary, baseline } = data
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatTile
          label="First call resolution"
          value={formatRate(summary.first_contact_resolution_rate, 2)}
          delta={fcrDelta(summary.first_contact_resolution_rate, baseline.fcr_rate)}
          caption={cohortCaption(data)}
        />
        <StatTile
          label="Matured initial contacts"
          value={formatInt(summary.mature_initial_contacts)}
          caption="Denominator — initial contacts with a complete 7-day follow-up window"
        />
      </div>
      <FcrTrendCard data={data} height={230} />
      <CohortColumnCard data={data} height={180} />
      <NotMeasured>
        exact resolved/unresolved counts, issue-type segmentation, or escalation status. Counts are
        not back-calculated from rounded rates.
      </NotMeasured>
    </div>
  )
}

export function RepeatTab({ data }: { data: OperationsDashboardResponse }) {
  const { summary, baseline } = data
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatTile
          label="Repeat contact rate"
          value={formatRate(summary.repeat_contact_rate, 2)}
          delta={repeatDelta(summary.repeat_contact_rate, baseline.repeat_contact_rate)}
          caption={cohortCaption(data)}
        />
        <StatTile
          label="Matured initial contacts"
          value={formatInt(summary.mature_initial_contacts)}
          caption="Denominator — initial contacts with a complete 7-day follow-up window"
        />
      </div>
      <RepeatTrendCard data={data} height={230} />
      <CohortColumnCard data={data} height={180} />
      <NotMeasured>
        exact repeat-contact counts, time-to-repeat distribution, issue/claim breakdown, or
        individual contact drill-down.
      </NotMeasured>
    </div>
  )
}

export function DenialsTab({ data }: { data: OperationsDashboardResponse }) {
  const { interventions } = data
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatTile
          label="Intervention coverage"
          value={formatRate(interventions.recorded_coverage_rate)}
          caption={
            interventions.recorded_coverage_rate === null
              ? 'No identified at-risk claims in range'
              : `${formatInt(interventions.recorded_claims)} of ${formatInt(interventions.identified_claims)} at-risk claims had a corrective intervention recorded`
          }
        />
      </div>
      <FunnelCard data={data} />
      <NotMeasured>
        intervention trend over time, risk-rule breakdown, claim status after intervention, or a
        true preventable-denial rate — a recorded intervention is not connected to later
        adjudication.
      </NotMeasured>
    </div>
  )
}
