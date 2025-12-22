import { expect, Page } from '@playwright/test'

export function attachConsoleErrorLogger(page: Page, allowlist: string[] = []) {
  const errors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text()
      if (allowlist.some((entry) => text.includes(entry))) return
      errors.push(text)
    }
  })
  return () => errors
}

export async function login(page: Page) {
  await page.goto('/login')
  await page.getByRole('heading', { name: 'Sign in' }).waitFor()
  await page.locator('input[name="tenant_id"]').fill('demo')
  await page.locator('input[name="email"]').fill('admin@demo.com')
  await page.locator('input[name="password"]').fill('password')
  await page.getByRole('button', { name: 'Login' }).click()
  await expect(page.getByText('Upload wizard')).toBeVisible()
}

export async function pollRunStatus(page: Page, runId: number, timeoutMs = 180000) {
  const token = await page.evaluate(() => localStorage.getItem('token'))
  const base = process.env.PLAYWRIGHT_API_URL || process.env.VITE_API_URL || 'http://localhost:8000'
  const start = Date.now()
  let last: any
  while (Date.now() - start < timeoutMs) {
    const response = await page.request.fetch(`${base.replace(/\/$/, '')}/runs/${runId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    last = await response.json()
    const status = (last as any).status
    if (status === 'SUCCEEDED' || status === 'FAILED') return last
    await page.waitForTimeout(2000)
  }
  throw new Error(`Run ${runId} did not complete in time; last status ${(last as any)?.status}`)
}

export function normalizeList<T>(res: any): T[] {
  if (Array.isArray(res)) return res as T[]
  if (res && typeof res === 'object') {
    const maybeItems = (res.items as any) ?? (res.data as any)
    if (Array.isArray(maybeItems)) return maybeItems as T[]
  }
  return []
}
