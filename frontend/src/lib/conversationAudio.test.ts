import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  decodePcm16,
  encodePcm16,
  MicrophonePcm16Capture,
  Pcm16PlaybackQueue,
  resampleAndEncodePcm16,
  resampleMono,
} from './conversationAudio'

afterEach(() => vi.unstubAllGlobals())

describe('conversation audio transforms', () => {
  it('resamples mono microphone input to 16 kHz', () => {
    const input = new Float32Array(48)
    input.fill(0.25)
    const output = resampleMono(input, 48_000, 16_000)
    expect(output).toHaveLength(16)
    expect(output.every((sample) => sample === 0.25)).toBe(true)
  })

  it('encodes and decodes little-endian PCM16', () => {
    const encoded = encodePcm16(new Float32Array([1, -1, 0]))
    const view = new DataView(encoded)
    expect(view.getInt16(0, true)).toBe(32_767)
    expect(view.getInt16(2, true)).toBe(-32_768)
    expect(Array.from(decodePcm16(encoded))).toEqual([1, -1, 0])
  })

  it('produces one 16-bit sample for each resampled microphone sample', () => {
    const encoded = resampleAndEncodePcm16(new Float32Array(48), 48_000, 16_000)
    expect(encoded.byteLength).toBe(32)
  })

  it('requests the microphone only when capture starts and stops every track on cleanup', async () => {
    const stop = vi.fn()
    const getUserMedia = vi.fn(async () => ({ getTracks: () => [{ stop }] }))
    const disconnect = vi.fn()
    const context = {
      state: 'running',
      destination: {},
      resume: vi.fn(async () => undefined),
      close: vi.fn(async () => undefined),
      createMediaStreamSource: vi.fn(() => ({ connect: vi.fn(), disconnect })),
      createScriptProcessor: vi.fn(() => ({ onaudioprocess: null, connect: vi.fn(), disconnect })),
      createGain: vi.fn(() => ({ gain: { value: 1 }, connect: vi.fn(), disconnect })),
    }
    vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
    vi.stubGlobal('AudioContext', function AudioContextMock() {
      return context
    })

    const capture = new MicrophonePcm16Capture()
    expect(getUserMedia).not.toHaveBeenCalled()
    await capture.start(vi.fn())
    expect(getUserMedia).toHaveBeenCalledOnce()
    capture.stop()
    expect(stop).toHaveBeenCalledOnce()
    expect(context.close).toHaveBeenCalledOnce()
  })

  it('stops every queued source when playback is interrupted', async () => {
    const stop = vi.fn()
    const disconnect = vi.fn()
    const source = {
      buffer: null,
      onended: null,
      connect: vi.fn(),
      disconnect,
      start: vi.fn(),
      stop,
    }
    const context = {
      state: 'running',
      currentTime: 0,
      destination: {},
      createBuffer: vi.fn(() => ({
        duration: 0.1,
        copyToChannel: vi.fn(),
      })),
      createBufferSource: vi.fn(() => source),
      close: vi.fn(async () => undefined),
    }
    vi.stubGlobal('AudioContext', function AudioContextMock() {
      return context
    })

    const playback = new Pcm16PlaybackQueue()
    await playback.enqueue(new ArrayBuffer(4), 24_000)
    playback.clear()
    expect(stop).toHaveBeenCalledOnce()
    expect(disconnect).toHaveBeenCalledOnce()
  })
})
