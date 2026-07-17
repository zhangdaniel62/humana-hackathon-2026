import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { useAuth } from './auth-context'
import { getSupportRoomWebSocketUrl } from './supportApi'
import { MicrophonePcm16Capture, Pcm16PlaybackQueue } from './conversationAudio'
import {
  initialSupportRoomState,
  parseSupportServerMessage,
  supportRoomReducer,
  type SupportClientMessage,
  type SupportMessage,
  type SupportRole,
} from './supportProtocol'

export type SupportMicrophoneState = 'inactive' | 'starting' | 'listening' | 'error'

function sendJson(socket: WebSocket, message: SupportClientMessage): void {
  socket.send(JSON.stringify(message))
}

export function useSupportRoom(roomId: string | null | undefined) {
  const { user } = useAuth()
  const [state, dispatch] = useReducer(supportRoomReducer, initialSupportRoomState)
  const [microphoneState, setMicrophoneState] = useState<SupportMicrophoneState>('inactive')
  const [connectionAttempt, setConnectionAttempt] = useState(0)
  const socketRef = useRef<WebSocket | null>(null)
  const microphoneRef = useRef<MicrophonePcm16Capture | null>(null)
  const playbackRef = useRef<Pcm16PlaybackQueue | null>(null)
  const activeRef = useRef(false)
  const localSequenceRef = useRef(0)

  const ownRole: SupportRole | null =
    user?.role === 'customer' || user?.role === 'rep' ? user.role : null

  const stopMicrophone = useCallback((dispose = false) => {
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

  const sendAudio = useCallback((frame: ArrayBuffer) => {
    const socket = socketRef.current
    if (activeRef.current && socket?.readyState === WebSocket.OPEN) socket.send(frame)
  }, [])

  const disableMicrophone = useCallback(() => {
    activeRef.current = false
    const socket = socketRef.current
    if (socket?.readyState === WebSocket.OPEN) {
      sendJson(socket, { type: 'set_voice', enabled: false })
    }
    stopMicrophone()
  }, [stopMicrophone])

  const startMicrophone = useCallback(async (): Promise<boolean> => {
    const socket = socketRef.current
    const peerPresent =
      ownRole === 'customer' ? state.presence.rep : ownRole === 'rep' && state.presence.customer
    if (
      socket?.readyState !== WebSocket.OPEN ||
      !state.room ||
      state.room?.status === 'completed' ||
      !peerPresent
    ) {
      dispatch({ type: 'client_error', message: 'Wait for a representative to join before using voice.' })
      return false
    }
    setMicrophoneState('starting')
    try {
      const microphone = microphoneRef.current ?? new MicrophonePcm16Capture()
      microphoneRef.current = microphone
      await microphone.start(sendAudio, 16_000)
      if (socketRef.current !== socket || socket.readyState !== WebSocket.OPEN) {
        microphone.stop()
        setMicrophoneState('inactive')
        return false
      }
      activeRef.current = true
      sendJson(socket, { type: 'set_voice', enabled: true })
      setMicrophoneState('listening')
      return true
    } catch (error) {
      activeRef.current = false
      setMicrophoneState('error')
      dispatch({
        type: 'client_error',
        message:
          error instanceof DOMException && error.name === 'NotAllowedError'
            ? 'Microphone access was denied. Allow access and try again.'
            : error instanceof Error
              ? error.message
              : 'The microphone could not be started.',
      })
      return false
    }
  }, [ownRole, sendAudio, state.presence, state.room])

  useEffect(() => {
    if (!roomId) {
      dispatch({ type: 'room_cleared' })
      return
    }
    let mounted = true
    const socket = new WebSocket(getSupportRoomWebSocketUrl(roomId))
    socket.binaryType = 'arraybuffer'
    socketRef.current = socket
    dispatch({ type: 'room_cleared' })
    dispatch({ type: 'socket_connecting' })

    socket.onopen = () => dispatch({ type: 'socket_opened' })
    socket.onmessage = (event) => {
      if (!mounted) return
      if (typeof event.data === 'string') {
        const message = parseSupportServerMessage(event.data)
        if (message) {
          if (message.type === 'presence') {
            const peerPresent =
              ownRole === 'customer'
                ? message.presence.rep
                : ownRole === 'rep' && message.presence.customer
            if (!peerPresent && activeRef.current) disableMicrophone()
          }
          dispatch({ type: 'server_message', message })
        }
        else dispatch({ type: 'client_error', message: 'The support server sent an invalid message.' })
        return
      }
      const play = async (pcm: ArrayBuffer) => {
        if (!mounted) return
        try {
          const playback = playbackRef.current ?? new Pcm16PlaybackQueue()
          playbackRef.current = playback
          await playback.enqueue(pcm, 16_000)
        } catch {
          dispatch({ type: 'client_error', message: 'The representative audio could not be played.' })
        }
      }
      if (event.data instanceof ArrayBuffer) void play(event.data)
      else if (event.data instanceof Blob) void event.data.arrayBuffer().then(play)
    }
    socket.onerror = () => {
      if (mounted) dispatch({ type: 'client_error', message: 'The live support connection encountered an error.' })
    }
    socket.onclose = (event) => {
      if (!mounted) return
      activeRef.current = false
      stopMicrophone()
      dispatch({ type: 'socket_closed', code: event.code })
    }

    return () => {
      mounted = false
      activeRef.current = false
      socket.onopen = null
      socket.onmessage = null
      socket.onerror = null
      socket.onclose = null
      if (socket.readyState === WebSocket.OPEN) {
        sendJson(socket, { type: 'set_voice', enabled: false })
      }
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close(1000)
      }
      if (socketRef.current === socket) socketRef.current = null
      stopMicrophone(true)
    }
  }, [connectionAttempt, disableMicrophone, ownRole, roomId, stopMicrophone])

  const sendText = useCallback(
    (text: string): boolean => {
      const normalized = text.trim().slice(0, 4000)
      if (!normalized) return false
      const socket = socketRef.current
      const peerPresent =
        ownRole === 'customer' ? state.presence.rep : ownRole === 'rep' && state.presence.customer
      if (
        socket?.readyState !== WebSocket.OPEN ||
        !state.room ||
        state.room?.status === 'completed' ||
        !peerPresent ||
        !user ||
        (user.role !== 'customer' && user.role !== 'rep')
      ) {
        dispatch({ type: 'client_error', message: 'Wait for live support to connect before sending a message.' })
        return false
      }
      localSequenceRef.current += 1
      const clientMessageId =
        globalThis.crypto?.randomUUID?.() ?? `support-${Date.now()}-${localSequenceRef.current}`
      sendJson(socket, { type: 'text', client_message_id: clientMessageId, text: normalized })
      const optimistic: SupportMessage = {
        id: `local-${clientMessageId}`,
        roomId: state.room.id,
        clientMessageId,
        text: normalized,
        sender: { id: user.id, username: user.username, role: user.role },
        createdAt: new Date().toISOString(),
        delivery: 'pending',
      }
      dispatch({ type: 'local_text_sent', message: optimistic })
      return true
    },
    [ownRole, state.presence, state.room, user],
  )

  const toggleMicrophone = useCallback(async (): Promise<boolean> => {
    if (microphoneState === 'listening' || microphoneState === 'starting') {
      disableMicrophone()
      return false
    }
    return startMicrophone()
  }, [disableMicrophone, microphoneState, startMicrophone])

  const peer = useMemo(() => {
    if (!ownRole || !state.room) return null
    const role: SupportRole = ownRole === 'customer' ? 'rep' : 'customer'
    return {
      role,
      user: role === 'customer' ? state.room.customer : state.room.assignedRep,
      present: state.presence[role],
      voiceEnabled: role === 'customer' ? state.voice.customerEnabled : state.voice.repEnabled,
    }
  }, [ownRole, state.presence, state.room, state.voice])

  const ownVoiceEnabled =
    ownRole === 'customer'
      ? state.voice.customerEnabled
      : ownRole === 'rep'
        ? state.voice.repEnabled
        : false

  return {
    ...state,
    status: state.room?.status ?? null,
    peer,
    ownVoiceEnabled,
    microphoneState,
    sendText,
    toggleMicrophone,
    retryMicrophone: startMicrophone,
    retryConnection: () => setConnectionAttempt((attempt) => attempt + 1),
    clearError: () => dispatch({ type: 'clear_error' }),
  }
}
