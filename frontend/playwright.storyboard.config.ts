import { defineConfig } from '@playwright/test'

// 056 — Proposal 초안 스토리보드 시연/회귀. 워크트리 스택(프론트 5174 → 백엔드 8310)을
// 대상으로 하며 영상(webm)을 항상 남긴다.
export default defineConfig({
  testDir: './tests',
  testMatch: /proposal-storyboard\.spec\.ts/,
  timeout: 300_000,
  outputDir: './tests/.artifacts/storyboard',
  use: {
    baseURL: process.env.PW_BASE_URL || 'http://localhost:5174',
    headless: process.env.PW_HEADED ? false : true,
    viewport: { width: 1440, height: 900 },
    video: { mode: 'on', size: { width: 1440, height: 900 } },
    screenshot: 'on',
    locale: 'ko-KR',
    testIdAttribute: 'data-test-id',
  },
  reporter: [['list']],
})
