import { test, expect } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'
import { attachConsoleErrorLogger, login, pollRunStatus } from './helpers'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const exposureCsv = path.resolve(__dirname, '..', 'fixtures', 'exposure_e2e.csv')
const hazardGeojson = path.resolve(__dirname, '..', 'fixtures', 'hazard_demo.geojson')

let exposureVersionId: number | null = null
let overlayResultId: number | null = null
let rollupResultId: number | null = null
let thresholdRuleId: number | null = null
let uwRuleName: string | null = null

async function extractRunIdFromText(text?: string | null) {
  if (!text) return null
  const match = text.match(/Run ID\s*(\d+)/i)
  if (match) return Number(match[1])
  return null
}

test.describe.serial('End-to-end flows', () => {
  test('Core happy-path ingestion + governance', async ({ page }) => {
    const readErrors = attachConsoleErrorLogger(page, ['Failed to load source map'])
    await login(page)

    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(exposureCsv)
    await expect(page.getByText(/Upload ID/)).toBeVisible()

    await page.getByRole('button', { name: 'Auto mapping' }).click()
    const mappingArea = page.getByPlaceholder('{"external_location_id": "external_location_id"}')
    await expect(mappingArea).toContainText('external_location_id')
    await page.getByRole('button', { name: 'Save mapping' }).click()

    await page.getByRole('button', { name: 'Validate' }).click()
    const validationRunLocator = page.getByText(/Run ID/).first()
    const validationRunText = await validationRunLocator.textContent({ timeout: 120000 })
    const validationRunId = await extractRunIdFromText(validationRunText)
    expect(validationRunId).toBeTruthy()

    if (validationRunId) {
      const runResult = await pollRunStatus(page, validationRunId)
      expect(runResult.status).toBe('SUCCEEDED')
      const errors = (runResult.output_refs_json as any)?.stats?.ERROR ?? 0
      expect(errors).toBe(0)
    }

    const commitButton = page.getByRole('button', { name: 'Commit' })
    await expect(commitButton).toBeEnabled({ timeout: 120000 })
    await commitButton.click()

    await expect(page).toHaveURL(/exposure-versions\//, { timeout: 180000 })
    const url = new URL(page.url())
    const idFromUrl = url.pathname.split('/').pop()
    exposureVersionId = idFromUrl ? Number(idFromUrl) : null
    expect(exposureVersionId).toBeTruthy()

    const locationRows = page.locator('table tbody tr')
    await expect.poll(async () => await locationRows.count(), { timeout: 120000 }).toBeGreaterThan(0)

    await page.getByRole('link', { name: 'Exposure Versions' }).click()
    await expect(page.getByRole('heading', { name: 'Exposure versions' })).toBeVisible()
    await expect.poll(async () => await page.locator('table tbody tr').count(), { timeout: 120000 }).toBeGreaterThan(0)
    if (exposureVersionId) {
      await expect(page.locator(`a[href="/exposure-versions/${exposureVersionId}"]`)).toBeVisible()
    }

    await page.getByRole('link', { name: 'Exceptions' }).click()
    await expect(page.getByRole('heading', { name: 'Exceptions' })).toBeVisible()
    if (exposureVersionId) {
      await page.locator('select').selectOption(exposureVersionId.toString())
    }
    await page.locator('text=Loading...').waitFor({ state: 'detached' })

    await page.getByRole('link', { name: 'Runs' }).click()
    await expect(page.getByRole('heading', { name: 'Runs' })).toBeVisible()
    await expect.poll(async () => await page.locator('table tbody tr').count(), { timeout: 120000 }).toBeGreaterThan(0)

    await page.getByRole('link', { name: 'Audit Log' }).click()
    await expect(page.getByRole('heading', { name: 'Audit log' })).toBeVisible()
    await expect.poll(async () => await page.locator('table tbody tr').count(), { timeout: 120000 }).toBeGreaterThan(0)

    await page.getByRole('link', { name: 'Threshold Rules' }).click()
    await expect(page.getByRole('heading', { name: 'Threshold rules' })).toBeVisible()
    const ruleName = `QA Rule ${Date.now()}`
    await page.getByPlaceholder('Name').fill(ruleName)
    await page.getByRole('button', { name: 'Create rule' }).click()
    await expect(page.getByText(ruleName)).toBeVisible()

    thresholdRuleId = Number((await page.getByText(ruleName).locator('..').locator('td').first().textContent()) || '') || null

    expect(readErrors()).toEqual([])
  })

  test('Geocode + quality run', async ({ page }) => {
    test.skip(!exposureVersionId, 'Exposure version required from ingestion test')
    const readErrors = attachConsoleErrorLogger(page, ['Failed to load source map'])
    await login(page)
    await page.goto(`/exposure-versions/${exposureVersionId}`)
    await page.getByRole('button', { name: 'Run geocode + quality' }).click()
    const statusBadge = page.getByText(/QUEUED|RUNNING|SUCCEEDED|FAILED/).first()
    await expect(statusBadge).toBeVisible()
    await expect(statusBadge).toHaveText(/SUCCEEDED|FAILED/, { timeout: 180000 })
    expect(readErrors()).toEqual([])
  })

  test('Hazard dataset upload + overlay', async ({ page }) => {
    test.skip(!exposureVersionId, 'Exposure version required')
    const readErrors = attachConsoleErrorLogger(page, ['Failed to load source map'])
    await login(page)
    await page.getByRole('link', { name: 'Hazard Datasets' }).click()
    const datasetName = `QA Hazard ${Date.now()}`
    await page.getByPlaceholder('Name').fill(datasetName)
    await page.getByPlaceholder('Peril').fill('wind')
    await page.getByRole('button', { name: 'Create' }).click()
    await expect(page.getByText(datasetName)).toBeVisible({ timeout: 120000 })

    const firstDatasetRow = page.getByText(datasetName).locator('..').locator('td').first()
    const datasetIdText = await firstDatasetRow.textContent()
    const datasetId = Number(datasetIdText || '')
    await page.locator('select').first().selectOption(datasetId.toString())

    const uploadInput = page.locator('input[type="file"]').last()
    await uploadInput.setInputFiles(hazardGeojson)

    await expect.poll(async () => await page.locator('table tbody tr').count(), { timeout: 120000 }).toBeGreaterThan(0)

    await page.getByRole('link', { name: 'Overlays' }).click()
    await page.locator('select').first().selectOption(exposureVersionId!.toString())
    await page.locator('select').nth(1).selectOption(datasetId.toString())
    await expect.poll(async () => await page.locator('select').nth(2).locator('option').count()).toBeGreaterThan(1)
    await page.locator('select').nth(2).selectOption({ index: 1 })
    await page.getByRole('button', { name: 'Start overlay' }).click()

    const overlayStatus = page.getByText(/Overlay result/)
    await expect(overlayStatus).toBeVisible({ timeout: 120000 })
    const overlayText = await overlayStatus.textContent()
    overlayResultId = overlayText ? Number(overlayText.replace(/\D+/g, '')) : null
    await expect(page.getByText(/SUCCEEDED|FAILED/)).toBeVisible({ timeout: 180000 })
    expect(readErrors()).toEqual([])
  })

  test('Rollups + drilldown', async ({ page }) => {
    test.skip(!exposureVersionId, 'Exposure required')
    const readErrors = attachConsoleErrorLogger(page, ['Failed to load source map'])
    await login(page)
    await page.getByRole('link', { name: 'Rollups' }).click()

    const configJson = {
      dimensions: ['country', 'hazard_band', 'lob'],
      measures: [
        { name: 'tiv_sum', op: 'sum', field: 'tiv' },
        { name: 'location_count', op: 'count', field: 'external_location_id' },
      ],
    }
    await page.getByPlaceholder('Config name').fill(`QA Rollup ${Date.now()}`)
    await page.locator('textarea').fill(JSON.stringify(configJson))
    await page.getByRole('button', { name: 'Save config' }).click()
    await expect.poll(async () => await page.locator('table tbody tr').count(), { timeout: 120000 }).toBeGreaterThan(0)
    const configIdText = await page.locator('table tbody tr td').first().textContent()
    const configId = Number(configIdText || '')

    await page.locator('select').first().selectOption(exposureVersionId!.toString())
    await page.locator('select').nth(1).selectOption(configId.toString())
    if (overlayResultId) {
      await page.getByPlaceholder('Overlay result IDs (comma separated)').fill(String(overlayResultId))
    }
    await page.getByRole('button', { name: 'Start rollup' }).click()

    const resultBadge = page.getByText(/Result/)
    await expect(resultBadge).toBeVisible({ timeout: 120000 })
    const rollupText = await resultBadge.textContent()
    rollupResultId = rollupText ? Number(rollupText.replace(/\D+/g, '')) : null

    await expect.poll(async () => await page.locator('table tbody tr').count(), { timeout: 180000 }).toBeGreaterThan(0)

    await page.getByPlaceholder('Drilldown key JSON').fill('{}')
    await page.getByRole('button', { name: 'Drilldown' }).click()
    await expect(page.locator('pre')).toBeVisible({ timeout: 120000 })
    expect(readErrors()).toEqual([])
  })

  test('Thresholds + breaches end-to-end', async ({ page }) => {
    test.skip(!thresholdRuleId || !rollupResultId, 'Prerequisites missing')
    const readErrors = attachConsoleErrorLogger(page, ['Failed to load source map'])
    await login(page)
    await page.getByRole('link', { name: 'Breaches' }).click()
    await page.locator('select').first().selectOption(thresholdRuleId!.toString())
    await page.locator('select').nth(1).selectOption(exposureVersionId!.toString())
    await page.getByPlaceholder('Rollup result ID').fill(String(rollupResultId))
    await page.getByRole('button', { name: 'Run evaluation' }).click()

    const breachesTable = page.locator('table tbody tr')
    await expect.poll(async () => await breachesTable.count(), { timeout: 180000 }).toBeGreaterThan(0)

    const firstRow = breachesTable.first()
    await firstRow.getByRole('button', { name: 'Ack' }).click()
    await firstRow.getByRole('button', { name: 'Resolve' }).click()
    await expect(firstRow.getByText(/RESOLVED/)).toBeVisible({ timeout: 120000 })

    expect(readErrors()).toEqual([])
  })

  test('Underwriting rules + findings + decision', async ({ page }) => {
    test.skip(!exposureVersionId, 'Exposure version required')
    const readErrors = attachConsoleErrorLogger(page, ['Failed to load source map'])
    await login(page)

    await page.getByRole('link', { name: 'Appetite & Referral Rules' }).click()
    await expect(page.getByRole('heading', { name: 'Appetite & referral rules' })).toBeVisible()
    uwRuleName = `UW Rule ${Date.now()}`
    await page.getByPlaceholder('Rule name').fill(uwRuleName)
    await page.getByPlaceholder('Value (comma separated for lists)').fill('0')
    await page.getByRole('button', { name: 'Create rule' }).click()
    await expect(page.getByText(uwRuleName)).toBeVisible()

    await page.getByRole('link', { name: 'Submission Workbench' }).click()
    await page.locator('select').first().selectOption(exposureVersionId!.toString())
    await page.getByRole('button', { name: 'Run UW eval' }).click()
    await expect(page.getByText(/QUEUED|RUNNING|SUCCEEDED|FAILED/)).toBeVisible()

    const findingRows = page.locator('table tbody tr')
    await expect.poll(async () => await findingRows.count(), { timeout: 180000 }).toBeGreaterThan(0)

    await page.getByRole('link', { name: 'Referrals' }).click()
    await page.locator('select').first().selectOption(exposureVersionId!.toString())
    await expect.poll(async () => await page.locator('table tbody tr').count(), { timeout: 180000 }).toBeGreaterThan(0)
    await page.getByRole('button', { name: 'View' }).first().click()
    await page.getByRole('button', { name: 'Ack' }).click()
    await page.getByPlaceholder('Add a note').fill('Reviewed and acknowledged.')
    await page.getByRole('button', { name: 'Add note' }).click()
    await expect(page.getByText('Reviewed and acknowledged.')).toBeVisible()

    await page.getByRole('link', { name: 'Submission Workbench' }).click()
    await page.locator('select').first().selectOption(exposureVersionId!.toString())
    await page.getByPlaceholder('Decision rationale').fill('Proceed with standard terms.')
    await page.getByRole('button', { name: 'Record decision' }).click()
    await expect(page.getByText(/Last decision/)).toBeVisible()

    await page.getByRole('link', { name: 'Audit Log' }).click()
    await expect(page.getByText(/uw_rule_created|uw_eval_requested|decision_recorded/)).toBeVisible()
    expect(readErrors()).toEqual([])
  })
})
