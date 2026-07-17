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
  Tensor: new (type: string, data: Float32Array, dims: readonly number[]) => unknown
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

let recognizerPromise: Promise<BrowserRecognizer> | null = null

export class BrowserRecognizer {
  constructor(private readonly runtime: RuntimeApi, private readonly session: RuntimeSession) {}

  async detect(
    source: CanvasImageSource,
    sourceWidth: number,
    sourceHeight: number,
    confidenceThreshold: number,
  ): Promise<BrowserRecognitionResult> {
    if (sourceWidth <= 0 || sourceHeight <= 0) {
      throw new Error('Не удалось определить размер кадра')
    }

    const startedAt = performance.now()
    const { input, scale, paddingX, paddingY } = createInput(source, sourceWidth, sourceHeight)
    const inputName = this.session.inputNames[0]
    if (!inputName) throw new Error('У модели не определён входной тензор')

    const outputs = await this.session.run({
      [inputName]: new this.runtime.Tensor('float32', input, [1, 3, INPUT_SIZE, INPUT_SIZE]),
    })
    const outputName = this.session.outputNames[0] ?? Object.keys(outputs)[0]
    const output = outputName ? outputs[outputName] : undefined
    if (!output) throw new Error('Модель не вернула результаты')

    const boxes = decodePeople(
      output,
      confidenceThreshold,
      sourceWidth,
      sourceHeight,
      scale,
      paddingX,
      paddingY,
    )
    const elapsedMs = performance.now() - startedAt
    return {
      boxes,
      averageConfidence: boxes.length
        ? boxes.reduce((sum, box) => sum + box.confidence, 0) / boxes.length
        : null,
      elapsedMs,
    }
  }
}

export function getBrowserRecognizer(): Promise<BrowserRecognizer> {
  if (!recognizerPromise) recognizerPromise = createRecognizer()
  return recognizerPromise
}

async function createRecognizer(): Promise<BrowserRecognizer> {
  const runtime = window.ort
  if (!runtime) {
    throw new Error('Средство локального распознавания не загрузилось. Обновите страницу.')
  }
  runtime.env.wasm.wasmPaths = `${import.meta.env.BASE_URL}ort/`
  runtime.env.wasm.numThreads = 1
  const session = await runtime.InferenceSession.create(
    `${import.meta.env.BASE_URL}models/yolov8n.onnx`,
    {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all',
    },
  )
  return new BrowserRecognizer(runtime, session)
}

function createInput(source: CanvasImageSource, sourceWidth: number, sourceHeight: number) {
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
  context.fillStyle = '#000000'
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
  confidenceThreshold: number,
  sourceWidth: number,
  sourceHeight: number,
  scale: number,
  paddingX: number,
  paddingY: number,
): BrowserDetection[] {
  const [, firstDimension, secondDimension] = output.dims
  const channelsFirst = firstDimension === 84
  const anchors = channelsFirst ? secondDimension : firstDimension
  const channels = channelsFirst ? firstDimension : secondDimension
  if (channels < PERSON_CLASS_INDEX + 1 || !anchors) {
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
    if (confidence < confidenceThreshold) continue

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
