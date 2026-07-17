import { useEffect, useMemo, useReducer, useState, type ReactNode } from 'react'
import {
  createRepresentativeDemoState,
  type RepresentativeDemoState,
  type RepresentativeInteraction,
} from '@/lib/representativeDemo'
import { representativeReducer } from './representative-reducer'
import { SessionsContext, type SessionsContextValue } from './sessions-context'
import {
  createEmptyRepresentativeDemoState,
  loadRepresentativeDemoScenario,
  type RepresentativeDemoScenario,
} from '@/lib/representativeDemoRepository'

function recordsFor(state: RepresentativeDemoState, ids: string[]): RepresentativeInteraction[] {
  return ids.map((id) => state.records[id]).filter(Boolean)
}

export function SessionsProvider({
  children,
  scenario = 'default',
}: {
  children: ReactNode
  scenario?: RepresentativeDemoScenario
}) {
  const [state, dispatch] = useReducer(
    representativeReducer,
    undefined,
    scenario === 'default' ? createRepresentativeDemoState : createEmptyRepresentativeDemoState,
  )
  const [loadStatus, setLoadStatus] = useState<'loading' | 'ready' | 'error'>(
    scenario === 'default' ? 'ready' : 'loading',
  )
  const [retryToken, setRetryToken] = useState(0)

  useEffect(() => {
    if (scenario === 'default') return
    let current = true
    loadRepresentativeDemoScenario(scenario)
      .then((loadedState) => {
        if (!current) return
        dispatch({ type: 'hydrate', state: loadedState })
        setLoadStatus('ready')
      })
      .catch(() => {
        if (current) setLoadStatus('error')
      })
    return () => {
      current = false
    }
  }, [retryToken, scenario])

  const value = useMemo<SessionsContextValue>(() => {
    const waiting = recordsFor(state, state.waitingIds)
    const activeInteractions = recordsFor(state, state.activeIds)
    const completed = recordsFor(state, state.completedIds)
    const openTabs = recordsFor(state, state.openTabIds)
    const selectedInteraction = state.selectedInteractionId
      ? state.records[state.selectedInteractionId] ?? null
      : null
    const hiddenActiveInteractions = activeInteractions.filter((interaction) => !interaction.tabOpen)

    return {
      ...state,
      loadStatus,
      waiting,
      activeInteractions,
      completed,
      openTabs,
      selectedInteraction,
      hiddenActiveInteractions,
      pickupNext: () => {
        const id = state.waitingIds[0] ?? null
        dispatch({ type: 'pickup_next' })
        return id
      },
      selectInteraction: (id) => dispatch({ type: 'select', id }),
      hideTab: (id) => dispatch({ type: 'hide_tab', id }),
      reopenTab: (id) => dispatch({ type: 'reopen_tab', id }),
      resumeVoice: (id) => dispatch({ type: 'resume_voice', id }),
      toggleMute: (id) => dispatch({ type: 'toggle_mute', id }),
      setSection: (id, section) => dispatch({ type: 'set_section', id, section }),
      setDraft: (id, draft) => dispatch({ type: 'set_draft', id, draft }),
      sendRepresentativeMessage: (id) => dispatch({ type: 'send_message', id }),
      completeInteraction: (id, disposition) => dispatch({ type: 'complete', id, disposition }),
      simulateIncomingMessage: (id) => dispatch({ type: 'incoming_message', id }),
      resetDemo: () => dispatch({ type: 'reset' }),
      retryDemo: () => {
        setLoadStatus('loading')
        dispatch({ type: 'hydrate', state: createEmptyRepresentativeDemoState() })
        setRetryToken((token) => token + 1)
      },
    }
  }, [loadStatus, state])

  return <SessionsContext.Provider value={value}>{children}</SessionsContext.Provider>
}
