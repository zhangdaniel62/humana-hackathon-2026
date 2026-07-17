import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, Mic } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import {
  Badge,
  Button,
  Cell,
  Column,
  Panel,
  Row,
  Tab,
  TabList,
  TabPanel,
  Table,
  TableBody,
  TableHeader,
  Tabs,
} from '@/components/ui'
import { useSessions } from '@/app/sessions-context'
import {
  canDisclose,
  roiLabel,
  statusLabel,
  type RepresentativeInteraction,
} from '@/lib/representativeDemo'
import { claimSupportRoom, fetchSupportQueue } from '@/lib/supportApi'
import type { SupportRoom } from '@/lib/supportProtocol'

function Channel({
  interaction,
  showStatus = true,
}: {
  interaction: RepresentativeInteraction
  showStatus?: boolean
}) {
  return (
    <div className="flex items-center gap-2">
      {interaction.channel === 'voice' ? (
        <Mic size={14} strokeWidth={1.5} aria-hidden="true" className="text-text-tertiary" />
      ) : (
        <MessageSquare
          size={14}
          strokeWidth={1.5}
          aria-hidden="true"
          className="text-text-tertiary"
        />
      )}
      <span className="capitalize">{interaction.channel}</span>
      {showStatus && <Badge variant={interaction.status}>{statusLabel(interaction)}</Badge>}
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[104px_minmax(0,1fr)] gap-3 py-1.5">
      <dt className="text-small text-text-tertiary">{label}</dt>
      <dd className="text-small text-text-secondary">{value}</dd>
    </div>
  )
}

function WaitingRail({ interaction }: { interaction: RepresentativeInteraction }) {
  return (
    <Panel dense className="w-[340px] shrink-0 self-start">
      <p className="text-micro font-medium text-text-quaternary">PREVIEW ONLY</p>
      <h2 className="mt-1 text-large font-medium text-text-primary">{interaction.memberLabel}</h2>
      <div className="mt-4 flex flex-col gap-4">
        <section>
          <h3 className="text-small font-medium text-text-primary">What the member needs</h3>
          <p className="mt-1 text-small text-text-secondary">{interaction.memberNeed}</p>
        </section>
        <section>
          <h3 className="text-small font-medium text-text-primary">Why Claim Assist handed off</h3>
          <p className="mt-1 text-small text-text-secondary">{interaction.handoffReason}</p>
        </section>
        <section>
          <h3 className="text-small font-medium text-text-primary">Recommended next step</h3>
          <p className="mt-1 text-small text-text-secondary">{interaction.recommendedNextStep}</p>
        </section>
        <section>
          <h3 className="text-small font-medium text-text-primary">Relevant grounded finding</h3>
          <p className="mt-1 text-small text-text-secondary">{interaction.groundedFinding}</p>
        </section>
        <dl className="border-t border-border-tertiary pt-2">
          <DetailRow label="Channel" value={interaction.channel === 'voice' ? 'Voice' : 'Chat'} />
          <DetailRow label="Waiting" value={interaction.waitingLabel} />
          <DetailRow label="ROI" value={roiLabel(interaction.roiStatus)} />
          {canDisclose(interaction) && interaction.claim && (
            <DetailRow label="Claim" value={interaction.claim.claimId} />
          )}
        </dl>
      </div>
    </Panel>
  )
}

function CompletedRail({ interaction }: { interaction: RepresentativeInteraction }) {
  const lastMessage = interaction.transcript.at(-1)
  return (
    <Panel dense className="w-[300px] shrink-0 self-start">
      <p className="text-micro font-medium text-text-quaternary">COMPLETED INTERACTION</p>
      <h2 className="mt-1 text-large font-medium text-text-primary">{interaction.memberLabel}</h2>
      <div className="mt-4 flex flex-col gap-4">
        <section>
          <h3 className="text-small font-medium text-text-primary">Recorded disposition</h3>
          <div className="mt-1">
            <Badge variant={interaction.status}>{interaction.disposition ?? 'Completed'}</Badge>
          </div>
        </section>
        <section>
          <h3 className="text-small font-medium text-text-primary">Resolution summary</h3>
          <p className="mt-1 text-small text-text-secondary">
            {interaction.resolutionSummary ?? 'No resolution summary was recorded.'}
          </p>
        </section>
        <dl className="border-t border-border-tertiary pt-2">
          <DetailRow label="Picked up" value={interaction.pickedUpAt ?? '—'} />
          <DetailRow label="Completed" value={interaction.completedAt ?? '—'} />
          <DetailRow label="Duration" value={interaction.durationLabel ?? '—'} />
        </dl>
        {lastMessage && (
          <section>
            <h3 className="text-small font-medium text-text-primary">Final transcript excerpt</h3>
            <p className="mt-1 text-small text-text-secondary">“{lastMessage.text}”</p>
          </section>
        )}
        <p className="border-t border-border-tertiary pt-2 text-micro text-text-quaternary">
          Grounded in deterministic synthetic interaction fixtures.
        </p>
      </div>
    </Panel>
  )
}

function WaitingTable({
  rows,
  selectedId,
  onSelect,
}: {
  rows: RepresentativeInteraction[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <Table
      aria-label="Waiting interactions"
      selectionMode="single"
      selectionBehavior="replace"
      selectedKeys={selectedId ? [selectedId] : []}
      onSelectionChange={(keys) => {
        if (keys === 'all') return
        const key = [...keys][0]
        if (key != null) onSelect(String(key))
      }}
    >
      <TableHeader>
        <Column isRowHeader>Member</Column>
        <Column>Channel</Column>
        <Column>Waiting</Column>
        <Column>Topic</Column>
        <Column>Handoff reason</Column>
      </TableHeader>
      <TableBody renderEmptyState={() => <div className="py-20 text-center text-regular text-text-tertiary">No interactions are waiting.</div>}>
        {rows.map((interaction, index) => (
          <Row key={interaction.id} id={interaction.id} textValue={interaction.memberLabel}>
            <Cell>
              <span className="mr-3 text-mini tabular-nums text-text-quaternary">{index + 1}</span>
              <span className="text-text-primary">{interaction.memberLabel}</span>
            </Cell>
            <Cell>
              <Channel interaction={interaction} />
            </Cell>
            <Cell className="tabular-nums">{interaction.waitingLabel}</Cell>
            <Cell>{interaction.topic}</Cell>
            <Cell className="max-w-64 text-small">{interaction.handoffReason}</Cell>
          </Row>
        ))}
      </TableBody>
    </Table>
  )
}

function CompletedTable({
  rows,
  selectedId,
  onSelect,
}: {
  rows: RepresentativeInteraction[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <Table
      aria-label="Completed interactions"
      className="text-small"
      selectionMode="single"
      selectionBehavior="replace"
      selectedKeys={selectedId ? [selectedId] : []}
      onSelectionChange={(keys) => {
        if (keys === 'all') return
        const key = [...keys][0]
        if (key != null) onSelect(String(key))
      }}
    >
      <TableHeader>
        <Column isRowHeader className="px-2">Member</Column>
        <Column className="px-2">Channel</Column>
        <Column className="px-2">Completed</Column>
        <Column className="px-2">Topic</Column>
        <Column className="px-2">Disposition</Column>
        <Column className="px-2">Duration</Column>
      </TableHeader>
      <TableBody renderEmptyState={() => <div className="py-20 text-center text-regular text-text-tertiary">No representative interactions have been completed.</div>}>
        {rows.map((interaction) => (
          <Row key={interaction.id} id={interaction.id} textValue={interaction.memberLabel}>
            <Cell className="px-2 text-text-primary">{interaction.memberLabel}</Cell>
            <Cell className="px-2">
              <Channel interaction={interaction} showStatus={false} />
            </Cell>
            <Cell className="px-2">{interaction.completedAt ?? '—'}</Cell>
            <Cell className="px-2">{interaction.topic}</Cell>
            <Cell className="px-2">{interaction.disposition ?? 'Completed'}</Cell>
            <Cell className="px-2">{interaction.durationLabel ?? '—'}</Cell>
          </Row>
        ))}
      </TableBody>
    </Table>
  )
}

function QueueSkeleton() {
  return (
    <div aria-label="Loading interactions" className="flex flex-col gap-2 py-2">
      {Array.from({ length: 5 }, (_, index) => (
        <div key={index} className="h-10 animate-pulse rounded-sm bg-bg-tertiary" />
      ))}
    </div>
  )
}

function QueueError({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="flex min-h-56 flex-col items-center justify-center text-center">
      <h2 className="text-large font-medium text-text-primary">Interactions could not be loaded</h2>
      <p className="mt-1 text-small text-text-tertiary">The synthetic repository did not return data.</p>
      <Button className="mt-4" onPress={onRetry}>Retry</Button>
    </div>
  )
}

export function QueuePage() {
  const navigate = useNavigate()
  const { waiting, completed, pickupNext, loadStatus, retryDemo } = useSessions()
  const [tab, setTab] = useState<'waiting' | 'completed'>('waiting')
  const [waitingSelection, setWaitingSelection] = useState<string | null>(waiting[0]?.id ?? null)
  const [completedSelection, setCompletedSelection] = useState<string | null>(completed[0]?.id ?? null)
  const [liveRooms, setLiveRooms] = useState<SupportRoom[]>([])
  const [liveQueueError, setLiveQueueError] = useState<string | null>(null)
  const [claimingRoomId, setClaimingRoomId] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const refresh = () => {
      void fetchSupportQueue(controller.signal)
        .then((rooms) => {
          setLiveRooms(rooms)
          setLiveQueueError(null)
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted) {
            setLiveQueueError(error instanceof Error ? error.message : 'Live requests are unavailable.')
          }
        })
    }
    refresh()
    const interval = window.setInterval(refresh, 2_000)
    return () => {
      controller.abort()
      window.clearInterval(interval)
    }
  }, [])

  const claimLiveRoom = async (roomId: string) => {
    setClaimingRoomId(roomId)
    setLiveQueueError(null)
    try {
      await claimSupportRoom(roomId)
      navigate(`/workspace?room=${encodeURIComponent(roomId)}`)
    } catch (error) {
      setLiveQueueError(
        error instanceof Error ? error.message : 'Another representative claimed this request.',
      )
      setLiveRooms((rooms) => rooms.filter((room) => room.id !== roomId))
    } finally {
      setClaimingRoomId(null)
    }
  }

  const effectiveWaitingSelection = waiting.some((item) => item.id === waitingSelection)
    ? waitingSelection
    : waiting[0]?.id ?? null
  const effectiveCompletedSelection = completed.some((item) => item.id === completedSelection)
    ? completedSelection
    : completed[0]?.id ?? null

  const selectedWaiting = useMemo(
    () => waiting.find((item) => item.id === effectiveWaitingSelection) ?? null,
    [waiting, effectiveWaitingSelection],
  )
  const selectedCompleted = useMemo(
    () => completed.find((item) => item.id === effectiveCompletedSelection) ?? null,
    [completed, effectiveCompletedSelection],
  )
  const next = waiting[0]

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        title="Interaction Queue"
        description="AI handoffs waiting in first-in, first-out order. Selecting a row previews it; pickup always claims the oldest handoff."
        actions={<Badge variant="neutral">Synthetic demo data</Badge>}
      />
      <div className="flex flex-1 flex-col p-6">
        <Panel bordered className="mb-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-small font-medium text-text-primary">Live customer requests</h2>
                <Badge variant={liveRooms.length > 0 ? 'info' : 'neutral'}>{liveRooms.length}</Badge>
              </div>
              <p className="mt-1 text-mini text-text-tertiary">
                Real customer-to-representative text and voice rooms.
              </p>
            </div>
            {liveRooms[0] && (
              <Button
                variant="primary"
                isDisabled={claimingRoomId !== null}
                onPress={() => void claimLiveRoom(liveRooms[0].id)}
              >
                {claimingRoomId === liveRooms[0].id ? 'Claiming…' : 'Claim next live request'}
              </Button>
            )}
          </div>
          {liveQueueError && (
            <p role="alert" className="mt-3 text-mini text-danger">{liveQueueError}</p>
          )}
          {liveRooms.length > 0 ? (
            <div className="mt-4 divide-y divide-border-tertiary border-y border-border-tertiary">
              {liveRooms.map((room, index) => (
                <div key={room.id} className="flex items-center gap-4 py-3 text-small">
                  <span className="text-mini tabular-nums text-text-quaternary">{index + 1}</span>
                  <span className="font-medium text-text-primary">Customer support request</span>
                  <span className="text-text-tertiary">
                    Waiting since {new Date(room.createdAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                  </span>
                  <Button
                    className="ml-auto"
                    size="sm"
                    isDisabled={claimingRoomId !== null}
                    onPress={() => void claimLiveRoom(room.id)}
                  >
                    Claim
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-small text-text-tertiary">No live customer is waiting.</p>
          )}
        </Panel>
        <Tabs
          selectedKey={tab}
          onSelectionChange={(key) => setTab(key === 'completed' ? 'completed' : 'waiting')}
        >
          <div className="flex items-center justify-between gap-4">
            <TabList aria-label="Queue views">
              <Tab id="waiting">Waiting · {loadStatus === 'ready' ? waiting.length : '—'}</Tab>
              <Tab id="completed">Completed · {loadStatus === 'ready' ? completed.length : '—'}</Tab>
            </TabList>
            {tab === 'waiting' && (
              <Button
                variant="primary"
                isDisabled={!next || loadStatus !== 'ready'}
                onPress={() => {
                  const id = pickupNext()
                  if (id) navigate('/workspace')
                }}
              >
                {loadStatus === 'loading'
                  ? 'Loading interactions…'
                  : loadStatus === 'error'
                    ? 'Interactions unavailable'
                    : next
                      ? `Pick up next · ${next.memberLabel}`
                      : 'No interactions waiting'}
              </Button>
            )}
          </div>
          <TabPanel id="waiting" className="pt-4">
            <p className="mb-3 text-mini text-text-tertiary">
              Oldest handoff first · selecting a row previews it only
            </p>
            <div className="flex min-w-0 gap-4">
              <Panel dense className="min-w-0 flex-1 overflow-x-auto">
                {loadStatus === 'loading' ? (
                  <QueueSkeleton />
                ) : loadStatus === 'error' ? (
                  <QueueError onRetry={retryDemo} />
                ) : (
                  <WaitingTable
                    rows={waiting}
                    selectedId={effectiveWaitingSelection}
                    onSelect={setWaitingSelection}
                  />
                )}
              </Panel>
              {loadStatus === 'ready' && selectedWaiting && <WaitingRail interaction={selectedWaiting} />}
            </div>
          </TabPanel>
          <TabPanel id="completed" className="pt-4">
            <div className="flex min-w-0 gap-4">
              <Panel dense className="min-w-0 flex-1 overflow-x-auto">
                {loadStatus === 'loading' ? (
                  <QueueSkeleton />
                ) : loadStatus === 'error' ? (
                  <QueueError onRetry={retryDemo} />
                ) : (
                  <CompletedTable
                    rows={completed}
                    selectedId={effectiveCompletedSelection}
                    onSelect={setCompletedSelection}
                  />
                )}
              </Panel>
              {loadStatus === 'ready' && selectedCompleted && <CompletedRail interaction={selectedCompleted} />}
            </div>
          </TabPanel>
        </Tabs>
      </div>
    </div>
  )
}
