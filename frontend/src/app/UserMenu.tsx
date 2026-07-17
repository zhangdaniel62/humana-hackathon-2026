import { Button, Menu, MenuItem, MenuTrigger, Popover } from 'react-aria-components'
import { LogOut } from 'lucide-react'
import { useAuth } from '@/lib/auth-context'
import { cn } from '@/lib/cn'

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2)
  return parts.map((part) => part[0]?.toUpperCase() ?? '').join('') || '?'
}

export function UserMenu({ className }: { className?: string }) {
  const { user, signOut } = useAuth()

  if (!user) return null

  return (
    <MenuTrigger>
      <Button
        className={cn(
          'flex w-full items-center gap-2 rounded-md p-2 text-left transition-colors',
          'data-hovered:bg-bg-tertiary data-pressed:bg-bg-tertiary',
          className,
        )}
      >
        <span
          aria-hidden="true"
          className="flex size-7 shrink-0 items-center justify-center rounded-full bg-bg-quaternary text-mini font-medium text-text-secondary"
        >
          {initials(user.name)}
        </span>
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-small font-medium text-text-primary">{user.name}</span>
          <span className="truncate text-mini text-text-tertiary">{user.role}</span>
        </span>
      </Button>
      <Popover
        placement="top start"
        offset={4}
        className="w-52 rounded-md border border-border-primary bg-bg-primary p-1 shadow-float data-entering:animate-pop-in data-exiting:animate-pop-out"
      >
        <Menu aria-label="Account" className="outline-none">
          <MenuItem
            textValue="Sign out"
            onAction={signOut}
            className="flex h-8 cursor-default items-center gap-2 rounded-sm px-2 text-small text-text-secondary outline-none transition-colors data-focused:bg-bg-tertiary"
          >
            <LogOut size={16} strokeWidth={1.5} className="text-text-tertiary" aria-hidden="true" />
            Sign out
          </MenuItem>
        </Menu>
      </Popover>
    </MenuTrigger>
  )
}
