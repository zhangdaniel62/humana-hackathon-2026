import { useState, type FormEvent } from 'react'
import { Form } from 'react-aria-components'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button, Input } from '@/components/ui'
import { ThemeMenu } from '@/components/ThemeMenu'
import { ApiError } from '@/lib/api'
import { canAccessPath, landingPathFor, useAuth } from '@/lib/auth-context'

export function SignInPage() {
  const { user, loading, signIn, continueAsMember } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [submitting, setSubmitting] = useState(false)
  const [memberSubmitting, setMemberSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const from =
    typeof location.state === 'object' &&
    location.state !== null &&
    'from' in location.state &&
    typeof location.state.from === 'string'
      ? location.state.from
      : '/'

  if (loading) {
    return (
      <main className="flex min-h-dvh items-center justify-center text-small text-text-tertiary">
        Loading…
      </main>
    )
  }

  if (user) {
    return <Navigate to={canAccessPath(user, from) ? from : landingPathFor(user)} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const username = String(data.get('username') ?? '').trim()
    const password = String(data.get('password') ?? '')

    setSubmitting(true)
    setError(null)
    try {
      const authenticated = await signIn({ username, password })
      navigate(canAccessPath(authenticated, from) ? from : landingPathFor(authenticated), {
        replace: true,
      })
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Sign-in failed. Check your username and password, then try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  async function handleMemberAccess() {
    setMemberSubmitting(true)
    setError(null)
    try {
      await continueAsMember()
      navigate('/member', { replace: true })
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Member access is unavailable right now. Please try again.',
      )
    } finally {
      setMemberSubmitting(false)
    }
  }

  return (
    <main className="relative flex min-h-dvh items-center justify-center p-8">
      <ThemeMenu className="absolute top-4 right-4" />
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
          <Button type="submit" variant="primary" isDisabled={submitting || memberSubmitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </Form>
        <div className="my-4 flex items-center gap-3" aria-hidden="true">
          <span className="h-px flex-1 bg-border-primary" />
          <span className="text-mini text-text-quaternary">or</span>
          <span className="h-px flex-1 bg-border-primary" />
        </div>
        <Button
          className="w-full"
          onPress={() => void handleMemberAccess()}
          isDisabled={submitting || memberSubmitting}
        >
          {memberSubmitting ? 'Opening member page…' : 'Continue as member'}
        </Button>
      </div>
    </main>
  )
}
