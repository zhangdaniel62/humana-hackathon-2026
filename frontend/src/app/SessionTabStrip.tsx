import { Button, Tag, TagGroup, TagList } from 'react-aria-components'
import { Plus, X } from 'lucide-react'
import { Dot } from '@/components/ui'
import { cn } from '@/lib/cn'
import { useSessions } from './sessions-context'

/*
 * Styled as Linear's window tab bar (design_system.md §11): uniform-width
 * pills, active = raised fill with no underline, ghost `+` after the last tab.
 * Tabs normally open on queue pickup; `+`/close exist for manual management.
 */
export function SessionTabStrip() {
  const { sessions, activeSessionId, openSession, activateSession, closeSession } = useSessions()

  if (sessions.length === 0) return null

  return (
    <div className="flex min-w-0 flex-1 items-center gap-1.5">
      <TagGroup
        aria-label="Active member sessions"
        selectionMode="single"
        disallowEmptySelection
        selectedKeys={activeSessionId ? [activeSessionId] : []}
        onSelectionChange={(keys) => {
          if (keys === 'all') return
          const key = [...keys][0]
          if (key != null) activateSession(String(key))
        }}
        onRemove={(keys) => {
          for (const key of keys) closeSession(String(key))
        }}
        className="min-w-0"
      >
        <TagList items={sessions} className="flex items-center gap-1.5 overflow-x-auto">
          {(session) => (
            <Tag
              id={session.id}
              textValue={session.memberLabel}
              className={cn(
                'group flex h-8 w-52 shrink-0 cursor-default items-center gap-2 whitespace-nowrap rounded-md px-2.5 text-small transition-colors',
                'text-text-tertiary data-hovered:bg-bg-primary/60',
                'data-selected:bg-bg-primary data-selected:font-medium data-selected:text-text-primary',
              )}
            >
              <span className="flex size-4 shrink-0 items-center justify-center">
                <Dot variant={session.status} />
              </span>
              <span className="min-w-0 flex-1 truncate">{session.memberLabel}</span>
              <Button
                slot="remove"
                aria-label={`Close session with ${session.memberLabel}`}
                className={cn(
                  'flex size-5 shrink-0 items-center justify-center rounded-sm text-text-tertiary opacity-0 transition-opacity',
                  'group-data-hovered:opacity-100 group-data-selected:opacity-100 data-focus-visible:opacity-100',
                  'data-hovered:bg-bg-quaternary data-hovered:text-text-primary',
                )}
              >
                <X size={14} strokeWidth={1.5} aria-hidden="true" />
              </Button>
            </Tag>
          )}
        </TagList>
      </TagGroup>
      <Button
        aria-label="New session"
        onPress={() =>
          openSession({ id: crypto.randomUUID(), memberLabel: 'New session', status: 'neutral' })
        }
        className={cn(
          'flex size-7 shrink-0 items-center justify-center rounded-md text-text-tertiary transition-colors',
          'data-hovered:bg-bg-tertiary data-hovered:text-text-primary',
        )}
      >
        <Plus size={16} strokeWidth={1.5} aria-hidden="true" />
      </Button>
    </div>
  )
}
