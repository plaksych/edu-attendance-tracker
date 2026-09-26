import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { once } from 'node:events'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { chromium } from '../../frontend/node_modules/@playwright/test/index.mjs'

const directory = dirname(fileURLToPath(import.meta.url))
const root = resolve(directory, '../..')
const story = JSON.parse(await readFile(resolve(directory, 'storyboard.json')))
const manifest = JSON.parse(await readFile(resolve(directory, 'manifest.json')))
for (const entries of [story.chapters, story.captions]) {
  let end = 0
  for (const entry of entries) {
    assert.equal(entry.start, end, 'Timeline has a gap or overlap')
    assert(entry.end > entry.start)
    end = entry.end
  }
  assert.equal(end, story.duration)
}
const bytes = await readFile(resolve(directory, 'project-overview-ru.mp4'))
assert.equal(createHash('sha256').update(bytes).digest('hex'), manifest.sha256)
execFileSync('ffmpeg', ['-v', 'error', '-threads', '2', '-i', resolve(directory, 'project-overview-ru.mp4'), '-f', 'null', '-'], { stdio: 'pipe' })
const preview = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-count_frames',
  '-show_entries', 'stream=width,height,nb_read_frames:format=duration', '-of', 'json', resolve(directory, 'preview.gif')]))
assert.equal(Number(preview.streams[0].nb_read_frames), story.chapters.length)
assert.equal(Number(preview.format.duration), 16)

const files = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/project-overview-ru.mp4', ['project-overview-ru.mp4', 'video/mp4']],
  ['/poster.jpg', ['poster.jpg', 'image/jpeg']],
  ['/captions.ru.vtt', ['captions.ru.vtt', 'text/vtt; charset=utf-8']],
])
const server = createServer(async (request, response) => {
  const entry = files.get(new URL(request.url, 'http://localhost').pathname)
  if (!entry) { response.writeHead(404).end(); return }
  try {
    const data = await readFile(resolve(directory, entry[0]))
    const range = request.headers.range?.match(/^bytes=(\d+)-(\d*)$/)
    const start = range ? Number(range[1]) : 0
    const end = range?.[2] ? Math.min(Number(range[2]), data.length - 1) : data.length - 1
    if (start > end) { response.writeHead(416).end(); return }
    response.writeHead(range ? 206 : 200, {
      'Content-Type': entry[1], 'Content-Length': end - start + 1,
      'Accept-Ranges': 'bytes',
      ...(range ? { 'Content-Range': `bytes ${start}-${end}/${data.length}` } : {}),
    })
    response.end(data.subarray(start, end + 1))
  } catch { response.writeHead(500).end() }
})
server.listen(0, '127.0.0.1')
await once(server, 'listening')
const browser = await chromium.launch({ channel: 'chrome' })
try {
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  const qa = resolve(root, 'output/overview-qa')
  await mkdir(qa, { recursive: true })
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 960 })
    await page.goto(`http://127.0.0.1:${server.address().port}/`)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    assert.equal(await page.locator('[data-time]').count(), story.chapters.length)
    await page.locator('[data-time="34"]').click()
    await page.waitForFunction(() => {
      const video = document.querySelector('video')
      return (video.currentTime >= 34 && video.readyState >= 2) || video.error
    }, null, { timeout: 15000 }).catch(async error => {
      console.error(await page.evaluate(() => {
        const v = document.querySelector('video')
        return { readyState: v.readyState, networkState: v.networkState, source: v.currentSrc, time: v.currentTime, error: v.error?.message }
      }))
      throw error
    })
    assert.equal(await page.evaluate(() => document.querySelector('video').error?.message || null), null)
    await page.evaluate(() => document.querySelector('video').pause())
    await page.screenshot({ path: resolve(qa, `player-${width}.png`), fullPage: true })
  }
  for (const t of [3, 22, 47, 59, 85]) {
    const pixels = await page.evaluate(async t => {
      const video = document.querySelector('video')
      const seeked = new Promise(resolve => video.addEventListener('seeked', resolve, { once: true }))
      video.currentTime = t
      await seeked
      const canvas = document.createElement('canvas')
      canvas.width = 320; canvas.height = 180
      const context = canvas.getContext('2d')
      context.drawImage(video, 0, 0, 320, 180)
      const data = context.getImageData(0, 0, 320, 180).data
      let dark = 0, light = 0
      for (let i = 0; i < data.length; i += 4) {
        if (data[i] < 160 && data[i+1] < 160 && data[i+2] < 160) dark++
        if (data[i] > 225 && data[i+1] > 225 && data[i+2] > 225) light++
      }
      return { dark, light, duration: video.duration, error: video.error?.message || null }
    }, t)
    assert(pixels.dark > 500 && pixels.light > 15000, `Blank frame at ${t}s`)
    assert.equal(pixels.duration, story.duration)
    assert.equal(pixels.error, null)
  }
  const markdown = await readFile(resolve(root, 'README.md'), 'utf8')
  const diagram = markdown.match(/```mermaid\n([\s\S]*?)```/)[1]
  await page.addScriptTag({ path: resolve(root, 'docs/diagrams/node_modules/mermaid/dist/mermaid.min.js') })
  await page.evaluate(async source => {
    window.mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' })
    await window.mermaid.parse(source)
  }, diagram)
  assert.deepEqual(errors, [])
  await writeFile(resolve(qa, 'checks.json'), JSON.stringify({
    status: 'passed', sha256: manifest.sha256, duration: story.duration,
    decoded_entire_video: true, viewports: [390, 768, 1440],
    nonblank_video_frames: [3, 22, 47, 59, 85], chapters: story.chapters.length,
    timeline_continuous: true, readme_mermaid: 'parsed', preview_frames: 8, browser_errors: errors,
  }, null, 2) + '\n')
  console.log('PASS: full video decode, SHA-256, timelines, responsive player, chapter navigation, nonblank frames and README diagram')
} finally {
  await browser.close()
  server.close()
}
