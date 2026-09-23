import { readFile, access, readdir } from 'node:fs/promises'
import { dirname, resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const files = ['README.md', ...['architecture', 'data-model', 'recognition', 'api', 'security', 'demo', 'testing'].map(n => `docs/${n}.md`)]
for (const dir of ['docs/diagrams', 'docs/adr']) {
  for (const name of await readdir(join(repo, dir))) if (name.endsWith('.md')) files.push(`${dir}/${name}`)
}
const missing = []
let count = 0
for (const file of files) {
  const content = await readFile(join(repo, file), 'utf8')
  for (const match of content.matchAll(/\]\(([^)]+)\)/g)) {
    const target = match[1].split('#')[0]
    if (!target || /^[a-z]+:/i.test(target)) continue
    count++
    try { await access(resolve(repo, dirname(file), decodeURIComponent(target))) }
    catch { missing.push(`${file}: ${target}`) }
  }
}
console.log(`Checked ${count} local file links in ${files.length} owned documents; anchors and remote URLs not checked.`)
if (missing.length) { console.error(missing.join('\n')); process.exitCode = 1 }
