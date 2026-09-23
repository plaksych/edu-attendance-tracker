import bootstrapUrl from '../workers/browserRecognition.bootstrap.js?url&no-inline'
import workerModuleUrl from '../workers/browserRecognition.worker.ts?worker&url'
import { BrowserRecognizer, createRecognizerCache } from './browserRecognitionClient'

export { BrowserRecognizer } from './browserRecognitionClient'
export type { BrowserDetection, BrowserRecognitionResult } from './browserRecognitionCore'

// Importing this module does not create a worker or fetch runtime/model assets.
const cache = createRecognizerCache(() => {
  if (typeof Worker === 'undefined' || typeof createImageBitmap === 'undefined') {
    throw new Error('Браузер не поддерживает локальную обработку в отдельном потоке')
  }
  const worker = new Worker(bootstrapUrl, { name: 'browser-recognition' })
  return new BrowserRecognizer(worker, {
    baseUrl: new URL(import.meta.env.BASE_URL, window.location.href).href,
    moduleUrl: new URL(workerModuleUrl, window.location.href).href,
  })
})

export const getBrowserRecognizer = cache.get
export const releaseBrowserRecognizer = cache.release
