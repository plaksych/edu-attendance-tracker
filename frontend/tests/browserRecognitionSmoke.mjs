// Opt-in real-model smoke. No runtime/session/tensor mocks; one browser, one WASM thread.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { createServer } from 'node:http'
import { readFile, writeFile } from 'node:fs/promises'
import os from 'node:os'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { build } from 'vite'

const root = new URL('../', import.meta.url)
const base = '/edu-attendance-tracker/'
const evidencePath = new URL('./browserRecognition-smoke.json', import.meta.url)
const screenshotPath = new URL('./browserRecognition-smoke.png', import.meta.url)
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex')
const manifest = JSON.parse(await readFile(new URL('public/models/manifest.json', root), 'utf8'))
const evidence = {
  startedAt: new Date().toISOString(), status: 'running', base,
  scope: 'Real vendored YOLOv8n + ONNX Runtime Web; synthetic 320x240 geometric canvas only; no private media',
  caveat: 'Execution smoke only. Not a people-detection or classroom-accuracy evaluation. Local timings are not benchmarks.',
  baseCommit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: fileURLToPath(root), encoding: 'utf8' }).trim(),
  environment: { node: process.version, platform: os.platform(), arch: os.arch(), cpu: os.cpus()[0]?.model },
  model: manifest.artifact, sourceHashes: {}, browserRequests: [], serverRequests: [], blockedRequests: [],
  console: [], pageErrors: [], stages: {},
}
for (const path of [
  'src/lib/browserRecognition.ts', 'src/lib/browserRecognitionClient.ts', 'src/lib/browserRecognitionCore.ts',
  'src/workers/browserRecognition.bootstrap.js', 'src/workers/browserRecognition.worker.ts',
  'tests/browserHarness.ts', 'tests/browserRecognitionSmoke.mjs',
]) evidence.sourceHashes[path] = sha256(await readFile(new URL(path, root)))

const built = await build({
  configFile: false, root: fileURLToPath(root), base, logLevel: 'error',
  build: { write: false, copyPublicDir: false, rollupOptions: { input: fileURLToPath(new URL('./browserHarness.ts', import.meta.url)) } },
})
assert.ok(!('on' in built))
const outputs = Array.isArray(built) ? built.flatMap((result) => result.output) : built.output
const entry = outputs.find((output) => output.type === 'chunk' && output.isEntry)
assert.ok(entry)
const assets = new Map(outputs.map((output) => [output.fileName, { body: output.type === 'chunk' ? output.code : output.source, mime: 'text/javascript' }]))
for (const relative of ['models/yolov8n.onnx', ...Object.keys(manifest.runtime.assets)]) {
  const body = await readFile(new URL(`public/${relative}`, root))
  const expected = relative.endsWith('.onnx') ? manifest.artifact.sha256 : manifest.runtime.assets[relative]
  assert.equal(sha256(body), expected, `Artifact hash: ${relative}`)
  assets.set(relative, { body, mime: relative.endsWith('.wasm') ? 'application/wasm' : relative.endsWith('.onnx') ? 'application/octet-stream' : 'text/javascript' })
}
const html = `<!doctype html><html lang="en"><meta charset="utf-8"><title>Browser inference smoke</title>
<style>body{font:16px system-ui;margin:32px;color:#172321;background:#f5f7f8}main{max-width:960px}h1{font-size:26px}canvas{border:1px solid #88938f;width:320px;height:240px;background:white}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px ui-monospace;line-height:1.5}small{color:#45514c}</style>
<main><h1>Real browser inference smoke</h1><p>Synthetic geometry only. No private media.</p><canvas id="input" width="320" height="240"></canvas>
<p id="status">Loading harness only</p><pre id="metrics"></pre><small>Execution evidence, not a counting-accuracy evaluation.</small></main>
<script type="module" src="${base}${entry.fileName}"></script></html>`
let modelMode = 'fail'
let pendingModelRequest
const server = createServer(async (request, response) => {
  const url = new URL(request.url, 'http://localhost')
  const record = { path: url.pathname, query: url.search, method: request.method, requestBodyBytes: 0, status: null, responseBytes: 0 }
  evidence.serverRequests.push(record)
  request.on('data', (chunk) => { record.requestBodyBytes += chunk.length })
  response.setHeader('Cache-Control', 'no-store')
  const send = (status, body = '', mime = 'text/plain') => {
    record.status = status
    record.responseBytes = Buffer.byteLength(body)
    response.writeHead(status, { 'Content-Type': mime }).end(body)
  }
  if (request.method !== 'GET' || url.search || !url.pathname.startsWith(base)) { send(403); return }
  const relative = url.pathname.slice(base.length)
  if (!relative) { send(200, html, 'text/html'); return }
  if (relative === 'models/yolov8n.onnx') {
    if (modelMode === 'fail') { send(503, 'Intentional model-download failure for retry test'); return }
    if (modelMode === 'hold') {
      pendingModelRequest?.()
      response.on('close', () => { if (!response.writableEnded) record.cancelled = true })
      return
    }
  }
  const asset = assets.get(relative)
  if (asset) { send(200, asset.body, asset.mime); return }
  send(404)
})
let browser
let context
let origin
try {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const address = server.address()
  assert.ok(address && typeof address !== 'string')
  origin = `http://127.0.0.1:${address.port}`
  browser = await chromium.launch({ channel: process.env.BROWSER_TEST_CHANNEL || undefined, headless: true })
  evidence.environment.browser = browser.version()
  context = await browser.newContext({ viewport: { width: 1040, height: 880 }, serviceWorkers: 'block' })
  const allowedPaths = new Set([base, ...[...assets.keys()].map((path) => base + path)])
  await context.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const record = { url: request.url(), method: request.method(), bodyBytes: request.postDataBuffer()?.length ?? 0, resourceType: request.resourceType() }
    evidence.browserRequests.push(record)
    if (url.origin !== origin || !allowedPaths.has(url.pathname) || url.search || record.method !== 'GET' || record.bodyBytes !== 0) {
      evidence.blockedRequests.push(record)
      await route.abort('blockedbyclient')
    } else await route.continue()
  })
  const page = await context.newPage()
  page.on('console', (message) => evidence.console.push({ type: message.type(), text: message.text() }))
  page.on('pageerror', (error) => evidence.pageErrors.push(String(error)))
  const workers = []
  page.on('worker', (worker) => workers.push(worker))
  await page.goto(origin + base)
  await page.waitForFunction(() => 'browserRecognitionTest' in window)
  await page.evaluate(() => {
    const canvas = document.querySelector('#input')
    const context = canvas.getContext('2d')
    context.fillStyle = '#ffffff'; context.fillRect(0, 0, 320, 240)
    context.fillStyle = '#2079b0'; context.fillRect(28, 36, 96, 64)
    context.fillStyle = '#ba3f51'; context.beginPath(); context.arc(236, 72, 30, 0, Math.PI * 2); context.fill()
    context.fillStyle = '#39946a'; context.fillRect(88, 160, 168, 28)
  })
  assert.equal(workers.length, 0)
  assert.equal(evidence.serverRequests.some(({ path }) => /\/(ort|models)\//.test(path)), false)
  evidence.stages.initialLoad = { passed: true, workers: 0, mlRequests: 0 }

  const getError = () => page.evaluate(async () => {
    const start = performance.now()
    try { await window.browserRecognitionTest.get(); return { error: null, elapsedMs: performance.now() - start } }
    catch (error) { return { name: error.name, error: error.message, elapsedMs: performance.now() - start } }
  })
  evidence.stages.failedInitialization = await getError()
  assert.match(evidence.stages.failedInitialization.error, /HTTP 503/)
  await page.waitForFunction(() => true)
  modelMode = 'hold'
  const modelRequested = new Promise((resolve) => { pendingModelRequest = resolve })
  const cancelledInitialization = getError()
  await modelRequested
  await page.evaluate(() => window.browserRecognitionTest.release())
  evidence.stages.cancelledInitialization = await cancelledInitialization
  assert.equal(evidence.stages.cancelledInitialization.name, 'AbortError')

  modelMode = 'real'
  const runReal = () => page.evaluate(async () => {
    const start = performance.now()
    const recognizer = await window.browserRecognitionTest.get()
    const initialized = performance.now()
    const result = await recognizer.detect(document.querySelector('#input'), 320, 240, 0.35)
    return { initMs: initialized - start, detectWallMs: performance.now() - initialized, totalMs: performance.now() - start, result }
  })
  evidence.stages.firstRealInference = await runReal()
  assert.equal(evidence.stages.firstRealInference.result.provenance, 'browser_inference')
  assert.equal(evidence.stages.firstRealInference.result.modelSha256, manifest.artifact.sha256)
  const liveWorker = workers.at(-1)
  evidence.runtime = await liveWorker.evaluate(() => ({ versions: self.ort.env.versions, numThreads: self.ort.env.wasm.numThreads, proxy: self.ort.env.wasm.proxy, wasmPaths: self.ort.env.wasm.wasmPaths }))
  assert.equal(evidence.runtime.numThreads, 1)
  assert.ok(evidence.serverRequests.some(({ path, status, responseBytes }) => path.endsWith('.wasm') && status === 200 && responseBytes > 1_000_000))
  console.log('REAL_INFERENCE', JSON.stringify(evidence.stages.firstRealInference))

  // Diagnostic wrapper announces entry into the actual runtime run() method,
  // then calls it unchanged. It does not fabricate or replace any inference.
  await liveWorker.evaluate(() => {
    const originalRun = self.ort.InferenceSession.prototype.run
    self.ort.InferenceSession.prototype.run = function (...args) {
      self.postMessage({ smokeRunEntered: true })
      return originalRun.apply(this, args)
    }
  })
  await page.evaluate(() => {
    // Find the real Worker instance via a test-only wrapper installed for this
    // second detect call; the first init/inference above was not instrumented.
    const original = Worker.prototype.postMessage
    Worker.prototype.postMessage = function (message, ...args) {
      if (message.type === 'detect') {
        const worker = this
        worker.addEventListener('message', function entered(event) {
          if (!event.data.smokeRunEntered) return
          worker.removeEventListener('message', entered)
          window.smokeRunEntered = true
          window.browserRecognitionTest.release()
        })
      }
      return original.call(this, message, ...args)
    }
    window.smokeRestorePostMessage = () => { Worker.prototype.postMessage = original }
  })
  const workerClosed = new Promise((resolve) => liveWorker.once('close', resolve))
  evidence.stages.cancelledInference = await page.evaluate(async () => {
    const recognizer = await window.browserRecognitionTest.get()
    const start = performance.now()
    try {
      const result = await recognizer.detect(document.querySelector('#input'), 320, 240, 0.35)
      return { unexpectedResult: result, elapsedMs: performance.now() - start }
    } catch (error) {
      return { name: error.name, error: error.message, runEntered: window.smokeRunEntered === true, elapsedMs: performance.now() - start }
    } finally { window.smokeRestorePostMessage() }
  })
  await workerClosed
  assert.equal(evidence.stages.cancelledInference.runEntered, true)
  assert.equal(evidence.stages.cancelledInference.name, 'AbortError')
  evidence.stages.cancelledInference.workerClosed = true
  evidence.stages.realInferenceAfterCancellation = await runReal()
  assert.equal(evidence.stages.realInferenceAfterCancellation.result.modelSha256, manifest.artifact.sha256)
  assert.equal(evidence.stages.realInferenceAfterCancellation.result.provenance, 'browser_inference')
  for (const stage of [evidence.stages.firstRealInference, evidence.stages.realInferenceAfterCancellation]) {
    assert.ok(Number.isFinite(stage.result.elapsedMs) && stage.result.elapsedMs > 0)
    assert.ok(stage.result.boxes.every((box) => Object.values(box).every(Number.isFinite)))
  }
  assert.equal(evidence.blockedRequests.length, 0)
  assert.equal(evidence.pageErrors.length, 0)
  assert.ok(evidence.serverRequests.every(({ method, requestBodyBytes, query }) => method === 'GET' && requestBodyBytes === 0 && query === ''))
  assert.equal(evidence.serverRequests.some(({ path }) => path.endsWith('.onnx.data')), false)
  evidence.network = {
    passed: true, policy: 'Exact same-origin harness/runtime/model asset GET allowlist; no queries or request bodies',
    uploadedBytes: evidence.serverRequests.reduce((total, request) => total + request.requestBodyBytes, 0),
    wasm: evidence.serverRequests.filter(({ path }) => path.endsWith('.wasm')),
    unexpectedRequests: evidence.blockedRequests.length,
  }
  evidence.workersCreated = workers.length
  const lastWorker = workers.at(-1)
  const lastClosed = new Promise((resolve) => lastWorker.once('close', resolve))
  await page.evaluate(() => window.browserRecognitionTest.release())
  await lastClosed
  evidence.cleanup = { finalWorkerClosed: true }
  evidence.status = 'passed'
  await page.evaluate((stages) => {
    document.querySelector('#status').textContent = 'PASS: real ONNX/WASM inference, cancellation and fresh-worker retry'
    document.querySelector('#metrics').textContent = JSON.stringify({
      base: '/edu-attendance-tracker/', model: 'YOLOv8n COCO', runtime: 'ONNX Runtime Web 1.22.0, WASM, 1 thread',
      input: '320x240 synthetic geometry; RGB114 letterbox to 640x640',
      first: { count: stages.firstRealInference.result.boxes.length, initializationMs: stages.firstRealInference.initMs, inferenceMs: stages.firstRealInference.result.elapsedMs },
      cancellation: { actualRunEntered: stages.cancelledInference.runEntered, error: stages.cancelledInference.name, workerClosed: stages.cancelledInference.workerClosed },
      retry: { count: stages.realInferenceAfterCancellation.result.boxes.length, initializationMs: stages.realInferenceAfterCancellation.initMs, inferenceMs: stages.realInferenceAfterCancellation.result.elapsedMs },
      network: 'Only same-origin static GETs; zero media/frame upload bytes',
    }, null, 2)
  }, evidence.stages)
  await page.screenshot({ path: fileURLToPath(screenshotPath), fullPage: true })
  evidence.screenshot = 'frontend/tests/browserRecognition-smoke.png'
} catch (error) {
  evidence.status = 'failed'
  evidence.failure = { message: String(error), stack: error.stack }
  process.exitCode = 1
} finally {
  await context?.close()
  await browser?.close()
  server.closeAllConnections()
  if (server.listening) await new Promise((resolve) => server.close(resolve))
  evidence.finishedAt = new Date().toISOString()
  evidence.cleanup = { ...evidence.cleanup, browserClosed: true, serverClosed: !server.listening }
  await writeFile(evidencePath, JSON.stringify(evidence, null, 2) + '\n')
  console.log('SMOKE_EVIDENCE', fileURLToPath(evidencePath))
  console.log(JSON.stringify({ status: evidence.status, stages: evidence.stages, network: evidence.network, failure: evidence.failure }, null, 2))
}
