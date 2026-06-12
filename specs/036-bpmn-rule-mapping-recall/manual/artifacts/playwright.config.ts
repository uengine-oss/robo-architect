import { defineConfig } from '@playwright/test'

// §036 매뉴얼 캡처용 self-contained 설정 (034 패턴 복제).
// Serial(workers:1) — neo4j 상태를 공유하고 매핑이 무겁다.
export default defineConfig({
  testDir: '.',
  testMatch: /playwright-036-.*\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180_000, // 매핑(LLM) 단계가 길어 034보다 넉넉히
  reporter: 'line',
  use: {
    baseURL: process.env.APP_URL || 'http://localhost:5173',
    viewport: { width: 1440, height: 900 },
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
  },
})
