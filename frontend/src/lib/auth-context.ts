import { createContext, useContext } from 'react'

export interface User {
  name: string
  role: string
}

export interface SignInCredentials {
  username: string
  password: string
}

export interface AuthContextValue {
  user: User | null
  signIn: (credentials: SignInCredentials) => Promise<void>
  signOut: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
