import { Button, Tooltip, TooltipTrigger } from 'react-aria-components'
import { Info } from 'lucide-react'

export function InfoTooltip({ label, children }: { label: string; children: string }) {
  return (
    <TooltipTrigger delay={200} closeDelay={100}>
      <Button
        aria-label={label}
        className="flex size-6 shrink-0 items-center justify-center rounded-sm text-text-quaternary transition-colors data-hovered:bg-bg-tertiary data-hovered:text-text-secondary"
      >
        <Info size={14} strokeWidth={1.5} aria-hidden="true" />
      </Button>
      <Tooltip
        placement="bottom start"
        offset={6}
        className="max-w-80 rounded-md border border-border-primary bg-bg-primary px-3 py-2 text-small text-text-secondary shadow-float data-entering:animate-pop-in data-exiting:animate-pop-out"
      >
        {children}
      </Tooltip>
    </TooltipTrigger>
  )
}
