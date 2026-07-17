export interface DashboardMetric {
  slug: string
  label: string
  pageTitle: string
  description: string
}

/** The four success metrics from design_philosophy.md's Design Goals. */
export const dashboardMetrics: DashboardMetric[] = [
  {
    slug: 'average-handle-time',
    label: 'Average Handle Time',
    pageTitle: 'Average Handle Time',
    description:
      'Average call-session duration across selected calls, including follow-ups. After-call work is not separately tracked; the comparison baseline is a labeled synthetic assumption and lower is better.',
  },
  {
    slug: 'first-call-resolution',
    label: 'First Call Resolution',
    pageTitle: 'First Call Resolution',
    description:
      'Mature initial contacts resolved with no repeat contact for the same member and claim within seven days. The baseline is synthetic and higher is better.',
  },
  {
    slug: 'repeat-contacts',
    label: 'Repeat Contacts',
    pageTitle: 'Repeat Contact Rate',
    description:
      'Mature initial contacts followed by another contact for the same member and claim within seven days. The baseline is synthetic and lower is better.',
  },
  {
    slug: 'preventable-denials',
    label: 'Denial Intervention',
    pageTitle: 'Denial Intervention Pipeline',
    description:
      'Corrective workflow activity from identified risk through a recorded intervention. Final adjudication outcomes are not measured, so recorded activity is not proof that a denial was prevented.',
  },
]
