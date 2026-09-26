import { readdir, readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
const directory = resolve(process.argv[2] || 'dist')
await readFile(resolve(directory, 'index.html'))
async function walk(path) {
  for (const entry of await readdir(path, { withFileTypes: true })) {
    const file = resolve(path, entry.name)
    if (/staticClient|synthetic-classroom|demo-data|recognition-demo/.test(entry.name)) throw new Error(`Fixture in production build: ${file}`)
    if (entry.isDirectory()) await walk(file)
    else if (/\.(js|html|json)$/.test(entry.name)) {
      const text = await readFile(file, 'utf8')
      if (/synthetic-classroom|Учебная группа [123]|classroom-eight|lecture-twelve|demo-data\.json|recognition-demo/.test(text)) throw new Error(`Fixture reference in production bytes: ${file}`)
    }
  }
}
await walk(directory)
console.log('PASS: production bytes exclude the synthetic fixture adapter, fixture identities, and demo media.')
