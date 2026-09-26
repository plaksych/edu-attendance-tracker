import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MODEL_BYTES, MODEL_SHA256 } from '../src/lib/browserRecognitionCore'

describe('dedicated worker execution contract (mock session, no real inference)', () => {
  let scope: { onmessage: (event: { data: object }) => Promise<void>; postMessage: ReturnType<typeof vi.fn>; ort: object }
  let session: { inputNames: string[]; outputNames: string[]; run: ReturnType<typeof vi.fn>; release: ReturnType<typeof vi.fn> }
  let create: ReturnType<typeof vi.fn>
  let inputDispose: ReturnType<typeof vi.fn>
  let outputDispose: ReturnType<typeof vi.fn>
  let context: { fillStyle: string; fillRect: ReturnType<typeof vi.fn>; drawImage: ReturnType<typeof vi.fn>; getImageData: ReturnType<typeof vi.fn> }
  const init = () => scope.onmessage({ data: { id: 1, type: 'init', baseUrl: 'https://example.test/edu-attendance-tracker/' } })

  beforeEach(async () => {
    vi.resetModules()
    inputDispose = vi.fn()
    outputDispose = vi.fn()
    session = {
      inputNames: ['images'], outputNames: ['output0'], release: vi.fn(async () => undefined),
      run: vi.fn(async () => ({ output0: { data: new Float32Array(84 * 8400), dims: [1, 84, 8400], dispose: outputDispose } })),
    }
    create = vi.fn(async () => session)
    scope = {
      onmessage: async () => undefined, postMessage: vi.fn(),
      ort: { env: { versions: { common: '1.22.0' }, wasm: {} }, InferenceSession: { create }, Tensor: class { dispose = inputDispose } },
    }
    context = { fillStyle: '', fillRect: vi.fn(), drawImage: vi.fn(), getImageData: vi.fn(() => ({ data: new Uint8ClampedArray(640 * 640 * 4) })) }
    vi.stubGlobal('self', scope)
    vi.stubGlobal('OffscreenCanvas', class { width = 640; height = 640; getContext() { return context } })
    vi.stubGlobal('crypto', { subtle: { digest: vi.fn(async () => Uint8Array.from(MODEL_SHA256.match(/../g)!, (pair) => parseInt(pair, 16)).buffer) } })
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, arrayBuffer: async () => new ArrayBuffer(MODEL_BYTES) })))
    await import('../src/workers/browserRecognition.worker')
  })
  afterEach(() => vi.unstubAllGlobals())

  it('verifies model before session creation, configures one WASM thread and base path', async () => {
    await init()
    expect(String(vi.mocked(fetch).mock.calls[0][0])).toBe('https://example.test/edu-attendance-tracker/models/yolov8n.onnx')
    expect(create).toHaveBeenCalledWith(expect.any(Uint8Array), { executionProviders: ['wasm'], graphOptimizationLevel: 'all' })
    expect(scope.ort).toMatchObject({ env: { wasm: { numThreads: 1, proxy: false, wasmPaths: 'https://example.test/edu-attendance-tracker/ort/' } } })
    expect(scope.postMessage).toHaveBeenLastCalledWith({ id: 1 })
  })

  it('rejects corrupt hash before running any model', async () => {
    vi.mocked(crypto.subtle.digest).mockResolvedValue(new ArrayBuffer(32))
    await init()
    expect(create).not.toHaveBeenCalled()
    expect(scope.postMessage).toHaveBeenLastCalledWith({ id: 1, error: expect.stringContaining('сумма') })
  })

  it('releases a session with the wrong input/output contract', async () => {
    session.outputNames = ['unsupported']
    await init()
    expect(session.release).toHaveBeenCalledOnce()
    expect(scope.postMessage).toHaveBeenLastCalledWith({ id: 1, error: expect.stringContaining('manifest') })
  })

  it('uses RGB114 letterbox, calls session.run, disposes tensors/bitmap and labels an empty result', async () => {
    await init()
    const bitmap = { width: 1920, height: 1080, close: vi.fn() }
    await scope.onmessage({ data: { id: 2, type: 'detect', bitmap, width: 1920, height: 1080, threshold: 0.35 } })
    expect(context.fillStyle).toBe('rgb(114, 114, 114)')
    expect(context.drawImage).toHaveBeenCalledWith(bitmap, 0, 140, 640, 360)
    expect(session.run).toHaveBeenCalledWith({ images: expect.any(Object) })
    expect(inputDispose).toHaveBeenCalledOnce()
    expect(outputDispose).toHaveBeenCalledOnce()
    expect(bitmap.close).toHaveBeenCalledOnce()
    expect(scope.postMessage).toHaveBeenLastCalledWith({ id: 2, result: expect.objectContaining({ boxes: [], averageConfidence: null, provenance: 'browser_inference', modelSha256: MODEL_SHA256, sourceWidth: 1920, sourceHeight: 1080 }) })
  })

  it('disposes input and bitmap and releases session when run rejects', async () => {
    await init()
    session.run.mockRejectedValue(new Error('WASM failed'))
    const bitmap = { width: 640, height: 640, close: vi.fn() }
    await scope.onmessage({ data: { id: 2, type: 'detect', bitmap, width: 640, height: 640, threshold: 0.35 } })
    expect(inputDispose).toHaveBeenCalledOnce()
    expect(bitmap.close).toHaveBeenCalledOnce()
    expect(session.release).toHaveBeenCalledOnce()
    expect(scope.postMessage).toHaveBeenLastCalledWith({ id: 2, error: 'WASM failed' })
  })

  it('closes bitmap on dimension mismatch before inference', async () => {
    await init()
    const bitmap = { width: 20, height: 20, close: vi.fn() }
    await scope.onmessage({ data: { id: 2, type: 'detect', bitmap, width: 640, height: 640, threshold: 0.35 } })
    expect(session.run).not.toHaveBeenCalled()
    expect(bitmap.close).toHaveBeenCalledOnce()
  })
})
