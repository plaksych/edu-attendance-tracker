export const INPUT_SIZE = 640
export const MODEL_SHA256 = '353ca4ab4fa9d4e5499d3300912faa30dae49718f90be8a159ff6af09a4e66b7'
export const MODEL_BYTES = 12756454
export const MODEL_ID = 'yolov8n-coco-browser'
export const RUNTIME_VERSION = '1.22.0'
export const NMS_IOU_THRESHOLD = 0.45
// WASM SIMD sigmoid can round just outside [0, 1] (observed -2^-24).
const PROBABILITY_EPSILON = 1e-6
export const MAX_IMAGE_BYTES = 20 * 1024 * 1024
export const MAX_VIDEO_BYTES = 200 * 1024 * 1024
export const MAX_PIXELS = 16_000_000
export const MAX_DIMENSION = 8192
export const MAX_VIDEO_SECONDS = 600
export const SAMPLE_DELAY_MS = 900

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
  provenance: 'browser_inference'
  model: string
  modelSha256: string
  runtime: string
  confidenceThreshold: number
  nmsIouThreshold: number
  processedAt: string
  sourceWidth: number
  sourceHeight: number
}

export interface RuntimeTensor { data: Float32Array; dims: readonly number[] }

export function validateDimensions(width: number, height: number): void {
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width < 1 || height < 1) {
    throw new Error('Не удалось определить размер кадра')
  }
  if (width > MAX_DIMENSION || height > MAX_DIMENSION || width * height > MAX_PIXELS) {
    throw new Error('Кадр превышает лимит: 16 Мп и не более 8192 пикселей по стороне')
  }
}

export function validateThreshold(threshold: number): void {
  if (!Number.isFinite(threshold) || threshold < 0.1 || threshold > 0.9) {
    throw new Error('Порог уверенности должен быть от 0.1 до 0.9')
  }
}

export function validateMediaFile(file: Pick<File, 'type' | 'size'>): 'image' | 'video' {
  const imageTypes = ['image/jpeg', 'image/png', 'image/webp']
  const videoTypes = ['video/mp4', 'video/quicktime', 'video/webm']
  const kind = imageTypes.includes(file.type) ? 'image' : videoTypes.includes(file.type) ? 'video' : null
  if (!kind) throw new Error('Поддерживаются JPEG, PNG, WebP, MP4, MOV и WebM')
  if (!Number.isSafeInteger(file.size) || file.size <= 0) throw new Error('Файл пуст или повреждён')
  if (file.size > (kind === 'image' ? MAX_IMAGE_BYTES : MAX_VIDEO_BYTES)) {
    throw new Error(kind === 'image' ? 'Изображение больше 20 МиБ' : 'Видео больше 200 МиБ')
  }
  return kind
}

export function validateVideoDuration(duration: number): void {
  if (!Number.isFinite(duration) || duration <= 0 || duration > MAX_VIDEO_SECONDS) {
    throw new Error('Видео должно иметь конечную длительность не более 10 минут')
  }
}

export async function validateMediaContent(file: File): Promise<'image' | 'video'> {
  const kind = validateMediaFile(file)
  const bytes = new Uint8Array(await file.slice(0, 32).arrayBuffer())
  const ascii = (start: number, text: string) => [...text].every((char, index) => bytes[start + index] === char.charCodeAt(0))
  const valid = file.type === 'image/jpeg' ? bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255
    : file.type === 'image/png' ? [137, 80, 78, 71, 13, 10, 26, 10].every((value, index) => bytes[index] === value)
    : file.type === 'image/webp' ? ascii(0, 'RIFF') && ascii(8, 'WEBP')
    : file.type === 'video/webm' ? [26, 69, 223, 163].every((value, index) => bytes[index] === value)
    : ascii(4, 'ftyp')
  if (!valid) throw new Error('Содержимое файла не соответствует выбранному формату')
  return kind
}

export function letterboxGeometry(width: number, height: number) {
  validateDimensions(width, height)
  const scale = Math.min(INPUT_SIZE / width, INPUT_SIZE / height)
  const resizedWidth = Math.max(1, Math.round(width * scale))
  const resizedHeight = Math.max(1, Math.round(height * scale))
  return {
    resizedWidth, resizedHeight,
    paddingX: Math.floor((INPUT_SIZE - resizedWidth) / 2),
    paddingY: Math.floor((INPUT_SIZE - resizedHeight) / 2),
    // Invert the actual rounded resize, not the ideal (pre-rounding) scale.
    scaleX: resizedWidth / width, scaleY: resizedHeight / height,
  }
}

export function pixelsToInput(pixels: Uint8ClampedArray): Float32Array {
  const channelSize = INPUT_SIZE * INPUT_SIZE
  if (pixels.length !== channelSize * 4) throw new Error('Неверный размер входного изображения')
  const input = new Float32Array(channelSize * 3)
  for (let index = 0; index < channelSize; index += 1) {
    input[index] = pixels[index * 4] / 255
    input[channelSize + index] = pixels[index * 4 + 1] / 255
    input[channelSize * 2 + index] = pixels[index * 4 + 2] / 255
  }
  return input
}

export function decodePeople(output: RuntimeTensor, confidenceThreshold: number, sourceWidth: number, sourceHeight: number): BrowserDetection[] {
  validateThreshold(confidenceThreshold)
  const { scaleX, scaleY, paddingX, paddingY } = letterboxGeometry(sourceWidth, sourceHeight)
  const dims = output.dims
  // Only raw COCO YOLOv8 output is supported, not objectness/embedded-NMS layouts.
  const channelsFirst = dims.length === 3 && dims[0] === 1 && dims[1] === 84 && dims[2] === 8400
  const channelsLast = dims.length === 3 && dims[0] === 1 && dims[1] === 8400 && dims[2] === 84
  if ((!channelsFirst && !channelsLast) || !(output.data instanceof Float32Array) || output.data.length !== 84 * 8400) {
    throw new Error('Неподдерживаемый выход модели: ожидается float32 [1,84,8400] или [1,8400,84]')
  }
  if (!output.data.every(Number.isFinite)) throw new Error('Модель вернула нечисловые значения')
  const valueAt = (channel: number, anchor: number) => output.data[channelsFirst ? channel * 8400 + anchor : anchor * 84 + channel]
  const candidates: BrowserDetection[] = []
  for (let anchor = 0; anchor < 8400; anchor += 1) {
    // COCO person class ID is 0; its score is channel 4 after xywh.
    const confidence = clamp(valueAt(4, anchor), 0, 1)
    for (let channel = 4; channel < 84; channel += 1) {
      const score = valueAt(channel, anchor)
      if (score < -PROBABILITY_EPSILON || score > 1 + PROBABILITY_EPSILON) {
        throw new Error(`Модель вернула некорректную уверенность (${score}, канал ${channel})`)
      }
    }
    if (confidence < confidenceThreshold) continue
    const centerX = valueAt(0, anchor)
    const centerY = valueAt(1, anchor)
    const width = valueAt(2, anchor)
    const height = valueAt(3, anchor)
    if (width <= 0 || height <= 0) continue
    const left = clamp((centerX - width / 2 - paddingX) / scaleX, 0, sourceWidth)
    const top = clamp((centerY - height / 2 - paddingY) / scaleY, 0, sourceHeight)
    const right = clamp((centerX + width / 2 - paddingX) / scaleX, 0, sourceWidth)
    const bottom = clamp((centerY + height / 2 - paddingY) / scaleY, 0, sourceHeight)
    if (right <= left || bottom <= top) continue
    candidates.push({ x: left, y: top, width: right - left, height: bottom - top, confidence })
  }
  return nonMaximumSuppression(candidates)
}

export function nonMaximumSuppression(candidates: BrowserDetection[]): BrowserDetection[] {
  const ordered = [...candidates].sort((a, b) => b.confidence - a.confidence)
  const kept: BrowserDetection[] = []
  for (const candidate of ordered) {
    if (kept.every((existing) => intersectionOverUnion(existing, candidate) < NMS_IOU_THRESHOLD)) kept.push(candidate)
  }
  return kept
}

export function intersectionOverUnion(a: BrowserDetection, b: BrowserDetection): number {
  const width = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x))
  const height = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y))
  const intersection = width * height
  const union = a.width * a.height + b.width * b.height - intersection
  return union > 0 ? intersection / union : 0
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum)
}
