export type ConversationMode = 'chat' | 'voice'

export interface AudioFormat {
  encoding: 'pcm_s16le'
  sampleRateHz: number
  channels: 1
}

export type ConversationServerMessage =
  | {
      type: 'session_started'
      sessionId: string
      summaryUrl: string
      mode: ConversationMode
      agentAudioEnabled: boolean
      inputAudio: AudioFormat
      outputAudio: AudioFormat
    }
  | { type: 'mode_changed'; mode: ConversationMode }
  | { type: 'user_transcript' | 'agent_transcript'; text: string }
  | { type: 'interrupted' }
  | { type: 'turn_complete'; sessionId: string; summaryUrl: string }
  | { type: 'error'; code: string; message: string; retryable: boolean }

export interface ConversationTranscriptItem {
  id: string
  speaker: 'user' | 'assistant'
  text: string
  complete: boolean
}

export type ConversationConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'unauthorized'
  | 'forbidden'
  | 'error'

export interface ConversationSessionState {
  connection: ConversationConnectionState
  mode: ConversationMode
  pendingMode: ConversationMode | null
  sessionId: string | null
  summaryUrl: string | null
  agentAudioEnabled: boolean
  inputSampleRateHz: number
  outputSampleRateHz: number
  messages: ConversationTranscriptItem[]
  error: string | null
  turnInterrupted: boolean
}

export type ConversationSessionAction =
  | { type: 'socket_connecting' }
  | { type: 'socket_opened' }
  | { type: 'socket_closed'; code: number }
  | { type: 'mode_requested'; mode: ConversationMode }
  | { type: 'server_message'; message: ConversationServerMessage }
  | { type: 'local_text_sent'; id: string; text: string }
  | { type: 'client_error'; message: string }
  | { type: 'clear_error' }

export const initialConversationSessionState: ConversationSessionState = {
  connection: 'connecting',
  mode: 'chat',
  pendingMode: null,
  sessionId: null,
  summaryUrl: null,
  agentAudioEnabled: false,
  inputSampleRateHz: 16_000,
  outputSampleRateHz: 24_000,
  messages: [],
  error: null,
  turnInterrupted: false,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isMode(value: unknown): value is ConversationMode {
  return value === 'chat' || value === 'voice'
}

function parseAudioFormat(value: unknown, fallbackRate: number): AudioFormat {
  if (!isRecord(value)) {
    return { encoding: 'pcm_s16le', sampleRateHz: fallbackRate, channels: 1 }
  }
  return {
    encoding: 'pcm_s16le',
    sampleRateHz:
      typeof value.sample_rate_hz === 'number' && value.sample_rate_hz > 0
        ? value.sample_rate_hz
        : fallbackRate,
    channels: 1,
  }
}

/** Parse every JSON variant emitted by the conversation WebSocket. */
export function parseConversationServerMessage(raw: string): ConversationServerMessage | null {
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return null
  }
  if (!isRecord(value) || typeof value.type !== 'string') return null

  switch (value.type) {
    case 'session_started':
      if (
        typeof value.session_id !== 'string' ||
        typeof value.summary_url !== 'string' ||
        !isMode(value.mode)
      ) {
        return null
      }
      return {
        type: value.type,
        sessionId: value.session_id,
        summaryUrl: value.summary_url,
        mode: value.mode,
        agentAudioEnabled: value.agent_audio_enabled !== false,
        inputAudio: parseAudioFormat(value.input_audio, 16_000),
        outputAudio: parseAudioFormat(value.output_audio, 24_000),
      }
    case 'mode_changed':
      return isMode(value.mode) ? { type: value.type, mode: value.mode } : null
    case 'user_transcript':
    case 'agent_transcript':
      return typeof value.text === 'string' ? { type: value.type, text: value.text } : null
    case 'interrupted':
      return { type: value.type }
    case 'turn_complete':
      return typeof value.session_id === 'string' && typeof value.summary_url === 'string'
        ? {
            type: value.type,
            sessionId: value.session_id,
            summaryUrl: value.summary_url,
          }
        : null
    case 'error':
      return typeof value.code === 'string' && typeof value.message === 'string'
        ? {
            type: value.type,
            code: value.code,
            message: value.message,
            retryable: value.retryable === true,
          }
        : null
    default:
      return null
  }
}

function appendTranscriptDelta(
  messages: ConversationTranscriptItem[],
  speaker: ConversationTranscriptItem['speaker'],
  text: string,
): ConversationTranscriptItem[] {
  if (!text) return messages
  const activeIndex = messages.findLastIndex(
    (message) => message.speaker === speaker && !message.complete,
  )
  if (activeIndex >= 0) {
    return messages.map((message, index) =>
      index === activeIndex ? { ...message, text: `${message.text}${text}` } : message,
    )
  }
  return [
    ...messages,
    {
      id: `${speaker}-${messages.length + 1}`,
      speaker,
      text,
      complete: false,
    },
  ]
}

function completeTranscript(messages: ConversationTranscriptItem[]): ConversationTranscriptItem[] {
  return messages.map((message) => (message.complete ? message : { ...message, complete: true }))
}

export function conversationSessionReducer(
  state: ConversationSessionState,
  action: ConversationSessionAction,
): ConversationSessionState {
  switch (action.type) {
    case 'socket_connecting':
      return { ...state, connection: 'connecting', error: null }
    case 'socket_opened':
      return { ...state, connection: 'connected', error: null }
    case 'socket_closed': {
      if (action.code === 4401) {
        return {
          ...state,
          connection: 'unauthorized',
          pendingMode: null,
          error: 'Your session is not signed in. Please sign in again.',
        }
      }
      if (action.code === 4403) {
        return {
          ...state,
          connection: 'forbidden',
          pendingMode: null,
          error: 'This account is not allowed to start this conversation.',
        }
      }
      return {
        ...state,
        connection: action.code === 1000 ? 'disconnected' : 'error',
        pendingMode: null,
        error:
          action.code === 1000
            ? state.error
            : state.error ?? 'The conversation connection closed unexpectedly.',
      }
    }
    case 'mode_requested':
      return { ...state, pendingMode: action.mode, error: null }
    case 'local_text_sent':
      return {
        ...state,
        messages: [
          ...completeTranscript(state.messages),
          { id: action.id, speaker: 'user', text: action.text, complete: true },
        ],
        turnInterrupted: false,
      }
    case 'client_error':
      return { ...state, error: action.message }
    case 'clear_error':
      return { ...state, error: null }
    case 'server_message': {
      const message = action.message
      switch (message.type) {
        case 'session_started':
          return {
            ...state,
            connection: 'connected',
            sessionId: message.sessionId,
            summaryUrl: message.summaryUrl,
            mode: message.mode,
            pendingMode: null,
            agentAudioEnabled: message.agentAudioEnabled,
            inputSampleRateHz: message.inputAudio.sampleRateHz,
            outputSampleRateHz: message.outputAudio.sampleRateHz,
            error: null,
          }
        case 'mode_changed':
          return {
            ...state,
            mode: message.mode,
            pendingMode: null,
            turnInterrupted: false,
          }
        case 'user_transcript':
          return {
            ...state,
            messages: appendTranscriptDelta(state.messages, 'user', message.text),
            turnInterrupted: false,
          }
        case 'agent_transcript':
          return {
            ...state,
            messages: appendTranscriptDelta(state.messages, 'assistant', message.text),
            turnInterrupted: false,
          }
        case 'interrupted':
          return {
            ...state,
            messages: completeTranscript(state.messages),
            turnInterrupted: true,
          }
        case 'turn_complete':
          return {
            ...state,
            sessionId: message.sessionId,
            summaryUrl: message.summaryUrl,
            messages: completeTranscript(state.messages),
            turnInterrupted: false,
          }
        case 'error':
          return {
            ...state,
            mode: message.code === 'voice_forbidden' ? 'chat' : state.mode,
            pendingMode: message.code === 'voice_forbidden' ? null : state.pendingMode,
            error: message.message,
          }
      }
    }
  }
}

/** Suppress a server echo of text already rendered optimistically by the client. */
export function consumePendingTextEcho(
  pending: string,
  delta: string,
): { pending: string; delta: string } {
  if (!pending || !delta) return { pending, delta }
  let matched = 0
  const limit = Math.min(pending.length, delta.length)
  while (matched < limit && pending[matched] === delta[matched]) matched += 1
  if (matched === 0) return { pending: '', delta }
  if (matched === delta.length) return { pending: pending.slice(matched), delta: '' }
  return { pending: '', delta: delta.slice(matched) }
}

export function canStreamMicrophoneAudio(mode: ConversationMode, socketIsOpen: boolean): boolean {
  return mode === 'voice' && socketIsOpen
}
