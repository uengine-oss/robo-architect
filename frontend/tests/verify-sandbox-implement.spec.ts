import { test, expect } from '@playwright/test'

/**
 * 핵심 버그 검증: sandbox 생성 후 IMPLEMENTING 전환 및 태스크 실행
 * 매 실행마다 새 Proposal 생성 → SUBMITTED → implement 시작
 * Primary check: API polling으로 lifecycle 전환 확인
 * Secondary check: SSE TASK_START 이벤트로 UI 태스크 카드 확인
 */
test.use({ headless: false, viewport: { width: 1440, height: 900 } })

const API = 'http://localhost:8000/api/proposals'

async function setupSubmittedProposal(): Promise<string> {
  const createRes = await fetch(`${API}/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ originalPrompt: '상품 위시리스트 추가 기능', title: '상품 위시리스트 추가' }),
  })
  if (!createRes.ok) throw new Error(`Create failed: ${createRes.status}`)
  const proposal = await createRes.json()
  const id: string = proposal.id

  const diffRes = await fetch(`${API}/${id}/diff`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      strategicDiff: {
        version: 1, epics: [], features: [],
        userStories: [{
          op: 'CREATE', entityType: 'userStory', entityId: null,
          entityTitle: '고객이 상품을 위시리스트에 추가한다',
          fields: null,
          acceptanceCriteria: ['상품 상세에서 위시리스트 버튼 클릭 시 추가'],
        }],
      },
      tacticalDiff: [{
        nodeId: 'AGG-wishlist-new', nodeLabel: 'Aggregate',
        nodeTitle: 'WishlistAggregate', impactLevel: 'HIGH',
        changeType: 'CREATE', semanticDiff: { v: 1, ops: [] },
      }],
    }),
  })
  if (!diffRes.ok) throw new Error(`Diff failed: ${diffRes.status}`)

  const submitRes = await fetch(`${API}/${id}/submit`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!submitRes.ok) throw new Error(`Submit failed: ${submitRes.status} ${await submitRes.text()}`)
  return id
}

async function pollStatus(id: string, targetStatuses: string[], timeoutMs: number): Promise<string | null> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const res = await fetch(`${API}/${id}`).catch(() => null)
    if (res?.ok) {
      const data = await res.json()
      if (targetStatuses.includes(data.status)) return data.status
    }
    await new Promise(r => setTimeout(r, 3000))
  }
  return null
}

test('sandbox 생성 → IMPLEMENTING → TESTING → 태스크 실행 확인', async ({ page }) => {
  test.setTimeout(720_000) // 12분: claude 구현 최대 10분 + 여유

  // ── 0. Setup ────────────────────────────────────────────────────────────────
  const proposalId = await setupSubmittedProposal()
  console.log(`✅ Proposal 준비 완료: ${proposalId} (SUBMITTED)`)

  await page.goto('http://localhost:5173')
  await page.waitForLoadState('networkidle')

  // Proposals 탭
  await page.getByText('Proposals').click()
  await page.waitForTimeout(600)

  const proposalItem = page.locator('.proposal-item').filter({ hasText: proposalId })
  await expect(proposalItem).toBeVisible({ timeout: 5000 })
  await proposalItem.click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: 'test-results/impl01-proposal-detail.png' })

  // 샌드박스 탭 활성화 (있으면)
  const sandboxTab = page.locator('.tab-btn, [class*="tab"]').filter({ hasText: /샌드박스|sandbox/i })
  if (await sandboxTab.isVisible({ timeout: 2000 }).catch(() => false)) {
    await sandboxTab.click()
    await page.waitForTimeout(300)
  }

  // ── 1. 구현 시작 ──────────────────────────────────────────────────────────
  const startBtn = page.locator('.sandbox-empty .btn--primary').first()
    .or(page.getByRole('button', { name: '구현 시작' }).first())
  await expect(startBtn).toBeVisible({ timeout: 5000 })
  console.log('✅ 구현 시작 버튼 발견')
  await startBtn.click()
  await page.screenshot({ path: 'test-results/impl02-clicked.png' })

  // ── 2. PRIMARY CHECK: API poll으로 IMPLEMENTING 전환 확인 (60s) ─────────
  const implementingStatus = await pollStatus(proposalId, ['IMPLEMENTING', 'TESTING', 'PENDING_ACCEPTANCE', 'ACCEPTED'], 60_000)
  console.log(`API 상태: ${implementingStatus ?? 'TIMEOUT'}`)
  await page.screenshot({ path: 'test-results/impl03-implementing.png' })

  expect(implementingStatus, `${proposalId}가 60초 내에 IMPLEMENTING으로 전환되어야 합니다`).not.toBeNull()

  // ── 3. 브랜치 레이블 UI 확인 ─────────────────────────────────────────────
  const branchLabel = page.locator('code').filter({ hasText: `proposal/${proposalId}` })
    .or(page.locator('.log-line code').filter({ hasText: proposalId }))
  const branchVisible = await branchLabel.first().waitFor({ state: 'visible', timeout: 10_000 })
    .then(() => true).catch(() => false)
  console.log(`브랜치 UI 표시: ${branchVisible}`)
  await page.screenshot({ path: 'test-results/impl04-branch.png' })

  // ── 4. SECONDARY CHECK: TASK_START SSE 이벤트 (최대 10분) ──────────────
  console.log('TASK_START 이벤트 대기 중 (최대 10분)...')
  const firstTask = page.locator('.task-item').first()
  const taskStarted = await firstTask.waitFor({ state: 'visible', timeout: 600_000 })
    .then(() => true).catch(() => false)

  await page.screenshot({ path: 'test-results/impl05-tasks.png' })

  if (taskStarted) {
    const taskTitle = await page.locator('.task-item__title').first().textContent().catch(() => '')
    const taskStatus = await page.locator('.task-status').first().textContent().catch(() => '')
    console.log(`✅ 첫 태스크: "${taskTitle}" [${taskStatus?.trim()}]`)
  } else {
    // Task_start 없이 완료된 경우 — lifecycle은 돌아가나 UI 진행 표시 없음
    const logLines = await page.locator('.log-line code').allTextContents()
    console.log(`⚠️ TASK_START 미수신 (SKILL.md 프로토콜 불일치 가능성)`)
    console.log(`   로그: ${logLines.join(' | ')}`)
  }

  // ── 5. PRIMARY CHECK 2: TESTING 또는 그 이후 상태까지 도달 (10분) ──────
  const finalStatus = await pollStatus(proposalId, ['TESTING', 'PENDING_ACCEPTANCE', 'ACCEPTED'], 600_000)
  console.log(`최종 상태: ${finalStatus ?? 'TIMEOUT'}`)
  await page.screenshot({ path: 'test-results/impl06-final.png' })

  expect(
    finalStatus,
    `${proposalId}가 10분 내에 TESTING 이후 상태에 도달해야 합니다 (현재: ${implementingStatus})`
  ).not.toBeNull()

  console.log(`\n=== 결과 ===`)
  console.log(`IMPLEMENTING 전환: ✅`)
  console.log(`TESTING 도달: ✅ (${finalStatus})`)
  console.log(`TASK_START UI: ${taskStarted ? '✅' : '⚠️ 없음 (구현은 완료됨)'}`)
})
