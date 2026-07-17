import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export type StatusVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral'

const badgeClasses: Record<StatusVariant, string> = {
  success: 'border-success-border bg-success-bg text-success',
  warning: 'border-warning-border bg-warning-bg text-warning',
  danger: 'border-danger-border bg-danger-bg text-danger',
  info: 'border-info-border bg-info-bg text-info',
  neutral: 'border-border-primary bg-bg-tertiary text-text-secondary',
}

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: StatusVariant
}

export function Badge({ variant = 'neutral', className, ...props }: BadgeProps) {
  return (
    <span
      {...props}
      className={cn(
        'inline-flex h-5 items-center rounded-sm border px-1.5 text-micro font-medium',
        badgeClasses[variant],
        className,
      )}
    />
  )
}

const dotClasses: Record<StatusVariant, string> = {
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-info',
  neutral: 'bg-text-quaternary',
}

export interface DotProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: StatusVariant
  /** Accessible name for the status; omit only when adjacent text already states it. */
  label?: string
}

export function Dot({ variant = 'neutral', label, className, ...props }: DotProps) {
  return (
    <span
      {...props}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn('inline-block size-1.5 rounded-full', dotClasses[variant], className)}
    />
  )
}
