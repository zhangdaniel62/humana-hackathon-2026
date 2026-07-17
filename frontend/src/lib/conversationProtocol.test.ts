import { describe, expect, it } from 'vitest'
import {
  canStreamMicrophoneAudio,
  consumePendingTextEcho,
  conversationSessionReducer,
  initialConversationSessionState,
  parseConversationServerMessage,
  type ConversationServerMessage,
} from './conversationProtocol'

const started: ConversationServerMessage = {
  type: 'session_started',
  sessionId: 'session-1',
  summaryUrl: '/api/sessions/session-1/summary',
  mode: 'chat',
  agentAudioEnabled: true,
  inputAudio: { encoding: 'pcm_s16le', sampleRateHz: 16_000, channels: 1 },
  outputAudio: { encoding: 'pcm_s16le', sampleRateHz: 24_000, channels: 1 },
}

describe('conversation WebSocket protocol', () => {
  it('parses every server JSON variant', () => {
    const variants = [
      {
        type: 'session_started',
        session_id: 'session-1',
        summary_url: '/api/sessions/session-1/summary',
        mode: 'chat',
        agent_audio_enabled: true,
        input_audio: { encoding: 'pcm_s16le', sample_rate_hz: 16_000, channels: 1 },
        output_audio: { encoding: 'pcm_s16le', sample_rate_hz: 24_000, channels: 1 },
      },
      { type: 'mode_changed', mode: 'voice' },
      { type: 'user_transcript', text: 'hello' },
      { type: 'agent_transcript', text: 'hi' },
      { type: 'interrupted' },
      {
        type: 'turn_complete',
        session_id: 'session-1',
        summary_url: '/api/sessions/session-1/summary',
      },
      { type: 'error', code: 'voice_mode_required', message: 'Choose Voice.', retryable: false },
    ]

    expect(variants.map((variant) => parseConversationServerMessage(JSON.stringify(variant))?.type)).toEqual([
      'session_started',
      'mode_changed',
      'user_transcript',
      'agent_transcript',
      'interrupted',
      'turn_complete',
      'error',
    ])
    expect(parseConversationServerMessage('not json')).toBeNull()
    expect(parseConversationServerMessage('{"type":"unknown"}')).toBeNull()
  })

  it('preserves one session while modes change', () => {
    const withSession = conversationSessionReducer(initialConversationSessionState, {
      type: 'server_message',
      message: started,
    })
    const requested = conversationSessionReducer(withSession, { type: 'mode_requested', mode: 'voice' })
    const voice = conversationSessionReducer(requested, {
      type: 'server_message',
      message: { type: 'mode_changed', mode: 'voice' },
    })
    const chat = conversationSessionReducer(voice, {
      type: 'server_message',
      message: { type: 'mode_changed', mode: 'chat' },
    })

    expect(requested.pendingMode).toBe('voice')
    expect(voice.sessionId).toBe('session-1')
    expect(chat.sessionId).toBe('session-1')
    expect(chat.mode).toBe('chat')
  })

  it('coalesces interleaved transcript deltas by speaker until turn completion', () => {
    let state = initialConversationSessionState
    for (const message of [
      { type: 'user_transcript', text: 'check' },
      { type: 'agent_transcript', text: 'I found' },
      { type: 'user_transcript', text: ' my claim' },
      { type: 'agent_transcript', text: ' it' },
    ] as ConversationServerMessage[]) {
      state = conversationSessionReducer(state, { type: 'server_message', message })
    }
    expect(state.messages.map(({ speaker, text }) => ({ speaker, text }))).toEqual([
      { speaker: 'user', text: 'check my claim' },
      { speaker: 'assistant', text: 'I found it' },
    ])

    state = conversationSessionReducer(state, {
      type: 'server_message',
      message: {
        type: 'turn_complete',
        sessionId: 'session-1',
        summaryUrl: '/api/sessions/session-1/summary',
      },
    })
    expect(state.messages.every((message) => message.complete)).toBe(true)
  })

  it('finishes interrupted playback turns and classifies authentication closes', () => {
    const speaking = conversationSessionReducer(initialConversationSessionState, {
      type: 'server_message',
      message: { type: 'agent_transcript', text: 'partial' },
    })
    const interrupted = conversationSessionReducer(speaking, {
      type: 'server_message',
      message: { type: 'interrupted' },
    })
    expect(interrupted.turnInterrupted).toBe(true)
    expect(interrupted.messages[0]?.complete).toBe(true)
    expect(
      conversationSessionReducer(interrupted, { type: 'socket_closed', code: 4401 }).connection,
    ).toBe('unauthorized')
    expect(
      conversationSessionReducer(interrupted, { type: 'socket_closed', code: 4403 }).connection,
    ).toBe('forbidden')
  })

  it('suppresses chunked typed-text echoes and gates microphone frames to Voice', () => {
    const first = consumePendingTextEcho('check my claim', 'check')
    const second = consumePendingTextEcho(first.pending, ' my claim')
    expect(first.delta).toBe('')
    expect(second).toEqual({ pending: '', delta: '' })
    expect(canStreamMicrophoneAudio('chat', true)).toBe(false)
    expect(canStreamMicrophoneAudio('voice', false)).toBe(false)
    expect(canStreamMicrophoneAudio('voice', true)).toBe(true)
  })
})
