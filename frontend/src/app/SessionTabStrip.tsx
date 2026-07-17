import {
  Button,
  Menu,
  MenuItem,
  MenuTrigger,
  Popover,
  Tag,
  TagGroup,
  TagList,
} from 'react-aria-components'
import { useEffect, useRef } from 'react'
import { MessageSquare, Mic, Plus, X } from 'lucide-react'
import { Badge, Dot } from '@/components/ui'
import { cn } from '@/lib/cn'
import { statusLabel } from '@/lib/representativeDemo'
import { useSessions } from './sessions-context'

export function SessionTabStrip() {
  const tabListRef = useRef<HTMLDivElement>(null)
  const {
    openTabs,
    selectedInteractionId,
    hiddenActiveInteractions,
    selectInteraction,
    hideTab,
    reopenTab,
  } = useSessions()

  useEffect(() => {
    const list = tabListRef.current
    if (!selectedInteractionId || !list) return
    const selected = Array.from(
      list.querySelectorAll<HTMLElement>('[data-interaction-id]'),
    ).find((element) => element.dataset.interactionId === selectedInteractionId)
    if (!selected) return

    const selectedStart = selected.offsetLeft
    const selectedEnd = selectedStart + selected.offsetWidth
    if (selectedStart < list.scrollLeft) list.scrollLeft = selectedStart
    if (selectedEnd > list.scrollLeft + list.clientWidth) {
      list.scrollLeft = selectedEnd - list.clientWidth
    }
  }, [selectedInteractionId, openTabs])

  if (openTabs.length === 0 && hiddenActiveInteractions.length === 0) return null

  return (
    <div className="flex min-w-0 flex-1 items-center gap-1.5">
      {openTabs.length > 0 && (
        <TagGroup
          aria-label="Active member interactions"
          selectionMode="single"
          disallowEmptySelection
          selectedKeys={selectedInteractionId ? [selectedInteractionId] : []}
          onSelectionChange={(keys) => {
            if (keys === 'all') return
            const key = [...keys][0]
            if (key != null) selectInteraction(String(key))
          }}
          onRemove={(keys) => {
            for (const key of keys) hideTab(String(key))
          }}
          className="min-w-0"
        >
          <TagList
            ref={tabListRef}
            items={openTabs}
            className="flex items-center gap-1.5 overflow-x-auto"
          >
            {(interaction) => {
              const state = statusLabel(interaction)
              const label = `${interaction.memberLabel}, ${interaction.channel}, ${state}${interaction.unreadCount ? `, ${interaction.unreadCount} unread` : ''}`
              return (
                <Tag
                  id={interaction.id}
                  data-interaction-id={interaction.id}
                  textValue={label}
                  aria-label={label}
                  className={cn(
                    'group flex h-8 w-52 shrink-0 cursor-default items-center gap-2 whitespace-nowrap rounded-md px-2.5 text-small transition-colors',
                    'text-text-tertiary data-hovered:bg-bg-primary/60',
                    'data-selected:bg-bg-primary data-selected:font-medium data-selected:text-text-primary',
                  )}
                >
                  <span className="flex size-4 shrink-0 items-center justify-center">
                    {interaction.channel === 'voice' ? (
                      <Mic size={14} strokeWidth={1.5} aria-hidden="true" />
                    ) : (
                      <MessageSquare size={14} strokeWidth={1.5} aria-hidden="true" />
                    )}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{interaction.memberLabel}</span>
                  {interaction.unreadCount > 0 ? (
                    <Badge variant="info" className="h-4 px-1">
                      {interaction.unreadCount}
                    </Badge>
                  ) : (
                    <Dot variant={interaction.status} label={state} />
                  )}
                  <Button
                    slot="remove"
                    aria-label={`Hide tab for ${interaction.memberLabel}`}
                    className={cn(
                      'flex size-5 shrink-0 items-center justify-center rounded-sm text-text-tertiary opacity-0 transition-opacity',
                      'group-data-hovered:opacity-100 group-data-selected:opacity-100 data-focus-visible:opacity-100',
                      'data-hovered:bg-bg-quaternary data-hovered:text-text-primary',
                    )}
                  >
                    <X size={14} strokeWidth={1.5} aria-hidden="true" />
                  </Button>
                </Tag>
              )
            }}
          </TagList>
        </TagGroup>
      )}
      <MenuTrigger>
        <Button
          aria-label="Open hidden interaction"
          isDisabled={hiddenActiveInteractions.length === 0}
          className={cn(
            'flex size-7 shrink-0 items-center justify-center rounded-md text-text-tertiary transition-colors',
            'data-hovered:bg-bg-tertiary data-hovered:text-text-primary data-disabled:text-text-quaternary',
          )}
        >
          <Plus size={16} strokeWidth={1.5} aria-hidden="true" />
        </Button>
        <Popover
          placement="bottom start"
          offset={6}
          className="min-w-56 rounded-md border border-border-primary bg-bg-primary p-1 shadow-float data-entering:animate-pop-in data-exiting:animate-pop-out"
        >
          <Menu
            aria-label="Hidden active interactions"
            items={hiddenActiveInteractions}
            onAction={(key) => reopenTab(String(key))}
            className="outline-none"
          >
            {(interaction) => (
              <MenuItem
                id={interaction.id}
                textValue={interaction.memberLabel}
                className="flex h-8 cursor-default items-center gap-2 rounded-sm px-2 text-small text-text-secondary data-focused:bg-bg-tertiary data-focused:text-text-primary"
              >
                {interaction.channel === 'voice' ? (
                  <Mic size={14} strokeWidth={1.5} aria-hidden="true" />
                ) : (
                  <MessageSquare size={14} strokeWidth={1.5} aria-hidden="true" />
                )}
                {interaction.memberLabel}
              </MenuItem>
            )}
          </Menu>
        </Popover>
      </MenuTrigger>
    </div>
  )
}
