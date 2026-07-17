import { StatTile } from '@/components/ui'
import { formatInt, formatMinutes, formatRate } from '@/lib/format'
import type { OperationsDashboardResponse } from '@/lib/operationsDashboard'
import { AhtTrendCard, FcrTrendCard, FunnelCard, RepWorkloadCard, RepeatTrendCard, VolumeCard } from './cards'
import { ahtDelta, fcrDelta, repeatDelta } from './kpis'

export function OverviewTab({ data }: { data: OperationsDashboardResponse }) {
  const { summary, baseline, interventions } = data

  const cohortCaption =
    summary.first_contact_resolution_rate === null
      ? 'Not enough matured contacts'
      : `7-day matured cohort · n = ${formatInt(summary.mature_initial_contacts)}`

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
              : `${formatInt(summary.completed_sessions)} completed sessions`
          }
        />
        <StatTile
          label="First call resolution"
          value={formatRate(summary.first_contact_resolution_rate, 2)}
          delta={fcrDelta(summary.first_contact_resolution_rate, baseline.fcr_rate)}
          caption={cohortCaption}
        />
        <StatTile
          label="Repeat contact rate"
          value={formatRate(summary.repeat_contact_rate, 2)}
          delta={repeatDelta(summary.repeat_contact_rate, baseline.repeat_contact_rate)}
          caption={cohortCaption}
        />
        <StatTile
          label="Intervention coverage"
          value={formatRate(interventions.recorded_coverage_rate)}
          caption={
            interventions.recorded_coverage_rate === null
              ? 'No identified at-risk claims in range'
              : `Corrective interventions recorded · ${formatInt(interventions.recorded_claims)} of ${formatInt(interventions.identified_claims)} identified`
          }
        />
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
        <AhtTrendCard data={data} height={170} />
        <FcrTrendCard data={data} height={170} />
        <RepeatTrendCard data={data} height={170} />
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <VolumeCard data={data} />
        <RepWorkloadCard data={data} />
      </div>
      <FunnelCard data={data} />
    </div>
  )
}
