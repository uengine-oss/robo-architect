import { defineConfig } from '@playwright/test'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

// 이 레포는 ESM("type":"module") — __dirname 이 없다.
const __dirname = dirname(fileURLToPath(import.meta.url))

/**
 * analyzer(robo-data-frontend) 단독 UI 검증 전용 config — 현행 graph UI E2E.
 *
 * 왜 별도 config 인가:
 *   기본 playwright.config.ts 는 architect host(5173)를 띄운다. 우리가 검증할 대상은
 *   **analyzer 프론트의 코드 그래프 / 데이터 스키마 탭**이라, analyzer 를 단독(3000)으로
 *   띄우는 편이 계층이 얕아 실패 원인이 명확하다 (federation/host 변수 제거).
 *
 * 전제 (이 config 가 자동으로 안 띄우는 것):
 *   - API Gateway 9000 + analyzer 백엔드 5502  →  robo-architect/scripts/dev-desktop.cmd -NoElectron
 *   - Neo4j (실행자가 명시적으로 선택한 database에 분석 1회 완료된 상태)
 */
const ANALYZER_FRONTEND = resolve(__dirname, '..', 'robo-analyzer', 'robo-data-frontend')

export default defineConfig({
  testDir: './tests-analyzer',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['html', { outputFolder: 'playwright-report-analyzer', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:3000',
    headless: true,
    screenshot: 'on',            // 실패뿐 아니라 항상 — 실물 확인이 목적
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    viewport: { width: 1600, height: 1000 },
  },
  webServer: {
    command: 'npm run dev',
    cwd: ANALYZER_FRONTEND,
    port: 3000,
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
