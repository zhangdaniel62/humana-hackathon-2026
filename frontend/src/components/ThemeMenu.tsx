import {
  Button,
  Menu,
  MenuItem,
  MenuTrigger,
  Popover,
  type PopoverProps,
} from 'react-aria-components'
import { Check, Monitor, Moon, Sun, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/cn'
import { useTheme } from '@/lib/theme-context'
import type { ThemePreference } from '@/lib/theme'

const themeOptions: Array<{
  id: ThemePreference
  label: string
  icon: LucideIcon
}> = [
  { id: 'light', label: 'Light', icon: Sun },
  { id: 'dark', label: 'Dark', icon: Moon },
  { id: 'system', label: 'System', icon: Monitor },
]

export function ThemeMenu({
  placement = 'bottom end',
  variant = 'icon',
  className,
}: {
  placement?: PopoverProps['placement']
  variant?: 'icon' | 'row'
  className?: string
}) {
  const { preference, resolvedTheme, setPreference } = useTheme()
  const current = themeOptions.find((option) => option.id === preference) ?? themeOptions[2]
  const CurrentIcon = current.icon
  const description = preference === 'system' ? `System (${resolvedTheme})` : current.label

  return (
    <MenuTrigger>
      <Button
        aria-label={`Theme: ${description}`}
        className={cn(
          'rounded-md text-text-secondary outline-none transition-colors data-hovered:bg-bg-tertiary data-pressed:bg-bg-tertiary',
          variant === 'row'
            ? 'flex h-8 w-full items-center gap-2 px-2 text-small'
            : 'flex size-8 items-center justify-center',
          className,
        )}
      >
        <CurrentIcon size={16} strokeWidth={1.5} aria-hidden="true" />
        {variant === 'row' && (
          <>
            <span>Appearance</span>
            <span className="ml-auto text-mini text-text-tertiary">{description}</span>
          </>
        )}
      </Button>
      <Popover
        placement={placement}
        offset={4}
        className="w-40 rounded-md border border-border-primary bg-bg-primary p-1 shadow-float data-entering:animate-pop-in data-exiting:animate-pop-out"
      >
        <Menu
          aria-label="Theme"
          selectionMode="single"
          selectedKeys={[preference]}
          className="outline-none"
        >
          {themeOptions.map((option) => {
            const Icon = option.icon
            return (
              <MenuItem
                key={option.id}
                id={option.id}
                textValue={option.label}
                onAction={() => setPreference(option.id)}
                className="flex h-8 cursor-default items-center gap-2 rounded-sm px-2 text-small text-text-secondary outline-none transition-colors data-focused:bg-bg-tertiary data-selected:text-text-primary"
              >
                <Icon size={16} strokeWidth={1.5} className="text-text-tertiary" aria-hidden="true" />
                {option.label}
                {preference === option.id && (
                  <Check size={14} strokeWidth={1.5} className="ml-auto text-accent" aria-hidden="true" />
                )}
              </MenuItem>
            )
          })}
        </Menu>
      </Popover>
    </MenuTrigger>
  )
}
