import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface PanelProps extends HTMLAttributes<HTMLDivElement> {
  /** space-3 padding instead of space-4, for dense/compact panels. */
  dense?: boolean
  /** 1px hairline border — only when background contrast alone can't separate the surface. */
  bordered?: boolean
}

export function Panel({ dense = false, bordered = false, className, ...props }: PanelProps) {
  return (
    <div
      {...props}
      className={cn(
        'rounded-md bg-bg-secondary',
        dense ? 'p-3' : 'p-4',
        bordered && 'border border-border-primary',
        className,
      )}
    />
  )
}
