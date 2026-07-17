import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch, AUTH_REQUIRED_EVENT, getConversationWebSocketUrl } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiFetch', () => {
  it('uses same-origin paths and includes the session cookie', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ user: { id: 1 } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/auth/me')

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/auth/me')
    expect(options.credentials).toBe('include')
    expect(new Headers(options.headers).has('Content-Type')).toBe(false)
  })

  it('surfaces FastAPI detail in ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Invalid username or password' }), {
          status: 401,
          statusText: 'Unauthorized',
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    const error = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username: 'missing', password: 'wrong' }),
    }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 401,
      message: 'Invalid username or password',
      detail: 'Invalid username or password',
    })
  })

  it('accepts a successful empty logout response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))

    await expect(apiFetch('/api/auth/logout', { method: 'POST' })).resolves.toBeUndefined()
  })

  it('notifies auth state when an established session expires', async () => {
    const dispatchEvent = vi.fn()
    vi.stubGlobal('window', { dispatchEvent })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Authentication required' }), { status: 401 }),
      ),
    )

    await expect(apiFetch('/api/operations/dashboard')).rejects.toMatchObject({ status: 401 })
    expect(dispatchEvent).toHaveBeenCalledOnce()
    expect((dispatchEvent.mock.calls[0]?.[0] as Event).type).toBe(AUTH_REQUIRED_EVENT)
  })
})

describe('getConversationWebSocketUrl', () => {
  it('uses wss for an HTTPS API origin and the canonical conversation path', () => {
    expect(getConversationWebSocketUrl('https://api.example.com/backend/')).toBe(
      'wss://api.example.com/ws/conversation',
    )
  })
})
