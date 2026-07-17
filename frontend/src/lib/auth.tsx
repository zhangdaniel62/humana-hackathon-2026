import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { AuthContext, type SignInCredentials, type User } from './auth-context'

const STORAGE_KEY = 'claim-assist.user'

function loadStoredUser(): User | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

/** Demo sign-in: any non-empty credentials; a "manager" username gets the manager role. */
function authenticate({ username, password }: SignInCredentials): User {
  if (!username || !password) throw new Error('Missing credentials')
  const isManager = username.toLowerCase().includes('manager')
  return { name: username, role: isManager ? 'Manager' : 'Representative' }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(loadStoredUser)

  const signIn = useCallback(async (credentials: SignInCredentials) => {
    const authenticated = authenticate(credentials)
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(authenticated))
    setUser(authenticated)
  }, [])

  const signOut = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY)
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, signIn, signOut }), [user, signIn, signOut])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
