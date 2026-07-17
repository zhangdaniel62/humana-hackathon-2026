import { Link } from 'react-router-dom'

/** Member entry — members talk to the AI directly, no account involved. */
export function MemberPage() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-1 p-8 text-center">
      <h1 className="text-title2">Talk to Claim Assist</h1>
      <p className="max-w-96 text-regular text-text-tertiary">
        Ask about a claim, your coverage, or a denial — the conversation starts here.
      </p>
      <Link
        to="/signin"
        className="mt-6 rounded-sm text-small text-text-tertiary transition-colors hover:text-text-primary"
      >
        Staff sign in
      </Link>
    </main>
  )
}
