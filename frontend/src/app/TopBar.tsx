import { useLocation } from 'react-router-dom'
import { SessionTabStrip } from './SessionTabStrip'
import { useSessions } from './sessions-context'

/*
 * Window-tab-bar chrome (design_system.md §11): holds only the session tab
 * strip, so it exists solely in the Interaction Workspace while sessions are
 * open. Page titles live in each page's in-card header, not up here.
 */
export function TopBar() {
  const { pathname } = useLocation()
  const { openTabs, hiddenActiveInteractions } = useSessions()

  if (pathname !== '/workspace' || (openTabs.length === 0 && hiddenActiveInteractions.length === 0)) {
    return null
  }

  return (
    <header className="flex h-11 shrink-0 items-center px-4">
      <SessionTabStrip />
    </header>
  )
}
