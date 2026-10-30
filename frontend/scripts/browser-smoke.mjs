import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { chromium } from 'playwright'

const browserPath = process.env.SKYWARDEN_BROWSER_BIN || (
  process.platform === 'win32' && existsSync('C:/Program Files/Google/Chrome/Application/chrome.exe')
    ? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
    : undefined
)
const baseURL = process.env.SKYWARDEN_UI_URL || 'http://127.0.0.1:5173/'
const browser = await chromium.launch({ headless: true, ...(browserPath ? { executablePath: browserPath } : {}) })
const page = await browser.newPage({ viewport: { width: 1365, height: 900 } })
const pageErrors = []
page.on('pageerror', error => pageErrors.push(error.message))
const tileRequests = []
page.on('request', request => {
  if (request.url().startsWith('https://tile.openstreetmap.org/')) tileRequests.push(request.url())
})
const expectStatus = async (status) => {
  await page.waitForFunction(expected => document.querySelector('.status-pill')?.textContent?.trim() === expected, status)
  assert.equal(await page.locator('.status-pill').innerText(), status)
}

try {
  await page.request.post(new URL('/api/v1/demo/scenario/flood', baseURL).toString(), { data: {} })
  await page.goto(baseURL)
  await page.getByText('BACKEND CONNECTED').waitFor()
  await page.locator('.maplibregl-canvas').waitFor()
  await page.getByRole('region', { name: /OpenStreetMap basemap/ }).waitFor()
  await page.getByText('© OpenStreetMap contributors').first().waitFor()
  await page.waitForFunction(() => document.querySelectorAll('.maplibregl-canvas').length === 1)
  for (let attempt = 0; tileRequests.length === 0 && attempt < 30; attempt++) await page.waitForTimeout(100)
  assert.ok(tileRequests.some(url => /^https:\/\/tile\.openstreetmap\.org\/\d+\/\d+\/\d+\.png$/.test(url)), 'The map must request official OpenStreetMap raster tiles')
  await expectStatus('DRAFT')
  await page.getByRole('button', { name: 'Verify plan' }).click()
  await page.getByText('All checks passed').waitFor()
  await expectStatus('CERTIFIED')
  await page.getByRole('button', { name: 'Launch simulation' }).click()
  await expectStatus('ACTIVE')
  await page.waitForFunction(() => Number.parseFloat(document.querySelector('.metrics > div:nth-child(4) strong')?.textContent || '0') > 0)
  await page.getByRole('combobox', { name: 'Event family' }).selectOption('SURVIVOR_DETECTED')
  await page.getByRole('button', { name: 'Inject event' }).click()
  await expectStatus('INTERVENTION REQUIRED')
  await page.getByRole('button', { name: /Replan & verify/ }).click()
  await expectStatus('CERTIFIED')

  for (const scenario of ['dam', 'wind', 'battery']) {
    await page.getByLabel('Scenario').selectOption(scenario)
    await page.getByRole('button', { name: 'Verify plan' }).click()
    await expectStatus('REJECTED')
    assert.equal(await page.getByRole('button', { name: 'Launch simulation' }).isDisabled(), true)
    assert.ok(await page.locator('.violation').count() > 0)
  }

  await page.route('**/api/v1/demo/location/search?*', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ source: 'OpenStreetMap Nominatim', results: [{
      label: 'MG Road, Bengaluru', latitude: 12.975, longitude: 77.605,
      bounds: [77.604, 12.974, 77.606, 12.976], osm_type: 'way', osm_id: 123,
    }] }),
  }))
  await page.getByLabel('Address or Indian PIN code').fill('560001')
  await page.getByRole('button', { name: 'Find on map' }).click()
  await page.getByRole('button', { name: /MG Road, Bengaluru/ }).click()
  await page.getByText('12.975000°, 77.605000°').waitFor()
  await page.unroute('**/api/v1/demo/location/search?*')

  await page.getByLabel('Seeded scenario').selectOption('flood')
  await expectStatus('DRAFT')
  for (let attempt = 0; attempt < 6; attempt++) {
    await page.locator('.maplibregl-ctrl-zoom-in').click()
    await page.waitForTimeout(350)
  }
  await page.getByRole('button', { name: 'Lock visible area' }).click()
  await expectStatus('DRAFT')
  await page.waitForFunction(() => document.querySelector('#scenario')?.value === 'custom')
  assert.equal(await page.getByLabel('Seeded scenario').inputValue(), 'custom')
  await page.getByLabel('Zone type').selectOption('safe')
  await page.getByRole('button', { name: 'Draw safe zone' }).click()
  const map = page.getByRole('region', { name: /OpenStreetMap basemap/ })
  await map.click({ position: { x: 390, y: 170 } })
  await map.click({ position: { x: 430, y: 170 } })
  await map.click({ position: { x: 430, y: 205 } })
  await map.click({ position: { x: 390, y: 205 } })
  await page.getByRole('button', { name: 'Finish drawing' }).click()
  await page.locator('.zone-row').filter({ hasText: 'Safe zone' }).waitFor()
  await page.getByRole('button', { name: /Auto route/ }).click()
  await expectStatus('CERTIFIED')
  await page.getByRole('button', { name: 'Verify & start simulation' }).click()
  await expectStatus('ACTIVE')
  await page.waitForFunction(() => Number.parseFloat(document.querySelector('.metrics > div:nth-child(4) strong')?.textContent || '0') > 0)
  await page.getByRole('combobox', { name: 'Event family' }).selectOption('NEW_RESTRICTED_ZONE')
  await page.getByRole('button', { name: 'Draw & inject zone' }).click()
  await map.click({ position: { x: 445, y: 175 } })
  await map.click({ position: { x: 475, y: 175 } })
  await map.click({ position: { x: 475, y: 205 } })
  await page.getByRole('button', { name: 'Finish drawing' }).click()
  await expectStatus('INTERVENTION REQUIRED')
  await page.waitForTimeout(1500)
  await page.screenshot({ path: '../results/browser-smoke.png', fullPage: true })
  await page.setViewportSize({ width: 375, height: 812 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true)
  await page.screenshot({ path: '../results/browser-smoke-mobile.png', fullPage: true })
  assert.deepEqual(pageErrors, [])
  console.log('Browser smoke passed: nominal launch, event/replan, three unsafe scenarios, custom survey, mobile width; no page errors')
} catch (error) {
  await page.screenshot({ path: '../results/browser-smoke-failure.png', fullPage: true })
  console.error('Browser status:', await page.locator('body').innerText())
  console.error('Page errors:', pageErrors)
  throw error
} finally {
  await browser.close()
}
