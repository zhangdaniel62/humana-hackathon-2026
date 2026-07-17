import {
  Tab as AriaTab,
  TabList as AriaTabList,
  TabPanel as AriaTabPanel,
  Tabs as AriaTabs,
  type TabListProps,
  type TabPanelProps,
  type TabProps,
  type TabsProps,
} from 'react-aria-components'
import { cn } from '@/lib/cn'

export function Tabs({ className, ...props }: Omit<TabsProps, 'className'> & { className?: string }) {
  return <AriaTabs {...props} className={cn('flex flex-col', className)} />
}

export function TabList<T extends object>({
  className,
  ...props
}: Omit<TabListProps<T>, 'className'> & { className?: string }) {
  return <AriaTabList {...props} className={cn('flex items-center gap-1', className)} />
}

/** Selection is a raised pill fill — no underline (design_system.md §10). */
export function Tab({ className, ...props }: Omit<TabProps, 'className'> & { className?: string }) {
  return (
    <AriaTab
      {...props}
      className={cn(
        'flex h-7 cursor-default items-center rounded-md px-3 text-small font-medium text-text-tertiary transition-colors',
        'data-hovered:bg-bg-secondary/60 data-hovered:text-text-secondary',
        'data-selected:bg-bg-secondary data-selected:text-text-primary',
        'data-disabled:text-text-quaternary',
        className,
      )}
    />
  )
}

export function TabPanel({
  className,
  ...props
}: Omit<TabPanelProps, 'className'> & { className?: string }) {
  return <AriaTabPanel {...props} className={cn('pt-4', className)} />
}
