import { createServer } from 'node:http'
import { readFile, writeFile, mkdir, stat } from 'node:fs/promises'
import { resolve, dirname, extname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { spawn, execFileSync } from 'node:child_process'
import { once } from 'node:events'
import { chromium } from '../../frontend/node_modules/@playwright/test/index.mjs'

const directory = dirname(fileURLToPath(import.meta.url))
const root = resolve(directory, '../..')
const story = JSON.parse(await readFile(resolve(directory, 'storyboard.json'), 'utf8'))
const capture = process.argv.includes('--capture')
const video = !process.argv.includes('--stills-only')
const origin = process.env.OVERVIEW_APP_URL || 'http://127.0.0.1:4180/'
if (capture && !['127.0.0.1', 'localhost'].includes(new URL(origin).hostname)) {
  throw new Error('Capture must use a local demo, not a deployed workspace')
}
await mkdir(resolve(directory, 'assets'), { recursive: true })
const qa = resolve(root, 'output/overview-qa')
await mkdir(qa, { recursive: true })
const browser = await chromium.launch()
let server, encoder
try {
  if (capture) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 960 } })
    const issues = []
    page.on('pageerror', error => issues.push(error.message))
    page.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/api/')) issues.push('Unexpected API call')
    })
    for (const [name, route, title] of [
      ['dashboard', '', 'Обзор'], ['schedule', 'schedule', 'Расписание'],
      ['recognition', 'recognition', 'Распознавание'], ['analytics', 'analytics', 'Аналитика'],
    ]) {
      await page.goto(`${origin.replace(/#.*$/, '')}#/${route}`, { waitUntil: 'networkidle' })
      await page.getByRole('heading', { level: 1, name: title, exact: true }).waitFor()
      if (!(await page.locator('body').innerText()).includes('Учебный пример')) {
        throw new Error('Only synthetic demo data may appear in the public overview')
      }
      await page.evaluate(async () => {
        await document.fonts.ready
        await Promise.all([...document.images].map(image => image.decode()))
      })
      const options = { path: resolve(directory, `assets/${name}.png`), animations: 'disabled' }
      if (name === 'dashboard') await page.screenshot({ ...options, clip: { x: 0, y: 0, width: 1440, height: 960 } })
      else await page.locator('#main-content').screenshot(options)
      console.log(`Captured ${route || 'dashboard'}`)
    }
    if (issues.length) throw new Error(issues.join('\n'))
    await page.close()
  }

  const fontRoot = resolve(root, 'frontend/node_modules/@fontsource-variable/golos-text/files')
  server = createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname)
      const path = resolve(root, '.' + pathname)
      if (![directory, fontRoot].some(base => path.startsWith(base + '/'))) {
        response.writeHead(403).end(); return
      }
      const mime = { '.html': 'text/html; charset=utf-8', '.png': 'image/png', '.woff2': 'font/woff2' }
      response.writeHead(200, { 'Content-Type': mime[extname(path)] || 'application/octet-stream' })
      response.end(await readFile(path))
    } catch { response.writeHead(404).end() }
  })
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`http://127.0.0.1:${server.address().port}/docs/overview/composition.html`)
  await page.evaluate(story => window.init(story), story)
  const layout = []
  for (const [i, chapter] of story.chapters.entries()) {
    await page.evaluate(t => window.seek(t), chapter.start + 2)
    const problems = await page.evaluate(() => {
      const scene = document.querySelector('.scene.active')
      return [...scene.querySelectorAll('h1,h2,h3,p,.note,.settings,.code-row,.mode-row,.screen-label')]
        .filter(node => {
          const box = node.getBoundingClientRect()
          return box.right > 1544 || box.bottom > 759 || node.scrollWidth > node.clientWidth + 2
        }).map(node => node.textContent)
    })
    if (problems.length) throw new Error(`Overflow in ${chapter.scene}: ${problems.join('; ')}`)
    await page.screenshot({ path: resolve(qa, `${i + 1}-${chapter.scene}.png`) })
    await page.evaluate(t => window.seek(t), chapter.end - 1)
    await page.screenshot({ path: resolve(qa, `${i + 1}-${chapter.scene}-end.png`) })
    layout.push({ scene: chapter.scene, overflow: false })
  }
  await page.evaluate(() => window.seek(3))
  await page.screenshot({ path: resolve(directory, 'poster.jpg'), type: 'jpeg', quality: 94 })
  if (errors.length) throw new Error(errors.join('\n'))

  const timestamp = n => `${String(Math.floor(n / 3600)).padStart(2, '0')}:${String(Math.floor(n / 60) % 60).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}.000`
  await writeFile(resolve(directory, 'captions.ru.vtt'), 'WEBVTT\n\n' + story.captions.map(c =>
    `${timestamp(c.start)} --> ${timestamp(c.end)}\n${c.text}\n`).join('\n'))

  if (video) {
    const output = resolve(directory, 'project-overview-ru.mp4')
    encoder = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y',
      '-threads', '1', '-f', 'image2pipe', '-framerate', '12', '-vcodec', 'mjpeg', '-i', '-',
      '-an', '-vf', 'fps=24,format=yuv420p', '-c:v', 'libx264', '-threads', '2',
      '-preset', 'fast', '-crf', '23', '-movflags', '+faststart', output], { stdio: ['pipe', 'ignore', 'pipe'] })
    let stderr = ''
    encoder.stderr.on('data', chunk => { stderr += chunk })
    const done = once(encoder, 'close')
    for (let frame = 0; frame < story.duration * 12; frame++) {
      await page.evaluate(t => window.seek(t), frame / 12)
      const bytes = await page.screenshot({ type: 'jpeg', quality: 87 })
      if (!encoder.stdin.write(bytes)) await once(encoder.stdin, 'drain')
      if (frame % 120 === 0) console.log(`Rendered ${frame / 12}/${story.duration}s`)
    }
    encoder.stdin.end()
    const [code] = await done
    if (code) throw new Error(stderr || `ffmpeg exited ${code}`)
    const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_format', '-show_streams', '-of', 'json', output]))
    const stream = probe.streams.find(s => s.codec_type === 'video')
    if (Math.abs(Number(probe.format.duration) - story.duration) > .1 || stream.width !== 1600 || stream.height !== 900) {
      throw new Error('Unexpected video dimensions or duration')
    }
    const size = (await stat(output)).size
    if (size > 20 * 1024 * 1024) throw new Error('Overview exceeds the 20 MiB repository budget')
    await writeFile(resolve(directory, 'manifest.json'), JSON.stringify({
      code_revision: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
      source: 'local frontend in static demo mode; synthetic fixtures only',
      backend_diagrams: 'explanation of server code, not a recording of a running backend',
      audio: 'none; Russian captions burned into the video and supplied as WebVTT',
      duration_seconds: Number(probe.format.duration), width: stream.width, height: stream.height,
      codec: stream.codec_name, bytes: size,
      sha256: createHash('sha256').update(await readFile(output)).digest('hex'),
      layout, browser_errors: errors,
    }, null, 2) + '\n')
    console.log(`Video verified: ${story.duration}s, ${(size / 1024 / 1024).toFixed(2)} MiB`)
  }
} finally {
  if (encoder && encoder.exitCode === null) encoder.kill('SIGTERM')
  await browser.close()
  if (server) server.close()
}
