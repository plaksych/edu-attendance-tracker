import { preview } from 'vite'
import { chromium } from '@playwright/test'
const server = await preview({ base: '/edu-attendance-tracker/', build: { outDir: 'dist-demo' }, preview: { host: '127.0.0.1', port: 4188, strictPort: true } })
const browser = await chromium.launch()
try {
  const page = await browser.newPage()
  const failures = []
  const api = []
  page.on('response', response => { if (!response.ok()) failures.push(response.url()) })
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/v1/')) api.push(request.url()) })
  await page.goto('http://127.0.0.1:4188/edu-attendance-tracker/#/recognition')
  await page.locator('.recognition-frame img').waitFor()
  await page.waitForFunction(() => [...document.images].every(image => image.complete && image.naturalWidth > 0))
  if (failures.length || api.length) throw new Error(JSON.stringify({ failures, api }))
  console.log('PASS: built demo loads at /edu-attendance-tracker/ with its synthetic image and no failed requests or backend calls.')
} finally {
  await browser.close()
  await new Promise((resolve, reject) => server.httpServer.close(error => error ? reject(error) : resolve()))
}
