import { Navigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { dashboardMetrics } from '@/app/metrics'
import { DashboardPageFrame } from '@/components/dashboard/DashboardPageFrame'
import { AhtTab, DenialsTab, FcrTab, RepeatTab } from '@/components/dashboard/MetricTabs'
import type { OperationsDashboardResponse } from '@/lib/operationsDashboard'

const tabsBySlug: Record<string, (props: { data: OperationsDashboardResponse }) => ReturnType<typeof AhtTab>> = {
  'average-handle-time': AhtTab,
  'first-call-resolution': FcrTab,
  'repeat-contacts': RepeatTab,
  'preventable-denials': DenialsTab,
}

export function MetricPage() {
  const { metricSlug } = useParams()
  const metric = dashboardMetrics.find((m) => m.slug === metricSlug)
  const Tab = metricSlug ? tabsBySlug[metricSlug] : undefined

  if (!metric || !Tab) return <Navigate to="/" replace />

  return (
    <div className="flex flex-col">
      <PageHeader title={metric.pageTitle} description={metric.description} />
      <DashboardPageFrame>{(data) => <Tab data={data} />}</DashboardPageFrame>
    </div>
  )
}
