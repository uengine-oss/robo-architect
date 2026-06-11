import { test, expect } from '@playwright/test'

/**
 * Sandbox → Implementation 전환 검증 (PRO-003 기준, Intent 이미 완료)
 * 버그 재현 포인트: sandbox_ready 이후 IMPLEMENTING으로 전환되는지
 */
test.use({ headless: false, viewport: { width: 1400, height: 900 } })

test('PRO-003: Submit → 구현시작 → Sandbox → IMPLEMENTING 전환', async ({ page }) => {
  // ── 1. 앱 → Proposals 탭 ─────────────────────────────────────────────────
  await page.goto('http://localhost:5173')
  await page.waitForLoadState('networkidle')
  await page.getByText('Proposals').click()
  await page.waitForTimeout(800)
  await page.screenshot({ path: 'test-results/s01-proposals.png' })

  // ── 2. PRO-003 선택 ──────────────────────────────────────────────────────
  const pro3 = page.locator('.proposal-item').filter({ hasText: 'PRO-003' })
  await expect(pro3).toBeVisible({ timeout: 5000 })
  await pro3.click()
  await page.waitForTimeout(600)
  await page.screenshot({ path: 'test-results/s02-pro003-detail.png' })

  // Strategic Diff가 표시되는지 확인
  const diffSection = page.locator('.strategic-diff, .diff-section, [class*="diff"]').first()
  const hasDiff = await diffSection.isVisible({ timeout: 3000 }).catch(() => false)
  console.log(`Strategic Diff 표시: ${hasDiff}`)

  // ── 3. SUBMIT (이미 SUBMITTED면 스킵) ────────────────────────────────────
  const submitBtn = page.getByText('Proposal 제출 (SUBMIT)')
  const needsSubmit = await submitBtn.isVisible({ timeout: 3000 }).catch(() => false)
  if (needsSubmit) {
    await submitBtn.click()
    await page.waitForTimeout(1000)
    console.log('✅ 제출 완료')
  } else {
    console.log('ℹ️  이미 SUBMITTED 상태 — submit 스킵')
  }
  await page.screenshot({ path: 'test-results/s03-after-submit.png' })

  // ── 4. Sandbox 탭 이동 ────────────────────────────────────────────────────
  const sandboxTab = page.getByRole('tab', { name: /sandbox|구현/i })
    .or(page.locator('.tab', { hasText: /sandbox|구현/i }))
    .or(page.getByText(/sandbox/i).first())

  const hasSandboxTab = await sandboxTab.isVisible({ timeout: 3000 }).catch(() => false)
  if (hasSandboxTab) {
    await sandboxTab.click()
    await page.waitForTimeout(400)
  }
  await page.screenshot({ path: 'test-results/s04-sandbox-tab.png' })

  // ── 5. 구현 시작 버튼 (sandbox-empty 영역 안의 첫 번째) ─────────────────────
  const startBtn = page.locator('.sandbox-empty .btn--primary').first()
    .or(page.getByRole('button', { name: '구현 시작' }).first())
  await expect(startBtn).toBeVisible({ timeout: 8000 })

  console.log('✅ 구현 시작 버튼 발견 — 클릭')
  await startBtn.click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: 'test-results/s05-implement-clicked.png' })

  // ── 6. sandbox_creating / sandbox_ready 로그 ─────────────────────────────
  // 브랜치 텍스트 "proposal/PRO-003" 또는 로그 라인이 나타나야 함
  const sandboxCreatingIndicator = page.locator('.log-stream, .sandbox-meta, .log-line')
  const sandboxAppeared = await sandboxCreatingIndicator.first()
    .waitFor({ state: 'visible', timeout: 30_000 })
    .then(() => true)
    .catch(() => false)

  await page.screenshot({ path: 'test-results/s06-sandbox-state.png' })

  if (sandboxAppeared) {
    const logText = await page.locator('.log-line code').first().textContent().catch(() => '')
    const branchCode = await page.locator('code').filter({ hasText: 'proposal/' }).first().textContent().catch(() => '')
    console.log(`브랜치: ${branchCode}`)
    console.log(`첫 로그: ${logText}`)
  } else {
    console.log('⚠️  sandbox 시작 표시 없음')
  }

  // ── 7. IMPLEMENTING 전환 확인 ──────────────────────────────────────────────
  // task_start 이벤트 또는 task-list가 나타나야 함
  const taskList = page.locator('.task-list, .task-item, .task-list__summary')
  const reachedTask = await taskList.first()
    .waitFor({ state: 'visible', timeout: 90_000 })
    .then(() => true)
    .catch(() => false)

  await page.screenshot({ path: 'test-results/s07-implementing.png' })

  if (reachedTask) {
    const summary = await page.locator('.task-list__summary').textContent().catch(() => '')
    console.log(`✅ IMPLEMENTING — 태스크: ${summary}`)
  } else {
    // 에러 메시지나 로그 확인
    const errMsg = await page.locator('.error-msg').textContent().catch(() => '')
    const sandboxStatus = await page.locator('.sandbox-status').textContent().catch(() => '')
    console.log(`❌ IMPLEMENTING 미진입`)
    console.log(`  에러: ${errMsg}`)
    console.log(`  sandbox 상태: ${sandboxStatus}`)

    // 서버 재시작이 됐는지 — SSE 연결이 끊겼으면 log-stream이 멈춤
    const logCount = await page.locator('.log-line').count()
    console.log(`  로그 라인 수: ${logCount}`)
  }

  await page.screenshot({ path: 'test-results/s08-final.png' })

  expect(
    reachedTask,
    'sandbox_ready 이후 task_start 이벤트가 수신되어 IMPLEMENTING으로 전환되어야 합니다'
  ).toBe(true)
})
