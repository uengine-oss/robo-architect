// 순수 로직 단위 spec 전용 — dev 서버를 띄우지 않는다(evlink).
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testMatch: '**/legacy-reference-unit.spec.ts',
  timeout: 15_000,
})
