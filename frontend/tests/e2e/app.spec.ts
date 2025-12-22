import { test, expect } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const exposureCsv = path.resolve(__dirname, '..', '..', '..', 'sample_data', 'exposure_small.csv')

test('end-to-end happy path', async ({ page }) => {
  test.setTimeout(180000)

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()

  await page.locator('input[name="tenant_id"]').fill('demo')
  await page.locator('input[name="email"]').fill('admin@demo.com')
  await page.locator('input[name="password"]').fill('password')
  await page.getByRole('button', { name: 'Login' }).click()

  await expect(page.getByRole('heading', { name: 'Upload wizard' })).toBeVisible()

  const fileInput = page.locator('input[type="file"]').first()
  await fileInput.setInputFiles(exposureCsv)
  await expect(page.getByText(/Upload ID/)).toBeVisible()

  await page.getByRole('button', { name: 'Auto mapping' }).click()
  await page.getByRole('button', { name: 'Save mapping' }).click()
  await expect(page.getByRole('button', { name: 'Save mapping' })).toBeEnabled()

  await page.getByRole('button', { name: 'Validate' }).click()
  const commitButton = page.getByRole('button', { name: 'Commit' })
  await expect(commitButton).toBeEnabled({ timeout: 120000 })
  await commitButton.click()

  await expect(page).toHaveURL(/exposure-versions\/\d+/, { timeout: 120000 })
  const exposureId = new URL(page.url()).pathname.split('/').pop()
  expect(exposureId).toBeTruthy()
  const locationRows = page.locator('table tbody tr')
  expect(await locationRows.count()).toBeGreaterThan(0)

  await page.getByRole('link', { name: 'Exposure Versions' }).click()
  await expect(page.getByRole('heading', { name: 'Exposure versions' })).toBeVisible()
  await page.locator('text=Loading...').waitFor({ state: 'detached' })
  await expect.poll(async () => await page.locator('table tbody tr').count(), { timeout: 120000 }).toBeGreaterThan(0)
  if (exposureId) {
    await expect(page.locator(`a[href="/exposure-versions/${exposureId}"]`)).toBeVisible()
  }

  await page.getByRole('link', { name: 'Exceptions' }).click()
  await expect(page.getByRole('heading', { name: 'Exceptions' })).toBeVisible()
  if (exposureId) {
    await page.locator('select').selectOption(exposureId)
  } else {
    await page.locator('select').selectOption({ index: 1 })
  }
  await page.locator('text=Loading...').waitFor({ state: 'detached' })
  const exceptionRows = page.locator('table tbody tr')
  if ((await exceptionRows.count()) === 0) {
    await expect(page.getByText('No exceptions for this version.')).toBeVisible()
  }

  await page.getByRole('link', { name: 'Runs' }).click()
  await expect(page.getByRole('heading', { name: 'Runs' })).toBeVisible()
  await expect.poll(async () => await page.locator('table tbody tr').count(), { timeout: 120000 }).toBeGreaterThan(0)

  await page.getByRole('link', { name: 'Audit Log' }).click()
  await expect(page.getByRole('heading', { name: 'Audit log' })).toBeVisible()
  await expect.poll(async () => await page.locator('table tbody tr').count(), { timeout: 120000 }).toBeGreaterThan(0)
  await expect.poll(async () => await page.locator('table tbody tr').filter({ hasText: 'login' }).count()).toBeGreaterThan(0)
  await expect.poll(async () => await page.locator('table tbody tr').filter({ hasText: 'upload_created' }).count()).toBeGreaterThan(0)

  await page.getByRole('link', { name: 'Threshold Rules' }).click()
  await expect(page.getByRole('heading', { name: 'Threshold rules' })).toBeVisible()
  const ruleName = `QA Rule ${Date.now()}`
  await page.getByPlaceholder('Name').fill(ruleName)
  await page.getByRole('button', { name: 'Create rule' }).click()
  await expect(page.getByText(ruleName)).toBeVisible()
})
