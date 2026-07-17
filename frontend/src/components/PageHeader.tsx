import { Button, Tooltip, TooltipTrigger } from 'react-aria-components'
import { Info } from 'lucide-react'

export interface PageHeaderProps {
  title: string
  /** Shown in a tooltip behind the (i) icon; omit to hide the icon. */
  description?: string
}

/** Compact in-card header bar: title left, hairline divider below. */
export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <header className="sticky top-0 z-10 flex h-11 shrink-0 items-center gap-1 border-b border-border-secondary bg-bg-primary px-6">
      <h1 className="text-small font-medium text-text-primary">{title}</h1>
      {description && (
        <TooltipTrigger delay={200} closeDelay={100}>
          <Button
            aria-label={`About ${title}`}
            className="flex size-6 items-center justify-center rounded-sm text-text-quaternary transition-colors data-hovered:bg-bg-tertiary data-hovered:text-text-secondary"
          >
            <Info size={14} strokeWidth={1.5} aria-hidden="true" />
          </Button>
          <Tooltip
            placement="bottom start"
            offset={6}
            className="max-w-72 rounded-md border border-border-primary bg-bg-primary px-3 py-2 text-small text-text-secondary shadow-float data-entering:animate-pop-in data-exiting:animate-pop-out"
          >
            {description}
          </Tooltip>
        </TooltipTrigger>
      )}
    </header>
  )
}
