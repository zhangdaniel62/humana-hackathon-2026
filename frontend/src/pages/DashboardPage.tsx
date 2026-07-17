import { PageHeader } from '@/components/PageHeader'
import { DashboardPageFrame } from '@/components/dashboard/DashboardPageFrame'
import { OverviewTab } from '@/components/dashboard/OverviewTab'

export function DashboardPage() {
  return (
    <div className="flex flex-col">
      <PageHeader
        title="Operations Dashboard"
        description="Synthetic operations data for handle time, seven-day matured contact outcomes, routing volume, representative workload, and corrective intervention activity. Recorded interventions do not prove a denial was prevented."
      />
      <DashboardPageFrame>{(data) => <OverviewTab data={data} />}</DashboardPageFrame>
    </div>
  )
}
