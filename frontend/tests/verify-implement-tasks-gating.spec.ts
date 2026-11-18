import { test, expect, Page, type WebSocketRoute } from '@playwright/test'
import { gotoView, railItem } from './helpers/nav'

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

// 목록·상세 — 라이브 백엔드 없이 자체 완결(원래는 :8000 의 실제 PRO-032 에 기대고 있었다).
// IMPLEMENTING + tasks.md 없음 → 샌드박스 버튼은 '구현하기'(SUBMITTED 면 '작업 목록 생성' 게이트가 먼저 뜬다).
const DETAIL = {
  id: PROPOSAL_ID, title: '고객: 주문의 일부 품목만 환불을 요청한다',
  originalPrompt: '부분 환불 기능 추가', author: 't@local',
  createdAt: '2026-06-10T07:26:40Z', status: 'IMPLEMENTING',
  strategicDiff: { userStories: [] }, tacticalDiff: [], impactMap: [],
  sandboxWorktreePath: null, projectRoot: '/Users/uengine/projects/my-project2',
  sandboxBranch: `proposal/${PROPOSAL_ID}`, sandboxStatus: 'IMPLEMENTING',
}

const IMPLEMENT_RESP = {
  proposalId: PROPOSAL_ID, status: 'IMPLEMENTING',
  worktreePath: '/tmp', branch: `proposal/${PROPOSAL_ID}`,
  command: `/robo-implement ${PROPOSAL_ID}`,
}

// onTerminalConnect: 가짜 터미널 소켓이 열릴 때(화면 글자 보내기 등). onTerminalMessage: 페이지가 보낸 프레임마다.
// WebSocketRoute.onMessage 는 처리기를 하나만 둔다 — 시험에서 따로 onMessage 를 걸면 wsSent 기록이 끊긴다.
async function commonStubs(
  page: Page,
  wsSent: string[],
  onTerminalConnect?: (ws: WebSocketRoute) => void,
  onTerminalMessage?: (m: string) => void,
) {
  await page.addInitScript(() => {
    try { localStorage.setItem('claude_code_workspace_root', '/Users/uengine/projects/my-project2') } catch {}
  })
  await page.route(/\/api\/proposals\/(\?.*)?$/, (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify([DETAIL]) })
  })
  await page.route(`**/api/proposals/${PROPOSAL_ID}`, (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(DETAIL) })
  })
  await page.route('**/api/proposals/*/progress', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(PROGRESS_NONE) }))
  await page.route('**/api/proposals/*/implement', (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(IMPLEMENT_RESP) })
  })
  // 터미널 WS는 mock(서버 미연결 → claude 미실행). 페이지가 보낸 입력을 캡처.
  await page.routeWebSocket('**/api/claude-code/terminal*', (ws) => {
    ws.onMessage((m: any) => {
      const text = typeof m === 'string' ? m : String(m)
      wsSent.push(text)
      onTerminalMessage?.(text)
    })
    onTerminalConnect?.(ws)
  })
}

async function openSandbox(page: Page) {
  await page.goto('/')
  await gotoView(page, '프로포절')
  const item = page.locator('.proposal-item', { hasText: PROPOSAL_ID }).first()
  await expect(item).toBeVisible({ timeout: 15000 })
  await item.click()
  await page.locator('.tab-btn', { hasText: '샌드박스 구현' }).click()
  const btn = page.getByRole('button', { name: '구현하기', exact: true })
  await expect(btn).toBeVisible({ timeout: 10000 })
  return btn
}

const goShellBtn = (page: Page) => page.getByRole('button', { name: 'Claude Code 셀로 이동' })
// 셀에 주입된 명령 프레임 — Enter(\r)까지 붙어 정확히 한 번 간다(sendWhenReady, dd688595).
const implementFrames = (sent: string[]) => sent.filter((m) => {
  try { const j = JSON.parse(m); return j.type === 'input' && j.data === `/robo-implement ${PROPOSAL_ID}\r` } catch { return false }
})
// 지금 켜진 화면 = 왼쪽 레일의 is-active 단추(상단 탭 막대는 없어졌다).
const activeRail = (page: Page) => page.locator('nav.rail .rail__item.is-active')

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
  await expect(activeRail(page)).toHaveText('프로포절')
  expect(sseHit).toBeTruthy()

  // 2) 분해 완료 후에도 자동 이동하지 않고 'Claude Code 셀로 이동' 버튼이 뜬다.
  await expect(goShellBtn(page)).toBeVisible({ timeout: 10000 })
  await expect(page.locator('.ccw-root')).toBeHidden()
  await expect(activeRail(page)).toHaveText('프로포절')

  // 3) 버튼을 눌러야 Code 탭으로 진입한다.
  await goShellBtn(page).click()
  await expect(page.locator('.ccw-root')).toBeVisible({ timeout: 15000 })
  await expect(activeRail(page)).toHaveText('코드')

  // 4) 셀에 /robo-implement 명령이 주입된다(초기 명령은 onopen 6s 후, 확인 화면이 없을 때 전송).
  await expect.poll(() => implementFrames(wsSent).length, { timeout: 9000 }).toBe(1)
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
  await expect(activeRail(page)).toHaveText('코드')
  await expect.poll(() => implementFrames(wsSent).length, { timeout: 9000 }).toBe(1)
})

// dd688595 회귀 — 새 샌드박스(신뢰 안 된 폴더)에서 claude 는 먼저 '이 폴더를 신뢰하나요?' 확인 화면을 띄운다.
// 그 위로 '/robo-implement …⏎' 가 들어가면 Enter 가 기본값 'No, exit' 를 골라 claude 가 꺼졌다.
// 가짜 터미널 소켓이 확인 화면을 그려 두면, 최소 대기(6s)+2.5s 가 지나도 명령이 가지 않아야 하고,
// 확인 화면이 사라진(사람이 답한) 뒤 2.5s 이상 지나서 정확히 한 번 가야 한다. 순수 로직은
// claude-ready-gate-unit.spec.ts 가, 여기서는 ClaudeCodeTerminal 이 그 로직에 화면 글자를 제대로 넘기는지 본다.
const TRUST_DIALOG = [
  '\x1b[2J\x1b[H',
  'Do you trust the files in this folder?\r\n\r\n',
  ' /tmp\r\n\r\n',
  'Quick safety check: Is this a project you created or one you trust?\r\n',
  '\x1b[36m❯ 1. Yes, I trust this folder\x1b[0m\r\n',
  '  2. No, exit\r\n\r\n',
  'Enter to confirm · Esc to cancel\r\n',
].join('')
const READY_PROMPT = '\x1b[2J\x1b[H╭────────────────────╮\r\n│ ✻ Welcome to Claude Code! │\r\n╰────────────────────╯\r\n\r\n> '

test('확인 화면(폴더 신뢰)이 떠 있는 동안은 /robo-implement 를 보내지 않고, 답한 뒤에 한 번 보낸다', async ({ page }) => {
  test.setTimeout(60_000)
  const wsSent: string[] = []
  const terminals: WebSocketRoute[] = []
  let sentAt = 0
  await commonStubs(
    page,
    wsSent,
    (ws) => {
      terminals.push(ws)
      ws.send(TRUST_DIALOG) // claude 첫 실행 확인 화면
    },
    (m) => { if (!sentAt && implementFrames([m]).length) sentAt = Date.now() },
  )
  await page.route('**/api/proposals/*/tasks', (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ exists: true, tasks: [{ id: 'T001', phase: 'Phase 1', text: '기존 작업', files: [], parallel: false }], markdown: '# Tasks', proposalId: PROPOSAL_ID }) })
  })
  await page.route('**/api/proposals/stream/*/tasks', (route) => route.abort())

  const btn = await openSandbox(page)
  await btn.click()
  await goShellBtn(page).click()
  await expect(page.locator('.ccw-root')).toBeVisible({ timeout: 15000 })

  // 최소 대기 6s + 맑음 2.5s 를 넉넉히 넘겨도 확인 화면이 있는 한 보내지 않는다.
  await page.waitForTimeout(10_000)
  expect(wsSent.length, '소켓 프레임(resize 등)은 기록되고 있어야 한다').toBeGreaterThan(0)
  expect(implementFrames(wsSent), '확인 화면 위로 명령이 들어가면 Enter 가 No, exit 를 고른다').toHaveLength(0)

  // 사람이 답함 → claude 가 화면을 지우고 입력란을 그린다.
  const answeredAt = Date.now()
  for (const ws of terminals) ws.send(READY_PROMPT)
  await expect.poll(() => implementFrames(wsSent).length, { timeout: 8000 }).toBe(1)
  expect(sentAt - answeredAt, '답한 뒤 2.5s 는 지나야 보낸다(다음 확인 화면이 뜰 틈)').toBeGreaterThanOrEqual(2400)

  // 한 번만 간다.
  await page.waitForTimeout(1500)
  expect(implementFrames(wsSent)).toHaveLength(1)
})
