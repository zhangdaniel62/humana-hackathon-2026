export interface DashboardMetric {
  slug: string
  label: string
}

/** The four success metrics from design_philosophy.md's Design Goals. */
export const dashboardMetrics: DashboardMetric[] = [
  { slug: 'average-handle-time', label: 'Average Handle Time' },
  { slug: 'first-call-resolution', label: 'First Call Resolution' },
  { slug: 'repeat-contacts', label: 'Repeat Contacts' },
  { slug: 'preventable-denials', label: 'Preventable Denials' },
]
