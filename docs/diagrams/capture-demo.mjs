import { chromium } from 'playwright'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'

const origin = new URL(process.argv[2] || 'http://127.0.0.1:4187')
if (!['localhost', '127.0.0.1'].includes(origin.hostname)) throw new Error('Only a local synthetic demo is allowed')
const root = dirname(fileURLToPath(import.meta.url))
const output = join(root, 'rendered')
const browser = await chromium.launch({ headless: true,
  ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}) })
const records = []
try {
  await mkdir(output, { recursive: true })
  const page = await browser.newPage()
  const errors = []
  const apiRequests = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/v1/**', route => { apiRequests.push(route.request().url()); return route.abort() })
  const capture = async (file, width, height) => {
    await page.locator('.loading').waitFor({ state: 'hidden' })
    await page.evaluate(() => document.fonts.ready)
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Horizontal overflow')
    const broken = await page.locator('img').evaluateAll(images => images.some(img => !img.complete || img.naturalWidth === 0))
    if (broken) throw new Error('Broken image')
    const bytes = await page.screenshot({ path: join(output, file), fullPage: true, animations: 'disabled' })
    records.push({ file, width, height, route: new URL(page.url()).hash,
      sha256: createHash('sha256').update(bytes).digest('hex') })
  }
  for (const [name, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844]]) {
    await page.setViewportSize({ width, height })
    await page.goto(new URL('/#/', origin).href)
    await page.getByRole('heading', { name: 'Обзор', exact: true }).waitFor()
    await page.getByText(/Учебный пример/).first().waitFor()
    await page.getByText('Занятия с полным итогом', { exact: true }).waitFor()
    await page.getByText('Занятия с двумя замерами', { exact: true }).waitFor()
    await capture(`UI-overview-${name}.png`, width, height)
  }
  const overviewCounts = await page.locator('.stat-card').allTextContents()
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByRole('button', { name: 'Режим показа', exact: true }).click()
  const controls = page.getByRole('region', { name: 'Навигация показа' })
  for (const [index, label] of ['Обзор', 'Распознавание', 'Первое занятие', 'Аналитика'].entries()) {
    await controls.getByRole('status').filter({ hasText: `${index + 1} / 4 · ${label}` }).waitFor()
    await capture(`UI-presentation-${index + 1}.png`, 1280, 900)
    if (index < 3) await controls.getByRole('button', { name: 'Далее', exact: true }).click()
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await capture('UI-presentation-mobile.png', 390, 844)
  await controls.getByRole('button', { name: 'Вернуться к работе', exact: true }).click()
  await page.getByRole('heading', { name: 'Обзор', exact: true }).waitFor()
  if (errors.length || apiRequests.length) throw new Error(JSON.stringify({ errors, apiRequests }))
  const sourceHashes = {}
  for (const file of ['frontend/src/components/Layout.tsx', 'frontend/src/components/PresentationControls.tsx',
    'frontend/src/pages/DashboardPage.tsx', 'frontend/src/api/staticClient.ts', 'frontend/src/production.css']) {
    sourceHashes[file] = createHash('sha256').update(await readFile(join(root, '../..', file))).digest('hex')
  }
  await writeFile(join(output, 'ui-manifest.json'), JSON.stringify({
    base_revision: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    provenance: 'actual frontend screenshot of synthetic demo_fixture; no inference run',
    chromium: browser.version(), source_hashes: sourceHashes, overview_counts: overviewCounts,
    page_errors: errors, api_requests: apiRequests, screenshots: records,
  }, null, 2) + '\n')
  console.log('PASS: 7 screenshots, session-count captions, four presentation steps and return, no page errors/API requests/overflow')
} finally { await browser.close() }
