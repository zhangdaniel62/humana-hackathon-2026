import { useState } from 'react'
import { NavLink, Outlet, useHref, useLocation, useNavigate } from 'react-router-dom'
import { Button, RouterProvider as AriaRouterProvider } from 'react-aria-components'
import {
  ChevronDown,
  ChevronRight,
  Inbox,
  LayoutDashboard,
  MessagesSquare,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { hasCapability, useAuth } from '@/lib/auth-context'
import { dashboardMetrics } from './metrics'
import { TopBar } from './TopBar'
import { UserMenu } from './UserMenu'

function navLinkClass(isActive: boolean, extra?: string): string {
  return cn(
    'flex h-8 items-center gap-2 rounded-md px-2 text-regular transition-colors',
    isActive
      ? 'bg-bg-quaternary text-text-primary'
      : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary',
    extra,
  )
}

function subLinkClass(isActive: boolean): string {
  return cn(
    // Sub-items step in by Linear's ~19px row-indent unit beyond the parent's 8px.
    'flex h-7 items-center rounded-md pr-2 pl-[27px] text-small font-medium transition-colors',
    isActive
      ? 'bg-bg-quaternary text-text-primary'
      : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary',
  )
}

function NavIcon({ icon: Icon, isActive }: { icon: LucideIcon; isActive: boolean }) {
  return (
    <Icon
      size={16}
      strokeWidth={1.5}
      aria-hidden="true"
      className={cn('shrink-0', isActive ? 'text-accent' : 'text-text-tertiary')}
    />
  )
}

export function AppShell() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [metricsExpanded, setMetricsExpanded] = useState(() =>
    location.pathname.startsWith('/metrics'),
  )
  const showDashboard = user?.role === 'manager' && hasCapability(user, 'manager_dashboard')
  const showRepresentativeTools = user?.role === 'rep' && hasCapability(user, 'rep_queue')

  return (
    <AriaRouterProvider navigate={(path) => void navigate(path)} useHref={useHref}>
      {/* Chrome (sidebar + top bar) shares one surface; the page content sits
          on a raised, rounded card one elevation step above it. */}
      <div className="flex h-dvh bg-bg-secondary">
        <aside className="flex w-[244px] shrink-0 flex-col px-3 py-4">
          <div className="mb-6 px-2 text-small font-semibold text-text-primary">Claim Assist</div>
          <nav aria-label="Primary">
            <ul className="flex flex-col gap-0.5">
              {showDashboard && (
                <li>
                  <div className="relative">
                    <NavLink
                      to="/"
                      end
                      className={({ isActive }) => navLinkClass(isActive, 'pr-8')}
                    >
                      {({ isActive }) => (
                        <>
                          <NavIcon icon={LayoutDashboard} isActive={isActive} />
                          Dashboard
                        </>
                      )}
                    </NavLink>
                    <Button
                      aria-expanded={metricsExpanded}
                      aria-controls="dashboard-metrics"
                      aria-label={
                        metricsExpanded
                          ? 'Collapse Dashboard metrics'
                          : 'Expand Dashboard metrics'
                      }
                      onPress={() => setMetricsExpanded((expanded) => !expanded)}
                      className={cn(
                        'absolute top-1/2 right-1 flex size-6 -translate-y-1/2 items-center justify-center rounded-sm text-text-tertiary transition-colors',
                        'data-hovered:bg-bg-quaternary data-hovered:text-text-primary',
                      )}
                    >
                      {metricsExpanded ? (
                        <ChevronDown size={14} strokeWidth={1.5} aria-hidden="true" />
                      ) : (
                        <ChevronRight size={14} strokeWidth={1.5} aria-hidden="true" />
                      )}
                    </Button>
                  </div>
                  {/* Collapse animates height (the rows below slide up) with a fade. */}
                  <div
                    id="dashboard-metrics"
                    inert={!metricsExpanded}
                    className={cn(
                      'grid transition-[grid-template-rows,opacity] duration-[250ms] ease-out',
                      metricsExpanded
                        ? 'grid-rows-[1fr] opacity-100'
                        : 'grid-rows-[0fr] opacity-0',
                    )}
                  >
                    <div className="min-h-0 overflow-hidden">
                      <ul className="flex flex-col gap-0.5 pt-0.5">
                        {dashboardMetrics.map((metric) => (
                          <li key={metric.slug}>
                            <NavLink
                              to={`/metrics/${metric.slug}`}
                              className={({ isActive }) => subLinkClass(isActive)}
                            >
                              {metric.label}
                            </NavLink>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </li>
              )}
              {showRepresentativeTools && (
                <li>
                  <NavLink to="/queue" className={({ isActive }) => navLinkClass(isActive)}>
                    {({ isActive }) => (
                      <>
                        <NavIcon icon={Inbox} isActive={isActive} />
                        Interaction Queue
                      </>
                    )}
                  </NavLink>
                </li>
              )}
              {showRepresentativeTools && user && hasCapability(user, 'chat') && (
                <li>
                  <NavLink to="/workspace" className={({ isActive }) => navLinkClass(isActive)}>
                    {({ isActive }) => (
                      <>
                        <NavIcon icon={MessagesSquare} isActive={isActive} />
                        Active Interactions
                      </>
                    )}
                  </NavLink>
                </li>
              )}
            </ul>
          </nav>
          <div className="mt-auto">
            <div aria-hidden="true" className="mx-2 mb-2 h-[0.5px] bg-border-primary" />
            <UserMenu />
          </div>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="mt-2 mr-2 mb-2 min-w-0 flex-1 overflow-y-auto rounded-md border border-border-secondary bg-bg-primary">
            <Outlet />
          </main>
        </div>
      </div>
    </AriaRouterProvider>
  )
}
