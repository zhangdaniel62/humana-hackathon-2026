import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ToggleButton, ToggleButtonGroup } from 'react-aria-components'
import { MessageSquare, Mic } from 'lucide-react'
import { Composer } from '@/components/conversation/Composer'
import { ConversationTranscript } from '@/components/conversation/ConversationTranscript'
import { ResultPanel } from '@/components/conversation/ResultPanel'
import { Badge, Button, InfoTooltip, Panel } from '@/components/ui'
import { cn } from '@/lib/cn'
import {
  createMemberConversationState,
  scriptedMemberTurn,
  switchMemberMode,
  type MemberMode,
  type MemberVisibleSummary,
} from '@/lib/memberDemo'

const starters = ['Check a claim', 'Ask about coverage', 'Understand a denial']

function MemberResult({ result, onChoice }: { result: MemberVisibleSummary; onChoice: (choice: string) => void }) {
  return (
    <div className="py-3">
      <ResultPanel
        title={result.title}
        summary={result.summary}
        tone={result.tone}
        badge={result.badge}
        source={result.source}
      >
        {result.details.length > 0 && (
          <dl className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {result.details.map((detail) => (
              <div key={detail.label}>
                <dt className="text-mini text-text-tertiary">{detail.label}</dt>
                <dd className="mt-0.5 text-small text-text-secondary">{detail.value}</dd>
              </div>
            ))}
          </dl>
        )}
        {result.choices && (
          <div className="flex flex-wrap gap-2">
            {result.choices.map((choice) => (
              <Button key={choice} size="sm" onPress={() => onChoice(choice)}>
                {choice}
              </Button>
            ))}
          </div>
        )}
      </ResultPanel>
    </div>
  )
}

export function MemberPage() {
  const [state, setState] = useState(createMemberConversationState)

  const setMode = (mode: MemberMode) => {
    setState((current) => switchMemberMode(current, mode))
  }

  const submit = (text = state.draft) => {
    const normalized = text.trim()
    if (!normalized) return
    setState((current) => ({
      ...current,
      draft: '',
      events: [...current.events, ...scriptedMemberTurn(normalized, current.events.length)],
    }))
  }

  const simulateVoiceTurn = () => {
    setState((current) => ({
      ...current,
      voiceState: 'speaking',
      events: [
        ...current.events,
        ...scriptedMemberTurn('Check whether my claim is ready for review', current.events.length),
      ],
    }))
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
          <Badge variant="neutral">Synthetic demo data</Badge>
          <ToggleButtonGroup
            aria-label="Conversation mode"
            selectionMode="single"
            disallowEmptySelection
            selectedKeys={[state.mode]}
            onSelectionChange={(keys) => {
              const key = [...keys][0]
              if (key === 'chat' || key === 'voice') setMode(key)
            }}
            className="flex items-center gap-0.5 rounded-md bg-bg-secondary p-0.5"
          >
            <ToggleButton
              id="chat"
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
              className={cn(
                'flex h-7 cursor-default items-center gap-1.5 rounded-md px-3 text-small font-medium transition-colors',
                'text-text-tertiary data-hovered:text-text-secondary data-selected:bg-bg-primary data-selected:text-text-primary',
              )}
            >
              <Mic size={14} strokeWidth={1.5} aria-hidden="true" />
              Voice
            </ToggleButton>
          </ToggleButtonGroup>
          <Link
            to="/signin"
            className="text-small text-text-tertiary transition-colors hover:text-text-primary"
          >
            Staff sign in
          </Link>
        </div>
      </header>

      <div className="mx-auto flex min-h-0 w-full max-w-[880px] flex-1 flex-col px-6">
        <section aria-label="Claim Assist conversation" className="flex-1 py-8">
          {state.events.map((event) =>
            event.type === 'message' ? (
              <ConversationTranscript key={event.id} messages={[event.message]} />
            ) : (
              <MemberResult key={event.id} result={event.result} onChoice={(choice) => submit(choice)} />
            ),
          )}
        </section>

        <div className="sticky bottom-0 bg-bg-primary pb-6 pt-3">
          {state.events.length === 1 && state.mode === 'chat' && (
            <div className="mb-3 flex flex-wrap gap-2">
              {starters.map((starter) => (
                <Button key={starter} size="sm" onPress={() => setState((current) => ({ ...current, draft: starter }))}>
                  {starter}
                </Button>
              ))}
            </div>
          )}
          {state.mode === 'chat' ? (
            <Composer
              value={state.draft}
              onChange={(draft) => setState((current) => ({ ...current, draft }))}
              onSend={() => submit()}
              placeholder="Ask about a claim, coverage, or denial…"
              ariaLabel="Message Claim Assist"
            />
          ) : (
            <Panel className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="flex size-8 items-center justify-center rounded-md bg-bg-tertiary text-text-tertiary">
                  <Mic size={16} strokeWidth={1.5} aria-hidden="true" />
                </span>
                <div>
                  <p className="text-small font-medium text-text-primary">
                    Voice interface preview · microphone inactive
                  </p>
                  <p className="text-mini text-text-tertiary">
                    {state.voiceState === 'speaking'
                      ? 'Simulated response added to this same session.'
                      : 'No permission, audio capture, playback, or network connection is used.'}
                  </p>
                </div>
              </div>
              <Button variant="primary" onPress={simulateVoiceTurn}>
                Simulate voice turn
              </Button>
            </Panel>
          )}
        </div>
      </div>
    </main>
  )
}
