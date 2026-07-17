const PCM16_SCALE = 0x8000
const PCM16_MAX = 0x7fff

/** Linear mono resampling, kept pure so the transport math is deterministic in tests. */
export function resampleMono(
  input: Float32Array,
  inputSampleRate: number,
  outputSampleRate: number,
): Float32Array {
  if (!Number.isFinite(inputSampleRate) || inputSampleRate <= 0) {
    throw new Error('Input sample rate must be positive')
  }
  if (!Number.isFinite(outputSampleRate) || outputSampleRate <= 0) {
    throw new Error('Output sample rate must be positive')
  }
  if (input.length === 0) return new Float32Array()
  if (inputSampleRate === outputSampleRate) return input.slice()

  const outputLength = Math.max(1, Math.round((input.length * outputSampleRate) / inputSampleRate))
  const output = new Float32Array(outputLength)
  const ratio = inputSampleRate / outputSampleRate
  for (let index = 0; index < outputLength; index += 1) {
    const sourcePosition = index * ratio
    const lowerIndex = Math.min(Math.floor(sourcePosition), input.length - 1)
    const upperIndex = Math.min(lowerIndex + 1, input.length - 1)
    const fraction = sourcePosition - lowerIndex
    output[index] = input[lowerIndex] * (1 - fraction) + input[upperIndex] * fraction
  }
  return output
}

/** Encode normalized floats as raw little-endian signed PCM16. */
export function encodePcm16(samples: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(samples.length * 2)
  const view = new DataView(buffer)
  samples.forEach((sample, index) => {
    const clamped = Math.max(-1, Math.min(1, sample))
    const integer = clamped < 0 ? Math.round(clamped * PCM16_SCALE) : Math.round(clamped * PCM16_MAX)
    view.setInt16(index * 2, integer, true)
  })
  return buffer
}

/** Decode raw little-endian signed PCM16 to normalized Web Audio samples. */
export function decodePcm16(buffer: ArrayBuffer): Float32Array {
  const sampleCount = Math.floor(buffer.byteLength / 2)
  const output = new Float32Array(sampleCount)
  const view = new DataView(buffer, 0, sampleCount * 2)
  for (let index = 0; index < sampleCount; index += 1) {
    const value = view.getInt16(index * 2, true)
    output[index] = value < 0 ? value / PCM16_SCALE : value / PCM16_MAX
  }
  return output
}

export function resampleAndEncodePcm16(
  input: Float32Array,
  inputSampleRate: number,
  outputSampleRate = 16_000,
): ArrayBuffer {
  return encodePcm16(resampleMono(input, inputSampleRate, outputSampleRate))
}

export class MicrophonePcm16Capture {
  private stream: MediaStream | null = null
  private context: AudioContext | null = null
  private source: MediaStreamAudioSourceNode | null = null
  private processor: ScriptProcessorNode | null = null
  private silentOutput: GainNode | null = null
  private generation = 0
  private startPromise: Promise<void> | null = null

  start(onFrame: (frame: ArrayBuffer) => void, outputSampleRate = 16_000): Promise<void> {
    if (this.stream) return Promise.resolve()
    if (this.startPromise) return this.startPromise
    const generation = ++this.generation
    this.startPromise = this.startInternal(generation, onFrame, outputSampleRate).finally(() => {
      this.startPromise = null
    })
    return this.startPromise
  }

  private async startInternal(
    generation: number,
    onFrame: (frame: ArrayBuffer) => void,
    outputSampleRate: number,
  ): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Microphone capture is not supported by this browser.')
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })
    if (generation !== this.generation) {
      stream.getTracks().forEach((track) => track.stop())
      return
    }

    const context = new AudioContext()
    await context.resume()
    if (generation !== this.generation) {
      stream.getTracks().forEach((track) => track.stop())
      await context.close()
      return
    }

    const source = context.createMediaStreamSource(stream)
    const processor = context.createScriptProcessor(4096, 1, 1)
    const silentOutput = context.createGain()
    silentOutput.gain.value = 0
    processor.onaudioprocess = (event) => {
      const mono = event.inputBuffer.getChannelData(0)
      const frame = resampleAndEncodePcm16(mono, event.inputBuffer.sampleRate, outputSampleRate)
      if (frame.byteLength > 0) onFrame(frame)
    }
    source.connect(processor)
    processor.connect(silentOutput)
    silentOutput.connect(context.destination)

    this.stream = stream
    this.context = context
    this.source = source
    this.processor = processor
    this.silentOutput = silentOutput
  }

  stop(): void {
    this.generation += 1
    if (this.processor) {
      this.processor.onaudioprocess = null
      this.processor.disconnect()
    }
    this.source?.disconnect()
    this.silentOutput?.disconnect()
    this.stream?.getTracks().forEach((track) => track.stop())
    if (this.context && this.context.state !== 'closed') void this.context.close()
    this.stream = null
    this.context = null
    this.source = null
    this.processor = null
    this.silentOutput = null
  }
}

/** Queue 24 kHz mono PCM16 frames without gaps, and make interruption cancellable. */
export class Pcm16PlaybackQueue {
  private context: AudioContext | null = null
  private nextStartTime = 0
  private sources = new Set<AudioBufferSourceNode>()

  async enqueue(buffer: ArrayBuffer, sampleRate = 24_000): Promise<void> {
    const samples = decodePcm16(buffer)
    if (samples.length === 0) return
    const context = this.context ?? new AudioContext()
    this.context = context
    if (context.state === 'suspended') await context.resume()

    const audioBuffer = context.createBuffer(1, samples.length, sampleRate)
    audioBuffer.copyToChannel(new Float32Array(samples), 0)
    const source = context.createBufferSource()
    source.buffer = audioBuffer
    source.connect(context.destination)
    source.onended = () => {
      source.disconnect()
      this.sources.delete(source)
    }
    const startTime = Math.max(context.currentTime, this.nextStartTime)
    source.start(startTime)
    this.nextStartTime = startTime + audioBuffer.duration
    this.sources.add(source)
  }

  clear(): void {
    for (const source of this.sources) {
      source.onended = null
      try {
        source.stop()
      } catch {
        // A source that ended between iteration and stop is already cleared.
      }
      source.disconnect()
    }
    this.sources.clear()
    this.nextStartTime = this.context?.currentTime ?? 0
  }

  dispose(): void {
    this.clear()
    if (this.context && this.context.state !== 'closed') void this.context.close()
    this.context = null
    this.nextStartTime = 0
  }
}
