import { createContext, useContext } from 'react'
import type {
  InteractionDisposition,
  InteractionSection,
  RepresentativeDemoState,
  RepresentativeInteraction,
} from '@/lib/representativeDemo'

export interface SessionsContextValue extends RepresentativeDemoState {
  loadStatus: 'loading' | 'ready' | 'error'
  waiting: RepresentativeInteraction[]
  activeInteractions: RepresentativeInteraction[]
  completed: RepresentativeInteraction[]
  openTabs: RepresentativeInteraction[]
  selectedInteraction: RepresentativeInteraction | null
  hiddenActiveInteractions: RepresentativeInteraction[]
  pickupNext: () => string | null
  selectInteraction: (id: string) => void
  hideTab: (id: string) => void
  reopenTab: (id: string) => void
  resumeVoice: (id: string) => void
  toggleMute: (id: string) => void
  setSection: (id: string, section: InteractionSection) => void
  setDraft: (id: string, draft: string) => void
  sendRepresentativeMessage: (id: string) => void
  completeInteraction: (id: string, disposition: InteractionDisposition) => void
  simulateIncomingMessage: (id: string) => void
  resetDemo: () => void
  retryDemo: () => void
}

export const SessionsContext = createContext<SessionsContextValue | null>(null)

export function useSessions(): SessionsContextValue {
  const context = useContext(SessionsContext)
  if (!context) throw new Error('useSessions must be used within SessionsProvider')
  return context
}
