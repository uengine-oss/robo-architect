import { test, expect } from '@playwright/test'

/**
 * 구현 완료(모든 작업 체크) → "구현 완료 → 검증" 버튼 → TESTING 전환 →
 * '검증 (자동 테스트)' 탭이 나타나고 자동 전환되는지 검증.
 * (이전엔 완료 시 '다시 구현하기'만 떠서 검증/승인 탭이 영영 안 나왔음.)
 */

const ID = 'PRO-033'

const detail = (status: string) => ({
  id: ID, title: '고객: 완료된 주문에 대해 전액 환불을 요청한다',
  originalPrompt: '결제 시스템에 환불기능 추가', author: 't@local',
  createdAt: '2026-06-10T07:26:40Z', status,
  strategicDiff: { userStories: [] }, tacticalDiff: [], impactMap: [],
  sandboxWorktreePath: '/tmp', projectRoot: '/Users/uengine/projects/my-project2',
  sandboxBranch: `proposal/${ID}`, sandboxStatus: 'IMPLEMENTING',
})

const PROGRESS_DONE = {
  exists: true, total: 2, done: 2, percent: 100,
  items: [
    { text: 'T001 setup', done: true, section: 'Phase 1: Setup' },
    { text: 'T002 domain', done: true, section: 'Phase 2: Domain' },
  ],
  sections: [
    { title: 'Phase 1: Setup', done: 1, total: 1 },
    { title: 'Phase 2: Domain', done: 1, total: 1 },
  ],
  updatedAt: 0, secondsSinceUpdate: 5, file: `PROPOSAL_${ID}_TASKS.md`,
}

test('구현 완료 → 검증 버튼이 TESTING으로 전환하고 검증 탭을 연다', async ({ page }) => {
  test.setTimeout(60_000)
  await page.addInitScript(() => {
    try { localStorage.setItem('claude_code_workspace_root', '/Users/uengine/projects/my-project2') } catch {}
  })

  let completed = false
  // 목록 GET — 상세 1건만 반환(라이브 백엔드 없이 자체 완결).
  await page.route(/\/api\/proposals\/(\?.*)?$/, (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify([detail(completed ? 'TESTING' : 'IMPLEMENTING')]) })
  })
  // 상세 GET — complete 전엔 IMPLEMENTING, 후엔 TESTING.
  await page.route(`**/api/proposals/${ID}`, (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(detail(completed ? 'TESTING' : 'IMPLEMENTING')) })
  })
  await page.route('**/api/proposals/*/progress', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(PROGRESS_DONE) }))
  await page.route('**/api/proposals/*/implement/complete', (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    completed = true
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ proposalId: ID, status: 'TESTING' }) })
  })
  await page.route('**/api/proposals/*/test-results', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify({ proposalId: ID, totalScenarios: 0, passed: 0, failed: 0, skipped: 0, items: [] }) }))

  await page.goto('/')
  await page.locator('.top-bar__tab', { hasText: 'Proposals' }).click()
  await page.locator('.proposal-item', { hasText: ID }).first().click()
  await page.locator('.tab-btn', { hasText: '샌드박스 구현' }).click()

  // 완료 상태이므로 '구현 완료 → 검증' 버튼이 떠야 한다(다시 구현하기가 primary가 아님).
  const validateBtn = page.getByRole('button', { name: '구현 완료 → 검증', exact: true })
  await expect(validateBtn).toBeVisible({ timeout: 10000 })

  // 클릭 → TESTING 전환 → '검증 (자동 테스트)' 탭이 생기고 활성화된다.
  await validateBtn.click()
  await expect(page.locator('.tab-btn', { hasText: '검증' })).toBeVisible({ timeout: 10000 })
  await expect(page.locator('.tab-btn--active', { hasText: '검증' })).toBeVisible({ timeout: 10000 })
})
