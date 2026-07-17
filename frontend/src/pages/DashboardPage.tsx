import { PageHeader } from '@/components/PageHeader'

export function DashboardPage() {
  return (
    <div className="flex flex-col">
      <PageHeader
        title="Dashboard"
        description="Handle time, first-call resolution, repeat contacts, and preventable denials as sessions complete."
      />
      <div className="flex flex-col gap-8 p-6" />
    </div>
  )
}
