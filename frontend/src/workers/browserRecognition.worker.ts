import {
  decodePeople, INPUT_SIZE, letterboxGeometry, MODEL_BYTES, MODEL_ID, MODEL_SHA256,
  NMS_IOU_THRESHOLD, pixelsToInput, RUNTIME_VERSION, validateDimensions, validateThreshold,
  type BrowserRecognitionResult, type RuntimeTensor,
} from '../lib/browserRecognitionCore'

interface Tensor extends RuntimeTensor { dispose(): void }
interface Session {
  inputNames: readonly string[]
  outputNames: readonly string[]
  run(feeds: Record<string, Tensor>): Promise<Record<string, Tensor>>
  release(): Promise<void>
}
interface Runtime {
  env: { wasm: { wasmPaths: string; numThreads: number; proxy: boolean }; versions: { common: string } }
  Tensor: new (type: string, input: Float32Array, dims: number[]) => Tensor
  InferenceSession: { create(bytes: Uint8Array, options: object): Promise<Session> }
}
type Request = { id: number; type: 'init'; baseUrl: string } | {
  id: number; type: 'detect'; bitmap: ImageBitmap; width: number; height: number; threshold: number
}
const scope = self as unknown as { ort: Runtime; onmessage: ((event: MessageEvent<Request>) => void) | null; postMessage(message: object): void }
let session: Session | undefined
let busy = false

scope.onmessage = async ({ data }) => {
  if (busy) {
    if (data.type === 'detect') data.bitmap.close()
    scope.postMessage({ id: data.id, error: 'Поток распознавания занят' })
    return
  }
  busy = true
  try {
    if (data.type === 'init') {
      const runtime = scope.ort
      if (!runtime || runtime.env.versions.common !== RUNTIME_VERSION) throw new Error('Несовместимая версия ONNX Runtime')
      if (typeof OffscreenCanvas === 'undefined' || !crypto.subtle) throw new Error('Нужны OffscreenCanvas и защищённое соединение HTTPS')
      runtime.env.wasm.wasmPaths = new URL('ort/', data.baseUrl).href
      runtime.env.wasm.numThreads = 1
      runtime.env.wasm.proxy = false
      const response = await fetch(new URL('models/yolov8n.onnx', data.baseUrl))
      if (!response.ok) throw new Error(`Не удалось загрузить модель (HTTP ${response.status})`)
      const bytes = await response.arrayBuffer()
      if (bytes.byteLength !== MODEL_BYTES) throw new Error('Размер модели не совпадает с manifest')
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (value) => value.toString(16).padStart(2, '0')).join('')
      if (hash !== MODEL_SHA256) throw new Error('Контрольная сумма модели не совпадает с manifest')
      session = await runtime.InferenceSession.create(new Uint8Array(bytes), { executionProviders: ['wasm'], graphOptimizationLevel: 'all' })
      if (session.inputNames.length !== 1 || session.inputNames[0] !== 'images' || session.outputNames.length !== 1 || session.outputNames[0] !== 'output0') {
        throw new Error('Входы/выходы модели не совпадают с manifest')
      }
      scope.postMessage({ id: data.id })
    } else {
      scope.postMessage({ id: data.id, result: await detect(data) })
    }
  } catch (error) {
    await session?.release().catch(() => undefined)
    session = undefined
    scope.postMessage({ id: data.id, error: error instanceof Error ? error.message : String(error) })
  } finally { busy = false }
}

async function detect(data: Extract<Request, { type: 'detect' }>): Promise<BrowserRecognitionResult> {
  let input: Tensor | undefined
  let outputs: Record<string, Tensor> | undefined
  let canvas: OffscreenCanvas | undefined
  const startedAt = performance.now()
  try {
    if (!session) throw new Error('Модель не загружена')
    validateDimensions(data.width, data.height)
    validateThreshold(data.threshold)
    if (data.bitmap.width !== data.width || data.bitmap.height !== data.height) throw new Error('Размер декодированного кадра изменился')
    const geometry = letterboxGeometry(data.width, data.height)
    canvas = new OffscreenCanvas(INPUT_SIZE, INPUT_SIZE)
    const context = canvas.getContext('2d', { willReadFrequently: true })
    if (!context) throw new Error('Canvas недоступен в потоке распознавания')
    context.fillStyle = 'rgb(114, 114, 114)'
    context.fillRect(0, 0, INPUT_SIZE, INPUT_SIZE)
    context.drawImage(data.bitmap, geometry.paddingX, geometry.paddingY, geometry.resizedWidth, geometry.resizedHeight)
    input = new scope.ort.Tensor('float32', pixelsToInput(context.getImageData(0, 0, INPUT_SIZE, INPUT_SIZE).data), [1, 3, INPUT_SIZE, INPUT_SIZE])
    outputs = await session.run({ images: input })
    if (!outputs.output0) throw new Error('Модель не вернула output0')
    const boxes = decodePeople(outputs.output0, data.threshold, data.width, data.height)
    return {
      boxes,
      averageConfidence: boxes.length ? boxes.reduce((sum, box) => sum + box.confidence, 0) / boxes.length : null,
      elapsedMs: performance.now() - startedAt,
      provenance: 'browser_inference', model: MODEL_ID, modelSha256: MODEL_SHA256,
      runtime: `onnxruntime-web ${RUNTIME_VERSION} / wasm`, confidenceThreshold: data.threshold,
      nmsIouThreshold: NMS_IOU_THRESHOLD, processedAt: new Date().toISOString(),
      sourceWidth: data.width, sourceHeight: data.height,
    }
  } finally {
    data.bitmap.close()
    input?.dispose()
    if (outputs) for (const tensor of new Set(Object.values(outputs))) tensor.dispose()
    if (canvas) { canvas.width = 0; canvas.height = 0 }
  }
}
