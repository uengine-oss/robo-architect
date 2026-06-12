import { test, expect, Page } from '@playwright/test'

/**
 * "구현하기" 게이팅 + 셀 진입 검증 (039):
 *  - tasks(작업 목록)가 있으면 → 분해 없이, 없으면 → 먼저 분해(생성).
 *  - 구현하기는 자동으로 Code 탭으로 이동하지 않는다(준비만).
 *  - "Claude Code 셀로 이동" 버튼을 눌러야 Code 탭으로 진입하며,
 *    그 셀에 `/robo-implement <PRO-NNN>` 명령이 주입된다.
 *
 * 느리고 비결정적인 부분(작업 분해 SSE / implement / 터미널 WS)은 모두 stub.
 */

const PROPOSAL_ID = 'PRO-032'

const PROGRESS_NONE = {
  exists: false, total: 0, done: 0, percent: 0,
  items: [], sections: [], file: `PROPOSAL_${PROPOSAL_ID}_TASKS.md`,
}

const SSE_BODY = [
  'event: log_line', 'data: {"text":"[검토] 부분 환불 VO/Command 분해"}', '',
  'event: tasks',
  'data: {"tasks":[{"id":"T001","phase":"Phase 1: Setup","text":"디렉터리 생성","files":[],"parallel":false}],"count":1}',
  '',
  'event: done', 'data: {"proposalId":"' + PROPOSAL_ID + '","count":1}', '', '',
].join('\n')

const IMPLEMENT_RESP = {
  proposalId: PROPOSAL_ID, status: 'IMPLEMENTING',
  worktreePath: '/tmp', branch: `proposal/${PROPOSAL_ID}`,
  command: `/robo-implement ${PROPOSAL_ID}`,
}

async function commonStubs(page: Page, wsSent: string[]) {
  await page.addInitScript(() => {
    try { localStorage.setItem('claude_code_workspace_root', '/Users/uengine/projects/my-project2') } catch {}
  })
  await page.route('**/api/proposals/*/progress', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(PROGRESS_NONE) }))
  await page.route('**/api/proposals/*/implement', (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(IMPLEMENT_RESP) })
  })
  // 터미널 WS는 mock(서버 미연결 → claude 미실행). 페이지가 보낸 입력을 캡처.
  await page.routeWebSocket('**/api/claude-code/terminal*', (ws) => {
    ws.onMessage((m: any) => { wsSent.push(typeof m === 'string' ? m : String(m)) })
  })
}

async function openSandbox(page: Page) {
  await page.goto('/')
  await page.locator('.top-bar__tab', { hasText: 'Proposals' }).click()
  const item = page.locator('.proposal-item', { hasText: PROPOSAL_ID }).first()
  await expect(item).toBeVisible({ timeout: 15000 })
  await item.click()
  await page.locator('.tab-btn', { hasText: '샌드박스 구현' }).click()
  const btn = page.getByRole('button', { name: '구현하기', exact: true })
  await expect(btn).toBeVisible({ timeout: 10000 })
  return btn
}

const goShellBtn = (page: Page) => page.getByRole('button', { name: 'Claude Code 셀로 이동' })
const activeTopTab = (page: Page) => page.locator('.top-bar__tab.is-active')

test('tasks 없음 → 분해 후, 자동이동 없이 버튼으로 셀 진입 + /robo-implement 주입', async ({ page }) => {
  test.setTimeout(60_000)
  const wsSent: string[] = []
  await commonStubs(page, wsSent)

  let sseHit = false
  await page.route('**/api/proposals/*/tasks', (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ exists: false, tasks: [], markdown: '', proposalId: PROPOSAL_ID }) })
  })
  await page.route('**/api/proposals/stream/*/tasks', async (route) => {
    sseHit = true
    await new Promise((r) => setTimeout(r, 1000))
    return route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' }, body: SSE_BODY })
  })

  const btn = await openSandbox(page)
  await btn.click()

  // 1) 작업 분해 과정이 보이고, 아직 Code 탭으로 안 넘어간다.
  await expect(page.locator('.tasks-block')).toBeVisible({ timeout: 5000 })
  await expect(activeTopTab(page)).toContainText('Proposals')
  expect(sseHit).toBeTruthy()

  // 2) 분해 완료 후에도 자동 이동하지 않고 'Claude Code 셀로 이동' 버튼이 뜬다.
  await expect(goShellBtn(page)).toBeVisible({ timeout: 10000 })
  await expect(page.locator('.ccw-root')).toBeHidden()
  await expect(activeTopTab(page)).toContainText('Proposals')

  // 3) 버튼을 눌러야 Code 탭으로 진입한다.
  await goShellBtn(page).click()
  await expect(page.locator('.ccw-root')).toBeVisible({ timeout: 15000 })
  await expect(activeTopTab(page)).toContainText('Code')

  // 4) 셀에 /robo-implement 명령이 주입된다(초기 명령은 onopen 6s 후 전송).
  await expect.poll(() => wsSent.some((m) => m.includes(`/robo-implement ${PROPOSAL_ID}`)), { timeout: 9000 }).toBe(true)
})

test('tasks 있음 → 분해 없이, 버튼으로 셀 진입 + /robo-implement 주입', async ({ page }) => {
  test.setTimeout(60_000)
  const wsSent: string[] = []
  await commonStubs(page, wsSent)

  let sseHit = false
  await page.route('**/api/proposals/*/tasks', (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ exists: true, tasks: [{ id: 'T001', phase: 'Phase 1', text: '기존 작업', files: [], parallel: false }], markdown: '# Tasks', proposalId: PROPOSAL_ID }) })
  })
  await page.route('**/api/proposals/stream/*/tasks', (route) => { sseHit = true; return route.abort() })

  const btn = await openSandbox(page)
  await btn.click()

  // 분해 없이, 자동 이동 없이 'Claude Code 셀로 이동' 버튼이 뜬다.
  await expect(goShellBtn(page)).toBeVisible({ timeout: 10000 })
  expect(sseHit, '작업 목록이 있으면 분해 SSE 미호출').toBeFalsy()
  await expect(page.locator('.ccw-root')).toBeHidden()

  // 버튼을 눌러 Code 탭 진입 + /robo-implement 주입.
  await goShellBtn(page).click()
  await expect(page.locator('.ccw-root')).toBeVisible({ timeout: 15000 })
  await expect(activeTopTab(page)).toContainText('Code')
  await expect.poll(() => wsSent.some((m) => m.includes(`/robo-implement ${PROPOSAL_ID}`)), { timeout: 9000 }).toBe(true)
})
