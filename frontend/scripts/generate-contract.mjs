import { execFileSync } from 'node:child_process'
import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import openapiTS, { astToString } from 'openapi-typescript'

const backend = fileURLToPath(new URL('../../backend/', import.meta.url))
const python = process.env.BACKEND_PYTHON || fileURLToPath(new URL('../../.venv/bin/python', import.meta.url))
// Import only: no lifespan, database connection, migration, or server startup.
const schema = JSON.parse(execFileSync(python, ['-c', 'import json; from app.main import app; print(json.dumps(app.openapi()))'], {
  cwd: backend,
  env: { ...process.env, ENVIRONMENT: 'test', DATABASE_URL: 'sqlite://', SCHEDULER_ENABLED: 'false' },
  encoding: 'utf8', maxBuffer: 8 * 1024 * 1024,
}))
const file = new URL('../src/api/generated.ts', import.meta.url)
const schemaFile = new URL('../contracts/openapi.json', import.meta.url)
const schemaContent = JSON.stringify(schema, null, 2) + '\n'
const content = '// Generated from the current backend OpenAPI by openapi-typescript 7.13.0. Do not edit.\n' + astToString(await openapiTS(schema, { alphabetize: true }))
if (process.argv.includes('--check')) {
  if (await readFile(file, 'utf8') !== content) throw new Error('Backend OpenAPI drift detected. Run npm run generate:api and review the contract changes.')
  if (await readFile(schemaFile, 'utf8') !== schemaContent) throw new Error('Backend schema snapshot drift detected. Run npm run generate:api.')
  console.log(`PASS: generated TypeScript matches the current backend (${Object.keys(schema.paths).length} paths).`)
} else {
  await writeFile(file, content)
  await writeFile(schemaFile, schemaContent)
  console.log(`Generated ${fileURLToPath(file)} from ${Object.keys(schema.paths).length} backend paths.`)
}
