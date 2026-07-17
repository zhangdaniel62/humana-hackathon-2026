import { Button as AriaButton, type ButtonProps as AriaButtonProps } from 'react-aria-components'
import { cn } from '@/lib/cn'

type ButtonVariant = 'primary' | 'secondary' | 'ghost'
type ButtonSize = 'default' | 'sm'

export interface ButtonProps extends Omit<AriaButtonProps, 'className'> {
  variant?: ButtonVariant
  size?: ButtonSize
  /** Square button holding a single icon; requires `aria-label`. */
  iconOnly?: boolean
  className?: string
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-accent text-white data-hovered:bg-accent-hover data-pressed:bg-accent-hover data-disabled:bg-bg-tertiary data-disabled:text-text-quaternary',
  secondary:
    'border border-border-primary bg-bg-secondary text-text-primary data-hovered:bg-bg-tertiary data-pressed:bg-bg-tertiary data-disabled:border-transparent data-disabled:bg-bg-secondary data-disabled:text-text-quaternary',
  ghost:
    'bg-transparent text-text-secondary data-hovered:bg-bg-tertiary data-pressed:bg-bg-tertiary data-disabled:bg-transparent data-disabled:text-text-quaternary',
}

const sizeClasses: Record<ButtonSize, { base: string; iconOnly: string }> = {
  default: { base: 'h-8 px-3', iconOnly: 'size-8' },
  sm: { base: 'h-7 px-2', iconOnly: 'size-7' },
}

export function Button({
  variant = 'secondary',
  size = 'default',
  iconOnly = false,
  className,
  ...props
}: ButtonProps) {
  return (
    <AriaButton
      {...props}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-md text-small font-medium transition-colors',
        variantClasses[variant],
        iconOnly ? sizeClasses[size].iconOnly : sizeClasses[size].base,
        className,
      )}
    />
  )
}
