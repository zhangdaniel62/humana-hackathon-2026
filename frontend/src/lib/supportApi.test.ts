import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  claimSupportRoom,
  createSupportRoom,
  fetchCurrentSupportRoom,
  fetchSupportQueue,
  getSupportRoomWebSocketUrl,
} from './supportApi'

const rawRoom = {
  id: 'room/id',
  status: 'waiting',
  customer: { id: 1, username: 'customer', role: 'customer' },
  assigned_rep: null,
  source_session_id: null,
  created_at: '2026-07-17T12:00:00Z',
  claimed_at: null,
  completed_at: null,
}

afterEach(() => vi.unstubAllGlobals())

describe('support REST API', () => {
  it('creates a room with the optional source session', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(rawRoom), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(createSupportRoom('session-1')).resolves.toMatchObject({ id: 'room/id' })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/support/rooms',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ source_session_id: 'session-1' }),
      }),
    )
  })

  it('accepts no current room and validates queue entries', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response('null', { status: 200, headers: { 'Content-Type': 'application/json' } }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([rawRoom]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchCurrentSupportRoom()).resolves.toBeNull()
    await expect(fetchSupportQueue()).resolves.toHaveLength(1)
  })

  it('URL-encodes room IDs for claims and sockets', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(rawRoom), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await claimSupportRoom('room/id')
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/support/rooms/room%2Fid/claim')
    expect(getSupportRoomWebSocketUrl('room/id', 'https://api.example.com/base')).toBe(
      'wss://api.example.com/ws/support/room%2Fid',
    )
  })

  it('rejects malformed room responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ...rawRoom, status: 'unknown' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    await expect(createSupportRoom()).rejects.toThrow('invalid room')
  })
})
