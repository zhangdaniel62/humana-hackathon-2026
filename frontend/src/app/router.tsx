import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from './AppShell'
import { DashboardFiltersProvider } from './dashboard-filters'
import { RequireAuth } from './RequireAuth'
import { SessionsProvider } from './sessions'
import { DashboardPage } from '@/pages/DashboardPage'
import { MemberPage } from '@/pages/MemberPage'
import { MetricPage } from '@/pages/MetricPage'
import { QueuePage } from '@/pages/QueuePage'
import { SignInPage } from '@/pages/SignInPage'
import { WorkspacePage } from '@/pages/WorkspacePage'

export const router = createBrowserRouter([
  { path: '/signin', element: <SignInPage /> },
  { path: '/member', element: <MemberPage /> },
  {
    path: '/',
    element: (
      <RequireAuth>
        <SessionsProvider>
          <DashboardFiltersProvider>
            <AppShell />
          </DashboardFiltersProvider>
        </SessionsProvider>
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'metrics/:metricSlug', element: <MetricPage /> },
      { path: 'queue', element: <QueuePage /> },
      { path: 'workspace', element: <WorkspacePage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
