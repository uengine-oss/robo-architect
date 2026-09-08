import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  // 인증 강제가 켜져 있으면 여기서 미리 로그인해 둔다. 안 그러면 모든 검사가
  // 로그인 화면에 막히고, 원인이 인증이라는 것이 화면만 봐서는 안 드러난다.
  globalSetup: './tests/global-setup.ts',
  use: {
    baseURL: 'http://localhost:5173',
    storageState: 'tests/.auth/state.json',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure'
  },
  webServer: {
    command: 'npm run dev',
    port: 5173,
    reuseExistingServer: true,
    timeout: 30_000
  }
})
