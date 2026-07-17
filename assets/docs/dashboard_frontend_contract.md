# Operations dashboard frontend contract

This is an implementation handoff for the manager dashboard. Keep the first version on the single API below. All values are labeled synthetic demo data, and intervention activity must never be described as proof that a denial was prevented.

## API and authentication

```http
GET /api/operations/dashboard?start=YYYY-MM-DD&end=YYYY-MM-DD&bucket=week
```

All query parameters are optional:

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `start` | ISO date, `YYYY-MM-DD` | earliest synthetic event date | Inclusive UTC start date. |
| `end` | ISO date, `YYYY-MM-DD` | end of the latest completed period | Inclusive UTC end date. |
| `bucket` | `week \| month` | `week` | Trend aggregation. Weeks start Monday; months start on day 1. |

When dates are omitted, the endpoint excludes the trailing incomplete week or month from displayed volume. It can still inspect later calls through `metadata.observation_cutoff` to determine whether earlier contacts repeated. Explicit dates may include a partial period.

This route is manager-only. Log in with `POST /api/auth/login`, then make requests with the HTTP-only session cookie (for a separate frontend origin, use `credentials: "include"`). `GET /api/auth/me` can restore the signed-in user. A non-manager receives `403`; no session receives `401`.

```ts
const response = await fetch(
  `/api/operations/dashboard?${new URLSearchParams({
    start: "2026-01-12",
    end: "2026-07-12",
    bucket: "week",
  })}`,
  { credentials: "include" },
);
```

## Representative seeded response

This is the current default seeded response shape and values. `trend` is shortened to its first and last points here; the actual response contains one point for each period that has calls.

```json
{
  "metadata": {
    "data_label": "synthetic_demo",
    "start": "2026-01-12",
    "end": "2026-07-12",
    "bucket": "week",
    "repeat_window_days": 7,
    "observation_cutoff": "2026-07-13T17:10:00Z"
  },
  "baseline": {
    "aht_minutes": 8.5,
    "fcr_rate": 0.72,
    "repeat_contact_rate": 0.18,
    "source_note": "Labeled synthetic hackathon comparison assumptions",
    "data_label": "synthetic_demo_assumption"
  },
  "summary": {
    "completed_sessions": 1520,
    "average_handle_time_minutes": 7.67,
    "mature_initial_contacts": 1266,
    "first_contact_resolution_rate": 0.7275,
    "repeat_contact_rate": 0.1611,
    "automated_calls": 1090,
    "manual_review_calls": 430
  },
  "trend": [
    {
      "completed_sessions": 55,
      "average_handle_time_minutes": 8.64,
      "mature_initial_contacts": 47,
      "first_contact_resolution_rate": 0.6596,
      "repeat_contact_rate": 0.234,
      "automated_calls": 36,
      "manual_review_calls": 19,
      "period_start": "2026-01-12"
    },
    {
      "completed_sessions": 58,
      "average_handle_time_minutes": 5.91,
      "mature_initial_contacts": 8,
      "first_contact_resolution_rate": 0.875,
      "repeat_contact_rate": 0.0,
      "automated_calls": 51,
      "manual_review_calls": 7,
      "period_start": "2026-07-06"
    }
  ],
  "interventions": {
    "identified_claims": 26,
    "recommended_claims": 23,
    "recorded_claims": 17,
    "recorded_coverage_rate": 0.6538
  },
  "manual_by_rep": [
    { "username": "rep.alex", "manual_review_calls": 108 },
    { "username": "rep.jordan", "manual_review_calls": 108 },
    { "username": "rep.morgan", "manual_review_calls": 107 },
    { "username": "rep.taylor", "manual_review_calls": 107 }
  ]
}
```

Seeded values are deterministic, but a caller should render the response rather than hard-code these numbers.

## Field glossary

Rates are decimal fractions (`0.7275` = `72.75%`). Date boundaries and period starts are UTC.

| Field | Type / nullable | Exact meaning |
|---|---|---|
| `metadata.data_label` | `"synthetic_demo"` | Required disclosure for the whole payload. Show “Synthetic demo data” in the UI. |
| `metadata.start`, `metadata.end` | ISO date | Effective inclusive range used by the server. Use these values to reflect defaulted filters. |
| `metadata.bucket` | `"week" \| "month"` | Actual trend grouping. |
| `metadata.repeat_window_days` | literal `7` | Follow-up observation window for FCR and repeat rate. |
| `metadata.observation_cutoff` | ISO datetime or `null` | Latest call timestamp the cohort logic can observe, capped at current time. `null` only when no calls exist. |
| `baseline.aht_minutes` | number or `null` | Synthetic comparison assumption for AHT. Lower is better. |
| `baseline.fcr_rate` | number or `null` | Synthetic FCR comparison assumption. Higher is better. |
| `baseline.repeat_contact_rate` | number or `null` | Synthetic repeat-rate comparison assumption. Lower is better. |
| `baseline.source_note` | string | Disclosure/tooltip copy for all baselines. |
| `baseline.data_label` | `"synthetic_demo_assumption"` | Confirms baselines are assumptions, not observed BigQuery facts. |
| `summary.completed_sessions` | integer | All selected call rows, including follow-up calls. This is the AHT and routing-volume population. |
| `summary.average_handle_time_minutes` | number or `null` | Mean `duration_seconds / 60` across all selected calls, rounded to 2 decimals. `null` when there are no selected calls. |
| `summary.mature_initial_contacts` | integer | Initial contacts whose complete 7-day follow-up window is observable. Denominator for both FCR and repeat rate. |
| `summary.first_contact_resolution_rate` | number or `null` | Mature initial contacts marked resolved with no same-member/same-claim follow-up within 7 days, divided by mature initial contacts; rounded to 4 decimals. |
| `summary.repeat_contact_rate` | number or `null` | Mature initial contacts with a same-member/same-claim follow-up within 7 days, divided by mature initial contacts; rounded to 4 decimals. |
| `summary.automated_calls` | integer | Selected calls handled in automated mode. |
| `summary.manual_review_calls` | integer | Selected calls routed to a representative for manual review. |
| `trend[]` | array | Same metric fields as `summary`, scoped to calls that started in each returned period. Periods with no calls are omitted, not zero-filled. |
| `trend[].period_start` | ISO date | Monday for a weekly bucket or first day of month for a monthly bucket. |
| `interventions.identified_claims` | integer | Distinct claims with an intervention-risk detection in the selected range. |
| `interventions.recommended_claims` | integer | Distinct identified claims that reached recommendation. |
| `interventions.recorded_claims` | integer | Distinct identified claims with a corrective intervention recorded. This is workflow completion, not a claim outcome. |
| `interventions.recorded_coverage_rate` | number or `null` | `recorded_claims / identified_claims`, rounded to 4 decimals; `null` when none were identified. |
| `manual_by_rep[]` | array | Manual-review workload in the selected range, sorted by descending count then username. Reps with zero calls are omitted. |
| `manual_by_rep[].username` | string | Synthetic representative username. |
| `manual_by_rep[].manual_review_calls` | integer | Calls assigned to that representative for manual review. |

### Seven-day cohort caveat

A call is an initial contact when the same member/claim pair has no contact in the preceding 7 days. It becomes mature only once 7 complete days are observable. A follow-up exactly 7 days later counts as a repeat. FCR and repeat rate therefore use `mature_initial_contacts`, not `completed_sessions`. Recent trend points can have small denominators (the seeded final week has only 8), so show the denominator in tooltips and add a “7-day matured cohort” caption. Do not interpret an immature contact as resolved or non-repeating.

## Page-by-page mapping

Use a shared date-range and weekly/monthly bucket filter across all five tabs. On every page, show a small “Synthetic demo data” badge and the selected range from `metadata`.

### 1. Overview

KPI cards:

| Card | Value | Comparison / direction |
|---|---|---|
| Average handle time | `summary.average_handle_time_minutes` as minutes | Baseline `baseline.aht_minutes`; lower is better. Improvement = `(baseline - current) / baseline`. |
| First call resolution | `summary.first_contact_resolution_rate` as percent | Baseline `baseline.fcr_rate`; higher is better. Display percentage-point delta `(current - baseline) * 100`. |
| Repeat contact rate | `summary.repeat_contact_rate` as percent | Baseline `baseline.repeat_contact_rate`; lower is better. Display favorable percentage-point reduction `(baseline - current) * 100`. |
| Intervention coverage | `interventions.recorded_coverage_rate` as percent | No baseline. Label “Corrective interventions recorded” and show `recorded / identified`; never label “denials prevented.” |

Charts:

- **Metric trend small multiples:** three line charts from `trend[].average_handle_time_minutes`, `first_contact_resolution_rate`, and `repeat_contact_rate`; x-axis `period_start`; add each corresponding baseline as a constant dashed line. Return/display the observed period value, baseline, and for FCR/repeat the `mature_initial_contacts` tooltip.
- **Automated vs manual volume:** stacked columns from `trend[].automated_calls` and `manual_review_calls`; x-axis `period_start`. Display call counts, not rates. The two series should sum to each point’s `completed_sessions`.
- **Manual review by representative:** horizontal bars from `manual_by_rep`; category `username`, value `manual_review_calls`. This is aggregate workload for the selected range, not a time trend.
- **Intervention funnel:** ordered stages `identified_claims`, `recommended_claims`, `recorded_claims`. Display counts and `recorded_coverage_rate` only as detected-to-recorded coverage.

### 2. Average Handle Time

- KPI: `summary.average_handle_time_minutes`, comparison to `baseline.aht_minutes`, plus `summary.completed_sessions` as sample size.
- Primary chart: line `trend[].average_handle_time_minutes` with constant baseline; x-axis `period_start`; tooltip includes `completed_sessions`.
- Supporting chart: stacked automated/manual call volume from the same trend to provide workload context.
- Copy: “Average call-session duration.” It does not include a separately tracked after-call-work field.

**Not available:** median, percentile, histogram, or AHT split by manual/automated/outcome. Smallest extension: add per-period `automated_aht_minutes` and `manual_review_aht_minutes`; add a `duration_distribution` object with explicit bin edges/counts if a histogram is required.

### 3. First Call Resolution

- KPI: `summary.first_contact_resolution_rate`, comparison to `baseline.fcr_rate`, with `summary.mature_initial_contacts` as denominator.
- Primary chart: line `trend[].first_contact_resolution_rate` with constant baseline; x-axis `period_start`; tooltip must include `mature_initial_contacts`.
- Supporting chart: bars of `trend[].mature_initial_contacts` to make cohort strength visible.
- Copy: “Resolved with no repeat contact for the same member and claim within 7 days.”

**Not available:** exact resolved/unresolved numerator counts, issue-type segmentation, escalation status, or outcome-stacked bars. Do not reverse-calculate an exact count from the rounded rate. Smallest extension: return `first_contact_resolved_contacts` and `unresolved_or_repeated_contacts` in summary/trend.

### 4. Repeat Contact Rate

- KPI: `summary.repeat_contact_rate`, comparison to `baseline.repeat_contact_rate`, with `summary.mature_initial_contacts` as denominator.
- Primary chart: line `trend[].repeat_contact_rate` with constant baseline; x-axis `period_start`; tooltip must include `mature_initial_contacts`.
- Supporting chart: bars of `trend[].mature_initial_contacts`.
- Copy: “Initial contacts followed by another contact for the same member and claim within 7 days.”

**Not available:** exact repeat-contact count, time-to-repeat distribution, issue/claim breakdown, or individual contact drill-down. Smallest extension: return `repeat_initial_contacts` in summary/trend. A time-to-repeat chart additionally needs duration bins and counts.

### 5. Preventable Denials / Denial Intervention

Prefer the visible title **Denial Intervention**. If navigation must follow the original bullet, use “Preventable Denials” in the tab but title the page “Denial Intervention Pipeline” with the subtitle “Corrective workflow activity; final adjudication outcomes are not measured.”

- KPI: `interventions.recorded_coverage_rate`; supporting text `${recorded_claims} of ${identified_claims} at-risk claims had a corrective intervention recorded`.
- Primary chart: three-stage funnel using identified, recommended, and recorded distinct-claim counts.
- Do not use “saved,” “avoided,” “prevented,” or “reduced denials.” The endpoint does not connect a recorded intervention to later adjudication.

**Not available:** intervention trend over time, risk-rule breakdown, claim status after intervention, or true preventable-denial rate. Smallest trend extension: add `intervention_trend[]` with `period_start`, `identified_claims`, `recommended_claims`, `recorded_claims`, and `recorded_coverage_rate`. A genuine prevention metric requires a separately sourced later adjudication outcome linked to each intervention; it cannot be inferred from this synthetic workflow table.

## Formatting and derived display values

- AHT: 2 decimals plus `min`.
- Rates: multiply by 100 and show 1–2 decimals.
- Percentage-point deltas: do not label them as percent change. Example: `0.7275 - 0.72 = +0.75 pp`.
- AHT relative improvement may be shown as a percent: `(8.5 - 7.67) / 8.5 = 9.76% lower`.
- Routing share may be derived as `automated_calls / (automated_calls + manual_review_calls)` when total is nonzero.
- Do not compute exact FCR/repeat numerator counts from rounded rates.
- For `null`, show `—` and “Not enough matured contacts” for FCR/repeat or “No calls in range” for AHT.

## Loading, errors, empty states, and filters

- **Loading:** preserve the filter controls and render skeletons; do not temporarily show `0`.
- **401:** response is `{"detail":"Authentication required"}`. Route to login, then retry after authentication.
- **403:** usually `{"detail":"Insufficient permissions"}`; an untrusted browser origin returns `{"detail":"Origin not allowed"}`. Show an access-denied state; do not retry repeatedly.
- **422:** invalid dates/bucket use FastAPI validation details; `start > end` returns `{"detail":"start must be on or before end"}`. Keep filters visible and show the returned detail.
- **Other/network error:** show a retry action and retain the last selected filters.
- **Empty range:** status is `200`; counts are `0`, metric rates/AHT and coverage are `null`, `trend` and `manual_by_rep` are `[]`. Show “No synthetic activity in this date range,” not zero-performance KPIs.
- **Sparse trend:** the API omits periods with no calls. Either leave gaps or zero-fill volume only on the client. Never zero-fill AHT/FCR/repeat rates.
- After a successful request, update filter controls from `metadata.start`, `metadata.end`, and `metadata.bucket`, because omitted dates are server-defaulted.

## TypeScript types

```ts
type IsoDate = string;
type IsoDateTime = string;
type DashboardBucket = "week" | "month";

interface MetricSummary {
  completed_sessions: number;
  average_handle_time_minutes: number | null;
  mature_initial_contacts: number;
  first_contact_resolution_rate: number | null;
  repeat_contact_rate: number | null;
  automated_calls: number;
  manual_review_calls: number;
}

interface TrendPoint extends MetricSummary {
  period_start: IsoDate;
}

interface OperationsDashboardResponse {
  metadata: {
    data_label: "synthetic_demo";
    start: IsoDate;
    end: IsoDate;
    bucket: DashboardBucket;
    repeat_window_days: 7;
    observation_cutoff: IsoDateTime | null;
  };
  baseline: {
    aht_minutes: number | null;
    fcr_rate: number | null;
    repeat_contact_rate: number | null;
    source_note: string;
    data_label: "synthetic_demo_assumption";
  };
  summary: MetricSummary;
  trend: TrendPoint[];
  interventions: {
    identified_claims: number;
    recommended_claims: number;
    recorded_claims: number;
    recorded_coverage_rate: number | null;
  };
  manual_by_rep: Array<{
    username: string;
    manual_review_calls: number;
  }>;
}
```

## Copy-paste prompt for a frontend coding agent

> Build a manager-only operations dashboard with five tabs: Overview, Average Handle Time, First Call Resolution, Repeat Contact Rate, and Denial Intervention. Use only `GET /api/operations/dashboard` with optional `start`, `end`, and `bucket=week|month`; send the existing auth cookie with `credentials: "include"`. Implement the response types and page mappings in `assets/docs/dashboard_frontend_contract.md`. Add shared date/bucket filters, loading/error/401/403/422/empty states, a visible “Synthetic demo data” disclosure, baseline directionality, and 7-day matured-cohort denominator tooltips. Never describe recorded interventions as denials prevented. Do not invent unsupported breakdowns or APIs; mark those charts unavailable. Keep the implementation consistent with the existing frontend stack and auth flow, and add focused tests for formatting, null/empty handling, permission errors, and chart mappings.
