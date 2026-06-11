import { test, expect, Page } from '@playwright/test'

/**
 * PRO lifecycle smoke test — headed mode
 * 목적: Proposal 생성 → Intent 분석 → Submit → 샌드박스 구현 시작이 IMPLEMENTING으로 전환되는지 확인
 */

const PROMPT = '고객이 상품 리뷰를 작성하고 평점을 남길 수 있는 기능을 추가해주세요'

test.use({ headless: false, viewport: { width: 1400, height: 900 } })

test('Proposal lifecycle: 생성 → Intent → Submit → 샌드박스 implement 전환', async ({ page }) => {
  // ── 1. 앱 로딩 ──────────────────────────────────────────────────────────────
  await page.goto('http://localhost:5173')
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: 'test-results/p01-app-loaded.png' })

  // ── 2. Proposals 탭 클릭 ───────────────────────────────────────────────────
  await page.getByText('Proposals').click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: 'test-results/p02-proposals-tab.png' })

  // ── 3. 새 Proposal 생성 ────────────────────────────────────────────────────
  await page.getByText('+ 새 Proposal').click()
  await page.waitForTimeout(300)

  const textarea = page.locator('textarea.proposal-create__textarea')
  await expect(textarea).toBeVisible()
  await textarea.fill(PROMPT)
  await page.screenshot({ path: 'test-results/p03-prompt-filled.png' })

  // ── 4. AI 분석 시작 ─────────────────────────────────────────────────────────
  await page.getByText('AI 분석 시작').click()

  // 분석 중 상태 확인
  await expect(page.locator('.analyzing-header')).toBeVisible({ timeout: 5000 })
  await page.screenshot({ path: 'test-results/p04-analyzing.png' })
  console.log('✅ Intent 분석 시작됨')

  // Intent 완료 대기 (최대 120초 — claude CLI 호출)
  const doneOrClarify = page.locator('.proposal-create__done, .proposal-create__clarify')
  await expect(doneOrClarify).toBeVisible({ timeout: 120_000 })

  const isDone = await page.locator('.proposal-create__done').isVisible()
  const isClarify = await page.locator('.proposal-create__clarify').isVisible()
  await page.screenshot({ path: 'test-results/p05-intent-result.png' })

  if (isClarify) {
    console.log('ℹ️  명확화 질문이 나왔습니다 — 현재 정보로 계속')
    const skipBtn = page.getByText('현재 정보로 계속')
    if (await skipBtn.isVisible()) {
      await skipBtn.click()
      await expect(page.locator('.proposal-create__done')).toBeVisible({ timeout: 120_000 })
    }
  }

  // ── 5. Proposal 보기 버튼 클릭 ──────────────────────────────────────────────
  const viewBtn = page.getByText('Proposal 보기')
  await expect(viewBtn).toBeVisible({ timeout: 10_000 })
  const proposalIdText = await page.locator('.proposal-create__done strong').textContent()
  console.log(`✅ Proposal 생성됨: ${proposalIdText}`)
  await viewBtn.click()
  await page.waitForTimeout(800)
  await page.screenshot({ path: 'test-results/p06-proposal-detail.png' })

  // ── 6. Submit 버튼 클릭 ─────────────────────────────────────────────────────
  const submitBtn = page.getByText('제출')
  if (await submitBtn.isVisible()) {
    await submitBtn.click()
    await page.waitForTimeout(500)
    await page.screenshot({ path: 'test-results/p07-submitted.png' })
    console.log('✅ Proposal SUBMITTED')
  } else {
    // 이미 SUBMITTED 상태일 수 있음
    console.log('ℹ️  Submit 버튼 없음 — 이미 SUBMITTED 상태인지 확인')
  }

  // ── 7. Sandbox 탭 / 구현 시작 버튼 찾기 ────────────────────────────────────
  // ProposalDetail에 Sandbox 탭이 있을 수 있음
  const sandboxTab = page.getByText('Sandbox').or(page.getByText('구현'))
  if (await sandboxTab.isVisible({ timeout: 2000 }).catch(() => false)) {
    await sandboxTab.click()
    await page.waitForTimeout(300)
  }
  await page.screenshot({ path: 'test-results/p08-sandbox-tab.png' })

  const startBtn = page.getByText('구현 시작')
  await expect(startBtn).toBeVisible({ timeout: 5000 })
  await startBtn.click()
  console.log('✅ 구현 시작 버튼 클릭됨')

  // ── 8. sandbox_creating / sandbox_ready 이벤트 확인 ──────────────────────────
  // 로그에 "READY" 또는 브랜치 텍스트가 나타나야 함
  const sandboxReadyIndicator = page.locator('.log-stream, .sandbox-meta')
  await expect(sandboxReadyIndicator).toBeVisible({ timeout: 30_000 })
  await page.screenshot({ path: 'test-results/p09-sandbox-creating.png' })

  // 브랜치 이름이 UI에 나타나는지
  const branchText = page.locator('code').filter({ hasText: 'proposal/' })
  const hasBranch = await branchText.isVisible({ timeout: 20_000 }).catch(() => false)
  if (hasBranch) {
    const branch = await branchText.first().textContent()
    console.log(`✅ Worktree 브랜치 생성됨: ${branch}`)
  } else {
    console.log('⚠️  브랜치 텍스트가 UI에 표시되지 않음')
  }

  await page.screenshot({ path: 'test-results/p10-sandbox-ready.png' })

  // ── 9. IMPLEMENTING 상태 전환 확인 ──────────────────────────────────────────
  // task_start 이벤트가 오거나, IMPLEMENTING 상태 배지가 보여야 함
  const implementingIndicator = page.locator(
    '.status-badge--implementing, .task-item, .task-list__summary'
  )

  const reachedImplementing = await implementingIndicator
    .first()
    .waitFor({ state: 'visible', timeout: 60_000 })
    .then(() => true)
    .catch(() => false)

  await page.screenshot({ path: 'test-results/p11-implementing-check.png' })

  if (reachedImplementing) {
    console.log('✅ IMPLEMENTING 상태 진입 확인됨')
    const taskSummary = page.locator('.task-list__summary')
    if (await taskSummary.isVisible()) {
      console.log(`  태스크 상태: ${await taskSummary.textContent()}`)
    }
  } else {
    // 에러 메시지가 있는지 확인
    const errMsg = page.locator('.error-msg')
    if (await errMsg.isVisible()) {
      console.log(`❌ 에러 메시지: ${await errMsg.textContent()}`)
    }
    const logLines = page.locator('.log-line code')
    const logCount = await logLines.count()
    console.log(`ℹ️  로그 라인 수: ${logCount}`)
    for (let i = 0; i < Math.min(logCount, 5); i++) {
      console.log(`   ${await logLines.nth(i).textContent()}`)
    }
    console.log('❌ IMPLEMENTING 상태로 전환되지 않음 — 버그 재현됨')
  }

  await page.screenshot({ path: 'test-results/p12-final.png' })
  expect(reachedImplementing, 'sandbox_creating 후 IMPLEMENTING 전환이 되어야 합니다').toBe(true)
})
