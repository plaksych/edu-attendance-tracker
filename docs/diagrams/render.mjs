import { createRequire } from 'node:module'
import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'

const root = dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const mermaidRoot = process.env.MERMAID_ROOT || dirname(require.resolve('mermaid/package.json'))
const playwrightRoot = process.env.PLAYWRIGHT_ROOT || dirname(require.resolve('playwright/package.json'))
const version = async path => JSON.parse(await readFile(join(path, 'package.json'), 'utf8')).version
if (await version(mermaidRoot) !== '11.17.2' || await version(playwrightRoot) !== '1.63.0') {
  throw new Error('Expected Mermaid 11.17.2 and Playwright 1.63.0')
}
const { chromium } = await import(pathToFileURL(join(playwrightRoot, 'index.mjs')))
const browser = await chromium.launch({
  ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}),
  headless: true,
})
const check = process.argv.includes('--check')
const output = join(root, 'rendered')
const sha = value => createHash('sha256').update(value).digest('hex')
const baseline = check ? JSON.parse(await readFile(join(output, 'manifest.json'), 'utf8')) : undefined
const records = []
try {
  await mkdir(output, { recursive: true })
  const page = await browser.newPage({ viewport: { width: 1800, height: 1200 }, deviceScaleFactor: 1 })
  await page.setContent('<html lang="ru"><body style="margin:0;background:white"><main></main></body></html>')
  await page.addScriptTag({ path: join(mermaidRoot, 'dist/mermaid.min.js') })
  const sources = (await readdir(join(root, 'src'))).filter(name => name.endsWith('.mmd')).sort()
  if (check && (baseline.diagrams.length !== sources.length ||
    baseline.diagrams.some(item => !sources.includes(`${item.id}.mmd`)))) {
    throw new Error('Source set differs from manifest')
  }
  for (const file of sources) {
    const source = await readFile(join(root, 'src', file), 'utf8')
    const id = file.replace('.mmd', '')
    const rendered = await page.evaluate(async ({ source, id }) => {
      mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'base',
        deterministicIds: true, deterministicIDSeed: id, handDrawnSeed: 42,
        fontFamily: 'Arial, sans-serif',
        themeVariables: { primaryColor: '#e8f2ef', primaryTextColor: '#182b28',
          primaryBorderColor: '#477365', lineColor: '#56626c', secondaryColor: '#eef1f5',
          tertiaryColor: '#fff4d9', fontSize: '16px' },
        flowchart: { htmlLabels: false, useMaxWidth: false },
        sequence: { useMaxWidth: false }, er: { useMaxWidth: false },
        state: { useMaxWidth: false } })
      await mermaid.parse(source)
      const { svg } = await mermaid.render(id, source)
      document.querySelector('main').innerHTML = svg
      await document.fonts.ready
      const element = document.querySelector('main svg')
      // Mermaid's SVG text labels can outgrow their generated background rectangle.
      for (const label of element.querySelectorAll('.edgeLabel')) {
        const text = label.querySelector('text')
        const background = label.querySelector('rect.background')
        if (!text || !background) continue
        const bounds = text.getBBox()
        for (const [key, value] of Object.entries({ x: bounds.x - 3, y: bounds.y - 2,
          width: bounds.width + 6, height: bounds.height + 4 })) background.setAttribute(key, String(value))
        background.style.fill = '#ffffff'
        background.style.opacity = '1'
      }
      const box = element.getBoundingClientRect()
      if (box.width < 50 || box.height < 50) throw new Error('Blank diagram')
      return { svg: element.outerHTML, width: Math.ceil(box.width), height: Math.ceil(box.height) }
    }, { source, id })
    const png = await page.locator('main svg').screenshot({ animations: 'disabled' })
    if (png.length < 1000) throw new Error(`Blank PNG: ${id}`)
    if (check) {
      const previous = await readFile(join(output, `${id}.svg`), 'utf8')
      if (previous !== rendered.svg) {
        let at = 0
        while (at < previous.length && previous[at] === rendered.svg[at]) at++
        throw new Error(`Stale SVG: ${id}; first difference ${at}: ${previous.slice(at, at + 120)} / ${rendered.svg.slice(at, at + 120)}`)
      }
      const record = baseline.diagrams.find(item => item.id === id)
      if (!record || record.source_sha256 !== sha(source) || record.png_sha256 !== sha(await readFile(join(output, `${id}.png`)))) {
        throw new Error(`Stale or modified PNG/source: ${id}`)
      }
    } else {
      await writeFile(join(output, `${id}.svg`), rendered.svg)
      await writeFile(join(output, `${id}.png`), png)
    }
    records.push({ id, source_sha256: sha(source), svg_sha256: sha(rendered.svg), png_sha256: sha(png),
      width: rendered.width, height: rendered.height })
    console.log(`${check ? 'CHECK' : 'RENDER'} ${id}: ${rendered.width}x${rendered.height}`)
  }
  if (!check) {
    const revision = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()
    await writeFile(join(output, 'manifest.json'), JSON.stringify({ base_revision: revision,
      note: 'Working-tree documentation, not a release validation. Browser/font versions affect pixels.',
      mermaid: '11.17.2', playwright: '1.63.0', chromium: browser.version(), diagrams: records }, null, 2) + '\n')
    await writeFile(join(output, 'render-log.txt'), `Mermaid 11.17.2; Playwright 1.63.0; Chromium ${browser.version()}\n` +
      records.map(r => `PASS ${r.id}: ${r.width}x${r.height}; source=${r.source_sha256}`).join('\n') + '\n')
    const thumbnails = records.map(({ id }) => `<figure><img src="${id}.svg" alt="${id}"><figcaption>${id}</figcaption></figure>`).join('\n')
    await writeFile(join(output, 'index.html'), `<!doctype html><html lang="ru"><meta charset="utf-8"><title>D01-D14</title><style>body{font:16px Arial;margin:24px;color:#182b28}figure{margin:0 0 32px;break-inside:avoid}img{max-width:100%;height:auto}figcaption{font-weight:bold;padding:8px}</style><h1>Схемы текущего кода</h1>${thumbnails}</html>\n`)
  }
} finally {
  await browser.close()
}
