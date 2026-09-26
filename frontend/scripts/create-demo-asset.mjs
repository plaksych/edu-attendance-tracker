import { chromium } from '@playwright/test'
import { fileURLToPath } from 'node:url'

// An authored diagram, not a photograph, detector output, or classroom evidence.
const browser = await chromium.launch()
try {
  const page = await browser.newPage({ viewport: { width: 960, height: 580 }, deviceScaleFactor: 1 })
  await page.setContent('<body style="margin:0"><canvas width="960" height="580"></canvas></body>')
  await page.evaluate(() => {
    const c = document.querySelector('canvas').getContext('2d')
    c.fillStyle = '#eef3f5'; c.fillRect(0, 0, 960, 580)
    c.fillStyle = '#ffffff'; c.fillRect(40, 35, 880, 510)
    c.strokeStyle = '#b4c5ce'; c.lineWidth = 2; c.strokeRect(40, 35, 880, 510)
    c.fillStyle = '#255c65'; c.fillRect(300, 54, 360, 26)
    c.font = '14px sans-serif'; c.fillStyle = '#ffffff'; c.textAlign = 'center'; c.fillText('BOARD', 480, 73)
    for (let row = 0; row < 3; row++) {
      for (let col = 0; col < 6; col++) {
        const x = 100 + col * 140; const y = 132 + row * 128
        c.fillStyle = '#e3eaf0'; c.fillRect(x, y, 64, 35)
        c.fillStyle = col % 3 === 0 ? '#b06c1d' : col % 3 === 1 ? '#2c699a' : '#27786c'
        c.beginPath(); c.arc(x + 32, y + 60, 15, 0, Math.PI * 2); c.fill()
        c.fillStyle = '#ffffff'; c.font = '12px sans-serif'; c.fillText(String(row * 6 + col + 1), x + 32, y + 64)
      }
    }
    c.fillStyle = '#516771'; c.font = '14px sans-serif'; c.fillText('SYNTHETIC DIAGRAM / 18 MARKERS / NOT INFERENCE', 480, 513)
  })
  await page.locator('canvas').screenshot({ path: fileURLToPath(new URL('../public/synthetic-classroom.png', import.meta.url)) })
} finally { await browser.close() }
