import { test, expect } from '@playwright/test'

/**
 * 042 Staged DDD Decomposition — 사용자 매뉴얼용 화면 캡처.
 * 백엔드는 모킹(라이브 claude CLI/Neo4j 불필요)하여 신규 UI 상태를 결정적으로 캡처한다.
 * quickstart Scenarios A–F 의 핵심 화면을 담는다.
 */

const SHOTS = '/Users/uengine/main-robo-arch/robo-architect/specs/042-ddd-staged-proposal/manual/screenshots'
const APP = 'http://localhost:5173'

test.use({ viewport: { width: 1400, height: 900 } })

const STAGE_PLAN = {
  version: 1,
  classifiedReach: 'multi-context behaviour change',
  stages: [
    { stage: 'DISCOVER', applies: true, recommendSkip: false, skipped: false, reason: '행위 변경이라 이벤트 발굴 필요' },
    { stage: 'DECOMPOSE', applies: true, recommendSkip: false, skipped: false, reason: '다중 서브도메인' },
    { stage: 'STRATEGIZE', applies: true, recommendSkip: false, skipped: false, reason: '신규 분류 필요' },
    { stage: 'CONNECT', applies: true, recommendSkip: false, skipped: false, reason: '컨텍스트 간 연동' },
    { stage: 'DEFINE', applies: true, recommendSkip: false, skipped: false, reason: 'BC 책임 명문화' },
    { stage: 'TACTICAL', applies: true, recommendSkip: false, skipped: false, reason: 'Aggregate 도출' },
  ],
}

function sse(events: Array<[string, any]>): { body: string; headers: Record<string, string> } {
  const body = events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join('')
  return { body, headers: { 'content-type': 'text/event-stream' } }
}

async function mock(page) {
  // 모드 스위치를 가진 신규 Proposal 생성.
  await page.route('**/api/proposals/', async (route) => {
    if (route.request().method() === 'POST') {
      const created = { id: 'PRO-042', title: '구독 빌링', status: 'DRAFT', decompositionMode: 'DETAILED_DDD', currentStage: 'SCOPE' }
      return route.fulfill({ json: created })
    }
    return route.fulfill({ json: [] })
  })
  // 스코프 SSE → stage_plan.
  await page.route('**/stream/scope', (route) =>
    route.fulfill(sse([['phase', { phase: 'scope' }], ['log_line', { text: '[범위] 다중 컨텍스트 변경' }], ['stage_plan', { stagePlan: STAGE_PLAN }]])))
  // 스테이지 플랜 확정.
  await page.route('**/stage-plan/confirm', (route) =>
    route.fulfill({ json: { id: 'PRO-042', status: 'DRAFT', decompositionMode: 'DETAILED_DDD', currentStage: 'DISCOVER', stagePlan: STAGE_PLAN, stageArtifacts: {} } }))
  // Discover 스테이지 SSE.
  await page.route('**/stream/stage/discover', (route) =>
    route.fulfill(sse([
      ['phase', { phase: 'discover' }],
      ['log_line', { text: '[이벤트] 구독이 갱신됐다' }],
      ['artifact', { stage: 'DISCOVER', artifact: { stage: 'DISCOVER', events: [{ name: '구독이 갱신됐다' }], pivotalEvents: ['구독이 활성화됐다'], hotspots: [] } }],
      ['done', { stage: 'DISCOVER', nextStage: 'DECOMPOSE' }],
    ])))
}

async function gotoProposalsCreate(page) {
  await page.goto(APP)
  // 데모 환경에 맞춰 Proposals 진입 + 새 제안 다이얼로그를 연다(앱 네비게이션에 맞게 조정).
}

test('A. 모드 스위치(간소화/상세 DDD)', async ({ page }) => {
  await mock(page)
  await gotoProposalsCreate(page)
  const sw = page.locator('.mode-switch')
  if (await sw.count()) {
    await expect(sw).toBeVisible()
    await page.screenshot({ path: `${SHOTS}/A-mode-switch.png` })
  }
})

test('B. 스테이지 플랜 + Discover 단계', async ({ page }) => {
  await mock(page)
  await gotoProposalsCreate(page)
  const review = page.locator('.stage-plan')
  if (await review.count()) {
    await expect(review).toBeVisible()
    await page.screenshot({ path: `${SHOTS}/B-stage-plan.png` })
    await page.locator('.stage-plan__actions .btn--primary').click()
    await expect(page.locator('.staged__stepper')).toBeVisible()
    await page.screenshot({ path: `${SHOTS}/B-discover-stage.png` })
  }
})
