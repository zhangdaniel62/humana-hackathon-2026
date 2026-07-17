import { describe, expect, it } from 'vitest'
import {
  initialSupportRoomState,
  parseSupportRoom,
  parseSupportServerMessage,
  supportRoomReducer,
  type SupportMessage,
} from './supportProtocol'

const rawRoom = {
  id: 'd69b7a40-0b61-4c20-89ae-23bdb7851a30',
  status: 'active',
  customer: { id: 1, username: 'customer', role: 'customer' },
  assigned_rep: { id: 2, username: 'rep', role: 'rep' },
  source_session_id: 'session-1',
  created_at: '2026-07-17T12:00:00Z',
  claimed_at: '2026-07-17T12:01:00Z',
  completed_at: null,
}

const rawMessage = {
  id: 7,
  room_id: rawRoom.id,
  client_message_id: 'client-1',
  text: 'Can you help?',
  sender: rawRoom.customer,
  created_at: '2026-07-17T12:02:00Z',
}

describe('support room protocol', () => {
  it('validates and normalizes support rooms', () => {
    expect(parseSupportRoom(rawRoom)).toMatchObject({
      id: rawRoom.id,
      status: 'active',
      assignedRep: { username: 'rep', role: 'rep' },
      sourceSessionId: 'session-1',
    })
    expect(parseSupportRoom({ ...rawRoom, assigned_rep: undefined })).toBeNull()
    expect(parseSupportRoom({ ...rawRoom, customer: { ...rawRoom.customer, role: 'rep' } })).toBeNull()
  })

  it('strictly parses every server JSON variant', () => {
    const snapshot = parseSupportServerMessage(
      JSON.stringify({
        type: 'snapshot',
        room: rawRoom,
        messages: [rawMessage],
        presence: { customer: true, rep: true },
        voice: { customer_enabled: true, rep_enabled: false },
      }),
    )
    expect(snapshot).toMatchObject({
      type: 'snapshot',
      messages: [{ id: '7', clientMessageId: 'client-1', delivery: 'sent' }],
      voice: { customerEnabled: true, repEnabled: false },
    })
    expect(
      parseSupportServerMessage(
        JSON.stringify({
          type: 'presence',
          presence: { customer: true, rep: false },
          voice: { customer_enabled: false, rep_enabled: false },
        }),
      )?.type,
    ).toBe('presence')
    expect(
      parseSupportServerMessage(JSON.stringify({ type: 'text', message: rawMessage }))?.type,
    ).toBe('text')
    expect(
      parseSupportServerMessage(JSON.stringify({ type: 'error', code: 'not_active', message: 'Wait.' })),
    ).toEqual({ type: 'error', code: 'not_active', message: 'Wait.' })
  })

  it('rejects malformed, incomplete, and unknown messages', () => {
    expect(parseSupportServerMessage('not json')).toBeNull()
    expect(parseSupportServerMessage('{"type":"unknown"}')).toBeNull()
    expect(
      parseSupportServerMessage(
        JSON.stringify({
          type: 'presence',
          presence: { customer: 'yes', rep: false },
          voice: { customer_enabled: false, rep_enabled: false },
        }),
      ),
    ).toBeNull()
    expect(
      parseSupportServerMessage(
        JSON.stringify({
          type: 'snapshot',
          room: rawRoom,
          messages: [{ ...rawMessage, sender: { ...rawMessage.sender, role: 'manager' } }],
          presence: { customer: true, rep: true },
          voice: { customer_enabled: false, rep_enabled: false },
        }),
      ),
    ).toBeNull()
  })

  it('reconciles an optimistic message with the server acknowledgement', () => {
    const optimistic: SupportMessage = {
      id: 'local-client-1',
      roomId: rawRoom.id,
      clientMessageId: 'client-1',
      text: 'Can you help?',
      sender: { ...rawRoom.customer, role: 'customer' },
      createdAt: '2026-07-17T12:01:59Z',
      delivery: 'pending',
    }
    const pending = supportRoomReducer(initialSupportRoomState, {
      type: 'local_text_sent',
      message: optimistic,
    })
    const parsed = parseSupportServerMessage(JSON.stringify({ type: 'text', message: rawMessage }))
    if (!parsed) throw new Error('Fixture must parse')
    const acknowledged = supportRoomReducer(pending, { type: 'server_message', message: parsed })

    expect(acknowledged.messages).toHaveLength(1)
    expect(acknowledged.messages[0]).toMatchObject({ id: '7', delivery: 'sent' })
  })

  it('classifies authentication close codes', () => {
    expect(
      supportRoomReducer(initialSupportRoomState, { type: 'socket_closed', code: 4401 }),
    ).toMatchObject({ connection: 'unauthorized' })
    expect(
      supportRoomReducer(initialSupportRoomState, { type: 'socket_closed', code: 4403 }),
    ).toMatchObject({ connection: 'forbidden' })
  })

  it('promotes a waiting customer snapshot when the claimed representative joins', () => {
    const snapshot = parseSupportServerMessage(
      JSON.stringify({
        type: 'snapshot',
        room: { ...rawRoom, status: 'waiting', assigned_rep: null, claimed_at: null },
        messages: [],
        presence: { customer: true, rep: false },
        voice: { customer_enabled: false, rep_enabled: false },
      }),
    )
    if (!snapshot) throw new Error('Fixture must parse')
    const waiting = supportRoomReducer(initialSupportRoomState, {
      type: 'server_message',
      message: snapshot,
    })
    const active = supportRoomReducer(waiting, {
      type: 'server_message',
      message: {
        type: 'presence',
        presence: { customer: true, rep: true },
        voice: { customerEnabled: false, repEnabled: false },
      },
    })

    expect(active.room?.status).toBe('active')
  })
})
