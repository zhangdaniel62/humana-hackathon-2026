import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { apiFetch, AUTH_REQUIRED_EVENT } from './api'
import {
  AuthContext,
  type Capability,
  type SignInCredentials,
  type User,
  type UserRole,
} from './auth-context'

interface BackendUser {
  id: number
  username: string
  role: UserRole
  capabilities: Capability[]
}

interface AuthResponse {
  user: BackendUser
}

function toUser(user: BackendUser): User {
  return { ...user, name: user.username }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    void apiFetch<AuthResponse>('/api/auth/me')
      .then((response) => {
        if (active) setUser(toUser(response.user))
      })
      .catch(() => {
        if (active) setUser(null)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const clearExpiredSession = () => setUser(null)
    window.addEventListener(AUTH_REQUIRED_EVENT, clearExpiredSession)
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, clearExpiredSession)
  }, [])

  const signIn = useCallback(async (credentials: SignInCredentials) => {
    const response = await apiFetch<AuthResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    })
    const authenticated = toUser(response.user)
    setUser(authenticated)
    return authenticated
  }, [])

  const signOut = useCallback(async () => {
    try {
      await apiFetch<void>('/api/auth/logout', { method: 'POST' })
    } finally {
      setUser(null)
    }
  }, [])

  const value = useMemo(
    () => ({ user, loading, signIn, signOut }),
    [user, loading, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
