import type { ReactNode } from 'react'
import { InfoTooltip } from '@/components/ui'

export interface PageHeaderProps {
  title: string
  /** Shown in a tooltip behind the (i) icon; omit to hide the icon. */
  description?: string
  actions?: ReactNode
}

/** Compact in-card header bar: title left, quiet actions right, hairline divider below. */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <header className="sticky top-0 z-10 flex h-11 shrink-0 items-center gap-1 border-b border-border-secondary bg-bg-primary px-6">
      <h1 className="text-small font-medium text-text-primary">{title}</h1>
      {description && <InfoTooltip label={`About ${title}`}>{description}</InfoTooltip>}
      {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
    </header>
  )
}
