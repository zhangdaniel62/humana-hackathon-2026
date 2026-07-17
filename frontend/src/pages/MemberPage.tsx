import { useMemo, useState } from 'react'
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
import { useConversation } from '@/lib/useConversation'

const starters = ['Check a claim', 'Ask about coverage', 'Understand a denial']

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
  const [draft, setDraft] = useState('')
  const badge = connectionBadge(conversation.connection)
  const selectedMode = conversation.pendingMode ?? conversation.mode
  const canInteract = conversation.connection === 'connected' && Boolean(conversation.sessionId)
  const transcript = useMemo<TranscriptMessage[]>(
    () =>
      conversation.messages.map((message) => ({
        id: message.id,
        speaker: message.speaker === 'user' ? 'member' : 'assistant',
        speakerLabel: message.speaker === 'user' ? 'You' : 'Claim Assist',
        text: message.text,
        timestamp: 'Now',
      })),
    [conversation.messages],
  )

  const submit = (text = draft) => {
    if (conversation.sendText(text)) setDraft('')
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
            aria-label="Conversation mode"
            selectionMode="single"
            disallowEmptySelection
            selectedKeys={[selectedMode]}
            onSelectionChange={(keys) => {
              const key = [...keys][0]
              if (key === 'chat' || key === 'voice') conversation.setMode(key)
            }}
            className="flex items-center gap-0.5 rounded-md bg-bg-secondary p-0.5"
          >
            <ToggleButton
              id="chat"
              isDisabled={!canInteract || conversation.pendingMode !== null}
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
              isDisabled={!canInteract || conversation.pendingMode !== null}
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
                {conversation.connection === 'connecting' && (
                  <LoaderCircle className="mx-auto mb-3 animate-spin text-text-quaternary" size={18} aria-hidden="true" />
                )}
                <p className="text-regular text-text-secondary">
                  {conversation.connection === 'connecting'
                    ? 'Starting a secure conversation…'
                    : 'Ask about a claim, coverage, authorization, or denial.'}
                </p>
              </div>
            </div>
          )}

          {conversation.error && (
            <Panel bordered className="mt-4 flex items-start gap-3" role="alert">
              <AlertCircle className="mt-0.5 shrink-0 text-danger" size={16} aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-small font-medium text-text-primary">Conversation notice</p>
                <p className="mt-1 text-small text-text-secondary">{conversation.error}</p>
              </div>
              <Button variant="ghost" size="sm" onPress={conversation.clearError}>Dismiss</Button>
            </Panel>
          )}

          {conversation.summaryLoading && (
            <p className="mt-6 text-mini text-text-tertiary">Updating structured session findings…</p>
          )}
          {conversation.summary && <ConversationSummary summary={conversation.summary} />}
        </section>

        <div className="sticky bottom-0 bg-bg-primary pb-6 pt-3">
          {conversation.messages.length === 0 && conversation.mode === 'chat' && canInteract && (
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
              placeholder={canInteract ? 'Ask about a claim, coverage, or denial…' : 'Connecting…'}
              ariaLabel="Message Claim Assist"
              isDisabled={!canInteract || conversation.pendingMode !== null}
            />
          ) : (
            <Panel className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="flex size-8 items-center justify-center rounded-md bg-bg-tertiary text-text-tertiary">
                  <Mic size={16} strokeWidth={1.5} aria-hidden="true" />
                </span>
                <div>
                  <p className="text-small font-medium text-text-primary">
                    {conversation.pendingMode === 'voice'
                      ? 'Switching to Voice…'
                      : conversation.microphoneState === 'listening'
                        ? 'Voice is listening'
                        : conversation.microphoneState === 'starting'
                          ? 'Starting microphone…'
                          : 'Microphone inactive'}
                  </p>
                  <p className="text-mini text-text-tertiary">
                    {conversation.agentAudioEnabled
                      ? 'Chat history and session findings stay in this same conversation.'
                      : 'Spoken responses are unavailable for this account; transcripts remain visible.'}
                  </p>
                </div>
              </div>
              {conversation.microphoneState === 'error' && (
                <Button variant="primary" onPress={conversation.retryMicrophone}>Retry microphone</Button>
              )}
            </Panel>
          )}
        </div>
      </div>
    </main>
  )
}
