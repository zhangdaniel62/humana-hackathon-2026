import { apiFetch } from './api'
import { parseSupportRoom, type SupportRoom } from './supportProtocol'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '')

function requireRoom(value: unknown): SupportRoom {
  const room = parseSupportRoom(value)
  if (!room) throw new Error('The support service returned an invalid room.')
  return room
}

function roomPath(roomId: string, suffix = ''): string {
  if (!roomId.trim()) throw new Error('Support room ID is required.')
  return `/api/support/rooms/${encodeURIComponent(roomId)}${suffix}`
}

export async function createSupportRoom(
  sourceSessionId?: string | null,
  signal?: AbortSignal,
): Promise<SupportRoom> {
  const value = await apiFetch<unknown>('/api/support/rooms', {
    method: 'POST',
    signal,
    body: JSON.stringify({ source_session_id: sourceSessionId ?? null }),
  })
  return requireRoom(value)
}

export async function fetchCurrentSupportRoom(signal?: AbortSignal): Promise<SupportRoom | null> {
  const value = await apiFetch<unknown>('/api/support/rooms/current', { signal })
  return value === null ? null : requireRoom(value)
}

export async function fetchSupportQueue(signal?: AbortSignal): Promise<SupportRoom[]> {
  const value = await apiFetch<unknown>('/api/support/queue', { signal })
  if (!Array.isArray(value)) throw new Error('The support service returned an invalid queue.')
  return value.map(requireRoom)
}

export async function claimSupportRoom(roomId: string, signal?: AbortSignal): Promise<SupportRoom> {
  return requireRoom(
    await apiFetch<unknown>(roomPath(roomId, '/claim'), { method: 'POST', signal }),
  )
}

export async function completeSupportRoom(
  roomId: string,
  signal?: AbortSignal,
): Promise<SupportRoom> {
  return requireRoom(
    await apiFetch<unknown>(roomPath(roomId, '/complete'), { method: 'POST', signal }),
  )
}

export function getSupportRoomWebSocketUrl(
  roomId: string,
  apiBaseUrl: string = API_BASE_URL,
): string {
  if (!roomId.trim()) throw new Error('Support room ID is required.')
  const browserOrigin = typeof window === 'undefined' ? 'http://localhost' : window.location.origin
  const url = new URL(apiBaseUrl || browserOrigin, browserOrigin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = `/ws/support/${encodeURIComponent(roomId)}`
  url.search = ''
  url.hash = ''
  return url.toString()
}
