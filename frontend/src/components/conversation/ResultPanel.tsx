import type { ReactNode } from 'react'
import { Badge, Panel, type StatusVariant } from '@/components/ui'

export function ResultPanel({
  title,
  summary,
  tone = 'neutral',
  badge,
  children,
  source,
}: {
  title: string
  summary: string
  tone?: StatusVariant
  badge?: string
  children?: ReactNode
  source?: string
}) {
  return (
    <Panel dense className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-small font-medium text-text-primary">{title}</h3>
          <p className="mt-1 text-regular text-text-secondary">{summary}</p>
        </div>
        {badge && <Badge variant={tone}>{badge}</Badge>}
      </div>
      {children}
      {source && (
        <p className="border-t border-border-tertiary pt-2 text-micro text-text-quaternary">
          Source · {source}
        </p>
      )}
    </Panel>
  )
}
