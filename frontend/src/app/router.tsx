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
  {
    path: '/member',
    element: (
      <RequireAuth roles={['customer']} capability="chat">
        <MemberPage />
      </RequireAuth>
    ),
  },
  {
    path: '/',
    element: (
      <RequireAuth roles={['manager', 'rep']}>
        <SessionsProvider>
          <DashboardFiltersProvider>
            <AppShell />
          </DashboardFiltersProvider>
        </SessionsProvider>
      </RequireAuth>
    ),
    children: [
      {
        index: true,
        element: (
          <RequireAuth roles={['manager']} capability="manager_dashboard">
            <DashboardPage />
          </RequireAuth>
        ),
      },
      {
        path: 'metrics/:metricSlug',
        element: (
          <RequireAuth roles={['manager']} capability="manager_dashboard">
            <MetricPage />
          </RequireAuth>
        ),
      },
      {
        path: 'queue',
        element: (
          <RequireAuth roles={['rep']} capability="rep_queue">
            <QueuePage />
          </RequireAuth>
        ),
      },
      {
        path: 'workspace',
        element: (
          <RequireAuth roles={['rep']} capability="chat">
            <WorkspacePage />
          </RequireAuth>
        ),
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
