import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import {
  hasCapability,
  landingPathFor,
  useAuth,
  type Capability,
  type UserRole,
} from '@/lib/auth-context'

interface RequireAuthProps {
  children: ReactNode
  capability?: Capability
  roles?: UserRole[]
}

export function RequireAuth({ children, capability, roles }: RequireAuthProps) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <div className="flex min-h-dvh items-center justify-center text-small text-text-tertiary">Loading…</div>
  }
  if (!user) {
    return (
      <Navigate
        to="/signin"
        replace
        state={{ from: `${location.pathname}${location.search}${location.hash}` }}
      />
    )
  }
  if (roles && !roles.includes(user.role)) return <Navigate to={landingPathFor(user)} replace />
  if (capability && !hasCapability(user, capability)) {
    return <Navigate to={landingPathFor(user)} replace />
  }
  return children
}
