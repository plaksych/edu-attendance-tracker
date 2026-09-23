// Opt-in integrated smoke: actual static application, real dialog, model and WASM.
// Generated media and all evidence stay in tests/browser*. No dist writes or containers.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { createServer } from 'node:http'
import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import os from 'node:os'
import { performance } from 'node:perf_hooks'
import { chromium, expect } from '@playwright/test'
import react from '@vitejs/plugin-react'
import { build } from 'vite'

const root = new URL('../', import.meta.url)
const artifact = (name) => new URL(`./browserRecognition-ui-${name}`, import.meta.url)
const base = '/edu-attendance-tracker/'
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex')
const evidence = {
  status: 'running', startedAt: new Date().toISOString(), base,
  scope: 'Actual compiled static application and LocalRecognitionDialog; generated blank PNG and 6-second white MP4; real ONNX/WASM',
  limitation: 'Execution/privacy/UI smoke on synthetic negative media, not classroom accuracy or cross-browser/device certification.',
  environment: { node: process.version, platform: os.platform(), arch: os.arch(), cpu: os.cpus()[0]?.model },
  baseCommit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: fileURLToPath(root), encoding: 'utf8' }).trim(),
  sourceHashes: {}, stages: {}, network: { requests: [], responses: [], rejected: [], localBlobRequests: [] },
  pageErrors: [], console: [], screenshots: [], workers: [],
}
for (const path of ['src/components/LocalRecognitionDialog.tsx', 'src/components/Modal.tsx', 'src/pages/RecognitionPage.tsx',
  'src/lib/browserRecognition.ts', 'src/lib/browserRecognitionCore.ts', 'src/lib/browserRecognitionClient.ts',
  'src/workers/browserRecognition.bootstrap.js', 'src/workers/browserRecognition.worker.ts', 'tests/browserRecognitionUiSmoke.mjs']) {
  evidence.sourceHashes[path] = sha256(await readFile(new URL(path, root)))
}
const manifest = JSON.parse(await readFile(new URL('public/models/manifest.json', root), 'utf8'))
evidence.model = manifest.artifact

// A seekable MP4 has a real finite duration, unlike an unfinished MediaRecorder stream.
execFileSync(process.env.FFMPEG || 'ffmpeg', ['-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
  '-filter_threads', '1', '-filter_complex_threads', '1', '-f', 'lavfi', '-i', 'color=c=white:s=320x240:r=4',
  '-t', '6', '-an', '-c:v', 'libx264', '-threads', '1', '-preset', 'ultrafast', '-crf', '35',
  '-pix_fmt', 'yuv420p', '-movflags', '+faststart', fileURLToPath(artifact('input.mp4'))], { timeout: 30_000 })
const video = await readFile(artifact('input.mp4'))
evidence.videoInput = { file: 'browserRecognition-ui-input.mp4', bytes: video.length, sha256: sha256(video), width: 320, height: 240, fps: 4, durationSeconds: 6, generator: 'ffmpeg lavfi white, libx264, one encoder/filter thread' }

process.env.VITE_STATIC_DATA = 'true'
const built = await build({
  // Deliberately do not execute the shared Vite config's filesystem cleanup hooks.
  configFile: false, root: fileURLToPath(root), base, plugins: [react()], logLevel: 'error',
  define: { 'import.meta.env.VITE_STATIC_DATA': JSON.stringify('true') },
  build: { write: false, copyPublicDir: false },
})
assert.ok(!('on' in built))
const outputs = Array.isArray(built) ? built.flatMap((item) => item.output) : built.output
const mime = (path) => path.endsWith('.html') ? 'text/html' : path.endsWith('.css') ? 'text/css'
  : path.endsWith('.woff2') ? 'font/woff2' : path.endsWith('.woff') ? 'font/woff'
  : path.endsWith('.png') ? 'image/png' : path.endsWith('.svg') ? 'image/svg+xml'
  : path.endsWith('.wasm') ? 'application/wasm' : path.endsWith('.onnx') ? 'application/octet-stream' : 'text/javascript'
const assets = new Map(outputs.map((output) => [output.fileName, { body: output.type === 'chunk' ? output.code : output.source, mime: mime(output.fileName) }]))
assert.ok(assets.has('index.html'))
evidence.compiledAssets = [...assets].map(([path, { body }]) => ({ path, bytes: Buffer.byteLength(body), sha256: sha256(body) }))
for (const relative of ['favicon.svg', 'synthetic-classroom.png', 'models/yolov8n.onnx', ...Object.keys(manifest.runtime.assets)]) {
  const body = await readFile(new URL(`public/${relative}`, root))
  const expected = relative.endsWith('.onnx') ? manifest.artifact.sha256 : manifest.runtime.assets[relative]
  if (expected) assert.equal(sha256(body), expected)
  assets.set(relative, { body, mime: mime(relative) })
}
let modelMode = 'fail'
let onHeldModel
const server = createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost')
  response.setHeader('Cache-Control', 'no-store')
  if (request.method !== 'GET' || url.search || !url.pathname.startsWith(base)) { response.writeHead(403).end(); return }
  const relative = url.pathname.slice(base.length) || 'index.html'
  if (relative === 'models/yolov8n.onnx') {
    if (modelMode === 'fail') { response.writeHead(503, { 'Content-Type': 'text/plain' }).end('Intentional download failure'); return }
    if (modelMode === 'hold') { onHeldModel?.(); return }
  }
  const asset = assets.get(relative)
  if (!asset) { response.writeHead(404).end(); return }
  response.writeHead(200, { 'Content-Type': asset.mime, 'Content-Length': Buffer.byteLength(asset.body) }).end(asset.body)
})
let browser
let context
let page
let stage = 'navigation'
let origin
let watchdog
try {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  origin = `http://127.0.0.1:${server.address().port}`
  browser = await chromium.launch({ channel: process.env.BROWSER_TEST_CHANNEL || undefined, headless: true })
  evidence.environment.browser = browser.version()
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block', acceptDownloads: true })
  context.setDefaultTimeout(20_000)
  watchdog = setTimeout(() => { evidence.timeout = true; void context.close() }, 180_000)
  const allowed = new Set([base, ...[...assets.keys()].map((path) => base + path)])
  await context.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const record = { stage, path: url.pathname, origin: url.origin, query: url.search, method: request.method(), bodyBytes: request.postDataBuffer()?.length ?? 0, resourceType: request.resourceType() }
    evidence.network.requests.push(record)
    if (url.origin !== origin || !allowed.has(url.pathname) || url.search || record.method !== 'GET' || record.bodyBytes !== 0) {
      evidence.network.rejected.push(record)
      await route.abort('blockedbyclient')
    } else await route.continue()
  })
  context.on('request', (request) => {
    if (request.url().startsWith('blob:')) evidence.network.localBlobRequests.push({ stage, method: request.method(), type: request.resourceType(), localOnly: true })
  })
  context.on('response', (response) => {
    if (!response.url().startsWith('http:')) return
    evidence.network.responses.push({ stage, path: new URL(response.url()).pathname, status: response.status(), contentType: response.headers()['content-type'], contentLength: response.headers()['content-length'] })
  })
  await context.addInitScript(() => {
    const created = new Set()
    const nativeCreate = URL.createObjectURL.bind(URL)
    const nativeRevoke = URL.revokeObjectURL.bind(URL)
    URL.createObjectURL = (blob) => { const url = nativeCreate(blob); created.add(url); return url }
    URL.revokeObjectURL = (url) => { created.delete(url); return nativeRevoke(url) }
    window.__uiSmoke = { activeUrls: () => created.size }
  })
  page = await context.newPage()
  page.on('pageerror', (error) => evidence.pageErrors.push(String(error)))
  page.on('console', (message) => { if (['error', 'warning'].includes(message.type())) evidence.console.push({ stage, type: message.type(), text: message.text() }) })
  const workers = []
  page.on('worker', (worker) => {
    const record = { id: workers.length, url: worker.url(), createdAt: new Date().toISOString(), stage, closed: false }
    workers.push(worker); evidence.workers.push(record)
    worker.on('close', () => { record.closed = true; record.closedAt = new Date().toISOString() })
  })
  await page.goto(`${origin}${base}#/recognition`)
  await page.getByRole('button', { name: 'Проверить файл', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Локальный анализ' })
  await expect(dialog).toBeVisible()
  const status = dialog.getByRole('status')
  await expect(status).toHaveText('Файл не выбран')
  assert.equal(workers.length, 0)
  assert.equal(evidence.network.requests.some(({ path }) => /\/(ort|models)\//.test(path)), false)
  evidence.stages.openDialog = { passed: true, runtimeRequests: 0, workers: 0, url: `${base}#/recognition` }

  const pngBase64 = await page.evaluate(() => {
    const canvas = document.createElement('canvas'); canvas.width = 320; canvas.height = 240
    const drawing = canvas.getContext('2d'); drawing.fillStyle = '#ffffff'; drawing.fillRect(0, 0, 320, 240)
    return canvas.toDataURL('image/png').split(',')[1]
  })
  const png = Buffer.from(pngBase64, 'base64')
  await writeFile(artifact('input.png'), png)
  evidence.imageInput = { file: 'browserRecognition-ui-input.png', bytes: png.length, sha256: sha256(png), width: 320, height: 240, generator: 'Browser canvas, solid white' }
  const fileInput = dialog.getByLabel('Фото или видео', { exact: true })
  await fileInput.setInputFiles({ name: 'synthetic-blank.png', mimeType: 'image/png', buffer: png })
  await expect(status).toHaveText('Готово к обработке')
  assert.equal(workers.length, 0)
  evidence.stages.selectImage = { passed: true, runtimeRequests: 0, workers: 0 }

  stage = 'intentional-model-failure'
  await dialog.getByRole('button', { name: 'Распознать', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('HTTP 503', { timeout: 30_000 })
  await expect(dialog.getByRole('button', { name: 'Повторить', exact: true })).toBeEnabled()
  evidence.stages.errorRetryUi = { passed: true, displayedError: await dialog.getByRole('alert').innerText() }
  stage = 'cancel-model-initialization'
  modelMode = 'hold'
  const held = new Promise((resolve) => { onHeldModel = resolve })
  await dialog.getByRole('button', { name: 'Повторить', exact: true }).click()
  let heldTimeout
  try {
    await Promise.race([held, new Promise((_, reject) => { heldTimeout = setTimeout(() => reject(new Error('Held model request did not arrive')), 20_000) })])
  } finally { clearTimeout(heldTimeout) }
  await expect(status).toHaveText('Подготовка модели')
  const stopStarted = performance.now()
  await dialog.getByRole('button', { name: 'Остановить', exact: true }).click()
  await expect(status).toHaveText('Обработка остановлена')
  await expect.poll(() => evidence.workers.at(-1).closed).toBe(true)
  evidence.stages.cancelInitializationUi = { passed: true, stopWallMs: performance.now() - stopStarted, workerClosed: true }

  const readExport = async () => {
    const downloadEvent = page.waitForEvent('download')
    await dialog.getByRole('button', { name: 'Скачать локальный результат JSON', exact: true }).click()
    const download = await downloadEvent
    const stream = await download.createReadStream()
    const chunks = []
    for await (const chunk of stream) chunks.push(chunk)
    const report = JSON.parse(Buffer.concat(chunks).toString('utf8'))
    assert.equal(report.provenance, 'browser_inference')
    assert.equal(report.modelSha256, manifest.artifact.sha256)
    assert.equal(report.sourceWidth, 320); assert.equal(report.sourceHeight, 240)
    assert.equal(report.quality.confidenceIsAccuracy, false)
    assert.ok(Number.isFinite(report.elapsedMs) && report.elapsedMs > 0)
    return report
  }
  const takeScreenshot = async (label) => {
    await dialog.evaluate((element) => { element.scrollTop = 0 })
    await page.screenshot({ path: fileURLToPath(artifact(`${label}-controls.png`)), fullPage: false })
    await dialog.locator('.local-recognition__metrics').scrollIntoViewIfNeeded()
    await page.screenshot({ path: fileURLToPath(artifact(`${label}.png`)), fullPage: false })
    const dimensions = await page.evaluate(() => {
      const modal = document.querySelector('[role="dialog"]')
      const frame = modal.querySelector('.local-recognition__frame')
      const media = frame.querySelector('img,video')
      const bounds = (element) => { const rect = element.getBoundingClientRect(); return { x: rect.x, y: rect.y, width: rect.width, height: rect.height } }
      return { viewport: { width: innerWidth, height: innerHeight }, pageWidth: document.documentElement.scrollWidth, modal: bounds(modal), frame: bounds(frame), media: bounds(media), horizontalOverflow: modal.scrollWidth > modal.clientWidth + 1 }
    })
    evidence.screenshots.push({ file: `frontend/tests/browserRecognition-ui-${label}.png`, controlsFile: `frontend/tests/browserRecognition-ui-${label}-controls.png`, ...dimensions })
    assert.ok(dimensions.pageWidth <= dimensions.viewport.width)
    assert.equal(dimensions.horizontalOverflow, false)
    assert.ok(Math.abs(dimensions.media.width / dimensions.media.height - 4 / 3) < 0.03)
  }
  stage = 'real-image-retry'
  modelMode = 'real'
  const imageStarted = performance.now()
  await dialog.getByRole('button', { name: 'Распознать', exact: true }).click()
  await expect(status).toHaveText('Обработано в браузере', { timeout: 120_000 })
  const imageWallMs = performance.now() - imageStarted
  evidence.stages.realImage = { passed: true, uiWallMs: imageWallMs, report: await readExport() }
  evidence.runtime = await workers.at(-1).evaluate(() => ({ versions: self.ort.env.versions, numThreads: self.ort.env.wasm.numThreads, wasmPaths: self.ort.env.wasm.wasmPaths }))
  assert.equal(evidence.runtime.numThreads, 1)
  await takeScreenshot('desktop-image')
  await page.setViewportSize({ width: 390, height: 844 })
  await takeScreenshot('mobile-image')

  stage = 'select-video'
  await fileInput.setInputFiles({ name: 'synthetic-white-6s.mp4', mimeType: 'video/mp4', buffer: video })
  await expect(status).toHaveText('Готово к обработке', { timeout: 30_000 })
  const metadata = await dialog.locator('video').evaluate((element) => ({ duration: element.duration, width: element.videoWidth, height: element.videoHeight, readyState: element.readyState, paused: element.paused }))
  assert.ok(Number.isFinite(metadata.duration) && metadata.duration > 0 && metadata.duration <= 6.1)
  assert.equal(metadata.width, 320); assert.equal(metadata.height, 240)
  evidence.stages.selectVideo = { passed: true, metadata }
  stage = 'real-video-frame'
  const videoStarted = performance.now()
  await dialog.getByRole('button', { name: 'Проверить кадр', exact: true }).click()
  await expect(status).toHaveText('Обработано в браузере', { timeout: 120_000 })
  evidence.stages.realVideoFrame = { passed: true, uiWallMs: performance.now() - videoStarted, report: await readExport() }
  assert.equal(evidence.stages.realVideoFrame.report.frameTimeSeconds, 0)
  await takeScreenshot('mobile-video')
  await page.setViewportSize({ width: 1440, height: 1000 })
  await takeScreenshot('desktop-video')

  stage = 'real-video-sampling'
  await dialog.getByRole('button', { name: 'Анализ видео', exact: true }).click()
  await expect(dialog.getByText(/Последние 2 кадров/)).toBeAttached({ timeout: 60_000 })
  await dialog.getByRole('button', { name: 'Остановить', exact: true }).click()
  await expect(status).toHaveText('Обработка остановлена')
  await expect.poll(() => evidence.workers.at(-1).closed).toBe(true)
  evidence.stages.videoSampling = { passed: true, report: await readExport(), pausedAfterStop: await dialog.locator('video').evaluate((element) => element.paused), workerClosed: true }
  assert.equal(evidence.stages.videoSampling.pausedAfterStop, true)
  assert.equal(evidence.stages.videoSampling.report.recentFrameCounts.length, 2)
  const workerCount = workers.length
  // Wait through the next sampling interval to detect an incorrectly restarted loop.
  await page.waitForTimeout(1200)
  assert.equal(workers.length, workerCount)
  await expect(status).toHaveText('Обработка остановлена')

  stage = 'clear-close-reopen'
  await dialog.getByRole('button', { name: 'Очистить', exact: true }).click()
  await expect(status).toHaveText('Файл не выбран')
  await expect(dialog.locator('video, .local-recognition__frame img')).toHaveCount(0)
  const activeUrlsAfterClear = await page.evaluate(() => window.__uiSmoke.activeUrls())
  assert.equal(activeUrlsAfterClear, 0)
  await dialog.getByRole('button', { name: 'Закрыть диалог', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await page.getByRole('button', { name: 'Проверить файл', exact: true }).click()
  await expect(dialog.getByRole('status')).toHaveText('Файл не выбран')
  await dialog.getByRole('button', { name: 'Закрыть диалог', exact: true }).click()
  evidence.stages.cleanupUi = { passed: true, activeUrlsAfterClear, reopenedEmpty: true }
  assert.equal(evidence.pageErrors.length, 0)
  assert.equal(evidence.network.rejected.length, 0)
  assert.ok(evidence.network.requests.every(({ method, bodyBytes, query }) => method === 'GET' && bodyBytes === 0 && query === ''))
  assert.ok(evidence.network.responses.some(({ path, status, contentType }) => path.endsWith('.wasm') && status === 200 && contentType === 'application/wasm'))
  assert.ok(evidence.workers.every(({ closed }) => closed))
  evidence.network.summary = { passed: true, uploadBytes: 0, unexpectedRequests: 0, staticGets: evidence.network.requests.length, note: 'PNG/MP4 selected by file input; media/exports are local blob URLs, never served or uploaded. All observed HTTP requests were exact-allowlist same-origin static GETs.' }
  evidence.status = 'passed'
} catch (error) {
  evidence.status = 'failed'; evidence.failure = { stage, message: String(error), stack: error.stack }; process.exitCode = 1
  if (page && !page.isClosed()) {
    await page.screenshot({ path: fileURLToPath(artifact('failure.png')), fullPage: true }).catch(() => undefined)
    evidence.failure.visibleText = await page.locator('body').innerText().catch(() => '')
  }
} finally {
  clearTimeout(watchdog)
  await context?.close()
  await browser?.close()
  server.closeAllConnections()
  if (server.listening) await new Promise((resolve) => server.close(resolve))
  evidence.finishedAt = new Date().toISOString()
  evidence.cleanup = { browserClosed: true, serverClosed: !server.listening }
  await writeFile(artifact('smoke.json'), JSON.stringify(evidence, null, 2) + '\n')
  console.log('UI_SMOKE_EVIDENCE', fileURLToPath(artifact('smoke.json')))
  console.log(JSON.stringify({ status: evidence.status, stages: evidence.stages, network: evidence.network.summary, failure: evidence.failure }, null, 2))
}
