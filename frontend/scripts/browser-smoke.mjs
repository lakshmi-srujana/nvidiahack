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
const expectStatus = async (status) => {
  await page.waitForFunction(expected => document.querySelector('.status-pill')?.textContent?.trim() === expected, status)
  assert.equal(await page.locator('.status-pill').innerText(), status)
}

try {
  await page.goto(baseURL)
  await page.getByText('BACKEND CONNECTED').waitFor()
  await expectStatus('DRAFT')
  await page.getByRole('button', { name: 'Verify plan' }).click()
  await page.getByText('All checks passed').waitFor()
  await expectStatus('CERTIFIED')
  await page.getByRole('button', { name: 'Launch simulation' }).click()
  await expectStatus('ACTIVE')
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

  await page.getByText('Create a survey area').click()
  await page.getByRole('button', { name: 'Create survey' }).click()
  await expectStatus('DRAFT')
  await page.getByRole('button', { name: 'Verify plan' }).click()
  await expectStatus('CERTIFIED')
  await page.screenshot({ path: '../results/browser-smoke.png', fullPage: true })
  await page.setViewportSize({ width: 375, height: 812 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true)
  await page.screenshot({ path: '../results/browser-smoke-mobile.png', fullPage: true })
  assert.deepEqual(pageErrors, [])
  console.log('Browser smoke passed: nominal launch, event/replan, three unsafe scenarios, custom survey, mobile width; no page errors')
} finally {
  await browser.close()
}
