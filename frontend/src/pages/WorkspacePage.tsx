import { PageHeader } from '@/components/PageHeader'

export function WorkspacePage() {
  return (
    <div className="flex flex-col">
      <PageHeader
        title="Interaction Workspace"
        description="The active session: what the member asked, what the AI found, and why it escalated."
      />
      <div className="flex flex-col gap-8 p-6" />
    </div>
  )
}
