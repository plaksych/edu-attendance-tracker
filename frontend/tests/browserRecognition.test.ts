import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  decodePeople, INPUT_SIZE, intersectionOverUnion, letterboxGeometry, MAX_IMAGE_BYTES,
  MAX_VIDEO_BYTES, MODEL_BYTES, MODEL_SHA256, nonMaximumSuppression, pixelsToInput,
  validateDimensions, validateMediaContent, validateMediaFile, validateThreshold, validateVideoDuration,
} from '../src/lib/browserRecognitionCore'
import { BrowserRecognizer, createRecognizerCache } from '../src/lib/browserRecognitionClient'

function tensor(transposed = false) {
  const data = new Float32Array(84 * 8400)
  return {
    data, dims: transposed ? [1, 8400, 84] : [1, 84, 8400],
    set(anchor: number, values: number[]) {
      values.forEach((value, channel) => { data[transposed ? anchor * 84 + channel : channel * 8400 + anchor] = value })
    },
  }
}

describe('browser detector math', () => {
  it.each([false, true])('decodes COCO person score offset 4, transpose=%s', (transposed) => {
    const output = tensor(transposed)
    output.set(0, [320, 320, 64, 64, 0.8])
    output.set(1, [100, 100, 30, 30, 0.1, 0.95])
    const boxes = decodePeople(output, 0.35, 640, 640)
    expect(boxes).toHaveLength(1)
    expect(boxes[0]).toMatchObject({ x: 288, y: 288, width: 64, height: 64 })
    expect(boxes[0].confidence).toBeCloseTo(0.8)
  })

  it.each([[1920, 1080], [1080, 1920], [333, 1000], [1000, 333], [8192, 1]])('inverts rounded letterbox %sx%s and clips', (width, height) => {
    const geometry = letterboxGeometry(width, height)
    const output = tensor()
    output.set(0, [geometry.paddingX + geometry.resizedWidth / 2, geometry.paddingY + geometry.resizedHeight / 2, geometry.resizedWidth, geometry.resizedHeight, 0.9])
    expect(decodePeople(output, 0.35, width, height)[0]).toMatchObject({ x: 0, y: 0, width, height })
    output.set(0, [320, 320, 2000, 2000, 0.9])
    expect(decodePeople(output, 0.35, width, height)[0]).toMatchObject({ x: 0, y: 0, width, height })
  })

  it('drops degenerate and wholly padded boxes, keeps sub-two-pixel boxes', () => {
    const output = tensor()
    output.set(0, [320, 30, 20, 20, 0.9])
    output.set(1, [320, 320, 0, 20, 0.9])
    output.set(2, [320, 320, -20, 20, 0.9])
    output.set(3, [320, 320, 0.5, 0.5, 0.9])
    expect(decodePeople(output, 0.35, 1920, 1080)).toHaveLength(1)
  })

  it('rejects wrong ranks, batch, objectness/NMS/ambiguous layouts and length/type mismatch', () => {
    for (const dims of [[84, 8400], [2, 84, 8400], [1, 85, 8400], [1, 6, 8400], [1, 84, 84], [1, 84, 0], [1, 84, NaN]]) {
      expect(() => decodePeople({ ...tensor(), dims }, 0.35, 640, 640)).toThrow(/выход/)
    }
    expect(() => decodePeople({ data: new Float32Array(1), dims: [1, 84, 8400] }, 0.35, 640, 640)).toThrow()
    expect(() => decodePeople({ data: new Float64Array(84 * 8400) as unknown as Float32Array, dims: [1, 84, 8400] }, 0.35, 640, 640)).toThrow()
  })

  it.each([NaN, Infinity, -Infinity])('rejects nonfinite values anywhere in tensor: %s', (value) => {
    const output = tensor()
    output.data[output.data.length - 1] = value
    expect(() => decodePeople(output, 0.35, 640, 640)).toThrow(/нечисловые/)
  })

  it.each([-0.1, 1.1, -0.000002, 1.000002])('rejects invalid probability: %s', (value) => {
    const output = tensor()
    output.data[4 * 8400] = value
    expect(() => decodePeople(output, 0.35, 640, 640)).toThrow(/уверенность/)
  })

  it('accepts only bounded float32 sigmoid roundoff and clamps selected scores', () => {
    const output = tensor()
    output.set(0, [320, 320, 64, 64, 1 + 2 ** -23, 0, 0, -(2 ** -24)])
    output.set(1, [100, 100, 64, 64, -(2 ** -24)])
    const boxes = decodePeople(output, 0.35, 640, 640)
    expect(boxes).toHaveLength(1)
    expect(boxes[0].confidence).toBe(1)
  })

  it('returns no people, not an invented count, for empty detections', () => {
    expect(decodePeople(tensor(), 0.35, 640, 640)).toEqual([])
  })

  it('does deterministic descending-confidence NMS without mutating input', () => {
    const a = { x: 0, y: 0, width: 100, height: 100, confidence: 0.7 }
    const b = { ...a, x: 5, confidence: 0.9 }
    const c = { ...a, x: 200, confidence: 0.8 }
    const input = [a, b, c]
    expect(nonMaximumSuppression(input)).toEqual([b, c])
    expect(input).toEqual([a, b, c])
    expect(intersectionOverUnion(a, a)).toBe(1)
    expect(intersectionOverUnion(a, c)).toBe(0)
    expect(intersectionOverUnion({ ...a, width: 0 }, { ...a, width: 0 })).toBe(0)
  })

  it('normalizes RGB into NCHW, including letterbox value 114/255', () => {
    const pixels = new Uint8ClampedArray(INPUT_SIZE * INPUT_SIZE * 4).fill(114)
    pixels.set([255, 0, 128, 255])
    const input = pixelsToInput(pixels)
    expect(input[0]).toBe(1)
    expect(input[640 * 640]).toBe(0)
    expect(input[2 * 640 * 640]).toBeCloseTo(128 / 255)
    expect(input[1]).toBeCloseTo(114 / 255)
    expect(() => pixelsToInput(new Uint8ClampedArray(4))).toThrow()
  })
})

describe('browser media validation', () => {
  it('checks MIME, empty files and exact byte limits', () => {
    expect(validateMediaFile({ type: 'image/png', size: MAX_IMAGE_BYTES })).toBe('image')
    expect(validateMediaFile({ type: 'video/mp4', size: MAX_VIDEO_BYTES })).toBe('video')
    for (const file of [{ type: 'image/png', size: 0 }, { type: 'image/svg+xml', size: 10 }, { type: '', size: 10 }, { type: 'image/png', size: MAX_IMAGE_BYTES + 1 }, { type: 'video/mp4', size: MAX_VIDEO_BYTES + 1 }]) {
      expect(() => validateMediaFile(file)).toThrow()
    }
  })
  it('checks actual file signature, not just declared MIME', async () => {
    await expect(validateMediaContent(new File(['not a png'], 'bad.png', { type: 'image/png' }))).rejects.toThrow(/Содержимое/)
    await expect(validateMediaContent(new File([new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10])], 'image.png', { type: 'image/png' }))).resolves.toBe('image')
  })
  it('checks dimensions, duration and thresholds for finite bounded values', () => {
    validateDimensions(4000, 4000)
    for (const [width, height] of [[0, 1], [-1, 1], [NaN, 10], [10, Infinity], [1.2, 3], [4001, 4000], [8193, 1]]) expect(() => validateDimensions(width, height)).toThrow()
    for (const duration of [0, -1, Infinity, NaN, 601]) expect(() => validateVideoDuration(duration)).toThrow()
    validateVideoDuration(600)
    for (const threshold of [NaN, Infinity, -1, 0, 0.09, 0.91]) expect(() => validateThreshold(threshold)).toThrow()
    validateThreshold(0.1)
    validateThreshold(0.9)
  })
})

class FakeWorker {
  onmessage: Worker['onmessage'] = null
  onerror: Worker['onerror'] = null
  onmessageerror: Worker['onmessageerror'] = null
  postMessage = vi.fn()
  terminate = vi.fn()
  reply(data: object) { this.onmessage?.call(this as unknown as Worker, { data } as MessageEvent) }
}

describe('browser worker lifecycle (mock transport, no inference)', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
  const config = { baseUrl: 'https://example.test/edu-attendance-tracker/', moduleUrl: 'https://example.test/assets/worker.js' }

  it('is lazy, deduplicates init and retries rejected initialization', async () => {
    const workers: FakeWorker[] = []
    const cache = createRecognizerCache(() => {
      const worker = new FakeWorker()
      workers.push(worker)
      return new BrowserRecognizer(worker, config)
    })
    expect(workers).toHaveLength(0)
    const first = cache.get()
    expect(cache.get()).toBe(first)
    workers[0].reply({ id: 1, error: 'model unavailable' })
    await expect(first).rejects.toThrow('model unavailable')
    expect(workers[0].terminate).toHaveBeenCalledOnce()
    const retry = cache.get()
    expect(workers).toHaveLength(2)
    workers[1].reply({ id: 1 })
    await expect(retry).resolves.toBeInstanceOf(BrowserRecognizer)
    cache.release()
    expect(workers[1].terminate).toHaveBeenCalledOnce()
  })

  it('old cancelled initialization cannot clear a newer attempt', async () => {
    const workers: FakeWorker[] = []
    const cache = createRecognizerCache(() => {
      const worker = new FakeWorker(); workers.push(worker)
      return new BrowserRecognizer(worker, config)
    })
    const old = cache.get()
    cache.release()
    const next = cache.get()
    await expect(old).rejects.toMatchObject({ name: 'AbortError' })
    expect(cache.get()).toBe(next)
    workers[1].reply({ id: 1 })
    await next
    cache.release()
  })

  it('rejects pending operations on worker error and timeout', async () => {
    vi.useFakeTimers()
    const worker = new FakeWorker()
    const client = new BrowserRecognizer(worker, config)
    const rejected = expect(client.ready).rejects.toThrow(/время/)
    await vi.advanceTimersByTimeAsync(120_000)
    await rejected
    expect(worker.terminate).toHaveBeenCalledOnce()
    const nextWorker = new FakeWorker()
    const nextClient = new BrowserRecognizer(nextWorker, config)
    nextWorker.onerror?.call(nextWorker as unknown as Worker, {} as ErrorEvent)
    await expect(nextClient.ready).rejects.toThrow(/потока/)
  })

  it('closes a bitmap completed after cancellation and never posts it', async () => {
    const worker = new FakeWorker()
    const client = new BrowserRecognizer(worker, config)
    worker.reply({ id: 1 })
    await client.ready
    let resolveBitmap!: (bitmap: object) => void
    const bitmap = { close: vi.fn() }
    vi.stubGlobal('createImageBitmap', vi.fn(() => new Promise((resolve) => { resolveBitmap = resolve })))
    const controller = new AbortController()
    const result = client.detect({} as CanvasImageSource, 640, 640, 0.35, controller.signal)
    await Promise.resolve()
    controller.abort()
    resolveBitmap(bitmap)
    await expect(result).rejects.toMatchObject({ name: 'AbortError' })
    expect(bitmap.close).toHaveBeenCalledOnce()
    expect(worker.postMessage).toHaveBeenCalledTimes(1)
  })

  it('prevents overlapping frames, transfers ownership and rejects in-flight cancellation', async () => {
    const worker = new FakeWorker()
    const client = new BrowserRecognizer(worker, config)
    worker.reply({ id: 1 })
    await client.ready
    const bitmap = { close: vi.fn() }
    vi.stubGlobal('createImageBitmap', vi.fn(async () => bitmap))
    const first = client.detect({} as CanvasImageSource, 640, 640, 0.35)
    await expect(client.detect({} as CanvasImageSource, 640, 640, 0.35)).rejects.toThrow(/Предыдущий/)
    await Promise.resolve()
    expect(worker.postMessage).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'detect', bitmap }), [bitmap])
    client.dispose()
    await expect(first).rejects.toMatchObject({ name: 'AbortError' })
    expect(bitmap.close).not.toHaveBeenCalled() // Transferred bitmap belongs to the terminated worker.
  })
})

describe('vendored browser model manifest', () => {
  it('pins the actual model and runtime assets without running any model', () => {
    const manifest = JSON.parse(readFileSync(new URL('../public/models/manifest.json', import.meta.url), 'utf8'))
    const model = readFileSync(new URL('../public/models/yolov8n.onnx', import.meta.url))
    expect(model.length).toBe(MODEL_BYTES)
    expect(manifest.artifact.sha256).toBe(MODEL_SHA256)
    expect(createHash('sha256').update(model).digest('hex')).toBe(MODEL_SHA256)
    for (const [path, hash] of Object.entries(manifest.runtime.assets)) {
      expect(createHash('sha256').update(readFileSync(new URL(`../public/${path}`, import.meta.url))).digest('hex')).toBe(hash)
    }
    const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')
    expect(html).not.toMatch(/<script[^>]+ort/)
  })
})
