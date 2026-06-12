import { test, expect } from '@playwright/test'

/**
 * '검증' 탭을 열면 검증(robo-sync 구조 검증 + GWT)이 **runner(스트리밍)** 로 자동 트리거되고,
 * 실행 로그가 실시간 표시되며, 완료 시 결과가 나타나는지 검증. 또한 진행 중 "중지" 가능 검증.
 * (헤드리스 일회 실행 + 폴링 → SSE 스트리밍 + 실행 로그 표시로 전환됨.)
 */

const ID = 'PRO-033'

const detail = (status: string) => ({
  id: ID, title: '고객: 완료된 주문에 대해 전액 환불을 요청한다',
  originalPrompt: '결제 시스템에 환불기능 추가', author: 't@local',
  createdAt: '2026-06-10T07:26:40Z', status,
  strategicDiff: { userStories: [] }, tacticalDiff: [{ nodeId: 'AGG-refund', nodeLabel: 'Aggregate', nodeTitle: '환불 Aggregate' }],
  impactMap: [], sandboxWorktreePath: '/tmp', projectRoot: '/Users/uengine/projects/my-project2',
  sandboxBranch: `proposal/${ID}`, sandboxStatus: 'DONE',
})

const RESULTS = {
  proposalId: ID, totalScenarios: 2, passed: 1, failed: 1, skipped: 0,
  items: [
    { scenarioId: 'SC-001', category: 'structural', storyId: 'AGG-refund', storyTitle: '환불 Aggregate', scenario: 'PartialRefundAmount VO 존재', result: 'PASS', reason: null },
    { scenarioId: 'SC-002', category: 'acceptance', storyId: 'US-1', storyTitle: '부분 환불', scenario: 'Given ... Then ...', result: 'FAIL', reason: 'validation 누락' },
  ],
}

// SSE 본문 — phase → log_line(여러 줄) → results → done.
const SSE_BODY = [
  `event: phase\ndata: ${JSON.stringify({ phase: 'validation', message: '검증 실행 중...' })}`,
  `event: log_line\ndata: ${JSON.stringify({ text: '인수 조건 1건 + 구조 검증 대상 로드. robo-sync 추출기로 대조합니다…' })}`,
  `event: log_line\ndata: ${JSON.stringify({ text: '[tool] Read /tmp/refund/PartialRefundAmount.ts' })}`,
  `event: results\ndata: ${JSON.stringify(RESULTS)}`,
  `event: done\ndata: ${JSON.stringify({ proposalId: ID, status: 'PENDING_ACCEPTANCE' })}`,
  '',
].join('\n\n')

async function routeCommon(page, getStatus: () => string) {
  // 목록 엔드포인트(/api/proposals/ 또는 ?쿼리) — 상세 1건만 반환.
  await page.route(/\/api\/proposals\/(\?.*)?$/, (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify([detail(getStatus())]) })
  })
  await page.route(`**/api/proposals/${ID}`, (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(detail(getStatus())) })
  })
  await page.route('**/api/proposals/*/progress', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify({ exists: false, total: 0, done: 0, percent: 0, items: [], sections: [] }) }))
  await page.route('**/api/proposals/*/test-results', (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'no results yet' }) }))
}

test('검증 탭 진입 → runner 스트리밍 자동 실행 → 실행 로그 + 결과 표시', async ({ page }) => {
  test.setTimeout(60_000)

  let streamCalled = false
  let done = false
  await routeCommon(page, () => (done ? 'PENDING_ACCEPTANCE' : 'TESTING'))
  await page.route('**/api/proposals/stream/*/validate', (route) => {
    streamCalled = true
    done = true  // done 이벤트 처리 후 fetchProposal이 PENDING_ACCEPTANCE를 받도록
    return route.fulfill({ contentType: 'text/event-stream', headers: { 'Cache-Control': 'no-cache' }, body: SSE_BODY })
  })

  await page.goto('/')
  await page.locator('.top-bar__tab', { hasText: 'Proposals' }).click()
  await page.locator('.proposal-item', { hasText: ID }).first().click()
  await page.locator('.tab-btn', { hasText: '검증' }).click()

  // 1) 검증이 자동 트리거되고 실행 로그(runner narration·tool)가 표시된다.
  await expect(page.locator('.validate-log')).toBeVisible({ timeout: 5000 })
  await expect(page.locator('.validate-log')).toContainText('robo-sync')
  expect(streamCalled, '검증 탭 진입 시 SSE 스트림이 호출되어야 함').toBeTruthy()

  // 2) 스트림 results/done 이후 요약 + 항목(구조/인수조건 배지)이 표시된다.
  await expect(page.locator('.test-summary')).toBeVisible({ timeout: 15000 })
  await expect(page.locator('.cat-badge--structural')).toBeVisible()
  await expect(page.locator('.test-item--fail')).toBeVisible()
})

test('검증 진행 중 "중지"로 멈출 수 있다', async ({ page }) => {
  test.setTimeout(60_000)

  await routeCommon(page, () => 'TESTING')
  // 스트림을 의도적으로 응답 보류 → "검증 중" 상태를 유지(완료되지 않음).
  let held: any = null
  await page.route('**/api/proposals/stream/*/validate', (route) => { held = route /* 절대 fulfill 안 함 */ })

  await page.goto('/')
  await page.locator('.top-bar__tab', { hasText: 'Proposals' }).click()
  await page.locator('.proposal-item', { hasText: ID }).first().click()
  await page.locator('.tab-btn', { hasText: '검증' }).click()

  // 진행 중 → "검증 중" 배지와 "중지" 버튼이 보인다.
  await expect(page.locator('.validating-badge')).toBeVisible({ timeout: 5000 })
  const stopBtn = page.locator('.validate-bar .btn', { hasText: '중지' })
  await expect(stopBtn).toBeVisible()

  // 중지 → 검증 중 상태가 해제되고 "재검증" 버튼이 다시 보인다.
  await stopBtn.click()
  await expect(page.locator('.validating-badge')).toHaveCount(0)
  await expect(page.locator('.validate-bar .btn', { hasText: '재검증' })).toBeVisible()
})
