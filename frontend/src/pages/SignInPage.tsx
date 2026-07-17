import { useState, type FormEvent } from 'react'
import { Form } from 'react-aria-components'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button, Input } from '@/components/ui'
import { useAuth } from '@/lib/auth-context'

export function SignInPage() {
  const { user, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const from =
    typeof location.state === 'object' &&
    location.state !== null &&
    'from' in location.state &&
    typeof location.state.from === 'string'
      ? location.state.from
      : '/'

  if (user) return <Navigate to={from} replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const username = String(data.get('username') ?? '').trim()
    const password = String(data.get('password') ?? '')

    setSubmitting(true)
    setError(null)
    try {
      await signIn({ username, password })
      navigate(from, { replace: true })
    } catch {
      setError('Sign-in failed. Check your username and password, then try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center p-8">
      <div className="w-full max-w-80">
        <h1 className="text-title2">Claim Assist</h1>
        <p className="mt-1 text-regular text-text-tertiary">Sign in to continue.</p>
        <Form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <Input
            label="Username"
            name="username"
            isRequired
            autoFocus
            autoComplete="username"
            errorMessage="Enter your username."
          />
          <Input
            label="Password"
            name="password"
            type="password"
            isRequired
            autoComplete="current-password"
            errorMessage="Enter your password."
          />
          {error && (
            <p role="alert" className="text-mini text-danger">
              {error}
            </p>
          )}
          <Button type="submit" variant="primary" isDisabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </Form>
        <div className="mt-6 border-t border-border-secondary pt-4">
          <p className="text-mini text-text-tertiary">Members don't need an account.</p>
          <Button className="mt-2 w-full" onPress={() => navigate('/member')}>
            Continue as a member
          </Button>
        </div>
      </div>
    </main>
  )
}
