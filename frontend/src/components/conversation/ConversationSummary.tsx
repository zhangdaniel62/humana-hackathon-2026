import { Badge, Panel, type StatusVariant } from '@/components/ui'
import type { ProjectedSessionSummary, ProjectedSummarySection } from '@/lib/conversationSummary'

function humanize(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

function toneFor(section: ProjectedSummarySection): StatusVariant {
  const status = section.status?.toLowerCase()
  if (!status) return 'neutral'
  if (['verified', 'not required', 'not_required', 'covered', 'clear', 'ready', 'success', 'ok'].includes(status)) {
    return 'success'
  }
  if (['missing', 'expired', 'unknown', 'denied', 'high', 'restricted'].includes(status)) return 'danger'
  if (['warning', 'incomplete', 'ambiguous', 'needs_escalation', 'needs escalation'].includes(status)) {
    return 'warning'
  }
  return 'info'
}

export function ConversationSummary({ summary }: { summary: ProjectedSessionSummary }) {
  return (
    <section aria-label="Structured session findings" className="mt-6 border-t border-border-secondary pt-6">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-small font-semibold text-text-primary">Session findings</h2>
        <Badge variant={summary.status === 'ready' ? 'success' : 'neutral'}>
          {humanize(summary.status)}
        </Badge>
      </div>

      {summary.sections.length > 0 && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {summary.sections.map((section) => (
            <Panel key={section.key} dense bordered className="flex flex-col gap-3">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-small font-medium text-text-primary">{section.title}</h3>
                {section.status && <Badge variant={toneFor(section)}>{humanize(section.status)}</Badge>}
              </div>
              {section.summary && <p className="text-regular leading-6 text-text-secondary">{section.summary}</p>}
              {section.details.length > 0 && (
                <dl className="grid grid-cols-1 gap-2">
                  {section.details.map((detail, index) => (
                    <div key={`${detail.label}-${index}`}>
                      <dt className="text-mini text-text-tertiary">{detail.label}</dt>
                      <dd className="mt-0.5 text-small text-text-secondary">{detail.value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </Panel>
          ))}
        </div>
      )}

      {summary.status === 'incomplete' && summary.missingFindings.length > 0 && (
        <p className="mt-3 text-mini text-text-tertiary">
          Awaiting backend findings: {summary.missingFindings.map(humanize).join(', ')}
        </p>
      )}
    </section>
  )
}
