// 순수 로직 단위 spec 전용 — dev 서버를 띄우지 않는다(evlink).
import { defineConfig } from '@playwright/test'

/**
 * 기본 `playwright.config.ts` 는 `webServer` 와 `globalSetup`(로그인)을 켠다 — 화면을
 * 실제로 밟는 검사에는 그게 맞지만, 로직만 재는 검사에 dev 서버와 로그인을 붙이면
 * **검사가 실패했을 때 원인이 로직인지 환경인지 안 갈린다.**
 *
 * spec 058 에서 `tests/unit/` 을 더했다. **기존 `testMatch` 를 덮지 않고 넓혔다** —
 * 좁히면 `legacy-reference-unit.spec.ts` 가 조용히 안 돌고, 검사가 사라진 것을
 * 아무도 모른다.
 *
 * 사용: `npx playwright test --config playwright.unit.config.ts`
 */
export default defineConfig({
  testDir: './tests',
  testMatch: ['**/legacy-reference-unit.spec.ts', 'unit/**/*.spec.ts'],
  timeout: 15_000,
})
