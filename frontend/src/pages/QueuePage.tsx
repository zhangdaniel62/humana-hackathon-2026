import { PageHeader } from '@/components/PageHeader'

export function QueuePage() {
  return (
    <div className="flex flex-col">
      <PageHeader
        title="Representative Queue"
        description="Sessions handed off by the AI, first in, first served."
      />
      <div className="flex flex-col gap-8 p-6" />
    </div>
  )
}
