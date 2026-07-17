import { createContext, useContext } from 'react'

export type UserRole = 'manager' | 'customer' | 'rep'
export type Capability = 'manager_dashboard' | 'chat' | 'rep_queue' | 'voice'

export interface User {
  id: number
  username: string
  /** Display-compatible alias for existing representative workspace surfaces. */
  name: string
  role: UserRole
  capabilities: Capability[]
}

export interface SignInCredentials {
  username: string
  password: string
}

export interface AuthContextValue {
  user: User | null
  loading: boolean
  signIn: (credentials: SignInCredentials) => Promise<User>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}

export function hasCapability(user: User, capability: Capability): boolean {
  return user.capabilities.includes(capability)
}

export function landingPathFor(user: User): string {
  if (user.role === 'manager' && hasCapability(user, 'manager_dashboard')) return '/'
  if (user.role === 'customer' && hasCapability(user, 'chat')) return '/member'
  if (user.role === 'rep' && hasCapability(user, 'rep_queue')) return '/queue'
  return '/signin'
}

export function canAccessPath(user: User, path: string): boolean {
  const pathname = path.split(/[?#]/, 1)[0]
  if (!pathname.startsWith('/') || pathname.startsWith('//')) return false

  if (user.role === 'manager' && hasCapability(user, 'manager_dashboard')) {
    return pathname === '/' || pathname.startsWith('/metrics/')
  }
  if (user.role === 'customer' && hasCapability(user, 'chat')) return pathname === '/member'
  if (user.role === 'rep') {
    return (
      (pathname === '/queue' && hasCapability(user, 'rep_queue')) ||
      (pathname === '/workspace' && hasCapability(user, 'chat'))
    )
  }
  return false
}

export function roleLabel(role: UserRole): string {
  switch (role) {
    case 'manager':
      return 'Manager'
    case 'customer':
      return 'Customer'
    case 'rep':
      return 'Representative'
  }
}
