import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { SessionsContext, type InteractionSession } from './sessions-context'

export function SessionsProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<InteractionSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)

  const openSession = useCallback((session: InteractionSession) => {
    setSessions((current) =>
      current.some((s) => s.id === session.id) ? current : [...current, session],
    )
    setActiveSessionId(session.id)
  }, [])

  const activateSession = useCallback((id: string) => {
    setActiveSessionId(id)
  }, [])

  const closeSession = useCallback((id: string) => {
    setSessions((current) => {
      const remaining = current.filter((s) => s.id !== id)
      setActiveSessionId((active) => {
        if (active !== id) return active
        const closedIndex = current.findIndex((s) => s.id === id)
        const neighbor = remaining[closedIndex] ?? remaining[closedIndex - 1]
        return neighbor?.id ?? null
      })
      return remaining
    })
  }, [])

  const value = useMemo(
    () => ({ sessions, activeSessionId, openSession, activateSession, closeSession }),
    [sessions, activeSessionId, openSession, activateSession, closeSession],
  )

  return <SessionsContext.Provider value={value}>{children}</SessionsContext.Provider>
}
