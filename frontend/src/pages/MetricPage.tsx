import { Navigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { dashboardMetrics } from '@/app/metrics'

export function MetricPage() {
  const { metricSlug } = useParams()
  const metric = dashboardMetrics.find((m) => m.slug === metricSlug)

  if (!metric) return <Navigate to="/" replace />

  return (
    <div className="flex flex-col">
      <PageHeader title={metric.label} />
      <div className="flex flex-col gap-8 p-6" />
    </div>
  )
}
