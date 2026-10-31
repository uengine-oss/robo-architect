import { defineConfig } from '@playwright/test'

// PW_PORT 로 dev 서버 포트를 바꿀 수 있다(5173 을 다른 서버가 쓰고 있을 때). 기본 5173.
const PORT = Number(process.env.PW_PORT || 5173)

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  use: {
    baseURL: `http://localhost:${PORT}`,
    // 화면 글자는 브라우저 언어를 따른다(app/i18n.js). 시험은 한국어 화면을 기준으로 쓴다.
    locale: 'ko-KR',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure'
  },
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    port: PORT,
    reuseExistingServer: true,
    timeout: 30_000
  }
})
