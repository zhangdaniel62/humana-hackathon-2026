import { formatInt, formatMinutes, formatRate } from '@/lib/format'
import type { OperationsDashboardResponse } from '@/lib/operationsDashboard'
import { ChartCard } from './ChartCard'
import { ColumnChart } from './ColumnChart'
import { HBarChart } from './HBarChart'
import { TooltipTitle, TooltipRow } from './chart-common'
import { chartColors, periodLabel } from './chart-utils'
import { TrendLineChart } from './TrendLineChart'

/**
 * The contract's chart blocks, composed once and reused across tabs.
 * Every card carries a table view as the chart's accessible equivalent.
 */

interface CardProps {
  data: OperationsDashboardResponse
  height?: number
}

const trendLegend = [
  { label: 'Observed', color: chartColors.accent, kind: 'line' as const },
  { label: 'Synthetic baseline', color: chartColors.baseline, kind: 'dashed' as const },
]

const BASELINE_NOTE = 'Baseline is a labeled synthetic comparison assumption.'
const COHORT_NOTE =
  '7-day matured cohort: rates use initial contacts whose full 7-day follow-up window is observable.'

export function AhtTrendCard({ data, height }: CardProps) {
  const { trend, baseline, metadata } = data
  return (
    <ChartCard
      title="Average handle time"
      subtitle="Average call-session duration, minutes"
      legend={trendLegend}
      caption={`After-call work is not separately tracked. ${BASELINE_NOTE}`}
      table={{
        columns: [
          { header: 'Period' },
          { header: 'AHT', align: 'right' },
          { header: 'Completed sessions', align: 'right' },
        ],
        rows: trend.map((p) => [
          periodLabel(p.period_start, metadata.bucket),
          formatMinutes(p.average_handle_time_minutes),
          formatInt(p.completed_sessions),
        ]),
      }}
    >
      <TrendLineChart
        points={trend}
        bucket={metadata.bucket}
        accessor={(p) => p.average_handle_time_minutes}
        seriesLabel="average handle time"
        baseline={baseline.aht_minutes}
        baselineLabel="synthetic baseline"
        formatValue={(v) => `${v.toFixed(2)} min`}
        tooltipExtras={(p) => [{ label: 'completed sessions', value: formatInt(p.completed_sessions) }]}
        height={height}
      />
    </ChartCard>
  )
}

export function FcrTrendCard({ data, height }: CardProps) {
  const { trend, baseline, metadata } = data
  return (
    <ChartCard
      title="First call resolution"
      subtitle="Resolved with no repeat contact for the same member and claim within 7 days"
      legend={trendLegend}
      caption={`${COHORT_NOTE} ${BASELINE_NOTE}`}
      table={{
        columns: [
          { header: 'Period' },
          { header: 'FCR', align: 'right' },
          { header: 'Matured contacts', align: 'right' },
        ],
        rows: trend.map((p) => [
          periodLabel(p.period_start, metadata.bucket),
          formatRate(p.first_contact_resolution_rate),
          formatInt(p.mature_initial_contacts),
        ]),
      }}
    >
      <TrendLineChart
        points={trend}
        bucket={metadata.bucket}
        accessor={(p) =>
          p.first_contact_resolution_rate === null ? null : p.first_contact_resolution_rate * 100
        }
        seriesLabel="first call resolution"
        baseline={baseline.fcr_rate === null ? null : baseline.fcr_rate * 100}
        baselineLabel="synthetic baseline"
        formatValue={(v) => `${v.toFixed(1)}%`}
        formatTick={(v) => `${v}%`}
        tooltipExtras={(p) => [
          { label: 'matured initial contacts', value: formatInt(p.mature_initial_contacts) },
        ]}
        height={height}
      />
    </ChartCard>
  )
}

export function RepeatTrendCard({ data, height }: CardProps) {
  const { trend, baseline, metadata } = data
  return (
    <ChartCard
      title="Repeat contact rate"
      subtitle="Initial contacts followed by another contact for the same member and claim within 7 days"
      legend={trendLegend}
      caption={`${COHORT_NOTE} ${BASELINE_NOTE}`}
      table={{
        columns: [
          { header: 'Period' },
          { header: 'Repeat rate', align: 'right' },
          { header: 'Matured contacts', align: 'right' },
        ],
        rows: trend.map((p) => [
          periodLabel(p.period_start, metadata.bucket),
          formatRate(p.repeat_contact_rate),
          formatInt(p.mature_initial_contacts),
        ]),
      }}
    >
      <TrendLineChart
        points={trend}
        bucket={metadata.bucket}
        accessor={(p) => (p.repeat_contact_rate === null ? null : p.repeat_contact_rate * 100)}
        seriesLabel="repeat contact rate"
        baseline={
          baseline.repeat_contact_rate === null ? null : baseline.repeat_contact_rate * 100
        }
        baselineLabel="synthetic baseline"
        formatValue={(v) => `${v.toFixed(1)}%`}
        formatTick={(v) => `${v}%`}
        tooltipExtras={(p) => [
          { label: 'matured initial contacts', value: formatInt(p.mature_initial_contacts) },
        ]}
        height={height}
      />
    </ChartCard>
  )
}

export function VolumeCard({ data, height }: CardProps) {
  const { trend, metadata } = data
  return (
    <ChartCard
      title="Automated vs manual volume"
      subtitle="Completed calls by routing mode"
      legend={[
        { label: 'Automated', color: chartColors.accent, kind: 'rect' },
        { label: 'Manual review', color: chartColors.muted, kind: 'rect' },
      ]}
      table={{
        columns: [
          { header: 'Period' },
          { header: 'Automated', align: 'right' },
          { header: 'Manual review', align: 'right' },
          { header: 'Completed sessions', align: 'right' },
        ],
        rows: trend.map((p) => [
          periodLabel(p.period_start, metadata.bucket),
          formatInt(p.automated_calls),
          formatInt(p.manual_review_calls),
          formatInt(p.completed_sessions),
        ]),
      }}
    >
      <ColumnChart
        points={trend}
        bucket={metadata.bucket}
        series={[
          { label: 'automated', color: chartColors.accent, accessor: (p) => p.automated_calls },
          { label: 'manual review', color: chartColors.muted, accessor: (p) => p.manual_review_calls },
        ]}
        totalRow={{ label: 'completed sessions', accessor: (p) => p.completed_sessions }}
        height={height}
      />
    </ChartCard>
  )
}

export function CohortColumnCard({ data, height }: CardProps) {
  const { trend, metadata } = data
  return (
    <ChartCard
      title="Matured cohort size"
      subtitle="Initial contacts with a complete 7-day follow-up window, per period"
      caption="Small cohorts make the period's rate less stable — recent periods mature over the following week."
      table={{
        columns: [{ header: 'Period' }, { header: 'Matured initial contacts', align: 'right' }],
        rows: trend.map((p) => [
          periodLabel(p.period_start, metadata.bucket),
          formatInt(p.mature_initial_contacts),
        ]),
      }}
    >
      <ColumnChart
        points={trend}
        bucket={metadata.bucket}
        series={[
          {
            label: 'matured initial contacts',
            color: chartColors.accent,
            accessor: (p) => p.mature_initial_contacts,
          },
        ]}
        height={height}
      />
    </ChartCard>
  )
}

export function RepWorkloadCard({ data }: CardProps) {
  const reps = data.manual_by_rep
  const totalManual = reps.reduce((sum, rep) => sum + rep.manual_review_calls, 0)
  return (
    <ChartCard
      title="Manual review by representative"
      subtitle="Aggregate workload in the selected range"
      table={{
        columns: [{ header: 'Representative' }, { header: 'Manual review calls', align: 'right' }],
        rows: reps.map((rep) => [rep.username, formatInt(rep.manual_review_calls)]),
      }}
    >
      <HBarChart
        items={reps.map((rep) => ({
          label: rep.username,
          value: rep.manual_review_calls,
          display: formatInt(rep.manual_review_calls),
          tooltip: (
            <>
              <TooltipTitle>{rep.username}</TooltipTitle>
              <TooltipRow
                seriesColor={chartColors.accent}
                label="manual review calls"
                value={formatInt(rep.manual_review_calls)}
              />
              <TooltipRow
                label="of manual volume"
                value={totalManual > 0 ? formatRate(rep.manual_review_calls / totalManual) : '—'}
              />
            </>
          ),
        }))}
      />
    </ChartCard>
  )
}

export function FunnelCard({ data }: CardProps) {
  const { interventions } = data
  const coverage =
    interventions.recorded_coverage_rate === null
      ? '—'
      : formatRate(interventions.recorded_coverage_rate)
  const stages = [
    {
      label: 'Identified',
      value: interventions.identified_claims,
      opacity: 0.4,
      note: 'distinct claims with an intervention-risk detection',
    },
    {
      label: 'Recommended',
      value: interventions.recommended_claims,
      opacity: 0.7,
      note: 'identified claims that reached recommendation',
    },
    {
      label: 'Recorded',
      value: interventions.recorded_claims,
      opacity: 1,
      note: 'corrective intervention recorded — workflow completion, not a claim outcome',
    },
  ]
  return (
    <ChartCard
      title="Denial Intervention Pipeline"
      subtitle="Corrective workflow activity; final adjudication outcomes are not measured."
      caption={`${formatInt(interventions.recorded_claims)} of ${formatInt(interventions.identified_claims)} identified at-risk claims have a corrective intervention recorded (${coverage} detected-to-recorded coverage).`}
      table={{
        columns: [{ header: 'Stage' }, { header: 'Distinct claims', align: 'right' }],
        rows: stages.map((stage) => [stage.label, formatInt(stage.value)]),
      }}
    >
      <HBarChart
        maxValue={Math.max(interventions.identified_claims, 1)}
        items={stages.map((stage) => ({
          label: stage.label,
          value: stage.value,
          display: formatInt(stage.value),
          opacity: stage.opacity,
          tooltip: (
            <>
              <TooltipTitle>{stage.label}</TooltipTitle>
              <TooltipRow
                seriesColor={chartColors.accent}
                label="distinct claims"
                value={formatInt(stage.value)}
              />
              <div className="mt-0.5 max-w-52 text-micro whitespace-normal text-text-tertiary">
                {stage.note}
              </div>
            </>
          ),
        }))}
      />
    </ChartCard>
  )
}
