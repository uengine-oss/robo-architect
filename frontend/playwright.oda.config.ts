import { defineConfig } from '@playwright/test'

// 043 매뉴얼 데모 전용 — 격리된 워크트리 앱(프론트 :5180 → 백엔드 :8011) 대상.
export default defineConfig({
  testDir: './tests',
  testMatch: 'oda-manual-demo.spec.ts',
  timeout: 120_000,
  workers: 1,
  use: {
    baseURL: 'http://localhost:5180',
    headless: false,
    viewport: { width: 1440, height: 900 },
    locale: 'ko-KR',
    screenshot: 'off',
    trace: 'off',
  },
  projects: [
    { name: 'headed-demo', use: { browserName: 'chromium', headless: false, launchOptions: { slowMo: 500 } } },
  ],
})
