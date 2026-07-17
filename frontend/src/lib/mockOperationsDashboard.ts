import type {
  DashboardBucket,
  DashboardQuery,
  IsoDate,
  OperationsDashboardResponse,
  TrendPoint,
} from './operationsDashboard'

/**
 * Local synthetic dataset shaped exactly like the backend's seeded response
 * (assets/docs/dashboard_frontend_contract.md). Deterministic: 26 weekly rows
 * of integer counts (Mondays 2026-01-12 → 2026-07-06) interpolated between the
 * contract's example first/last trend points, then nudged so the full-range
 * aggregates land on the contract's summary numbers. Rates are always derived
 * from the integer counts, so any range/bucket stays internally consistent
 * (resolved + repeats ≤ mature ≤ sessions, stacks sum to sessions, …).
 */

/** Earliest synthetic event date / end of the latest completed week. */
export const MOCK_RANGE = { start: '2026-01-12', end: '2026-07-12' } as const

const OBSERVATION_CUTOFF = '2026-07-13T17:10:00Z'
const WEEK_COUNT = 26
const REPS = ['rep.alex', 'rep.jordan', 'rep.morgan', 'rep.taylor'] as const

const BASELINE = {
  aht_minutes: 8.5,
  fcr_rate: 0.72,
  repeat_contact_rate: 0.18,
  source_note: 'Labeled synthetic hackathon comparison assumptions',
  data_label: 'synthetic_demo_assumption',
} as const

interface WeekRow {
  /** Monday, ISO date. */
  periodStart: IsoDate
  sessions: number
  /** Already rounded to 2 decimals; weekly mean of duration_seconds / 60. */
  ahtMinutes: number
  mature: number
  resolved: number
  repeats: number
  automated: number
  manual: number
  /** Manual calls per rep, same order as REPS. */
  manualByRep: number[]
  identified: number
  recommended: number
  recorded: number
}

const DAY_MS = 86_400_000

function toUtcMs(iso: IsoDate): number {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}

function toIso(ms: number): IsoDate {
  return new Date(ms).toISOString().slice(0, 10)
}

function monthStart(iso: IsoDate): IsoDate {
  return `${iso.slice(0, 7)}-01`
}

function round2(value: number): number {
  return Math.round(value * 100) / 100
}

function round4(value: number): number {
  return Math.round(value * 10_000) / 10_000
}

function sum(values: number[]): number {
  return values.reduce((total, v) => total + v, 0)
}

/**
 * Nudge interior values by ±1 until the series sums to `target`, keeping each
 * value inside [min(i), max(i)]. First and last entries stay anchored to the
 * contract's example trend points.
 */
function adjustToTotal(
  values: number[],
  target: number,
  min: (i: number) => number,
  max: (i: number) => number,
): void {
  let diff = target - sum(values)
  let guard = 10_000
  while (diff !== 0 && guard > 0) {
    for (let i = 1; i < values.length - 1 && diff !== 0; i++) {
      if (diff > 0 && values[i] < max(i)) {
        values[i] += 1
        diff -= 1
      } else if (diff < 0 && values[i] > min(i)) {
        values[i] -= 1
        diff += 1
      }
      guard -= 1
    }
  }
}

function buildWeeks(): WeekRow[] {
  const startMs = toUtcMs(MOCK_RANGE.start)
  const t = (i: number) => i / (WEEK_COUNT - 1)

  // Completed sessions: gentle growth with wobble; full range totals 1520.
  const sessions = Array.from({ length: WEEK_COUNT }, (_, i) =>
    Math.round(55 + 3 * t(i) + 6 * Math.sin(i * 1.7) + 3 * Math.sin(i * 0.6)),
  )
  sessions[0] = 55
  sessions[WEEK_COUNT - 1] = 58
  adjustToTotal(sessions, 1520, () => 40, () => 75)

  // Automated routing share rises over the pilot; totals 1090 (manual 430).
  const automated = sessions.map((s, i) =>
    Math.round(s * (0.6545 + 0.2248 * t(i) + 0.05 * Math.sin(i * 2.1))),
  )
  automated[0] = 36
  automated[WEEK_COUNT - 1] = 51
  adjustToTotal(automated, 1090, () => 1, (i) => sessions[i] - 3)
  const manual = sessions.map((s, i) => s - automated[i])

  // Mature initial contacts: ~85% of sessions while the 7-day window is fully
  // observable; the trailing weeks are mostly immature. Totals 1266.
  const mature = sessions.map((s, i) => {
    if (i === WEEK_COUNT - 1) return 8
    if (i === WEEK_COUNT - 2) return Math.round(s * 0.45)
    return Math.round(s * 0.85 + 2.5 * Math.sin(i * 1.3))
  })
  mature[0] = 47
  adjustToTotal(mature, 1266, (i) => (i >= WEEK_COUNT - 2 ? 0 : 20), (i) => sessions[i])

  // First-contact resolutions improve from .66 toward .875; totals 921.
  const resolved = mature.map((m, i) =>
    Math.round(m * (0.6596 + 0.2154 * t(i) + 0.03 * Math.sin(i * 1.9))),
  )
  resolved[0] = 31
  resolved[WEEK_COUNT - 1] = 7
  adjustToTotal(resolved, 921, () => 0, (i) => mature[i])

  // Repeat contacts fall from .234 toward zero; totals 204.
  const repeats = mature.map((m, i) =>
    Math.round(m * Math.max(0, 0.234 - 0.234 * t(i) + 0.025 * Math.sin(i * 1.1))),
  )
  repeats[0] = 11
  repeats[WEEK_COUNT - 1] = 0
  adjustToTotal(repeats, 204, () => 0, (i) => mature[i] - resolved[i])

  // AHT holds near 8.6 early, then falls to 5.91; the convex curve keeps the
  // range-weighted mean at the contract's 7.67.
  const aht = Array.from({ length: WEEK_COUNT }, (_, i) =>
    round2(8.64 - 2.73 * t(i) ** 1.8 + 0.38 * Math.sin(i * 1.5)),
  )
  aht[0] = 8.64
  aht[WEEK_COUNT - 1] = 5.91

  // Corrective-intervention workflow stages; full-range totals 26 / 23 / 17.
  const noRecommendation = new Set([4, 12, 20])
  const noRecord = new Set([2, 7, 9, 15, 18, 24])
  const identified = Array.from({ length: WEEK_COUNT }, () => 1)
  const recommended = identified.map((v, i) => (noRecommendation.has(i) ? 0 : v))
  const recorded = recommended.map((v, i) => (noRecord.has(i) ? 0 : v))

  return Array.from({ length: WEEK_COUNT }, (_, i) => {
    // Rotate the remainder so rep workloads stay near-even over any range.
    const perRep = REPS.map((_, j) =>
      Math.floor(manual[i] / REPS.length) + ((j + i) % REPS.length < manual[i] % REPS.length ? 1 : 0),
    )
    return {
      periodStart: toIso(startMs + i * 7 * DAY_MS),
      sessions: sessions[i],
      ahtMinutes: aht[i],
      mature: mature[i],
      resolved: resolved[i],
      repeats: repeats[i],
      automated: automated[i],
      manual: manual[i],
      manualByRep: perRep,
      identified: identified[i],
      recommended: recommended[i],
      recorded: recorded[i],
    }
  })
}

const WEEKS: WeekRow[] = buildWeeks()

interface Aggregate {
  sessions: number
  handleMinutes: number
  mature: number
  resolved: number
  repeats: number
  automated: number
  manual: number
}

function aggregate(rows: WeekRow[]): Aggregate {
  return rows.reduce<Aggregate>(
    (acc, row) => ({
      sessions: acc.sessions + row.sessions,
      handleMinutes: acc.handleMinutes + row.ahtMinutes * row.sessions,
      mature: acc.mature + row.mature,
      resolved: acc.resolved + row.resolved,
      repeats: acc.repeats + row.repeats,
      automated: acc.automated + row.automated,
      manual: acc.manual + row.manual,
    }),
    { sessions: 0, handleMinutes: 0, mature: 0, resolved: 0, repeats: 0, automated: 0, manual: 0 },
  )
}

function toMetrics(agg: Aggregate) {
  return {
    completed_sessions: agg.sessions,
    average_handle_time_minutes: agg.sessions > 0 ? round2(agg.handleMinutes / agg.sessions) : null,
    mature_initial_contacts: agg.mature,
    first_contact_resolution_rate: agg.mature > 0 ? round4(agg.resolved / agg.mature) : null,
    repeat_contact_rate: agg.mature > 0 ? round4(agg.repeats / agg.mature) : null,
    automated_calls: agg.automated,
    manual_review_calls: agg.manual,
  }
}

/**
 * Client-side stand-in for `GET /api/operations/dashboard`: filters the weekly
 * rows to the requested range, re-buckets to months when asked, and aggregates
 * every derived figure from the underlying integer counts.
 */
export function buildMockDashboardResponse(params: DashboardQuery = {}): OperationsDashboardResponse {
  const start = params.start ?? MOCK_RANGE.start
  const end = params.end ?? MOCK_RANGE.end
  const bucket: DashboardBucket = params.bucket ?? 'week'

  const selected =
    start <= end ? WEEKS.filter((w) => w.periodStart >= start && w.periodStart <= end) : []

  const groups = new Map<IsoDate, WeekRow[]>()
  for (const week of selected) {
    const key = bucket === 'month' ? monthStart(week.periodStart) : week.periodStart
    const group = groups.get(key)
    if (group) group.push(week)
    else groups.set(key, [week])
  }

  const trend: TrendPoint[] = [...groups.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([periodStart, rows]) => ({ ...toMetrics(aggregate(rows)), period_start: periodStart }))

  const repTotals = REPS.map((username, j) => ({
    username,
    manual_review_calls: sum(selected.map((w) => w.manualByRep[j])),
  }))
    .filter((rep) => rep.manual_review_calls > 0)
    .sort((a, b) =>
      b.manual_review_calls - a.manual_review_calls || (a.username < b.username ? -1 : 1),
    )

  const identified = sum(selected.map((w) => w.identified))
  const recommended = sum(selected.map((w) => w.recommended))
  const recorded = sum(selected.map((w) => w.recorded))

  return {
    metadata: {
      data_label: 'synthetic_demo',
      start,
      end,
      bucket,
      repeat_window_days: 7,
      observation_cutoff: OBSERVATION_CUTOFF,
    },
    baseline: { ...BASELINE },
    summary: toMetrics(aggregate(selected)),
    trend,
    interventions: {
      identified_claims: identified,
      recommended_claims: recommended,
      recorded_claims: recorded,
      recorded_coverage_rate: identified > 0 ? round4(recorded / identified) : null,
    },
    manual_by_rep: repTotals,
  }
}
