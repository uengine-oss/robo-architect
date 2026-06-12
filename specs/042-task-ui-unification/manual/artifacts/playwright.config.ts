import { defineConfig } from '@playwright/test'

// §042 매뉴얼 캡처 (039 패턴 복제).
export default defineConfig({
  testDir: '.',
  testMatch: /playwright-042-.*\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  reporter: 'line',
  use: {
    baseURL: process.env.APP_URL || 'http://localhost:5173',
    viewport: { width: 1440, height: 900 },
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
  },
})
