import { defineConfig } from '@playwright/test'

// §042 매뉴얼 캡처용 self-contained 설정 (036 패턴 복제).
// Serial(workers:1) — neo4j 세션 상태를 공유한다.
export default defineConfig({
  testDir: '.',
  testMatch: /playwright-039-.*\.spec\.ts/,
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
