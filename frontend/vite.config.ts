import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { rm } from 'node:fs/promises'
import { resolve } from 'node:path'
let outputDirectory = ''

export default defineConfig({
  plugins: [react(), {
    name: 'omit-unverified-demo-media',
    apply: 'build',
    configResolved(config) { outputDirectory = resolve(config.root, config.build.outDir) },
    async closeBundle() {
      // These legacy photographs are not part of the synthetic fixture or live product.
      await rm(resolve(outputDirectory, 'recognition-demo'), { recursive: true, force: true })
      if (process.env.VITE_STATIC_DATA !== 'true') await rm(resolve(outputDirectory, 'synthetic-classroom.png'), { force: true })
    },
  }],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/media': 'http://localhost:8000',
    },
  },
})
