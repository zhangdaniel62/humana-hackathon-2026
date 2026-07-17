/** Same-origin by default; set VITE_API_BASE_URL only when the API is hosted elsewhere. */
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '')
export const AUTH_REQUIRED_EVENT = 'claim-assist:auth-required'

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export interface ApiFetchOptions extends Omit<RequestInit, 'headers'> {
  headers?: HeadersInit
}

function formatErrorDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (!Array.isArray(detail)) return null

  const messages = detail.flatMap((item) => {
    if (typeof item === 'string') return [item]
    if (typeof item === 'object' && item !== null && 'msg' in item && typeof item.msg === 'string') {
      return [item.msg]
    }
    return []
  })
  return messages.length > 0 ? messages.join('; ') : null
}

/** Typed JSON fetch against the backend — the frontend renders, it doesn't decide. */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  if (!path.startsWith('/')) throw new Error(`API path must start with "/": ${path}`)
  const headers = new Headers(options.headers)
  if (options.body !== undefined && options.body !== null && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers,
  })
  if (!response.ok) {
    let detail: unknown
    try {
      const body = (await response.json()) as { detail?: unknown }
      detail = body.detail
    } catch {
      // Non-JSON failures still retain the useful HTTP status fallback below.
    }
    const message = formatErrorDetail(detail) ?? `${response.status} ${response.statusText}`
    if (
      response.status === 401 &&
      path !== '/api/auth/login' &&
      typeof window !== 'undefined'
    ) {
      window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))
    }
    throw new ApiError(response.status, message, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Build the authenticated conversation WebSocket URL from the configured API origin. */
export function getConversationWebSocketUrl(apiBaseUrl: string = API_BASE_URL): string {
  const browserOrigin = typeof window === 'undefined' ? 'http://localhost' : window.location.origin
  const url = new URL(apiBaseUrl || browserOrigin, browserOrigin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = '/ws/conversation'
  url.search = ''
  url.hash = ''
  return url.toString()
}
