import { defineConfig } from '@playwright/test'

// PW_PORT 로 dev 서버 포트를 바꿀 수 있다(5173 을 다른 서버가 쓰고 있을 때). 기본 5173.
const PORT = Number(process.env.PW_PORT || 5173)

export default defineConfig({
  testDir: './tests',
  // 순수 로직 spec 은 여기서 안 돈다 — `playwright.unit.config.ts` 가 돌린다.
  // 로직만 재는 검사에 dev 서버와 로그인을 붙이면 **실패 원인이 로직인지 환경인지
  // 안 갈린다**(단위 설정에 적힌 그 이유 그대로).
  testIgnore: ['**/legacy-reference-unit.spec.ts', '**/runtime-status.spec.ts', '**/*-unit.spec.ts'],
  timeout: 60_000,
  // 인증 강제가 켜져 있으면 여기서 미리 로그인해 둔다. 안 그러면 모든 검사가
  // 로그인 화면에 막히고, 원인이 인증이라는 것이 화면만 봐서는 안 드러난다.
  globalSetup: './tests/global-setup.ts',
  use: {
    baseURL: `http://localhost:${PORT}`,
    storageState: 'tests/.auth/state.json',
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
