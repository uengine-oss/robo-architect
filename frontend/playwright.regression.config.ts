// 회귀 관문(npm run test:regression)의 화면 시험 — 백엔드(:8000) 없이 네트워크를 모킹해 도는 spec 만.
// 라이브 백엔드가 필요한 spec 은 여기 넣지 않는다(기본 playwright.config.ts 로 따로 돌린다).
// 순수 로직 단위 시험은 playwright.unit.config.ts(서버 없이)가 맡는다.
import { defineConfig } from '@playwright/test'
import base from './playwright.config'

export const MOCKED_SPECS = [
  'requirements-tab',
  'requirements-tab-manual',
  'clarification-flow',
  'ui-flow-edges',
  'ui-flow-journeys',
  'aggregate-invariants',
  'ingestion-resume-button',
  'ingestion-mini-item-select',
  'verify-implement-tasks-gating',
  'verify-proposal-validate-step',
  'verify-proposal-validation-run',
  'verify-strategic-generic-render',
]

export default defineConfig({
  ...base,
  testMatch: MOCKED_SPECS.map((name) => `**/${name}.spec.ts`),
  retries: 0,
  webServer: {
    ...(base.webServer as object),
    // 관문은 이 작업 트리의 코드를 시험해야 한다 — 다른 체크아웃의 dev 서버가 같은 포트에 떠 있으면
    // 조용히 그걸 시험하게 되므로 기본은 새로 띄운다(--strictPort 라 포트가 차 있으면 바로 실패한다;
    // PW_PORT=5180 처럼 다른 포트를 쓰거나, 같은 트리의 서버면 PW_REUSE_SERVER=1).
    reuseExistingServer: !!process.env.PW_REUSE_SERVER,
  },
})
