export type SupportRole = 'customer' | 'rep'
export type SupportRoomStatus = 'waiting' | 'active' | 'completed'

export interface SupportUser {
  id: number
  username: string
  role: SupportRole
}

export interface SupportRoom {
  id: string
  status: SupportRoomStatus
  customer: SupportUser & { role: 'customer' }
  assignedRep: (SupportUser & { role: 'rep' }) | null
  sourceSessionId: string | null
  createdAt: string
  claimedAt: string | null
  completedAt: string | null
}

export interface SupportPresence {
  customer: boolean
  rep: boolean
}

export interface SupportVoiceState {
  customerEnabled: boolean
  repEnabled: boolean
}

export interface SupportMessage {
  id: string
  roomId: string
  clientMessageId: string
  text: string
  sender: SupportUser
  createdAt: string
  delivery: 'pending' | 'sent'
}

export type SupportServerMessage =
  | {
      type: 'snapshot'
      room: SupportRoom
      messages: SupportMessage[]
      presence: SupportPresence
      voice: SupportVoiceState
    }
  | { type: 'presence'; presence: SupportPresence; voice: SupportVoiceState }
  | { type: 'text'; message: SupportMessage }
  | { type: 'error'; code: string; message: string }

export type SupportClientMessage =
  | { type: 'text'; client_message_id: string; text: string }
  | { type: 'set_voice'; enabled: boolean }

export type SupportConnectionState =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'unauthorized'
  | 'forbidden'
  | 'error'

export interface SupportRoomState {
  connection: SupportConnectionState
  room: SupportRoom | null
  messages: SupportMessage[]
  presence: SupportPresence
  voice: SupportVoiceState
  error: string | null
}

export type SupportRoomAction =
  | { type: 'room_cleared' }
  | { type: 'socket_connecting' }
  | { type: 'socket_opened' }
  | { type: 'socket_closed'; code: number }
  | { type: 'server_message'; message: SupportServerMessage }
  | { type: 'local_text_sent'; message: SupportMessage }
  | { type: 'client_error'; message: string }
  | { type: 'clear_error' }

const EMPTY_PRESENCE: SupportPresence = { customer: false, rep: false }
const EMPTY_VOICE: SupportVoiceState = { customerEnabled: false, repEnabled: false }

export const initialSupportRoomState: SupportRoomState = {
  connection: 'idle',
  room: null,
  messages: [],
  presence: EMPTY_PRESENCE,
  voice: EMPTY_VOICE,
  error: null,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function parseUser(value: unknown): SupportUser | null {
  if (
    !isRecord(value) ||
    !Number.isInteger(value.id) ||
    typeof value.username !== 'string' ||
    (value.role !== 'customer' && value.role !== 'rep')
  ) {
    return null
  }
  return { id: value.id as number, username: value.username, role: value.role }
}

/** Runtime validation shared by REST responses and WebSocket snapshots. */
export function parseSupportRoom(value: unknown): SupportRoom | null {
  if (
    !isRecord(value) ||
    typeof value.id !== 'string' ||
    (value.status !== 'waiting' && value.status !== 'active' && value.status !== 'completed') ||
    !isNullableString(value.source_session_id) ||
    typeof value.created_at !== 'string' ||
    !isNullableString(value.claimed_at) ||
    !isNullableString(value.completed_at)
  ) {
    return null
  }
  const customer = parseUser(value.customer)
  const assignedRep = value.assigned_rep === null ? null : parseUser(value.assigned_rep)
  if (
    customer?.role !== 'customer' ||
    (value.assigned_rep !== null && assignedRep?.role !== 'rep')
  ) {
    return null
  }
  return {
    id: value.id,
    status: value.status,
    customer: { ...customer, role: 'customer' },
    assignedRep: assignedRep ? { ...assignedRep, role: 'rep' } : null,
    sourceSessionId: value.source_session_id,
    createdAt: value.created_at,
    claimedAt: value.claimed_at,
    completedAt: value.completed_at,
  }
}

function parsePresence(value: unknown): SupportPresence | null {
  if (
    !isRecord(value) ||
    typeof value.customer !== 'boolean' ||
    typeof value.rep !== 'boolean'
  ) {
    return null
  }
  return { customer: value.customer, rep: value.rep }
}

function parseVoice(value: unknown): SupportVoiceState | null {
  if (
    !isRecord(value) ||
    typeof value.customer_enabled !== 'boolean' ||
    typeof value.rep_enabled !== 'boolean'
  ) {
    return null
  }
  return { customerEnabled: value.customer_enabled, repEnabled: value.rep_enabled }
}

function parseMessage(value: unknown): SupportMessage | null {
  if (
    !isRecord(value) ||
    !Number.isInteger(value.id) ||
    typeof value.room_id !== 'string' ||
    typeof value.client_message_id !== 'string' ||
    typeof value.text !== 'string' ||
    typeof value.created_at !== 'string'
  ) {
    return null
  }
  const sender = parseUser(value.sender)
  if (!sender) return null
  return {
    id: String(value.id),
    roomId: value.room_id,
    clientMessageId: value.client_message_id,
    text: value.text,
    sender,
    createdAt: value.created_at,
    delivery: 'sent',
  }
}

/** Reject malformed and unknown WebSocket JSON rather than partially trusting it. */
export function parseSupportServerMessage(raw: string): SupportServerMessage | null {
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return null
  }
  if (!isRecord(value) || typeof value.type !== 'string') return null

  if (value.type === 'snapshot') {
    const room = parseSupportRoom(value.room)
    const presence = parsePresence(value.presence)
    const voice = parseVoice(value.voice)
    if (!room || !presence || !voice || !Array.isArray(value.messages)) return null
    const messages = value.messages.map(parseMessage)
    if (messages.some((message) => message === null)) return null
    return {
      type: value.type,
      room,
      messages: messages as SupportMessage[],
      presence,
      voice,
    }
  }
  if (value.type === 'presence') {
    const presence = parsePresence(value.presence)
    const voice = parseVoice(value.voice)
    return presence && voice ? { type: value.type, presence, voice } : null
  }
  if (value.type === 'text') {
    const message = parseMessage(value.message)
    return message ? { type: value.type, message } : null
  }
  if (value.type === 'error') {
    return typeof value.code === 'string' && typeof value.message === 'string'
      ? { type: value.type, code: value.code, message: value.message }
      : null
  }
  return null
}

function reconcileMessage(messages: SupportMessage[], incoming: SupportMessage): SupportMessage[] {
  const matchingIndex = messages.findIndex(
    (message) =>
      message.id === incoming.id ||
      (message.clientMessageId === incoming.clientMessageId &&
        message.sender.id === incoming.sender.id),
  )
  if (matchingIndex < 0) return [...messages, incoming]
  return messages.map((message, index) => (index === matchingIndex ? incoming : message))
}

export function supportRoomReducer(
  state: SupportRoomState,
  action: SupportRoomAction,
): SupportRoomState {
  switch (action.type) {
    case 'room_cleared':
      return initialSupportRoomState
    case 'socket_connecting':
      return { ...state, connection: 'connecting', error: null }
    case 'socket_opened':
      return { ...state, connection: 'connected', error: null }
    case 'socket_closed':
      if (action.code === 4401) {
        return {
          ...state,
          connection: 'unauthorized',
          presence: EMPTY_PRESENCE,
          voice: EMPTY_VOICE,
          error: 'Please sign in again.',
        }
      }
      if (action.code === 4403) {
        return {
          ...state,
          connection: 'forbidden',
          presence: EMPTY_PRESENCE,
          voice: EMPTY_VOICE,
          error: 'You cannot join this support room.',
        }
      }
      return {
        ...state,
        connection: action.code === 1000 ? 'disconnected' : 'error',
        presence: EMPTY_PRESENCE,
        voice: EMPTY_VOICE,
        error:
          action.code === 1000
            ? state.error
            : state.error ?? 'The live support connection closed unexpectedly.',
      }
    case 'local_text_sent':
      return { ...state, messages: reconcileMessage(state.messages, action.message), error: null }
    case 'client_error':
      return { ...state, error: action.message }
    case 'clear_error':
      return { ...state, error: null }
    case 'server_message': {
      const message = action.message
      if (message.type === 'snapshot') {
        return {
          ...state,
          connection: 'connected',
          room: message.room,
          messages: message.messages,
          presence: message.presence,
          voice: message.voice,
          error: null,
        }
      }
      if (message.type === 'presence') {
        // A waiting customer socket is already open when a representative claims
        // the room. The representative can only become present after that claim,
        // so promote the local snapshot without requiring a reconnect.
        const room =
          state.room?.status === 'waiting' && message.presence.rep
            ? { ...state.room, status: 'active' as const }
            : state.room
        return { ...state, room, presence: message.presence, voice: message.voice }
      }
      if (message.type === 'text') {
        return { ...state, messages: reconcileMessage(state.messages, message.message) }
      }
      return { ...state, error: message.message }
    }
  }
}
