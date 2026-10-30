import assert from 'node:assert/strict'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { chromium } from 'playwright'

const baseURL = process.env.SKYWARDEN_UI_URL || 'http://127.0.0.1:5174/'
const browserPath = process.platform === 'win32' && existsSync('C:/Program Files/Google/Chrome/Application/chrome.exe')
  ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : undefined
const browser = await chromium.launch({ headless: true, ...(browserPath ? { executablePath: browserPath } : {}) })
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
try {
  const survey = await page.request.post(new URL('/api/v1/demo/survey', baseURL).toString(), {
    data: { instruction: 'Survey the selected map area', west: -122.403, south: 37.793, east: -122.402, north: 37.794 },
  })
  assert.equal(survey.status(), 200)
  await page.goto(baseURL)
  await page.getByRole('button', { name: 'Review map image with local AI · no credits' }).waitFor()
  await page.locator('.maplibregl-canvas').waitFor()
  await page.waitForTimeout(1800)
  const capture = await page.locator('canvas.maplibregl-canvas').evaluate(canvas => {
    const image = canvas.toDataURL('image/png')
    return { width: canvas.width, height: canvas.height, imageLength: image.length }
  })
  assert.ok(capture.imageLength > 1000, 'Map canvas must contain a real PNG')
  console.log('Map image captured:', capture)
  mkdirSync('../results', { recursive: true })
  const imageBase64 = await page.locator('canvas.maplibregl-canvas').evaluate(canvas => canvas.toDataURL('image/png').split(',')[1])
  writeFileSync('../results/local-map-capture.png', Buffer.from(imageBase64, 'base64'))
  const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/v1/demo/vision/local'), { timeout: 150000 })
  await page.getByRole('button', { name: 'Review map image with local AI · no credits' }).click()
  const response = await responsePromise
  const payload = await response.json()
  assert.equal(response.status(), 200, JSON.stringify(payload))
  assert.equal(payload.vision_analysis.model, 'qwen3.5:2b')
  assert.equal(payload.vision_analysis.count, payload.vision_findings.length)
  assert.ok(payload.vision_findings.every(finding => finding.source === 'local_vision' && finding.review_required))
  if (payload.vision_findings.length) {
    await page.getByRole('button', { name: 'Draft zones from suggestions' }).click()
    await page.locator('.zone-row').filter({ hasText: payload.vision_findings[0].label }).waitFor()
    const zoneRows = await page.locator('.zone-row').allTextContents()
    assert.ok(zoneRows.some(row => row.includes(payload.vision_findings[0].label)))
  }
  await page.screenshot({ path: '../results/local-vision-smoke.png', fullPage: true })
  console.log('Local vision smoke passed:', payload.vision_analysis.count, 'suggestions')
} finally {
  await browser.close()
}
