import { isCompleteInTile, mergeDetections, planTiles, validateFrame, type Candidate } from './browserRecognitionTiling'

export interface BrowserDetection {
  x: number
  y: number
  width: number
  height: number
  confidence: number
}

export interface BrowserRecognitionResult {
  boxes: BrowserDetection[]
  averageConfidence: number | null
  elapsedMs: number
}

interface RuntimeTensor {
  data: Float32Array
  dims: readonly number[]
  dispose?: () => void
}

interface RuntimeSession {
  inputNames: string[]
  outputNames: string[]
  run(feeds: Record<string, unknown>): Promise<Record<string, RuntimeTensor>>
}

interface RuntimeApi {
  env: {
    wasm: {
      wasmPaths: string
      numThreads: number
    }
  }
  Tensor: new (type: string, data: Float32Array, dims: readonly number[]) => { dispose?: () => void }
  InferenceSession: {
    create(path: string, options: Record<string, unknown>): Promise<RuntimeSession>
  }
}

declare global {
  interface Window {
    ort?: RuntimeApi
  }
}

const INPUT_SIZE = 640
const PERSON_CLASS_INDEX = 4
const NMS_IOU_THRESHOLD = 0.45

const MODELS = {
  coco: { filename: 'yolov8n.onnx', outputChannels: 84, paddingColor: '#000000' },
  classroom: { filename: 'yolov8n-classroom.onnx', outputChannels: 5, paddingColor: '#727272' },
} as const

export type BrowserRecognitionModel = keyof typeof MODELS

type ModelConfig = (typeof MODELS)[BrowserRecognitionModel]

const recognizerPromises = new Map<BrowserRecognitionModel, Promise<BrowserRecognizer>>()

export class BrowserRecognizer {
  private pendingInference: Promise<void> = Promise.resolve()

  constructor(
    private readonly runtime: RuntimeApi,
    private readonly session: RuntimeSession,
    private readonly model: ModelConfig,
  ) {}

  async detect(
    source: CanvasImageSource,
    sourceWidth: number,
    sourceHeight: number,
    confidenceThreshold: number,
    options: { detailed?: boolean; signal?: AbortSignal } = {},
  ): Promise<BrowserRecognitionResult> {
    validateFrame(sourceWidth, sourceHeight)
    if (!Number.isFinite(confidenceThreshold) || confidenceThreshold < 0.1 || confidenceThreshold > 0.9) {
      throw new Error('Порог должен быть от 0.1 до 0.9')
    }
    const startedAt = performance.now()
    options.signal?.throwIfAborted()
    const tiles = options.detailed === false ? [] : planTiles(sourceWidth, sourceHeight)
    if (tiles.length === 0) {
      const boxes = await this.detectSingle(source, sourceWidth, sourceHeight, confidenceThreshold)
      options.signal?.throwIfAborted()
      return {
        boxes,
        averageConfidence: boxes.length ? boxes.reduce((sum, box) => sum + box.confidence, 0) / boxes.length : null,
        elapsedMs: performance.now() - startedAt,
      }
    }
    // Freeze a single frame before any asynchronous inference, including video.
    const frame = document.createElement('canvas')
    frame.width = sourceWidth
    frame.height = sourceHeight
    const context = frame.getContext('2d')
    if (!context) throw new Error('Canvas недоступен в этом браузере')
    context.drawImage(source, 0, 0, sourceWidth, sourceHeight)
    const candidates: Candidate[] = (await this.detectSingle(frame, sourceWidth, sourceHeight, confidenceThreshold))
      .map((box) => ({ ...box, pass: 0 }))
    const crop = document.createElement('canvas')
    for (const [index, tile] of tiles.entries()) {
      options.signal?.throwIfAborted()
      crop.width = tile.width
      crop.height = tile.height
      const cropContext = crop.getContext('2d')
      if (!cropContext) throw new Error('Canvas недоступен в этом браузере')
      cropContext.drawImage(frame, tile.x, tile.y, tile.width, tile.height, 0, 0, tile.width, tile.height)
      const boxes = await this.detectSingle(crop, tile.width, tile.height, confidenceThreshold)
      for (const box of boxes) {
        if (isCompleteInTile(box, tile, sourceWidth, sourceHeight)) {
          candidates.push({ ...box, x: box.x + tile.x, y: box.y + tile.y, pass: index + 1 })
        }
      }
      // Let input and cancellation events run between WASM passes.
      await new Promise((resolve) => setTimeout(resolve, 0))
    }
    options.signal?.throwIfAborted()
    const boxes = mergeDetections(candidates)
    return {
      boxes,
      averageConfidence: boxes.length ? boxes.reduce((sum, box) => sum + box.confidence, 0) / boxes.length : null,
      elapsedMs: performance.now() - startedAt,
    }
  }

  private async detectSingle(
    source: CanvasImageSource, sourceWidth: number, sourceHeight: number, confidenceThreshold: number,
  ): Promise<BrowserDetection[]> {
    const { input, scale, paddingX, paddingY } = createInput(source, sourceWidth, sourceHeight, this.model.paddingColor)
    const inputName = this.session.inputNames[0]
    if (!inputName) throw new Error('У модели не определён входной тензор')

    const tensor = new this.runtime.Tensor('float32', input, [1, 3, INPUT_SIZE, INPUT_SIZE])
    let outputs: Record<string, RuntimeTensor> = {}
    const previous = this.pendingInference
    let release!: () => void
    this.pendingInference = new Promise<void>((resolve) => { release = resolve })
    await previous
    try {
      outputs = await this.session.run({ [inputName]: tensor })
      const outputName = this.session.outputNames[0] ?? Object.keys(outputs)[0]
      const output = outputName ? outputs[outputName] : undefined
      if (!output) throw new Error('Модель не вернула результаты')

      return decodePeople(
        output,
        this.model.outputChannels,
        confidenceThreshold,
        sourceWidth,
        sourceHeight,
        scale,
        paddingX,
        paddingY,
      )
    } finally {
      try {
        tensor.dispose?.()
        for (const output of Object.values(outputs)) output.dispose?.()
      } finally {
        release()
      }
    }
  }
}

export function getBrowserRecognizer(model: BrowserRecognitionModel = 'coco'): Promise<BrowserRecognizer> {
  const cached = recognizerPromises.get(model)
  if (cached) return cached

  const recognizer = createRecognizer(MODELS[model]).catch((error: unknown) => {
    recognizerPromises.delete(model)
    throw error
  })
  recognizerPromises.set(model, recognizer)
  return recognizer
}

async function createRecognizer(model: ModelConfig): Promise<BrowserRecognizer> {
  const runtime = window.ort
  if (!runtime) {
    throw new Error('Средство локального распознавания не загрузилось. Обновите страницу.')
  }
  runtime.env.wasm.wasmPaths = `${import.meta.env.BASE_URL}ort/`
  runtime.env.wasm.numThreads = 1
  const session = await runtime.InferenceSession.create(
    `${import.meta.env.BASE_URL}models/${model.filename}`,
    {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all',
    },
  )
  return new BrowserRecognizer(runtime, session, model)
}

function createInput(
  source: CanvasImageSource,
  sourceWidth: number,
  sourceHeight: number,
  paddingColor: string,
) {
  const canvas = document.createElement('canvas')
  canvas.width = INPUT_SIZE
  canvas.height = INPUT_SIZE
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) throw new Error('Canvas недоступен в этом браузере')

  const scale = Math.min(INPUT_SIZE / sourceWidth, INPUT_SIZE / sourceHeight)
  const resizedWidth = Math.round(sourceWidth * scale)
  const resizedHeight = Math.round(sourceHeight * scale)
  const paddingX = Math.floor((INPUT_SIZE - resizedWidth) / 2)
  const paddingY = Math.floor((INPUT_SIZE - resizedHeight) / 2)
  context.fillStyle = paddingColor
  context.fillRect(0, 0, INPUT_SIZE, INPUT_SIZE)
  context.drawImage(source, 0, 0, sourceWidth, sourceHeight, paddingX, paddingY, resizedWidth, resizedHeight)

  const pixels = context.getImageData(0, 0, INPUT_SIZE, INPUT_SIZE).data
  const channelSize = INPUT_SIZE * INPUT_SIZE
  const input = new Float32Array(channelSize * 3)
  for (let index = 0; index < channelSize; index += 1) {
    const pixel = index * 4
    input[index] = pixels[pixel] / 255
    input[channelSize + index] = pixels[pixel + 1] / 255
    input[channelSize * 2 + index] = pixels[pixel + 2] / 255
  }
  return { input, scale, paddingX, paddingY }
}

function decodePeople(
  output: RuntimeTensor,
  channels: number,
  confidenceThreshold: number,
  sourceWidth: number,
  sourceHeight: number,
  scale: number,
  paddingX: number,
  paddingY: number,
): BrowserDetection[] {
  const [batch, firstDimension, secondDimension] = output.dims
  const channelsFirst = firstDimension === channels
  const anchors = channelsFirst ? secondDimension : firstDimension
  if (
    output.dims.length !== 3 || batch !== 1 || !anchors ||
    (!channelsFirst && secondDimension !== channels) || output.data.length !== channels * anchors
  ) {
    throw new Error('Получен неподдерживаемый формат результата модели')
  }

  const valueAt = (channel: number, anchor: number) => (
    channelsFirst
      ? output.data[channel * anchors + anchor]
      : output.data[anchor * channels + channel]
  )
  const candidates: BrowserDetection[] = []
  for (let anchor = 0; anchor < anchors; anchor += 1) {
    const confidence = valueAt(PERSON_CLASS_INDEX, anchor)
    if (!Number.isFinite(confidence) || confidence < confidenceThreshold) continue
    // COCO assigns each proposal to its strongest class before class filtering.
    let personIsBest = true
    for (let channel = PERSON_CLASS_INDEX + 1; channel < channels; channel += 1) {
      if (valueAt(channel, anchor) > confidence) { personIsBest = false; break }
    }
    if (!personIsBest) continue

    const centerX = valueAt(0, anchor)
    const centerY = valueAt(1, anchor)
    const width = valueAt(2, anchor)
    const height = valueAt(3, anchor)
    const left = (centerX - width / 2 - paddingX) / scale
    const top = (centerY - height / 2 - paddingY) / scale
    const right = (centerX + width / 2 - paddingX) / scale
    const bottom = (centerY + height / 2 - paddingY) / scale
    const clippedLeft = clamp(left, 0, sourceWidth)
    const clippedTop = clamp(top, 0, sourceHeight)
    const clippedRight = clamp(right, 0, sourceWidth)
    const clippedBottom = clamp(bottom, 0, sourceHeight)
    if (clippedRight - clippedLeft < 2 || clippedBottom - clippedTop < 2) continue
    candidates.push({
      x: clippedLeft,
      y: clippedTop,
      width: clippedRight - clippedLeft,
      height: clippedBottom - clippedTop,
      confidence,
    })
  }
  return nonMaximumSuppression(candidates)
}

function nonMaximumSuppression(candidates: BrowserDetection[]): BrowserDetection[] {
  const ordered = [...candidates].sort((first, second) => second.confidence - first.confidence)
  const kept: BrowserDetection[] = []
  for (const candidate of ordered) {
    if (kept.every((existing) => intersectionOverUnion(existing, candidate) < NMS_IOU_THRESHOLD)) {
      kept.push(candidate)
    }
  }
  return kept
}

function intersectionOverUnion(first: BrowserDetection, second: BrowserDetection): number {
  const left = Math.max(first.x, second.x)
  const top = Math.max(first.y, second.y)
  const right = Math.min(first.x + first.width, second.x + second.width)
  const bottom = Math.min(first.y + first.height, second.y + second.height)
  const intersection = Math.max(0, right - left) * Math.max(0, bottom - top)
  const union = first.width * first.height + second.width * second.height - intersection
  return union > 0 ? intersection / union : 0
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum)
}
