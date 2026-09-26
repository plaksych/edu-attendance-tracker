import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { build } from 'vite'
import { expect, it } from 'vitest'

it('loads vendored runtime only on demand in a real worker; retries/stops at Pages subpath without model execution', async () => {
  const base = '/edu-attendance-tracker/'
  const built = await build({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), base, logLevel: 'error',
    build: { write: false, copyPublicDir: false, rollupOptions: { input: fileURLToPath(new URL('./browserHarness.ts', import.meta.url)) } },
  })
  if ('on' in built) throw new Error('Unexpected watch build')
  const outputs = Array.isArray(built) ? built.flatMap((result) => result.output) : built.output
  const entry = outputs.find((output) => output.type === 'chunk' && output.isEntry)!
  const requests: { path: string; method: string }[] = []
  let modelStatus = 503
  const server = createServer(async (request, response) => {
    const path = new URL(request.url!, 'http://localhost').pathname
    requests.push({ path, method: request.method! })
    if (!path.startsWith(base)) { response.writeHead(404).end(); return }
    const relative = path.slice(base.length)
    if (!relative) {
      response.setHeader('Content-Type', 'text/html')
      response.end(`<html><body><script type="module" src="${base}${entry.fileName}"></script></body></html>`)
      return
    }
    const asset = outputs.find((output) => output.fileName === relative)
    if (asset) {
      response.setHeader('Content-Type', 'text/javascript')
      response.end(asset.type === 'chunk' ? asset.code : asset.source)
      return
    }
    if (relative === 'models/yolov8n.onnx') {
      if (modelStatus) response.writeHead(modelStatus).end('Test intentionally prevents model execution')
      return
    }
    if (relative === 'ort/ort.min.js') {
      response.setHeader('Content-Type', 'text/javascript')
      response.end(await readFile(new URL('../public/ort/ort.min.js', import.meta.url)))
      return
    }
    response.writeHead(404).end()
  })
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
  const address = server.address()
  if (!address || typeof address === 'string') throw new Error('No server port')
  let browser: Awaited<ReturnType<typeof chromium.launch>> | undefined
  try {
    browser = await chromium.launch({ channel: process.env.BROWSER_TEST_CHANNEL || undefined, headless: true })
    const page = await browser.newPage()
    const workers: unknown[] = []
    page.on('worker', (worker) => workers.push(worker))
    await page.goto(`http://127.0.0.1:${address.port}${base}`)
    await page.waitForFunction(() => 'browserRecognitionTest' in window)
    expect(requests.some(({ path }) => /\/(ort|models)\//.test(path))).toBe(false)
    expect(workers).toHaveLength(0)
    const getError = () => page.evaluate(async () => {
      const api = (window as unknown as { browserRecognitionTest: { get(): Promise<unknown> } }).browserRecognitionTest
      try { await api.get(); return 'unexpected success' } catch (error) { return String(error) }
    })
    expect(await getError()).toContain('HTTP 503')
    expect(await getError()).toContain('HTTP 503')
    expect(workers).toHaveLength(2)
    expect(requests.filter(({ path }) => path.endsWith('/ort/ort.min.js'))).toHaveLength(2)
    modelStatus = 0
    const cancelled = getError()
    await expect.poll(() => requests.filter(({ path }) => path.endsWith('/models/yolov8n.onnx')).length).toBe(3)
    await page.evaluate(() => (window as unknown as { browserRecognitionTest: { release(): void } }).browserRecognitionTest.release())
    expect(await cancelled).toContain('AbortError')
    modelStatus = 503
    expect(await getError()).toContain('HTTP 503')
    expect(requests.every(({ method }) => method === 'GET')).toBe(true)
    expect(requests.some(({ path }) => path.endsWith('.wasm') || path.endsWith('.onnx.data'))).toBe(false)
  } finally {
    await browser?.close()
    server.closeAllConnections()
    await new Promise<void>((resolve) => server.close(() => resolve()))
  }
}, 30_000)
