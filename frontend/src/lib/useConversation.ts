import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { getConversationWebSocketUrl } from './api'
import { MicrophonePcm16Capture, Pcm16PlaybackQueue } from './conversationAudio'
import {
  canStreamMicrophoneAudio,
  consumePendingTextEcho,
  conversationSessionReducer,
  initialConversationSessionState,
  parseConversationServerMessage,
  type ConversationMode,
  type ConversationServerMessage,
} from './conversationProtocol'
import { fetchConversationSummary, type ProjectedSessionSummary } from './conversationSummary'

type MicrophoneState = 'inactive' | 'starting' | 'listening' | 'error'

export function useConversation() {
  const [state, dispatch] = useReducer(conversationSessionReducer, initialConversationSessionState)
  const [summary, setSummary] = useState<ProjectedSessionSummary | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [microphoneState, setMicrophoneState] = useState<MicrophoneState>('inactive')
  const socketRef = useRef<WebSocket | null>(null)
  const microphoneRef = useRef<MicrophonePcm16Capture | null>(null)
  const playbackRef = useRef<Pcm16PlaybackQueue | null>(null)
  const modeRef = useRef<ConversationMode>('chat')
  const outputRateRef = useRef(24_000)
  const pendingTextEchoRef = useRef('')
  const summaryRequestRef = useRef(0)
  const localMessageSequenceRef = useRef(0)

  const stopVoice = useCallback((dispose = false) => {
    microphoneRef.current?.stop()
    microphoneRef.current = null
    if (dispose) {
      playbackRef.current?.dispose()
      playbackRef.current = null
    } else {
      playbackRef.current?.clear()
    }
    setMicrophoneState('inactive')
  }, [])

  const sendBinary = useCallback((pcm: ArrayBuffer) => {
    const socket = socketRef.current
    if (canStreamMicrophoneAudio(modeRef.current, socket?.readyState === WebSocket.OPEN)) {
      socket?.send(pcm)
    }
  }, [])

  const startMicrophone = useCallback(async () => {
    if (modeRef.current !== 'voice') return
    setMicrophoneState('starting')
    try {
      const microphone = microphoneRef.current ?? new MicrophonePcm16Capture()
      microphoneRef.current = microphone
      await microphone.start(sendBinary, 16_000)
      if (modeRef.current === 'voice') setMicrophoneState('listening')
    } catch (error) {
      setMicrophoneState('error')
      dispatch({
        type: 'client_error',
        message:
          error instanceof DOMException && error.name === 'NotAllowedError'
            ? 'Microphone access was denied. Allow microphone access to use Voice.'
            : 'The microphone could not be started. You can return to Chat or try Voice again.',
      })
    }
  }, [sendBinary])

  const loadSummary = useCallback(async (summaryUrl: string) => {
    const request = summaryRequestRef.current + 1
    summaryRequestRef.current = request
    setSummaryLoading(true)
    try {
      const nextSummary = await fetchConversationSummary(summaryUrl)
      if (request === summaryRequestRef.current) setSummary(nextSummary)
    } catch (error) {
      if (request === summaryRequestRef.current) {
        dispatch({
          type: 'client_error',
          message: error instanceof Error ? error.message : 'The session summary could not be loaded.',
        })
      }
    } finally {
      if (request === summaryRequestRef.current) setSummaryLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    const socket = new WebSocket(getConversationWebSocketUrl())
    socket.binaryType = 'arraybuffer'
    socketRef.current = socket
    dispatch({ type: 'socket_connecting' })

    const handleServerMessage = (message: ConversationServerMessage) => {
      if (message.type === 'user_transcript' && pendingTextEchoRef.current) {
        const consumed = consumePendingTextEcho(pendingTextEchoRef.current, message.text)
        pendingTextEchoRef.current = consumed.pending
        if (!consumed.delta) return
        dispatch({ type: 'server_message', message: { ...message, text: consumed.delta } })
        return
      }

      if (message.type === 'session_started') {
        modeRef.current = message.mode
        outputRateRef.current = message.outputAudio.sampleRateHz
      }
      if (message.type === 'mode_changed') {
        modeRef.current = message.mode
        if (message.mode === 'voice') void startMicrophone()
        else stopVoice()
      }
      if (message.type === 'interrupted') playbackRef.current?.clear()
      if (message.type === 'turn_complete') void loadSummary(message.summaryUrl)
      if (message.type === 'error' && message.code === 'voice_forbidden') {
        modeRef.current = 'chat'
        stopVoice()
      }
      dispatch({ type: 'server_message', message })
    }

    socket.onopen = () => dispatch({ type: 'socket_opened' })
    socket.onmessage = (event) => {
      if (!active) return
      if (typeof event.data === 'string') {
        const message = parseConversationServerMessage(event.data)
        if (message) handleServerMessage(message)
        else dispatch({ type: 'client_error', message: 'The server sent an unsupported message.' })
        return
      }

      const play = async (pcm: ArrayBuffer) => {
        if (!active || modeRef.current !== 'voice') return
        try {
          const playback = playbackRef.current ?? new Pcm16PlaybackQueue()
          playbackRef.current = playback
          await playback.enqueue(pcm, outputRateRef.current)
        } catch {
          dispatch({ type: 'client_error', message: 'The voice response could not be played.' })
        }
      }
      if (event.data instanceof ArrayBuffer) void play(event.data)
      else if (event.data instanceof Blob) void event.data.arrayBuffer().then(play)
    }
    socket.onerror = () => {
      if (active) dispatch({ type: 'client_error', message: 'The conversation connection encountered an error.' })
    }
    socket.onclose = (event) => {
      if (!active) return
      stopVoice()
      dispatch({ type: 'socket_closed', code: event.code })
    }

    return () => {
      active = false
      summaryRequestRef.current += 1
      socket.onopen = null
      socket.onmessage = null
      socket.onerror = null
      socket.onclose = null
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close(1000)
      }
      if (socketRef.current === socket) socketRef.current = null
      stopVoice(true)
    }
  }, [loadSummary, startMicrophone, stopVoice])

  const setMode = useCallback(
    (mode: ConversationMode) => {
      const socket = socketRef.current
      if (socket?.readyState !== WebSocket.OPEN || !state.sessionId) {
        dispatch({ type: 'client_error', message: 'Wait for the conversation to connect before changing modes.' })
        return
      }
      if (mode === 'chat') {
        modeRef.current = 'chat'
        stopVoice()
      }
      dispatch({ type: 'mode_requested', mode })
      socket.send(JSON.stringify({ type: 'set_mode', mode }))
    },
    [state.sessionId, stopVoice],
  )

  const sendText = useCallback(
    (text: string): boolean => {
      const normalized = text.trim().slice(0, 4000)
      if (!normalized) return false
      const socket = socketRef.current
      if (socket?.readyState !== WebSocket.OPEN || !state.sessionId) {
        dispatch({ type: 'client_error', message: 'Wait for the conversation to connect before sending a message.' })
        return false
      }
      socket.send(JSON.stringify({ type: 'text', text: normalized }))
      pendingTextEchoRef.current = normalized
      localMessageSequenceRef.current += 1
      dispatch({
        type: 'local_text_sent',
        id: `local-user-${localMessageSequenceRef.current}`,
        text: normalized,
      })
      return true
    },
    [state.sessionId],
  )

  return {
    ...state,
    summary,
    summaryLoading,
    microphoneState,
    setMode,
    sendText,
    retryMicrophone: startMicrophone,
    clearError: () => dispatch({ type: 'clear_error' }),
  }
}
