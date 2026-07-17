import { PageHeader } from '@/components/PageHeader'
import { DashboardPageFrame } from '@/components/dashboard/DashboardPageFrame'
import { OverviewTab } from '@/components/dashboard/OverviewTab'

export function DashboardPage() {
  return (
    <div className="flex flex-col">
      <PageHeader
        title="Dashboard"
        description="Handle time, first-call resolution, repeat contacts, and preventable denials as sessions complete."
      />
      <DashboardPageFrame>{(data) => <OverviewTab data={data} />}</DashboardPageFrame>
    </div>
  )
}
