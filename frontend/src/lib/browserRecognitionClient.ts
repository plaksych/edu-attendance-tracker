import { validateDimensions, validateThreshold, type BrowserRecognitionResult } from './browserRecognitionCore'

type WorkerPort = Pick<Worker, 'postMessage' | 'terminate' | 'onmessage' | 'onerror' | 'onmessageerror'>
type Pending = { resolve: (result: BrowserRecognitionResult | undefined) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }

export class BrowserRecognizer {
  private pending = new Map<number, Pending>()
  private sequence = 0
  private stopped = false
  private busy = false
  readonly ready: Promise<void>

  constructor(private readonly worker: WorkerPort, config: { baseUrl: string; moduleUrl: string }) {
    worker.onmessage = ({ data }) => {
      const pending = this.pending.get(data.id)
      if (!pending) return
      clearTimeout(pending.timer)
      this.pending.delete(data.id)
      if (data.error) {
        const error = new Error(String(data.error))
        pending.reject(error)
        this.dispose(error)
      } else pending.resolve(data.result)
    }
    worker.onerror = () => this.dispose(new Error('Ошибка потока распознавания. Повторите обработку.'))
    worker.onmessageerror = () => this.dispose(new Error('Не удалось получить результат распознавания'))
    this.ready = this.request({ type: 'init', ...config }).then(() => undefined)
  }

  get disposed(): boolean { return this.stopped }

  async detect(source: CanvasImageSource, width: number, height: number, threshold: number, signal?: AbortSignal): Promise<BrowserRecognitionResult> {
    validateDimensions(width, height)
    validateThreshold(threshold)
    if (this.stopped) throw new Error('Обработка остановлена. Запустите её повторно.')
    if (this.busy) throw new Error('Предыдущий кадр ещё обрабатывается')
    const abort = () => this.dispose(new DOMException('Обработка отменена', 'AbortError'))
    if (signal?.aborted) { abort(); throw new DOMException('Обработка отменена', 'AbortError') }
    signal?.addEventListener('abort', abort, { once: true })
    this.busy = true
    let bitmap: ImageBitmap | undefined
    try {
      await this.ready
      if (this.stopped) throw new DOMException('Обработка отменена', 'AbortError')
      // Only the decoded frame crosses the worker boundary. No media is uploaded.
      bitmap = await createImageBitmap(source as ImageBitmapSource)
      if (this.stopped) throw new DOMException('Обработка отменена', 'AbortError')
      const response = this.request({ type: 'detect', bitmap, width, height, threshold }, [bitmap])
      bitmap = undefined // Ownership transferred to the worker.
      const result = await response
      if (!result) throw new Error('Пустой ответ потока распознавания')
      return result
    } finally {
      bitmap?.close()
      this.busy = false
      signal?.removeEventListener('abort', abort)
    }
  }

  dispose(reason: Error = new DOMException('Обработка отменена', 'AbortError')): void {
    if (this.stopped) return
    this.stopped = true
    // Termination interrupts fetch/WASM and frees the worker's entire heap.
    this.worker.terminate()
    this.worker.onmessage = this.worker.onerror = this.worker.onmessageerror = null
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer)
      pending.reject(reason)
    }
    this.pending.clear()
  }

  private request(message: object, transfer: Transferable[] = []): Promise<BrowserRecognitionResult | undefined> {
    if (this.stopped) return Promise.reject(new DOMException('Обработка отменена', 'AbortError'))
    const id = ++this.sequence
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.dispose(new Error('Превышено время обработки. Повторите попытку.')), 120_000)
      this.pending.set(id, { resolve, reject, timer })
      try { this.worker.postMessage({ ...message, id }, transfer) }
      catch (error) {
        for (const item of transfer) if (typeof ImageBitmap !== 'undefined' && item instanceof ImageBitmap) item.close()
        this.dispose(error instanceof Error ? error : new Error(String(error)))
      }
    })
  }
}

export function createRecognizerCache(factory: () => BrowserRecognizer) {
  let current: BrowserRecognizer | undefined
  let promise: Promise<BrowserRecognizer> | undefined
  const release = () => {
    const previous = current
    current = undefined
    promise = undefined
    previous?.dispose()
  }
  const get = (): Promise<BrowserRecognizer> => {
    if (current?.disposed) release()
    if (!promise) {
      try { current = factory() } catch (error) { return Promise.reject(error) }
      const instance = current
      promise = instance.ready.then(() => instance).catch((error) => {
        if (current === instance) release()
        throw error
      })
    }
    return promise
  }
  return { get, release }
}
