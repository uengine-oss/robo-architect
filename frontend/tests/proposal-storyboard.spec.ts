import { test, expect } from '@playwright/test'

/**
 * 056 — Proposal 초안 스토리보드.
 *
 * 시나리오: Intent 결과(strategicDiff + journeys)를 가진 DRAFT Proposal 을 열면
 * Intent 탭 상단에 스토리보드 섹션이 나타나고, 저니의 화면들이 open-pencil
 * 와이어프레임(FramePreview)으로 순서대로 렌더된다. 카드의 ✎ 로 FrameEditor 를
 * 열 수 있다.
 *
 * 사전 조건: `uv run python scripts/seed_proposal_storyboard_demo.py` 로 시드
 * (PRO-DEMO-SB). 렌더는 백엔드가 LLM + wireframe-service 로 수행하므로
 * 첫 실행은 수 분 걸릴 수 있다.
 */
const PROPOSAL_ID = process.env.PW_PROPOSAL_ID || 'PRO-DEMO-SB'
const API = process.env.PW_API_BASE || 'http://localhost:8310'

test('proposal draft shows an open-pencil storyboard of its journeys', async ({ page, request }) => {
  // 0) 백엔드 상태 확인 + 스토리보드 초기화(재현성)
  const health = await request.get(`${API}/api/health`)
  expect(health.ok()).toBeTruthy()
  const before = await request.get(`${API}/api/proposals/${PROPOSAL_ID}/storyboard?scenes=0`)
  expect(before.status(), 'seeded proposal must exist').toBe(200)

  // 1) 앱 → Proposals 탭 → 시드된 proposal 선택
  page.on('pageerror', (e) => console.log('[pageerror]', String(e).slice(0, 300)))
  page.on('console', (m) => { if (m.type() === 'error') console.log('[console.error]', m.text().slice(0, 200)) })
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(3000)
  console.log('[diag] body:', JSON.stringify((await page.locator('body').innerText().catch(() => '')).slice(0, 120)))
  await page.getByRole('button', { name: 'Proposals', exact: true }).click({ timeout: 30_000 })
  const item = page.locator('.proposal-item', { hasText: PROPOSAL_ID }).first()
  await expect(item).toBeVisible({ timeout: 30_000 })
  await item.click()

  // 2) Intent 탭 상단에 스토리보드 섹션이 바로 보인다
  const board = page.getByTestId('proposal-storyboard')
  await expect(board).toBeVisible({ timeout: 30_000 })
  await expect(board.getByText(/초안 스토리보드|Draft storyboard/)).toBeVisible()

  // 3) 생성이 자동으로 시작되었거나(없던 경우) 이미 있으면 그대로 — 완료까지 대기
  const generate = board.getByTestId('storyboard-generate')
  await expect(generate).toBeVisible()
  await expect
    .poll(async () => {
      const r = await request.get(`${API}/api/proposals/${PROPOSAL_ID}/storyboard?scenes=0`)
      const j = await r.json()
      return `${j.status}:${j.done ?? 0}/${j.total ?? 0}`
    }, { timeout: 540_000, intervals: [3000] })
    .toMatch(/^(completed|failed):/)

  // 4) 저니 + 화면 카드가 순서대로, 분기(gateway)는 마름모로
  const journey = board.locator('[data-test-id^="storyboard-journey-"]').first()
  await expect(journey).toBeVisible({ timeout: 30_000 })
  const cards = board.locator('[data-test-id^="storyboard-step-"]')
  await expect.poll(() => cards.count()).toBeGreaterThanOrEqual(3)
  await expect(board.getByTestId('storyboard-gateway')).toBeVisible()

  // 5) 최소 한 장은 실제 sceneGraph 로 렌더된 프레임(FramePreview)이어야 한다
  const done = board.locator('[data-test-id^="storyboard-step-"][data-status="done"]')
  await expect.poll(() => done.count(), { timeout: 60_000 }).toBeGreaterThanOrEqual(1)
  await expect(done.first().locator('.frame-preview')).toBeVisible()
  await page.screenshot({ path: 'tests/.artifacts/storyboard/storyboard-overview.png', fullPage: true })

  // 6) 카드 ✎ → open-pencil FrameEditor 모달
  await done.first().hover()
  await done.first().getByTestId('storyboard-edit').click()
  const editor = page.getByTestId('storyboard-editor')
  await expect(editor).toBeVisible()
  await expect(editor.getByTestId('frame-editor')).toBeVisible({ timeout: 30_000 })
  await page.waitForTimeout(2500) // CanvasKit 첫 페인트/줌 맞춤을 영상에 담는다
  await page.screenshot({ path: 'tests/.artifacts/storyboard/storyboard-editor.png' })
  await editor.getByRole('button', { name: /닫기|Close/ }).click()
  await expect(editor).toBeHidden()
})
