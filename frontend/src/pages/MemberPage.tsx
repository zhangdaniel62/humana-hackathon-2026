import { useEffect, useMemo, useState } from 'react'
import { ToggleButton, ToggleButtonGroup } from 'react-aria-components'
import { AlertCircle, LoaderCircle, MessageSquare, Mic } from 'lucide-react'
import { Composer } from '@/components/conversation/Composer'
import { ThemeMenu } from '@/components/ThemeMenu'
import { ConversationSummary } from '@/components/conversation/ConversationSummary'
import { ConversationTranscript } from '@/components/conversation/ConversationTranscript'
import { Badge, Button, InfoTooltip, Panel, type StatusVariant } from '@/components/ui'
import { cn } from '@/lib/cn'
import { useAuth } from '@/lib/auth-context'
import type { TranscriptMessage } from '@/lib/representativeDemo'
import { createSupportRoom, fetchCurrentSupportRoom } from '@/lib/supportApi'
import { useConversation } from '@/lib/useConversation'
import { useSupportRoom } from '@/lib/useSupportRoom'

const starters = ['Check a claim', 'Ask about coverage', 'Understand a denial']
type ConversationTarget = 'assistant' | 'representative'

function connectionBadge(connection: ReturnType<typeof useConversation>['connection']): {
  label: string
  tone: StatusVariant
} {
  switch (connection) {
    case 'connected':
      return { label: 'Connected', tone: 'success' }
    case 'connecting':
      return { label: 'Connecting', tone: 'neutral' }
    case 'unauthorized':
      return { label: 'Sign-in required', tone: 'warning' }
    case 'forbidden':
      return { label: 'Access denied', tone: 'danger' }
    case 'error':
      return { label: 'Connection error', tone: 'danger' }
    case 'disconnected':
      return { label: 'Disconnected', tone: 'neutral' }
  }
}

export function MemberPage() {
  const { signOut } = useAuth()
  const conversation = useConversation()
  const [target, setTarget] = useState<ConversationTarget>('assistant')
  const [supportRoomId, setSupportRoomId] = useState<string | null>(null)
  const [supportLoading, setSupportLoading] = useState(false)
  const [supportRequestError, setSupportRequestError] = useState<string | null>(null)
  const [supportMode, setSupportMode] = useState<'chat' | 'voice'>('chat')
  const support = useSupportRoom(supportRoomId)
  const [draft, setDraft] = useState('')
  const badge =
    target === 'assistant'
      ? connectionBadge(conversation.connection)
      : supportLoading
        ? { label: 'Opening request', tone: 'neutral' as const }
        : support.status === 'waiting'
          ? { label: 'Waiting for representative', tone: 'warning' as const }
          : support.status === 'active' && support.peer?.present
            ? { label: 'Representative connected', tone: 'success' as const }
            : support.status === 'active'
              ? { label: 'Representative reconnecting', tone: 'warning' as const }
              : support.connection === 'error' || supportRequestError
                ? { label: 'Connection error', tone: 'danger' as const }
                : { label: 'Live support', tone: 'neutral' as const }
  const selectedMode =
    target === 'assistant' ? conversation.pendingMode ?? conversation.mode : supportMode
  const canInteract =
    target === 'assistant'
      ? conversation.connection === 'connected' && Boolean(conversation.sessionId)
      : support.status === 'active' && Boolean(support.peer?.present)

  useEffect(() => {
    const controller = new AbortController()
    void fetchCurrentSupportRoom(controller.signal)
      .then((room) => setSupportRoomId(room?.id ?? null))
      .catch(() => undefined)
    return () => controller.abort()
  }, [])

  const transcript = useMemo<TranscriptMessage[]>(
    () =>
      target === 'assistant'
        ? conversation.messages.map((message) => ({
            id: message.id,
            speaker: message.speaker === 'user' ? 'member' : 'assistant',
            speakerLabel: message.speaker === 'user' ? 'You' : 'Claim Assist',
            text: message.text,
            timestamp: 'Now',
          }))
        : support.messages.map((message) => ({
            id: message.id,
            speaker: message.sender.role === 'customer' ? 'member' : 'representative',
            speakerLabel: message.sender.role === 'customer' ? 'You' : 'Representative',
            text: message.text,
            timestamp: new Date(message.createdAt).toLocaleTimeString([], {
              hour: 'numeric',
              minute: '2-digit',
            }),
          })),
    [conversation.messages, support.messages, target],
  )

  const submit = (text = draft) => {
    const sent = target === 'assistant' ? conversation.sendText(text) : support.sendText(text)
    if (sent) setDraft('')
  }

  const selectTarget = async (next: ConversationTarget) => {
    if (next === target) return
    if (next === 'assistant') {
      if (support.microphoneState === 'listening') await support.toggleMicrophone()
      setSupportMode('chat')
      setTarget(next)
      return
    }
    if (conversation.mode === 'voice') conversation.setMode('chat')
    setTarget(next)
    if (supportRoomId || supportLoading) return
    setSupportLoading(true)
    setSupportRequestError(null)
    try {
      const room = await createSupportRoom(conversation.sessionId)
      setSupportRoomId(room.id)
    } catch (error) {
      setSupportRequestError(
        error instanceof Error ? error.message : 'A live support room could not be opened.',
      )
    } finally {
      setSupportLoading(false)
    }
  }

  return (
    <main className="flex min-h-dvh flex-col bg-bg-primary">
      <header className="flex h-12 shrink-0 items-center border-b border-border-secondary px-6">
        <div className="flex items-center gap-1">
          <h1 className="text-small font-semibold text-text-primary">Claim Assist</h1>
          <InfoTooltip label="About Claim Assist">
            A synthetic demonstration of grounded claim, coverage, authorization, and readiness guidance. Chat and Voice share one preserved session.
          </InfoTooltip>
        </div>
        <div className="ml-auto flex items-center gap-4">
          <ThemeMenu />
          <Badge variant={badge.tone}>{badge.label}</Badge>
          <ToggleButtonGroup
            aria-label="Conversation participant"
            selectionMode="single"
            disallowEmptySelection
            selectedKeys={[target]}
            onSelectionChange={(keys) => {
              const key = [...keys][0]
              if (key === 'assistant' || key === 'representative') void selectTarget(key)
            }}
            className="flex items-center gap-0.5 rounded-md bg-bg-secondary p-0.5"
          >
            <ToggleButton
              id="assistant"
              className={cn(
                'flex h-7 cursor-default items-center rounded-md px-3 text-small font-medium transition-colors',
                'text-text-tertiary data-hovered:text-text-secondary data-selected:bg-bg-primary data-selected:text-text-primary',
              )}
            >
              AI assistant
            </ToggleButton>
            <ToggleButton
              id="representative"
              className={cn(
                'flex h-7 cursor-default items-center rounded-md px-3 text-small font-medium transition-colors',
                'text-text-tertiary data-hovered:text-text-secondary data-selected:bg-bg-primary data-selected:text-text-primary',
              )}
            >
              Live representative
            </ToggleButton>
          </ToggleButtonGroup>
          <ToggleButtonGroup
            aria-label="Conversation mode"
            selectionMode="single"
            disallowEmptySelection
            selectedKeys={[selectedMode]}
            onSelectionChange={(keys) => {
              const key = [...keys][0]
              if (key !== 'chat' && key !== 'voice') return
              if (target === 'assistant') {
                conversation.setMode(key)
                return
              }
              if (key === 'voice') {
                void support.toggleMicrophone().then((enabled) => {
                  if (enabled) setSupportMode('voice')
                })
              } else {
                if (support.microphoneState === 'listening') void support.toggleMicrophone()
                setSupportMode('chat')
              }
            }}
            className="flex items-center gap-0.5 rounded-md bg-bg-secondary p-0.5"
          >
            <ToggleButton
              id="chat"
              isDisabled={!canInteract || (target === 'assistant' && conversation.pendingMode !== null)}
              className={cn(
                'flex h-7 cursor-default items-center gap-1.5 rounded-md px-3 text-small font-medium transition-colors',
                'text-text-tertiary data-hovered:text-text-secondary data-selected:bg-bg-primary data-selected:text-text-primary',
              )}
            >
              <MessageSquare size={14} strokeWidth={1.5} aria-hidden="true" />
              Chat
            </ToggleButton>
            <ToggleButton
              id="voice"
              isDisabled={!canInteract || (target === 'assistant' && conversation.pendingMode !== null)}
              className={cn(
                'flex h-7 cursor-default items-center gap-1.5 rounded-md px-3 text-small font-medium transition-colors',
                'text-text-tertiary data-hovered:text-text-secondary data-selected:bg-bg-primary data-selected:text-text-primary',
              )}
            >
              <Mic size={14} strokeWidth={1.5} aria-hidden="true" />
              Voice
            </ToggleButton>
          </ToggleButtonGroup>
          <Button variant="ghost" size="sm" onPress={() => void signOut()}>
            Sign out
          </Button>
        </div>
      </header>

      <div className="mx-auto flex min-h-0 w-full max-w-[880px] flex-1 flex-col overflow-y-auto px-6">
        <section aria-label="Claim Assist conversation" className="flex-1 py-8">
          {transcript.length > 0 ? (
            <ConversationTranscript messages={transcript} />
          ) : (
            <div className="flex min-h-48 items-center justify-center text-center">
              <div>
                {(target === 'assistant' ? conversation.connection === 'connecting' : supportLoading) && (
                  <LoaderCircle className="mx-auto mb-3 animate-spin text-text-quaternary" size={18} aria-hidden="true" />
                )}
                <p className="text-regular text-text-secondary">
                  {target === 'assistant'
                    ? conversation.connection === 'connecting'
                      ? 'Starting a secure conversation…'
                      : 'Ask about a claim, coverage, authorization, or denial.'
                    : support.status === 'waiting'
                      ? 'Your request is waiting in the representative queue.'
                      : supportLoading
                        ? 'Opening a secure support room…'
                        : support.status === 'active' && support.peer?.present
                          ? 'Your representative is connected. Send a message or choose Voice.'
                          : 'Choose Live representative to request a person.'}
                </p>
              </div>
            </div>
          )}

          {(target === 'assistant' ? conversation.error : support.error ?? supportRequestError) && (
            <Panel bordered className="mt-4 flex items-start gap-3" role="alert">
              <AlertCircle className="mt-0.5 shrink-0 text-danger" size={16} aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-small font-medium text-text-primary">Conversation notice</p>
                <p className="mt-1 text-small text-text-secondary">
                  {target === 'assistant' ? conversation.error : support.error ?? supportRequestError}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onPress={
                  target === 'assistant'
                    ? conversation.clearError
                    : () => {
                        support.clearError()
                        setSupportRequestError(null)
                      }
                }
              >
                Dismiss
              </Button>
            </Panel>
          )}

          {target === 'assistant' && conversation.summaryLoading && (
            <p className="mt-6 text-mini text-text-tertiary">Updating structured session findings…</p>
          )}
          {target === 'assistant' && conversation.summary && (
            <ConversationSummary summary={conversation.summary} />
          )}
        </section>

        <div className="sticky bottom-0 bg-bg-primary pb-6 pt-3">
          {target === 'assistant' && conversation.messages.length === 0 && conversation.mode === 'chat' && canInteract && (
            <div className="mb-3 flex flex-wrap gap-2">
              {starters.map((starter) => (
                <Button key={starter} size="sm" onPress={() => setDraft(starter)}>
                  {starter}
                </Button>
              ))}
            </div>
          )}
          {selectedMode === 'chat' ? (
            <Composer
              value={draft}
              onChange={setDraft}
              onSend={() => submit()}
              placeholder={
                canInteract
                  ? target === 'assistant'
                    ? 'Ask about a claim, coverage, or denial…'
                    : 'Message your representative…'
                  : target === 'representative' && support.status === 'waiting'
                    ? 'Waiting for a representative…'
                    : 'Connecting…'
              }
              ariaLabel={target === 'assistant' ? 'Message Claim Assist' : 'Message representative'}
              isDisabled={
                !canInteract || (target === 'assistant' && conversation.pendingMode !== null)
              }
            />
          ) : (
            <Panel className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="flex size-8 items-center justify-center rounded-md bg-bg-tertiary text-text-tertiary">
                  <Mic size={16} strokeWidth={1.5} aria-hidden="true" />
                </span>
                <div>
                  <p className="text-small font-medium text-text-primary">
                    {target === 'representative'
                      ? support.microphoneState === 'listening'
                        ? 'Your representative can hear you'
                        : support.microphoneState === 'starting'
                          ? 'Starting microphone…'
                          : 'Microphone inactive'
                      : conversation.pendingMode === 'voice'
                      ? 'Switching to Voice…'
                      : conversation.microphoneState === 'listening'
                        ? 'Voice is listening'
                        : conversation.microphoneState === 'starting'
                          ? 'Starting microphone…'
                          : 'Microphone inactive'}
                  </p>
                  <p className="text-mini text-text-tertiary">
                    {target === 'representative'
                      ? support.peer?.voiceEnabled
                        ? 'The representative microphone is live.'
                        : 'Live PCM audio is shared only with this assigned representative.'
                      : conversation.agentAudioEnabled
                        ? 'Chat history and session findings stay in this same conversation.'
                        : 'Spoken responses are unavailable for this account; transcripts remain visible.'}
                  </p>
                </div>
              </div>
              {(target === 'assistant'
                ? conversation.microphoneState === 'error'
                : support.microphoneState === 'error') && (
                <Button
                  variant="primary"
                  onPress={
                    target === 'assistant' ? conversation.retryMicrophone : support.retryMicrophone
                  }
                >
                  Retry microphone
                </Button>
              )}
            </Panel>
          )}
        </div>
      </div>
    </main>
  )
}
