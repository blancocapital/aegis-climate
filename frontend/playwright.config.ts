import { defineConfig } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 180000,
  expect: {
    timeout: 20000,
  },
  outputDir: 'test-results',
  reporter: [
    ['list'],
    ['json', { outputFile: path.join(__dirname, '..', 'qa-results.json') }],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
})
