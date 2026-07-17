import { createContext, useContext } from 'react'
import type { StatusVariant } from '@/components/ui'

export interface InteractionSession {
  id: string
  memberLabel: string
  status: StatusVariant
}

export interface SessionsContextValue {
  sessions: InteractionSession[]
  activeSessionId: string | null
  /** Called on queue pickup — adds the session (if new) and makes it active. */
  openSession: (session: InteractionSession) => void
  activateSession: (id: string) => void
  /** Called when the member leaves, or manually via a tab's close button. */
  closeSession: (id: string) => void
}

export const SessionsContext = createContext<SessionsContextValue | null>(null)

export function useSessions(): SessionsContextValue {
  const context = useContext(SessionsContext)
  if (!context) throw new Error('useSessions must be used within SessionsProvider')
  return context
}
